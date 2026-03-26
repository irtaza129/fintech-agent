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

from .models import RawArticle, ProcessedSummary
from .config import (
    LLM_MODEL,
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
        Process ONE article for MULTIPLE tickers.
        Calls the LLM once per ticker (avoids truncation / None content from large batches).
        Uses cache to skip already-processed pairs.
        """
        summaries = []
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        for ticker in tickers:
            # 1. Check in-memory run cache first
            cache_key = (article.id, ticker)
            if cache_key in self.run_cache:
                logger.info(f"[CACHE-MEM] {article.title[:30]}... | {ticker}")
                summaries.append(self.run_cache[cache_key])
                continue

            # 2. Check DB cache
            existing = db.query(ProcessedSummary).filter(
                ProcessedSummary.article_id == article.id,
                ProcessedSummary.stock_ticker == ticker,
                ProcessedSummary.created_at >= today_start
            ).first()
            if existing:
                logger.info(f"[CACHE-DB] {article.title[:30]}... | {ticker}")
                summaries.append(existing)
                self.run_cache[cache_key] = existing
                continue

            # 3. Single-ticker LLM call
            try:
                prompt = self._build_single_prompt(article, ticker)
                raw = self._call_llm(prompt)

                if not raw or not raw.strip():
                    logger.error(f"[FAIL] Empty LLM response for {ticker} | {article.title[:40]}")
                    continue

                parsed = self._parse_single_response(raw, ticker)
                if not parsed:
                    logger.error(f"[FAIL] Parse failed for {ticker} | {article.title[:40]}")
                    continue

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
                db.commit()
                db.refresh(summary)
                self.run_cache[cache_key] = summary
                summaries.append(summary)
                logger.info(f"[OK] {article.title[:40]}... | {ticker} | {parsed.get('sentiment')} | {parsed.get('impact_level')}")

            except Exception as e:
                logger.error(f"[ERROR] {ticker} | {article.title[:40]} | {str(e)}")
                try:
                    db.rollback()
                except Exception:
                    pass

        return summaries

    def _build_single_prompt(self, article: RawArticle, ticker: str) -> str:
        """
        Build a compact single-ticker prompt.
        Keeps content short to avoid reasoning-model truncation.
        """
        topics = article.topics_detected.split(',') if article.topics_detected else []
        topics_str = ', '.join(t.strip() for t in topics) if topics else 'None'
        # Limit content to 1200 chars to keep total tokens well under limit
        content_preview = (article.content or '')[:1200]

        return f"""Analyze this financial news article for stock ticker {ticker}.

TITLE: {article.title}
CONTENT: {content_preview}
TOPICS: {topics_str}

Respond with a JSON object containing exactly these fields:
{{
  "summary": "3-5 concise bullet points about this article's relevance to {ticker}",
  "sentiment": "bullish or bearish or neutral",
  "impact_level": "low or medium or high",
  "impact_explanation": "2-3 sentences on why this matters for {ticker}",
  "confidence_score": 7
}}

Rules: respond ONLY with the JSON object, no extra text, no code fences."""

    def _parse_single_response(self, response: str, ticker: str) -> Optional[Dict]:
        """
        Parse a single-ticker JSON response. Returns the dict or None on failure.
        """
        logger.info(f"[LLM-RESPONSE] {response[:400]}")

        clean = response.strip()
        # Strip markdown fences
        clean = re.sub(r'^```(?:json)?\s*', '', clean, flags=re.MULTILINE)
        clean = re.sub(r'\s*```$', '', clean, flags=re.MULTILINE)
        clean = clean.strip()

        parsed = None
        # Attempt 1: direct parse
        try:
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Attempt 2: extract { }
        if parsed is None:
            start, end = clean.find('{'), clean.rfind('}')
            if start != -1 and end > start:
                try:
                    parsed = json.loads(clean[start:end + 1])
                except json.JSONDecodeError:
                    pass

        # Attempt 3: balance braces
        if parsed is None and clean.find('{') != -1:
            fragment = clean[clean.find('{'):]
            diff = fragment.count('{') - fragment.count('}')
            if diff > 0:
                fragment += '}' * diff
            try:
                parsed = json.loads(fragment)
            except json.JSONDecodeError:
                pass

        if not parsed:
            logger.error(f"[PARSE-FAIL] {ticker} — could not parse. Response: {response}")
            return None

        # If the LLM wrapped under a ticker key, unwrap it
        if ticker in parsed and isinstance(parsed[ticker], dict):
            parsed = parsed[ticker]

        required = ['summary', 'sentiment', 'impact_level', 'impact_explanation', 'confidence_score']
        if not all(k in parsed for k in required):
            missing = [k for k in required if k not in parsed]
            logger.error(f"[PARSE-FAIL] {ticker} missing fields: {missing}")
            return None

        # Normalize lists to strings
        if isinstance(parsed.get('summary'), list):
            parsed['summary'] = '\n'.join(str(x) for x in parsed['summary'])
        if isinstance(parsed.get('impact_explanation'), list):
            parsed['impact_explanation'] = ' '.join(str(x) for x in parsed['impact_explanation'])

        # Coerce enum fields
        sentiment = str(parsed.get('sentiment', '')).lower().strip()
        parsed['sentiment'] = sentiment if sentiment in {'bullish', 'bearish', 'neutral'} else 'neutral'

        impact = str(parsed.get('impact_level', '')).lower().strip()
        parsed['impact_level'] = impact if impact in {'low', 'medium', 'high'} else 'low'

        try:
            parsed['confidence_score'] = float(parsed['confidence_score'])
        except (ValueError, TypeError):
            parsed['confidence_score'] = 5.0

        logger.info(f"[PARSE-OK] {ticker}: sentiment={parsed['sentiment']}, impact={parsed['impact_level']}")
        return parsed

    def _build_batch_prompt(self, article: RawArticle, tickers: List[str]) -> str:
        """
        Build a clean prompt for multiple tickers.
        Uses explicit field descriptions per ticker instead of '...' placeholders
        that the model may copy verbatim.
        """
        topics = article.topics_detected.split(',') if article.topics_detected else []
        topics_str = ', '.join(t.strip() for t in topics) if topics else 'None'
        tickers_str = ', '.join(tickers)

        # Build a concrete schema block for EACH ticker (no '...' placeholders)
        ticker_schema_lines = []
        for t in tickers:
            ticker_schema_lines.append(
                f'  "{t}": {{\n'
                f'    "summary": "3-5 concise bullet points about this article relevant to {t}",\n'
                f'    "sentiment": "bullish or bearish or neutral",\n'
                f'    "impact_level": "low or medium or high",\n'
                f'    "impact_explanation": "2-3 sentences on why this matters for {t}",\n'
                f'    "confidence_score": 7\n'
                f'  }}'
            )
        schema_block = '{\n' + ',\n'.join(ticker_schema_lines) + '\n}'

        prompt = f"""You are a financial news analyst. Analyze the article below for the specified stocks and return a JSON object.

ARTICLE TITLE: {article.title}

ARTICLE CONTENT:
{article.content[:1800]}

TOPICS DETECTED: {topics_str}

STOCKS TO ANALYZE: {tickers_str}

INSTRUCTIONS:
- Return a single JSON object where each key is a ticker symbol.
- For every ticker in [{tickers_str}], include an entry with these exact fields:
  - "summary": 3-5 bullet points (use \\n between bullets)
  - "sentiment": exactly one of "bullish", "bearish", or "neutral"
  - "impact_level": exactly one of "low", "medium", or "high"
  - "impact_explanation": 2-3 sentences
  - "confidence_score": integer 1-10
- Do NOT include any text outside the JSON object.
- Do NOT use markdown formatting or code fences.

EXPECTED JSON STRUCTURE:
{schema_block}"""

        return prompt

    def _call_llm(self, prompt: str) -> str:
        """
        Call OpenAI API (synchronous).
        Uses response_format=json_object so GPT-5 mini always returns valid JSON.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial analyst. You must respond with a valid JSON object only. No markdown, no code fences, no extra text."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )

            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                tokens_used = getattr(response.usage, 'total_tokens', 0)
                input_tokens = getattr(response.usage, 'prompt_tokens', 0)
                output_tokens = getattr(response.usage, 'completion_tokens', 0)

                # GPT-5 mini pricing: $0.25/1M input, $2.00/1M output
                input_cost = input_tokens * 0.25 / 1_000_000
                output_cost = output_tokens * 2.00 / 1_000_000
                total_cost = input_cost + output_cost

                token_usage_cache['total_tokens'] += tokens_used
                token_usage_cache['total_cost'] += total_cost

                logger.info(f"[TOKENS] {tokens_used} | Cost: ${total_cost:.4f} | Total: ${token_usage_cache['total_cost']:.4f}")

            choice = response.choices[0]
            finish_reason = getattr(choice, 'finish_reason', 'unknown')
            content = choice.message.content
            refusal = getattr(choice.message, 'refusal', None)

            if content is None:
                logger.warning(f"[LLM] content=None, finish_reason={finish_reason}, refusal={refusal}")
                return ""

            return content

        except Exception as e:
            logger.error(f"[API ERROR] {str(e)}")
            raise

    async def _call_llm_async(self, prompt: str) -> str:
        """
        ASYNC LLM call. Uses response_format=json_object for guaranteed valid JSON.
        """
        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a financial analyst. You must respond with a valid JSON object only. No markdown, no code fences, no extra text."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )

            if hasattr(response, 'usage') and response.usage:
                tokens_used = getattr(response.usage, 'total_tokens', 0)
                token_usage_cache['total_tokens'] += tokens_used

            choice = response.choices[0]
            content = choice.message.content
            if content is None:
                refusal = getattr(choice.message, 'refusal', None)
                logger.warning(f"[ASYNC LLM] content=None, finish_reason={choice.finish_reason}, refusal={refusal}")
                return ""

            return content

        except Exception as e:
            logger.error(f"[ASYNC API ERROR] {str(e)}")
            raise

    def _parse_batch_response(self, response: str, tickers: List[str]) -> Dict[str, Dict]:
        """
        Parse the JSON response from the LLM.
        With response_format=json_object, the response should always be valid JSON.
        Keeps multi-layer fallback for safety.
        """
        results = {}
        logger.info(f"[LLM-RESPONSE] {response[:600]}")

        # Strip markdown fences just in case
        clean = response.strip()
        clean = re.sub(r'^```(?:json)?\s*', '', clean, flags=re.MULTILINE)
        clean = re.sub(r'\s*```$', '', clean, flags=re.MULTILINE)
        clean = clean.strip()

        # Attempt 1: Direct parse
        parsed = None
        try:
            parsed = json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Attempt 2: Extract outermost { }
        if parsed is None:
            start = clean.find('{')
            end = clean.rfind('}')
            if start != -1 and end > start:
                try:
                    parsed = json.loads(clean[start:end + 1])
                except json.JSONDecodeError:
                    pass

        # Attempt 3: Balance unmatched braces (truncated response)
        if parsed is None and clean.find('{') != -1:
            json_str = clean[clean.find('{'):]
            diff = json_str.count('{') - json_str.count('}')
            if diff > 0:
                json_str += '}' * diff
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                logger.error(f"[PARSE] All 3 attempts failed. Full response: {response}")
                return results

        if not parsed:
            logger.error(f"[PARSE] Could not parse response. Full response: {response}")
            return results

        # Extract and validate per-ticker data
        required_fields = ['summary', 'sentiment', 'impact_level', 'impact_explanation', 'confidence_score']
        valid_sentiments = {'bullish', 'bearish', 'neutral'}
        valid_impacts = {'low', 'medium', 'high'}

        for ticker in tickers:
            if ticker not in parsed:
                logger.warning(f"[PARSE] Ticker {ticker} missing from response keys: {list(parsed.keys())}")
                continue

            data = parsed[ticker]
            if not isinstance(data, dict):
                logger.warning(f"[PARSE] Ticker {ticker} value is not a dict: {type(data)}")
                continue

            if not all(k in data for k in required_fields):
                missing = [k for k in required_fields if k not in data]
                logger.warning(f"[PARSE] Ticker {ticker} missing fields: {missing}")
                continue

            # Normalize list values to strings
            if isinstance(data.get('summary'), list):
                data['summary'] = '\n'.join(str(x) for x in data['summary'])
            if isinstance(data.get('impact_explanation'), list):
                data['impact_explanation'] = ' '.join(str(x) for x in data['impact_explanation'])

            # Coerce sentinel/invalid values to safe defaults
            sentiment = str(data.get('sentiment', '')).lower().strip()
            if sentiment not in valid_sentiments:
                logger.warning(f"[PARSE] {ticker}: invalid sentiment '{sentiment}', defaulting to neutral")
                data['sentiment'] = 'neutral'

            impact = str(data.get('impact_level', '')).lower().strip()
            if impact not in valid_impacts:
                logger.warning(f"[PARSE] {ticker}: invalid impact_level '{impact}', defaulting to low")
                data['impact_level'] = 'low'

            try:
                data['confidence_score'] = float(data['confidence_score'])
            except (ValueError, TypeError):
                data['confidence_score'] = 5.0

            results[ticker] = data
            logger.info(f"[PARSE-OK] {ticker}: sentiment={data['sentiment']}, impact={data['impact_level']}, confidence={data['confidence_score']}")

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
    from .models import PortfolioStock

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

    from .rss_fetcher import RSSFetcher
    from .models import SelectedTopic

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