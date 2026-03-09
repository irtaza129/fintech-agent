"""
RSS Feed Fetcher - Fetch news articles from RSS feeds
"""
import feedparser
import re
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed

from models import RawArticle, PortfolioStock, SelectedTopic
from config import RSS_FEEDS
from ticker_extractor import extract_tickers

class RSSFetcher:
    def __init__(self, db: Session):
        self.db = db
        self.use_dynamic_feeds = True  # Enable ticker-specific feeds
    
    def fetch_all_feeds(self) -> List[Dict]:
        """
        Fetch articles from all RSS feeds (parallelized for speed)
        Returns list of parsed articles
        """
        all_articles = []
        
        # Use dynamic ticker-specific feeds if enabled
        if self.use_dynamic_feeds:
            feeds = self._get_dynamic_feeds()
        else:
            feeds = RSS_FEEDS
        
        # 🚀 Parallel fetching with MORE workers (10 instead of 5)
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(self._fetch_single_feed, url): url for url in feeds}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    articles = future.result(timeout=15)  # 15s timeout per feed
                    all_articles.extend(articles)
                except Exception as e:
                    print(f"[RSS ERROR] {url}: {str(e)}")
        
        return all_articles
    
    def _fetch_single_feed(self, feed_url: str) -> List[Dict]:
        """
        Fetch a single RSS feed
        """
        articles = []
        try:
            print(f"📰 Fetching from: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            # Check for feed parsing errors
            if feed.bozo:
                print(f"⚠️ Feed parsing warning: {feed.bozo_exception}")
                # Continue anyway - some feeds have minor issues but are still usable
            
            for entry in feed.entries:
                article = self._parse_entry(entry, feed_url)
                if article:
                    articles.append(article)
            
            print(f"✅ Found {len(feed.entries)} articles from {feed_url}")
        except Exception as e:
            print(f"❌ Error parsing {feed_url}: {str(e)}")
        
        return articles
    
    def _parse_entry(self, entry, source: str) -> Dict:
        """
        Parse individual RSS entry into article dict
        """
        try:
            # Extract basic info
            title = entry.get('title', '')
            url = entry.get('link', '')
            
            # Skip if no URL
            if not url:
                return None
            
            # Parse published date
            published_at = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published_at = datetime(*entry.published_parsed[:6])
            
            # Get content
            content = ''
            if hasattr(entry, 'summary'):
                content = entry.summary
            elif hasattr(entry, 'description'):
                content = entry.description
            
            return {
                'title': title,
                'url': url,
                'source': source,
                'published_at': published_at,
                'content': content
            }
        except Exception as e:
            print(f"Error parsing entry: {str(e)}")
            return None
    
    def filter_and_save_articles(self, articles: List[Dict]) -> List[RawArticle]:
        """
        Filter articles by user stocks/topics and save to database
        Returns list of saved articles
        """
        saved_articles = []
        
        # Get all user stocks and topics
        all_stocks = self.db.query(PortfolioStock).all()
        all_topics = self.db.query(SelectedTopic).all()
        
        # Build ticker and topic lists
        tickers = set([stock.ticker.upper() for stock in all_stocks])
        company_names = {stock.company_name.lower(): stock.ticker for stock in all_stocks if stock.company_name}
        topics = set([topic.topic_name.lower() for topic in all_topics])
        
        print(f"🔍 Filtering for {len(tickers)} stocks and {len(topics)} topics")
        
        # Recency filter - only process articles from last 24 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        for article in articles:
            # CRITICAL: Filter out old articles (save DB space and LLM tokens)
            if article['published_at']:
                if article['published_at'] < cutoff_time:
                    continue
            
            # Check if article already exists
            existing = self.db.query(RawArticle).filter(
                RawArticle.url == article['url']
            ).first()
            
            if existing:
                continue
            
            # Detect tickers and topics
            detected_tickers = self._detect_tickers(article, tickers, company_names)
            detected_topics = self._detect_topics(article, topics)
            
            # Only save if matches at least one ticker or topic
            if detected_tickers or detected_topics:
                new_article = RawArticle(
                    title=article['title'],
                    url=article['url'],
                    source=article['source'],
                    published_at=article['published_at'],
                    content=article['content'],
                    tickers_detected=','.join(detected_tickers) if detected_tickers else None,
                    topics_detected=','.join(detected_topics) if detected_topics else None
                )
                
                self.db.add(new_article)
                
                # Commit immediately to catch duplicates
                try:
                    self.db.commit()
                    saved_articles.append(new_article)
                    print(f"✅ Saved: {article['title'][:60]}... (Tickers: {detected_tickers}, Topics: {detected_topics})")
                except Exception as e:
                    self.db.rollback()
                    if "UNIQUE constraint failed" in str(e):
                        continue  # Duplicate URL, skip silently
                    else:
                        raise  # Re-raise if it's a different error
        
        print(f"💾 Saved {len(saved_articles)} new articles to database")
        
        return saved_articles
    
    def _detect_tickers(self, article: Dict, tickers: set, company_names: Dict) -> List[str]:
        """
        Detect stock tickers in article title and content.
        Uses the multi-strategy TickerExtractor for:
          - $AAPL cashtag regex
          - Company name → ticker mapping (500+ companies)
          - Parenthesized tickers: Apple (AAPL), (NASDAQ: TSLA)
          - Bare ticker validation with false-positive filtering
        Portfolio tickers are boosted so user's stocks are always prioritized.
        """
        text = f"{article['title']} {article['content']}"
        detected = extract_tickers(text, portfolio_tickers=tickers)
        return detected
    
    def _detect_topics(self, article: Dict, topics: set) -> List[str]:
        """
        Detect financial topics in article title and content
        """
        detected = set()
        text = f"{article['title']} {article['content']}".lower()
        
        for topic in topics:
            topic_lower = topic.lower()
            # Check if topic keywords appear in text
            if topic_lower in text:
                detected.add(topic)
        
        return list(detected)
    
    def _get_dynamic_feeds(self) -> List[str]:
        """
        Generate ticker-specific RSS feeds for better targeting
        """
        feeds = []
        
        # Get all tracked stocks
        all_stocks = self.db.query(PortfolioStock).all()
        tickers = [stock.ticker for stock in all_stocks]
        
        if not tickers:
            print("⚠️ No stocks tracked, using general feeds")
            return RSS_FEEDS
        
        print(f"🎯 Generating feeds for {len(tickers)} tickers: {tickers}")
        
        # Generate Google News RSS for each ticker
        for ticker in tickers:
            feeds.append(f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en")
        
        # Add general market feeds
        feeds.extend([
            "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "https://www.marketwatch.com/rss/topstories",
        ])
        
        return feeds
    
    def get_recent_unprocessed_articles(self, hours: int = 24) -> List[RawArticle]:
        """
        Get articles from last N hours that haven't been processed yet
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        articles = self.db.query(RawArticle).filter(
            RawArticle.published_at >= cutoff_time,
            ~RawArticle.summaries.any()  # No summaries yet
        ).all()
        
        return articles

def fetch_daily_news(db: Session) -> List[RawArticle]:
    """
    Main function to fetch and filter daily news
    Called by scheduler
    """
    fetcher = RSSFetcher(db)
    
    # Fetch all articles
    articles = fetcher.fetch_all_feeds()
    
    # Filter and save
    saved_articles = fetcher.filter_and_save_articles(articles)
    
    return saved_articles
