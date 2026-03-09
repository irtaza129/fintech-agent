"""
LLM Processor - OPTIMIZED with async, batching, and reduced latency
"""
import json
import re
import logging
import asyncio
from typing import Dict, Optional, List, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import openai
import os
from concurrent.futures import ThreadPoolExecutor

from models import RawArticle, ProcessedSummary
from config import (
    LLM_MODEL, LLM_MAX_TOKENS,
    OPENAI_API_KEY
)

# Setup logging to file with UTF-8 encoding
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f'llm_processor_{datetime.now().strftime("%Y%m%d")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Simple in-memory cache for token tracking
token_usage_cache = {
    'total_tokens': 0,
    'total_cost': 0.0,
    'last_reset': datetime.now()
}

# FIX 1: Module-level run cache so it persists across multiple calls within the same process
_global_run_cache: Dict[Tuple, object] = {}


class LLMProcessor:
    def __init__(self):
        self.model = LLM_MODEL
        openai.api_key = OPENAI_API_KEY
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        self.async_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        # FIX 1: Use shared module-level cache instead of instance cache (survives re-instantiation)
        self.run_cache = _global_run_cache

    def process_article_batch(self, article: RawArticle, tickers: List[str], db: Session) -> List[ProcessedSummary]:
        """
        OPTIMIZED: Process ONE article for MULTIPLE tickers in a SINGLE LLM call
        Returns list of ProcessedSummary objects
        """
        summaries = []

        # Filter out already processed (article_id, ticker) pairs
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tickers_to_process = []

        for ticker in tickers:
            # Check in-memory run cache first (avoid DB query)
            cache_key = (article.id, ticker)
            if cache_key in self.run_cache:
                logger.info(f"[CACHE-MEM] {article.title[:30]}... | {ticker} (in-memory)")
                summaries.append(self.run_cache[cache_key])
                continue

            # Fallback to DB query
            existing = db.query(ProcessedSummary).filter(
                ProcessedSummary.article_id == article.id,
                ProcessedSummary.stock_ticker == ticker,
                ProcessedSummary.created_at >= today_start
            ).first()

            if existing:
                logger.info(f"[CACHE-DB] {article.title[:30]}... | {ticker} (cached)")
                summaries.append(existing)
                self.run_cache[cache_key] = existing  # Promote to run cache
            else:
                tickers_to_process.append(ticker)

        if not tickers_to_process:
            logger.info(f"[SKIP-LLM] All {len(tickers)} tickers cached, skipping LLM call")
            return summaries  # All cached - NO LLM CALL

        try:
            # BATCH: Single LLM call for all tickers
            prompt = self._build_batch_prompt(article, tickers_to_process)
            response = self._call_llm(prompt)
            parsed_results = self._parse_batch_response(response, tickers_to_process)

            # BATCH DB COMMIT: Create all summaries first, commit once
            new_summaries = []
            for ticker in tickers_to_process:
                parsed = parsed_results.get(ticker, {})
                if parsed:
                    summary = ProcessedSummary(
                        article_id=article.id,
                        stock_ticker=ticker,
                        summary=parsed.get('summary', ''),
                        sentiment=parsed.get('sentiment', 'neutral'),
                        impact_level=parsed.get('impact_level', 'low'),
                        impact_explanation=parsed.get('impact_explanation', ''),
                        confidence_score=parsed.get('confidence_score', 5.0)
                    )
                    db.add(summary)
                    new_summaries.append(summary)
                    logger.info(f"[OK] {article.title[:40]}... | {ticker} | {parsed.get('sentiment')} | {parsed.get('impact_level')}")
                else:
                    logger.error(f"[FAIL] No result for {ticker} in article: {article.title[:40]}")

            # Single commit for all summaries
            if new_summaries:
                db.commit()
                for s in new_summaries:
                    db.refresh(s)
                    cache_key = (s.article_id, s.stock_ticker)
                    self.run_cache[cache_key] = s
                summaries.extend(new_summaries)

        except Exception as e:
            logger.error(f"[ERROR] Batch processing failed: {str(e)}")
            db.rollback()

        return summaries

    def _build_batch_prompt(self, article: RawArticle, tickers: List[str]) -> str:
        """
        Build prompt for MULTIPLE tickers in ONE call
        """
        topics = article.topics_detected.split(',') if article.topics_detected else []
        topics_str = ', '.join(topics) if topics else 'None'
        tickers_str = ', '.join(tickers)

        example_json = f'{{\n    "{tickers[0]}": {{\n        "summary": "5-7 bullet points for {tickers[0]}",\n        "sentiment": "bullish|bearish|neutral",\n        "impact_level": "low|medium|high",\n        "impact_explanation": "2-3 sentences for {tickers[0]}",\n        "confidence_score": 7\n    }}'

        if len(tickers) > 1:
            for t in tickers[1:]:
                example_json += f',\n    "{t}": {{\n        "summary": "...",\n        "sentiment": "...",\n        "impact_level": "...",\n        "impact_explanation": "...",\n        "confidence_score": ...\n    }}'

        example_json += '\n}'

        prompt = f"""You are a financial news analyst. Analyze this article for MULTIPLE stocks.

**Article Title:** {article.title}

**Article Content:**
{article.content[:2000]}

**Topics Detected:** {topics_str}

**Stocks to Analyze:** {tickers_str}

**Task:**
For EACH stock ticker ({tickers_str}), provide analysis in the following JSON format.

**Return Format (JSON object with ticker keys):**
{example_json}

Return ONLY valid JSON with ALL tickers as keys. No additional text."""

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """
        Call OpenAI API (synchronous) - uses chat.completions for compatibility
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial analyst. Always respond with valid JSON only. No markdown, no code blocks, no extra text."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=LLM_MAX_TOKENS
            )

            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                tokens_used = getattr(response.usage, 'total_tokens', 0)
                input_tokens = getattr(response.usage, 'prompt_tokens', 0)
                output_tokens = getattr(response.usage, 'completion_tokens', 0)

                input_cost = input_tokens * 0.15 / 1_000_000
                output_cost = output_tokens * 0.60 / 1_000_000
                total_cost = input_cost + output_cost

                token_usage_cache['total_tokens'] += tokens_used
                token_usage_cache['total_cost'] += total_cost

                logger.info(f"[TOKENS] {tokens_used} | Cost: ${total_cost:.4f} | Total: ${token_usage_cache['total_cost']:.4f}")

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"[API ERROR] {str(e)}")
            raise

    async def _call_llm_async(self, prompt: str) -> str:
        """
        ASYNC LLM call for concurrent processing
        """
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial analyst. Always respond with valid JSON only. No markdown, no code blocks, no extra text."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=LLM_MAX_TOKENS
            )

            if hasattr(response, 'usage') and response.usage:
                tokens_used = getattr(response.usage, 'total_tokens', 0)
                token_usage_cache['total_tokens'] += tokens_used

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"[ASYNC API ERROR] {str(e)}")
            raise

    def _parse_batch_response(self, response: str, tickers: List[str]) -> Dict[str, Dict]:
        """
        FIX 2: Robust JSON parser - tries direct parse first, then falls back to extraction
        """
        results = {}

        # Strip markdown fences if present
        clean = response.strip()
        clean = re.sub(r'^```(?:json)?\s*', '', clean)
        clean = re.sub(r'\s*```$', '', clean)
        clean = clean.strip()

        # Attempt 1: Direct parse (handles clean responses)
        parsed = None
        try:
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Attempt 2: Extract outermost { } using rfind (handles leading/trailing garbage)
        if parsed is None:
            start = clean.find('{')
            end = clean.rfind('}')
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(clean[start:end + 1])
                except json.JSONDecodeError:
                    pass

        # Attempt 3: Try to balance unmatched braces (handles truncated responses)
        if parsed is None and start != -1:
            json_str = clean[start:]
            open_count = json_str.count('{')
            close_count = json_str.count('}')
            if open_count > close_count:
                json_str += '}' * (open_count - close_count)
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                logger.error(f"[PARSE] All attempts failed. Raw response: {response[:300]}...")
                return results

        if parsed is None:
            logger.error(f"[PARSE] Could not extract JSON from response: {response[:200]}...")
            return results

        # Extract per-ticker data
        for ticker in tickers:
            if ticker not in parsed:
                logger.warning(f"[PARSE] Ticker {ticker} not in response")
                continue

            ticker_data = parsed[ticker]
            required = ['summary', 'sentiment', 'impact_level', 'impact_explanation', 'confidence_score']

            if not all(key in ticker_data for key in required):
                logger.warning(f"[PARSE] Missing fields for {ticker}: {list(ticker_data.keys())}")
                continue

            # Normalize list values to strings
            if isinstance(ticker_data.get('summary'), list):
                ticker_data['summary'] = '\n'.join(ticker_data['summary'])
            if isinstance(ticker_data.get('impact_explanation'), list):
                ticker_data['impact_explanation'] = ' '.join(ticker_data['impact_explanation'])

            results[ticker] = ticker_data

        return results


async def process_articles_async(db: Session, limit_per_ticker: int = 3, max_concurrent: int = 5) -> int:
    """
    ASYNC article processing - delegates to sync version to avoid SQLite threading issues
    """
    return process_articles(db, limit_per_ticker)


def process_articles(db: Session, limit_per_ticker: int = 3) -> int:
    """
    OPTIMIZED: Main function with batching and quota-gated early exit
    """
    from models import PortfolioStock

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # FIX 3: Deduplicate portfolio stocks before processing
    all_stocks_raw = db.query(PortfolioStock).all()
    seen_tickers = set()
    all_stocks = []
    for stock in all_stocks_raw:
        if stock.ticker not in seen_tickers:
            seen_tickers.add(stock.ticker)
            all_stocks.append(stock)

    if not all_stocks:
        logger.info("[SKIP] No stocks in portfolio")
        return 0

    # Check which stocks already have enough summaries today
    stocks_needing_processing = []
    ticker_remaining: Dict[str, int] = {}  # FIX 4: track how many more each ticker needs

    for stock in all_stocks:
        existing_count = db.query(ProcessedSummary).filter(
            ProcessedSummary.stock_ticker == stock.ticker,
            ProcessedSummary.created_at >= today_start
        ).count()

        if existing_count >= limit_per_ticker:
            logger.info(f"[SKIP-STOCK] {stock.ticker} already has {existing_count} summaries today (quota: {limit_per_ticker})")
        else:
            remaining = limit_per_ticker - existing_count
            stocks_needing_processing.append(stock.ticker)
            ticker_remaining[stock.ticker] = remaining
            logger.info(f"[PROCESS] {stock.ticker} needs {remaining} more summaries")

    # FIX: Early exit BEFORE fetching articles if nothing to do
    if not stocks_needing_processing:
        logger.info("[SKIP-ALL] All stocks have enough summaries today. Zero API calls needed.")
        return 0

    processor = LLMProcessor()

    from rss_fetcher import RSSFetcher
    from models import SelectedTopic

    fetcher = RSSFetcher(db)
    articles = fetcher.get_recent_unprocessed_articles(hours=24)

    logger.info(f"[START] Found {len(articles)} unprocessed articles")

    user_topics = db.query(SelectedTopic).all()
    user_topic_names = set([topic.topic_name.lower() for topic in user_topics])

    logger.info(f"[TOPICS] Tracking {len(user_topic_names)} topics")

    # Group articles by ticker
    ticker_articles: Dict[str, List[Tuple[RawArticle, List[str]]]] = {}
    filtered_out = 0

    for article in articles:
        # Topic filter
        if article.topics_detected and user_topic_names:
            article_topics = set([t.strip().lower() for t in article.topics_detected.split(',')])
            if not article_topics.intersection(user_topic_names):
                filtered_out += 1
                continue

        if article.tickers_detected:
            tickers = list(set([t.strip() for t in article.tickers_detected.split(',')]))
            relevant_tickers = [t for t in tickers if t in stocks_needing_processing]

            if relevant_tickers:
                for ticker in relevant_tickers:
                    if ticker not in ticker_articles:
                        ticker_articles[ticker] = []
                    ticker_articles[ticker].append((article, relevant_tickers))

    if filtered_out > 0:
        logger.info(f"[FILTER] Removed {filtered_out} irrelevant articles")

    # FIX 4: Limit articles per ticker using each ticker's actual remaining quota
    # FIX 5: Merge tickers on same article instead of overwriting
    limited_articles: Dict[int, Tuple[RawArticle, set]] = {}

    for ticker, article_list in ticker_articles.items():
        sorted_articles = sorted(article_list, key=lambda x: x[0].published_at or datetime.min, reverse=True)
        needed = ticker_remaining.get(ticker, limit_per_ticker)

        for article, tickers in sorted_articles[:needed]:
            if article.id not in limited_articles:
                limited_articles[article.id] = (article, set(tickers))
            else:
                # Merge tickers rather than overwrite
                limited_articles[article.id][1].update(tickers)

        logger.info(f"[LIMIT] {ticker}: Processing top {min(len(article_list), needed)} of {len(article_list)} articles")

    logger.info(f"[BATCH] {len(limited_articles)} unique articles to process")

    processed_count = 0

    for article_id, (article, tickers) in limited_articles.items():
        tickers_list = list(tickers)[:5]  # Max 5 tickers per article
        summaries = processor.process_article_batch(article, tickers_list, db)
        processed_count += len([s for s in summaries if s and s.id])

    logger.info(f"[DONE] {processed_count} summaries created")

    return processed_count


def process_articles_fast(db: Session, limit_per_ticker: int = 3) -> int:
    """
    FASTEST: Run async processing
    """
    return asyncio.run(process_articles_async(db, limit_per_ticker))