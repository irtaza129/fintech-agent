"""
Scheduler - Daily cron job to fetch, process, and send email
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from sqlalchemy.orm import Session

from .database import SessionLocal
from .rss_fetcher import fetch_daily_news
from .llm_processor_optimized import process_articles
from .email_sender import send_daily_digest
from .config import DIGEST_HOUR, DIGEST_MINUTE

class DailyScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
    
    def start(self):
        """
        Start the scheduler
        """
        # Schedule daily digest job
        self.scheduler.add_job(
            func=self.run_daily_pipeline,
            trigger=CronTrigger(hour=DIGEST_HOUR, minute=DIGEST_MINUTE),
            id='daily_digest',
            name='Daily news digest pipeline',
            replace_existing=True
        )
        
        self.scheduler.start()
        print(f"⏰ Scheduler started! Daily digest will run at {DIGEST_HOUR:02d}:{DIGEST_MINUTE:02d}")
    
    def stop(self):
        """
        Stop the scheduler
        """
        self.scheduler.shutdown()
        print("⏰ Scheduler stopped")
    
    def run_daily_pipeline(self):
        """
        Main daily pipeline:
        1. Fetch RSS articles
        2. Process with LLM
        3. Send email digest
        """
        print(f"\n{'='*60}")
        print(f"🚀 Starting daily pipeline at {datetime.now()}")
        print(f"{'='*60}\n")
        
        db = SessionLocal()
        
        try:
            # Step 1: Fetch RSS articles
            print("📰 Step 1: Fetching RSS articles...")
            articles = fetch_daily_news(db)
            print(f"✅ Fetched {len(articles)} relevant articles\n")
            
            # Step 2: Process with LLM
            print("🤖 Step 2: Processing articles with LLM...")
            processed_count = process_articles(db)
            print(f"✅ Processed {processed_count} summaries\n")
            
            # Step 3: Send email digest
            print("📧 Step 3: Sending email digest...")
            sent_count = send_daily_digest(db)
            print(f"✅ Sent digest to {sent_count} users\n")
            
            print(f"{'='*60}")
            print(f"✅ Daily pipeline completed successfully!")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"❌ Error in daily pipeline: {str(e)}")
            
        finally:
            db.close()
    
    def run_now(self):
        """
        Manually trigger the pipeline (for testing)
        """
        print("🔧 Running pipeline manually...")
        self.run_daily_pipeline()

# Global scheduler instance
scheduler = DailyScheduler()

def start_scheduler():
    """
    Start the background scheduler
    """
    scheduler.start()

def stop_scheduler():
    """
    Stop the background scheduler
    """
    scheduler.stop()

def run_manual():
    """
    Manually run the pipeline once (for testing)
    """
    scheduler.run_now()

if __name__ == "__main__":
    # For testing - run immediately
    print("🧪 Test mode: Running pipeline once...")
    run_manual()
