"""
Dynamic RSS Feed Generator - Generate ticker-specific RSS feeds
This is an OPTIONAL optimization to reduce noise and LLM costs
"""
from typing import List

def generate_ticker_rss_feeds(tickers: List[str]) -> List[str]:
    """
    Generate RSS feeds dynamically based on user tickers
    This reduces noise and focuses on relevant articles
    
    COST OPTIMIZATION:
    - Less irrelevant articles = Less DB storage
    - Less filtering work = Faster processing
    - Less LLM calls = Lower API costs
    
    Usage in rss_fetcher.py:
        Instead of using static RSS_FEEDS,
        generate feeds per ticker:
        
        tickers = [stock.ticker for stock in all_stocks]
        dynamic_feeds = generate_ticker_rss_feeds(tickers)
    """
    feeds = []
    
    for ticker in tickers:
        # Google News RSS for specific ticker
        feeds.append(f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en")
        
        # Yahoo Finance RSS for ticker (if available)
        # Note: Not all tickers have dedicated Yahoo RSS feeds
        # feeds.append(f"https://finance.yahoo.com/rss/headline?s={ticker}")
    
    return feeds

def get_hybrid_feeds(tickers: List[str], include_general: bool = True) -> List[str]:
    """
    Get a mix of ticker-specific and general market feeds
    
    Args:
        tickers: List of stock tickers
        include_general: Include general market news feeds
    
    Returns:
        Combined list of RSS feeds
    """
    feeds = []
    
    # Add ticker-specific feeds
    if tickers:
        feeds.extend(generate_ticker_rss_feeds(tickers))
    
    # Add general market feeds (optional)
    if include_general:
        feeds.extend([
            "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC Top News
            "https://www.marketwatch.com/rss/topstories",              # MarketWatch
        ])
    
    return feeds

# Example usage:
# >>> tickers = ["TSLA", "AAPL", "NVDA"]
# >>> feeds = generate_ticker_rss_feeds(tickers)
# >>> print(feeds)
# [
#     'https://news.google.com/rss/search?q=TSLA+stock&hl=en-US&gl=US&ceid=US:en',
#     'https://news.google.com/rss/search?q=AAPL+stock&hl=en-US&gl=US&ceid=US:en',
#     'https://news.google.com/rss/search?q=NVDA+stock&hl=en-US&gl=US&ceid=US:en'
# ]
