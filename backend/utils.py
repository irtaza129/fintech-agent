"""
Utility functions for the Fintech AI Agent
"""
import re
from typing import List

# Common stock ticker symbols and company names
COMMON_STOCKS = {
    'AAPL': 'Apple Inc.',
    'MSFT': 'Microsoft Corporation',
    'GOOGL': 'Alphabet Inc.',
    'AMZN': 'Amazon.com Inc.',
    'TSLA': 'Tesla Inc.',
    'META': 'Meta Platforms Inc.',
    'NVDA': 'NVIDIA Corporation',
    'BRK.B': 'Berkshire Hathaway',
    'JPM': 'JPMorgan Chase & Co.',
    'V': 'Visa Inc.',
    'JNJ': 'Johnson & Johnson',
    'WMT': 'Walmart Inc.',
    'PG': 'Procter & Gamble',
    'MA': 'Mastercard Inc.',
    'UNH': 'UnitedHealth Group',
    'HD': 'Home Depot',
    'DIS': 'Walt Disney Company',
    'BAC': 'Bank of America',
    'ADBE': 'Adobe Inc.',
    'NFLX': 'Netflix Inc.',
    'CRM': 'Salesforce Inc.',
    'PYPL': 'PayPal Holdings',
    'INTC': 'Intel Corporation',
    'AMD': 'Advanced Micro Devices',
    'COIN': 'Coinbase Global',
    'SQ': 'Block Inc.',
    'SHOP': 'Shopify Inc.',
}

def validate_ticker(ticker: str) -> bool:
    """
    Validate stock ticker format
    """
    # Basic validation: 1-5 uppercase letters, optional dot and letter
    pattern = r'^[A-Z]{1,5}(\.[A-Z])?$'
    return bool(re.match(pattern, ticker.upper()))

def get_company_name(ticker: str) -> str:
    """
    Get company name for ticker (if known)
    """
    return COMMON_STOCKS.get(ticker.upper(), None)

def clean_html(text: str) -> str:
    """
    Remove HTML tags from text
    """
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def truncate_text(text: str, max_length: int = 500) -> str:
    """
    Truncate text to max length
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + '...'

def extract_tickers_from_text(text: str) -> List[str]:
    """
    Extract potential stock tickers from text
    """
    # Look for $TICKER or standalone uppercase words that might be tickers
    pattern = r'\$([A-Z]{1,5})\b'
    matches = re.findall(pattern, text.upper())
    
    # Filter to valid tickers
    valid_tickers = [t for t in matches if validate_ticker(t)]
    
    return list(set(valid_tickers))

def format_sentiment_emoji(sentiment: str) -> str:
    """
    Get emoji for sentiment
    """
    sentiment_lower = sentiment.lower()
    if sentiment_lower == 'bullish':
        return '📈'
    elif sentiment_lower == 'bearish':
        return '📉'
    else:
        return '➡️'

def format_impact_emoji(impact: str) -> str:
    """
    Get emoji for impact level
    """
    impact_lower = impact.lower()
    if impact_lower == 'high':
        return '🔴'
    elif impact_lower == 'medium':
        return '🟡'
    else:
        return '🟢'
