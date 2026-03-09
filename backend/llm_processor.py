"""
LLM Processor - Process articles with OpenAI GPT-4o-mini
"""
import json
import re
import logging
from typing import Dict, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import openai
import os

from models import RawArticle, ProcessedSummary
from config import (
    LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS,
    OPENAI_API_KEY
)

# Setup logging to file
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, f'llm_processor_{datetime.now().strftime("%Y%m%d")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()  # Also print to console
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
    
    def process_article(self, article: RawArticle, ticker: str, db: Session) -> Optional[ProcessedSummary]:
        """
        Process a single article with LLM
        Returns ProcessedSummary object (with caching to avoid duplicate processing)
        """
        try:
            # 🚀 CACHE CHECK: Skip if already processed today
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            existing_summary = db.query(ProcessedSummary).filter(
                ProcessedSummary.article_id == article.id,
                ProcessedSummary.stock_ticker == ticker,
                ProcessedSummary.created_at >= today_start
            ).first()
            
            if existing_summary:
                logger.info(f"💾 Cache hit: {article.title[:40]}... | {ticker} (skipped, already processed)")
                return existing_summary
            
            # Create prompt
            prompt = self._build_prompt(article, ticker)
            
            # Call LLM
            response = self._call_llm(prompt)
            
            # Parse response
            parsed = self._parse_llm_response(response)
            
            if not parsed:
                logger.error(f"❌ Failed to parse LLM response for article: {article.title}")
                logger.error(f"❌ Article URL: {article.url}")
                return None
            
            # Create summary object
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
            
            logger.info(f"✅ Processed: {article.title[:60]}... | {ticker} | {parsed.get('sentiment')} | {parsed.get('impact_level')}")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error processing article {article.id}: {str(e)}")
            logger.exception("Full traceback:")  # Logs full stack trace
            return None
    
    def _build_prompt(self, article: RawArticle, ticker: str) -> str:
        """
        Build prompt for LLM (with topic-awareness)
        """
        # Get detected topics for context
        topics = article.topics_detected.split(',') if article.topics_detected else []
        topics_str = ', '.join(topics) if topics else 'None'
        
        topic_instruction = ""
        if topics:
            topic_instruction = f"""
**Related Topics Detected:** {topics_str}

In your impact explanation, also mention how this relates to these topics if relevant.
"""
        
        prompt = f"""You are a financial news analyst with expertise in equity markets.

**Article Title:** {article.title}

**Article Content:**
{article.content[:2000]}  

**Stock Ticker:** {ticker}
{topic_instruction}
**Task:**
Analyze this article in relation to {ticker} and provide:

1. **Summary:** 5-7 bullet points covering the key information
2. **Sentiment:** bullish, bearish, or neutral for {ticker}
3. **Impact Level:** low, medium, or high
4. **Impact Explanation:** 2-3 sentences explaining why this matters for {ticker}{' and how it relates to the detected topics' if topics else ''}
5. **Confidence Score:** 1-10 (how confident are you in this analysis)

**Return Format (JSON):**
{{
    "summary": "• Point 1\\n• Point 2\\n• Point 3\\n• Point 4\\n• Point 5",
    "sentiment": "bullish|bearish|neutral",
    "impact_level": "low|medium|high",
    "impact_explanation": "Your explanation here",
    "confidence_score": 7
}}

Return ONLY valid JSON, no additional text."""

        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """
        Call OpenAI API using chat.completions (compatible with all versions)
        Tracks token usage and costs
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial news analyst. Always respond with valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=LLM_MAX_TOKENS
            )
            
            # Track token usage
            if hasattr(response, 'usage') and response.usage:
                tokens_used = getattr(response.usage, 'total_tokens', 0)
                
                # GPT-4o-mini pricing: $0.15/1M input, $0.60/1M output
                input_cost = getattr(response.usage, 'prompt_tokens', 0) * 0.15 / 1_000_000
                output_cost = getattr(response.usage, 'completion_tokens', 0) * 0.60 / 1_000_000
                total_cost = input_cost + output_cost
                
                # Update global cache
                token_usage_cache['total_tokens'] += tokens_used
                token_usage_cache['total_cost'] += total_cost
                
                logger.info(f"💰 Tokens: {tokens_used} | Cost: ${total_cost:.4f} | Total today: ${token_usage_cache['total_cost']:.4f}")

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"❌ OpenAI API Error: {str(e)}")
            raise
    
    def _parse_llm_response(self, response: str) -> Optional[Dict]:
        """
        Parse LLM JSON response with detailed error logging
        """
        try:
            # Log raw response for debugging
            logger.debug(f"Raw LLM response (first 500 chars): {response[:500]}...")
            
            # Try to extract JSON from response
            # Sometimes LLM adds markdown code blocks
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)
                
                # Validate required fields
                required = ['summary', 'sentiment', 'impact_level', 'impact_explanation', 'confidence_score']
                missing_fields = [field for field in required if field not in parsed]
                
                if missing_fields:
                    logger.error(f"❌ Missing required fields: {missing_fields}")
                    logger.error(f"❌ Parsed JSON keys: {list(parsed.keys())}")
                    logger.error(f"❌ Full response: {response}")
                    return None
                
                if all(key in parsed for key in required):
                    return parsed
            else:
                logger.error(f"❌ No JSON found in response")
                logger.error(f"❌ Full response: {response}")
            
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON Parse Error: {str(e)}")
            logger.error(f"❌ Failed to parse response: {response}")
            return None

def process_articles(db: Session, limit_per_ticker: int = 3) -> int:
    """
    Main function to process unprocessed articles
    Called by scheduler
    Processes top N articles per ticker to save costs
    NOW with topic filtering: only processes articles matching user's topics
    """
    processor = LLMProcessor()
    
    # Get articles that have been saved but not yet processed
    from rss_fetcher import RSSFetcher
    from models import SelectedTopic
    fetcher = RSSFetcher(db)
    articles = fetcher.get_recent_unprocessed_articles(hours=24)
    
    logger.info(f"📊 Found {len(articles)} unprocessed articles")
    
    # Get user's selected topics for filtering
    user_topics = db.query(SelectedTopic).all()
    user_topic_names = set([topic.topic_name.lower() for topic in user_topics])
    
    logger.info(f"🏷️ User tracking {len(user_topic_names)} topics: {list(user_topic_names)[:5]}...")
    
    # Group articles by ticker (with topic filter)
    ticker_articles = {}
    filtered_out = 0
    
    for article in articles:
        # TOPIC FILTER: Only process if article matches user's topics OR has no topic requirement
        if article.topics_detected:
            article_topics = set([t.strip().lower() for t in article.topics_detected.split(',')])
            # Check if any article topic matches user's topics
            if user_topic_names and not article_topics.intersection(user_topic_names):
                filtered_out += 1
                continue  # Skip articles with irrelevant topics
        
        if article.tickers_detected:
            tickers = article.tickers_detected.split(',')
            for ticker in tickers:
                ticker = ticker.strip()
                if ticker not in ticker_articles:
                    ticker_articles[ticker] = []
                ticker_articles[ticker].append(article)
    
    if filtered_out > 0:
        logger.info(f"🔍 Filtered out {filtered_out} articles with irrelevant topics")
    
    logger.info(f"🎯 Processing top {limit_per_ticker} articles for each of {len(ticker_articles)} tickers")
    
    processed_count = 0
    
    # Process top N articles per ticker
    for ticker, articles_list in ticker_articles.items():
        # Sort by published date (most recent first)
        articles_list.sort(key=lambda x: x.published_at if x.published_at else datetime.min, reverse=True)
        
        # Process only top N
        for article in articles_list[:limit_per_ticker]:
            summary = processor.process_article(article, ticker, db)
            if summary:
                processed_count += 1
    
    logger.info(f"✅ Processed {processed_count} article-ticker combinations")
    logger.info(f"📊 Summary: {processed_count} processed, {len(articles) - processed_count} failed/cached")
    
    return processed_count
