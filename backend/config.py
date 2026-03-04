"""
Configuration settings for the Fintech AI Agent
"""
import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


# LLM Settings
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai" or "groq"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")  # or "mistral-7b" for Groq
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1000"))

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fintech_agent.db")

# Email Settings
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

# RSS Feeds
RSS_FEEDS = [
    "https://finance.yahoo.com/news/rssindex",
    "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
]

# Scheduler Settings
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "7"))  # 7 AM
DIGEST_MINUTE = int(os.getenv("DIGEST_MINUTE", "0"))

# API Settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")

# Topic Categories
AVAILABLE_TOPICS = [
    # Macro
    "Interest Rates",
    "Inflation",
    "Federal Reserve Policy",
    "Recession Risk",
    "GDP",
    "Treasury Yields",
    "Oil Prices",
    
    # Regulation
    "SEC Enforcement",
    "Crypto Regulation",
    "Antitrust Cases",
    "Tax Changes",
    "Banking Regulations",
    
    # Market Structure
    "Earnings Reports",
    "Insider Trading",
    "Institutional Buying",
    "M&A",
    "IPOs",
    "ETF Approvals",
    
    # Sector Specific
    "AI Stocks",
    "Semiconductor Industry",
    "EV Market",
    "Fintech",
    "DeFi",
    "Banking Crisis",
    
    # Risk Events
    "Lawsuits",
    "Data Breaches",
    "Bankruptcy",
    "Credit Downgrade",
]
