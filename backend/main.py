"""
FastAPI backend for Fintech AI Agent
"""
from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import os
from collections import defaultdict

from .database import get_db, init_db
from .models import User, PortfolioStock, SelectedTopic, RawArticle, ProcessedSummary
from .config import API_HOST, API_PORT, CORS_ORIGINS, AVAILABLE_TOPICS

# Rate limiting: Track requests per IP
rate_limit_cache = defaultdict(list)
RATE_LIMIT_REQUESTS = 10  # Max requests
RATE_LIMIT_WINDOW = 60  # Per 60 seconds

# Initialize FastAPI app
app = FastAPI(
    title="Fintech AI Agent API",
    description="Personal fintech AI agent for portfolio news summarization",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup templates and static files
# Get the parent directory (project root) to find templates folder
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Mount static files if directory exists
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Rate limiting dependency
def check_rate_limit(request: Request):
    """
    Check if request exceeds rate limit (10 requests per 60 seconds)
    """
    client_ip = request.client.host
    now = datetime.now()
    
    # Clean old requests outside the time window
    rate_limit_cache[client_ip] = [
        req_time for req_time in rate_limit_cache[client_ip]
        if now - req_time < timedelta(seconds=RATE_LIMIT_WINDOW)
    ]
    
    # Check if limit exceeded
    if len(rate_limit_cache[client_ip]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds."
        )
    
    # Add current request
    rate_limit_cache[client_ip].append(now)

# Pydantic models for request/response
class UserCreate(BaseModel):
    email: EmailStr

class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class StockAdd(BaseModel):
    ticker: str
    company_name: Optional[str] = None

class StockResponse(BaseModel):
    id: int
    ticker: str
    company_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class TopicAdd(BaseModel):
    topic_name: str

class TopicResponse(BaseModel):
    id: int
    topic_name: str
    
    class Config:
        from_attributes = True

class SummaryResponse(BaseModel):
    id: int
    stock_ticker: str
    summary: str
    sentiment: str
    impact_level: str
    impact_explanation: str
    confidence_score: float
    created_at: datetime
    article_title: str
    article_url: str
    related_topics: List[str] = []  # NEW: Topics this article relates to
    
    class Config:
        from_attributes = True

# Startup event
@app.on_event("startup")
async def startup_event():
    try:
        init_db()
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"⚠️ Database init warning: {e}")
    print("🚀 Fintech AI Agent API started!")

# Health check for Render
@app.get("/health")
async def health_check():
    """Health check endpoint for Render"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# Frontend - Serve dashboard
@app.get("/", response_class=HTMLResponse)
@app.head("/")
async def dashboard(request: Request):
    """Serve the main dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})

# API Health check
@app.get("/api/health")
async def health():
    return {"message": "Fintech AI Agent API", "status": "running"}

# User endpoints
@app.post("/api/users", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(email=user.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/api/users/by-email/{email}", response_model=UserResponse)
def get_user_by_email(email: str, db: Session = Depends(get_db)):
    """Get user by email for login - auto-creates if doesn't exist"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Auto-create user on first access (handles ephemeral DB on Render)
        user = User(email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

# Portfolio stock endpoints
@app.post("/api/users/{user_id}/stocks", response_model=StockResponse)
def add_stock(user_id: int, stock: StockAdd, db: Session = Depends(get_db)):
    """Add a stock to user's portfolio"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if stock already exists
    existing = db.query(PortfolioStock).filter(
        PortfolioStock.user_id == user_id,
        PortfolioStock.ticker == stock.ticker.upper()
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Stock already in portfolio")
    
    new_stock = PortfolioStock(
        user_id=user_id,
        ticker=stock.ticker.upper(),
        company_name=stock.company_name
    )
    db.add(new_stock)
    db.commit()
    db.refresh(new_stock)
    return new_stock

@app.get("/api/users/{user_id}/stocks", response_model=List[StockResponse])
def get_stocks(user_id: int, db: Session = Depends(get_db)):
    """Get all stocks in user's portfolio"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return db.query(PortfolioStock).filter(PortfolioStock.user_id == user_id).all()

@app.delete("/api/users/{user_id}/stocks/{stock_id}")
def delete_stock(user_id: int, stock_id: int, db: Session = Depends(get_db)):
    """Remove a stock from user's portfolio"""
    stock = db.query(PortfolioStock).filter(
        PortfolioStock.id == stock_id,
        PortfolioStock.user_id == user_id
    ).first()
    
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    db.delete(stock)
    db.commit()
    return {"message": "Stock removed successfully"}

# Topics endpoints
@app.get("/api/topics/available")
def get_available_topics():
    """Get list of available topics"""
    return {"topics": AVAILABLE_TOPICS}

@app.post("/api/users/{user_id}/topics", response_model=TopicResponse)
def add_topic(user_id: int, topic: TopicAdd, db: Session = Depends(get_db)):
    """Add a topic to user's selections"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if topic already exists
    existing = db.query(SelectedTopic).filter(
        SelectedTopic.user_id == user_id,
        SelectedTopic.topic_name == topic.topic_name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Topic already selected")
    
    new_topic = SelectedTopic(user_id=user_id, topic_name=topic.topic_name)
    db.add(new_topic)
    db.commit()
    db.refresh(new_topic)
    return new_topic

@app.get("/api/users/{user_id}/topics", response_model=List[TopicResponse])
def get_topics(user_id: int, db: Session = Depends(get_db)):
    """Get all topics selected by user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return db.query(SelectedTopic).filter(SelectedTopic.user_id == user_id).all()

@app.delete("/api/users/{user_id}/topics/{topic_id}")
def delete_topic(user_id: int, topic_id: int, db: Session = Depends(get_db)):
    """Remove a topic from user's selections"""
    topic = db.query(SelectedTopic).filter(
        SelectedTopic.id == topic_id,
        SelectedTopic.user_id == user_id
    ).first()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    db.delete(topic)
    db.commit()
    return {"message": "Topic removed successfully"}

# Summaries endpoints
@app.get("/api/users/{user_id}/summaries", response_model=List[SummaryResponse])
def get_summaries(user_id: int, limit: int = 50, db: Session = Depends(get_db)):
    """Get processed summaries for user's portfolio"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's tickers
    stocks = db.query(PortfolioStock).filter(PortfolioStock.user_id == user_id).all()
    tickers = [stock.ticker for stock in stocks]
    
    if not tickers:
        return []
    
    # Get summaries for those tickers
    summaries = db.query(ProcessedSummary).filter(
        ProcessedSummary.stock_ticker.in_(tickers)
    ).order_by(ProcessedSummary.created_at.desc()).limit(limit).all()
    
    # Format response
    result = []
    for summary in summaries:
        # Include topics from the original article
        topics = summary.article.topics_detected.split(',') if summary.article.topics_detected else []
        
        result.append({
            "id": summary.id,
            "stock_ticker": summary.stock_ticker,
            "summary": summary.summary,
            "sentiment": summary.sentiment,
            "impact_level": summary.impact_level,
            "impact_explanation": summary.impact_explanation,
            "confidence_score": summary.confidence_score,
            "created_at": summary.created_at,
            "article_title": summary.article.title,
            "article_url": summary.article.url,
            "related_topics": [t.strip() for t in topics]  # NEW: Show which topics this relates to
        })
    
    return result

# Digest trigger endpoint (for GitHub Actions)
@app.post("/api/trigger-digest")
async def trigger_digest(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Trigger the daily digest pipeline
    Called by GitHub Actions cron job or manual user trigger
    Rate limited to prevent abuse
    """
    # Rate limiting check
    check_rate_limit(request)
    
    # Optional authorization - only enforce if DIGEST_SECRET is set
    digest_secret = os.getenv('DIGEST_SECRET')
    if digest_secret and authorization != f"Bearer {digest_secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        from .rss_fetcher import fetch_daily_news
        from .llm_processor_optimized import process_articles, token_usage_cache
        from .email_sender import send_daily_digest
        
        # Step 1: Fetch RSS articles (parallel)
        articles = fetch_daily_news(db)
        
        # Step 2: Process with LLM (BATCHED - 5-10x faster)
        processed_count = process_articles(db)
        
        # Step 3: Send email digest
        sent_count = send_daily_digest(db)
        
        return {
            "status": "success",
            "articles_fetched": len(articles),
            "summaries_processed": processed_count,
            "emails_sent": sent_count,
            "tokens_used": token_usage_cache['total_tokens'],
            "estimated_cost": f"${token_usage_cache['total_cost']:.4f}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Digest pipeline failed: {str(e)}")

@app.get("/api/usage-stats")
async def get_usage_stats():
    """
    Get token usage and cost statistics
    """
    from .llm_processor_optimized import token_usage_cache
    
    return {
        "total_tokens": token_usage_cache['total_tokens'],
        "total_cost": f"${token_usage_cache['total_cost']:.4f}",
        "last_reset": token_usage_cache['last_reset'].isoformat(),
        "model": "gpt-4o-mini",
        "pricing": {
            "input": "$0.15 per 1M tokens",
            "output": "$0.60 per 1M tokens"
        }
    }

@app.post("/api/trigger-digest-fast")
async def trigger_digest_fast(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    FAST digest trigger with async processing (PUBLIC - no auth required)
    Uses concurrent LLM calls for maximum speed
    """
    check_rate_limit(request)
    
    try:
        import time
        import traceback
        start_time = time.time()
        
        # Check critical environment variables
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set in environment")
        
        print("[STEP 1] Importing modules...")
        from .rss_fetcher import fetch_daily_news
        from .llm_processor_optimized import process_articles_async, token_usage_cache
        
        print("[STEP 2] Fetching RSS articles...")
        articles = fetch_daily_news(db)
        fetch_time = time.time() - start_time
        print(f"[STEP 2] Fetched {len(articles)} articles in {fetch_time:.2f}s")
        
        print("[STEP 3] Processing with LLM...")
        llm_start = time.time()
        processed_count = await process_articles_async(db)
        llm_time = time.time() - llm_start
        print(f"[STEP 3] Processed {processed_count} summaries in {llm_time:.2f}s")
        
        # Email is optional - don't fail if it errors
        sent_count = 0
        print("[STEP 4] Sending emails (optional)...")
        try:
            from .email_sender import send_daily_digest
            sent_count = send_daily_digest(db)
            print(f"[STEP 4] Sent {sent_count} emails")
        except Exception as email_error:
            print(f"[EMAIL WARNING] Email failed: {email_error}")
        
        total_time = time.time() - start_time
        
        return {
            "status": "success",
            "mode": "fast_async",
            "articles_fetched": len(articles),
            "summaries_processed": processed_count,
            "emails_sent": sent_count,
            "tokens_used": token_usage_cache['total_tokens'],
            "estimated_cost": f"${token_usage_cache['total_cost']:.4f}",
            "timing": {
                "fetch_seconds": round(fetch_time, 2),
                "llm_seconds": round(llm_time, 2),
                "total_seconds": round(total_time, 2)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Fast digest failed:")
        print(error_trace)
        raise HTTPException(
            status_code=500, 
            detail=f"Fast digest failed: {str(e)} | Type: {type(e).__name__}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)
