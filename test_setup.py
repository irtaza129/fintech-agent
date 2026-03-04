"""
Test script to verify the fintech agent setup
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from database import init_db, SessionLocal
from models import User, PortfolioStock, SelectedTopic

def test_database():
    """Test database initialization"""
    print("🧪 Testing database setup...")
    
    try:
        # Initialize database
        init_db()
        print("✅ Database initialized successfully")
        
        # Test database connection
        db = SessionLocal()
        
        # Create a test user
        test_user = User(email="test@example.com")
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        print(f"✅ Created test user: {test_user.email}")
        
        # Add a test stock
        test_stock = PortfolioStock(
            user_id=test_user.id,
            ticker="TSLA",
            company_name="Tesla Inc."
        )
        db.add(test_stock)
        db.commit()
        print(f"✅ Added test stock: {test_stock.ticker}")
        
        # Add a test topic
        test_topic = SelectedTopic(
            user_id=test_user.id,
            topic_name="AI Stocks"
        )
        db.add(test_topic)
        db.commit()
        print(f"✅ Added test topic: {test_topic.topic_name}")
        
        # Query test
        user = db.query(User).filter(User.email == "test@example.com").first()
        print(f"✅ Query test passed: Found user {user.email}")
        print(f"   - Stocks: {len(user.portfolio_stocks)}")
        print(f"   - Topics: {len(user.selected_topics)}")
        
        # Cleanup
        db.delete(test_topic)
        db.delete(test_stock)
        db.delete(test_user)
        db.commit()
        print("✅ Cleaned up test data")
        
        db.close()
        
        print("\n" + "="*50)
        print("✅ ALL DATABASE TESTS PASSED!")
        print("="*50 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Database test failed: {str(e)}\n")
        return False

def test_imports():
    """Test all module imports"""
    print("🧪 Testing module imports...")
    
    try:
        from config import OPENAI_API_KEY, LLM_PROVIDER, RSS_FEEDS
        print("✅ config.py imported successfully")
        
        from database import get_db, init_db
        print("✅ database.py imported successfully")
        
        from models import User, PortfolioStock, SelectedTopic, RawArticle, ProcessedSummary
        print("✅ models.py imported successfully")
        
        from rss_fetcher import RSSFetcher, fetch_daily_news
        print("✅ rss_fetcher.py imported successfully")
        
        from llm_processor import LLMProcessor, process_articles
        print("✅ llm_processor.py imported successfully")
        
        from email_sender import EmailDigestSender, send_daily_digest
        print("✅ email_sender.py imported successfully")
        
        from scheduler import DailyScheduler, start_scheduler
        print("✅ scheduler.py imported successfully")
        
        from utils import validate_ticker, get_company_name
        print("✅ utils.py imported successfully")
        
        print("\n" + "="*50)
        print("✅ ALL IMPORTS SUCCESSFUL!")
        print("="*50 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Import test failed: {str(e)}\n")
        return False

def test_config():
    """Test configuration"""
    print("🧪 Testing configuration...")
    
    try:
        from config import (
            OPENAI_API_KEY, LLM_PROVIDER, LLM_MODEL,
            RSS_FEEDS, EMAIL_ENABLED, AVAILABLE_TOPICS
        )
        
        print(f"✅ LLM Provider: {LLM_PROVIDER}")
        print(f"✅ LLM Model: {LLM_MODEL}")
        print(f"✅ RSS Feeds: {len(RSS_FEEDS)} configured")
        print(f"✅ Email Enabled: {EMAIL_ENABLED}")
        print(f"✅ Available Topics: {len(AVAILABLE_TOPICS)}")
        
        if not OPENAI_API_KEY and LLM_PROVIDER == "openai":
            print("⚠️  WARNING: OPENAI_API_KEY not set in .env")
        
        print("\n" + "="*50)
        print("✅ CONFIGURATION LOADED!")
        print("="*50 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Configuration test failed: {str(e)}\n")
        return False

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 FINTECH AI AGENT - SETUP VERIFICATION")
    print("="*50 + "\n")
    
    # Run tests
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Database", test_database),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {name}")
        print(f"{'='*50}\n")
        results.append((name, test_func()))
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n" + "="*50)
        print("🎉 ALL TESTS PASSED!")
        print("="*50)
        print("\nYour Fintech AI Agent is ready to use!")
        print("\nNext steps:")
        print("1. Copy .env.example to .env and add your API keys")
        print("2. Run: python backend/main.py")
        print("3. Open: frontend/index.html in your browser")
        print("="*50 + "\n")
    else:
        print("\n" + "="*50)
        print("⚠️  SOME TESTS FAILED")
        print("="*50)
        print("\nPlease check the errors above and fix them.")
        print("="*50 + "\n")
