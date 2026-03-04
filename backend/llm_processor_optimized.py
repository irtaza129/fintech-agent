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
    LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS,
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
        logging.FileHandler(log_file, encoding='utf-8'),  # FIX: UTF-8 encoding for emojis
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


class LLMProcessor:
    def __init__(self):
        self.model = LLM_MODEL
        openai.api_key = OPENAI_API_KEY
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        self.async_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.run_cache = {}  # In-memory cache for this run: key = (article_id, ticker)
    
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
                self.run_cache[cache_key] = existing  # Store in run cache
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
                    # Store in run cache for future lookups
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
        
        # Build example JSON format
        example_json = f'{{\n    "{tickers[0]}": {{\n        "summary": "5-7 bullet points for {tickers[0]}",\n        "sentiment": "bullish|bearish|neutral",\n        "impact_level": "low|medium|high",\n        "impact_explanation": "2-3 sentences for {tickers[0]}",\n        "confidence_score": 7\n    }}'
        
        # Add additional ticker examples if multiple tickers
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
        Call OpenAI API (synchronous)
        """
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": "You are a financial analyst. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_output_tokens=LLM_MAX_TOKENS
            )
            
            # Track token usage
            if hasattr(response, 'usage'):
                tokens_used = getattr(response.usage, 'total_tokens', 0)
                input_tokens = getattr(response.usage, 'input_tokens', 0)
                output_tokens = getattr(response.usage, 'output_tokens', 0)
                
                input_cost = input_tokens * 0.15 / 1_000_000
                output_cost = output_tokens * 0.60 / 1_000_000
                total_cost = input_cost + output_cost
                
                token_usage_cache['total_tokens'] += tokens_used
                token_usage_cache['total_cost'] += total_cost
                
                logger.info(f"[TOKENS] {tokens_used} | Cost: ${total_cost:.4f} | Total: ${token_usage_cache['total_cost']:.4f}")

            return response.output_text

        except Exception as e:
            logger.error(f"[API ERROR] {str(e)}")
            raise
    
    async def _call_llm_async(self, prompt: str) -> str:
        """
        ASYNC LLM call for concurrent processing
        """
        try:
            response = await self.async_client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": "You are a financial analyst. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                max_output_tokens=LLM_MAX_TOKENS
            )
            
            if hasattr(response, 'usage'):
                tokens_used = getattr(response.usage, 'total_tokens', 0)
                token_usage_cache['total_tokens'] += tokens_used
                
            return response.output_text

        except Exception as e:
            logger.error(f"[ASYNC API ERROR] {str(e)}")
            raise
    
    def _parse_batch_response(self, response: str, tickers: List[str]) -> Dict[str, Dict]:
        """
        Parse batch response with multiple tickers
        """
        results = {}
        try:
            # Extract JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                
                # Handle both flat and nested structures
                for ticker in tickers:
                    if ticker in parsed:
                        ticker_data = parsed[ticker]
                        required = ['summary', 'sentiment', 'impact_level', 'impact_explanation', 'confidence_score']
                        if all(key in ticker_data for key in required):
                            results[ticker] = ticker_data
                        else:
                            logger.warning(f"[PARSE] Missing fields for {ticker}")
                    else:
                        logger.warning(f"[PARSE] Ticker {ticker} not in response")
            else:
                logger.error(f"[PARSE] No JSON found in response: {response[:200]}...")
                
        except json.JSONDecodeError as e:
            logger.error(f"[JSON ERROR] {str(e)}")
            logger.error(f"[RESPONSE] {response[:500]}...")
        
        return results


async def process_articles_async(db: Session, limit_per_ticker: int = 3, max_concurrent: int = 5) -> int:
    """
    ASYNC article processing with concurrent LLM calls
    """
    processor = LLMProcessor()
    
    from rss_fetcher import RSSFetcher
    from models import SelectedTopic
    
    fetcher = RSSFetcher(db)
    articles = fetcher.get_recent_unprocessed_articles(hours=24)
    
    logger.info(f"[START] Found {len(articles)} unprocessed articles")
    
    # Get user topics for filtering
    user_topics = db.query(SelectedTopic).all()
    user_topic_names = set([topic.topic_name.lower() for topic in user_topics])
    
    # Group articles by article (with all their tickers)
    article_tickers: Dict[int, Tuple[RawArticle, List[str]]] = {}
    filtered_out = 0
    
    for article in articles:
        # Topic filter
        if article.topics_detected and user_topic_names:
            article_topics = set([t.strip().lower() for t in article.topics_detected.split(',')])
            if not article_topics.intersection(user_topic_names):
                filtered_out += 1
                continue
        
        if article.tickers_detected:
            tickers = [t.strip() for t in article.tickers_detected.split(',')]
            if article.id not in article_tickers:
                article_tickers[article.id] = (article, tickers)
            else:
                article_tickers[article.id][1].extend(tickers)
    
    logger.info(f"[FILTER] Filtered out {filtered_out} irrelevant articles")
    logger.info(f"[BATCH] Processing {len(article_tickers)} articles with batched ticker analysis")
    
    # Process articles in parallel batches
    processed_count = 0
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_one(article: RawArticle, tickers: List[str]) -> int:
        async with semaphore:
            # Use thread pool for sync DB operations
            loop = asyncio.get_event_loop()
            summaries = await loop.run_in_executor(
                None, 
                processor.process_article_batch, 
                article, 
                tickers[:limit_per_ticker],  # Limit tickers per article
                db
            )
            return len([s for s in summaries if s])
    
    # Create tasks for all articles
    tasks = []
    for article_id, (article, tickers) in list(article_tickers.items())[:50]:  # Limit to 50 articles max
        tasks.append(process_one(article, tickers))
    
    # Run concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, int):
            processed_count += result
        elif isinstance(result, Exception):
            logger.error(f"[TASK ERROR] {result}")
    
    logger.info(f"[DONE] Processed {processed_count} summaries")
    
    return processed_count


def process_articles(db: Session, limit_per_ticker: int = 3) -> int:
    """
    OPTIMIZED: Main function with batching (backward compatible)
    """
    from models import PortfolioStock
    
    # Check existing summaries count per ticker TODAY
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get all portfolio stocks
    all_stocks = db.query(PortfolioStock).all()
    if not all_stocks:
        logger.info("[SKIP] No stocks in portfolio")
        return 0
    
    # Check which stocks already have enough summaries today
    stocks_needing_processing = []
    for stock in all_stocks:
        existing_count = db.query(ProcessedSummary).filter(
            ProcessedSummary.stock_ticker == stock.ticker,
            ProcessedSummary.created_at >= today_start
        ).count()
        
        if existing_count >= limit_per_ticker:
            logger.info(f"[SKIP-STOCK] {stock.ticker} already has {existing_count} summaries today (quota: {limit_per_ticker})")
        else:
            stocks_needing_processing.append(stock.ticker)
            logger.info(f"[PROCESS] {stock.ticker} needs {limit_per_ticker - existing_count} more summaries")
    
    if not stocks_needing_processing:
        logger.info("[SKIP-ALL] All stocks have enough summaries today. Zero API calls needed.")
        return 0
    
    processor = LLMProcessor()
    
    from rss_fetcher import RSSFetcher
    from models import SelectedTopic
    
    fetcher = RSSFetcher(db)
    articles = fetcher.get_recent_unprocessed_articles(hours=24)
    
    logger.info(f"[START] Found {len(articles)} unprocessed articles")
    
    # Get user topics
    user_topics = db.query(SelectedTopic).all()
    user_topic_names = set([topic.topic_name.lower() for topic in user_topics])
    
    logger.info(f"[TOPICS] Tracking {len(user_topic_names)} topics")
    
    # Group by TICKER first, then limit articles per ticker
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
            tickers = list(set([t.strip() for t in article.tickers_detected.split(',')]))  # Dedupe
            
            # Only process tickers that need more summaries
            relevant_tickers = [t for t in tickers if t in stocks_needing_processing]
            
            if relevant_tickers:
                for ticker in relevant_tickers:
                    if ticker not in ticker_articles:
                        ticker_articles[ticker] = []
                    ticker_articles[ticker].append((article, relevant_tickers))
    
    if filtered_out > 0:
        logger.info(f"[FILTER] Removed {filtered_out} irrelevant articles")
    
    # Limit to top N articles per ticker
    limited_articles: Dict[int, Tuple[RawArticle, List[str]]] = {}
    for ticker, article_list in ticker_articles.items():
        # Sort by published date (most recent first)
        sorted_articles = sorted(article_list, key=lambda x: x[0].published_at or datetime.min, reverse=True)
        
        # Take only top N per ticker
        for article, tickers in sorted_articles[:limit_per_ticker]:
            if article.id not in limited_articles:
                limited_articles[article.id] = (article, tickers)
        
        logger.info(f"[LIMIT] {ticker}: Processing top {min(len(article_list), limit_per_ticker)} of {len(article_list)} articles")
    
    logger.info(f"[BATCH] {len(limited_articles)} articles to process (limited to {limit_per_ticker} per ticker)")
    
    processed_count = 0
    
    # Process each article with ALL its tickers in ONE call
    for article_id, (article, tickers) in limited_articles.items():
        summaries = processor.process_article_batch(article, tickers[:5], db)  # Max 5 tickers per article
        processed_count += len([s for s in summaries if s and s.id])
    
    logger.info(f"[DONE] {processed_count} summaries created")
    
    return processed_count


def process_articles_fast(db: Session, limit_per_ticker: int = 3) -> int:
    """
    FASTEST: Run async processing
    """
    return asyncio.run(process_articles_async(db, limit_per_ticker))
