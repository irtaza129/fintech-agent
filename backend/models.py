"""
SQLAlchemy database models
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    portfolio_stocks = relationship("PortfolioStock", back_populates="user", cascade="all, delete-orphan")
    selected_topics = relationship("SelectedTopic", back_populates="user", cascade="all, delete-orphan")

class PortfolioStock(Base):
    __tablename__ = "portfolio_stocks"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticker = Column(String, nullable=False)
    company_name = Column(String, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="portfolio_stocks")

class SelectedTopic(Base):
    __tablename__ = "selected_topics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_name = Column(String, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="selected_topics")

class RawArticle(Base):
    __tablename__ = "raw_articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    url = Column(String, unique=True, index=True, nullable=False)  # Added index for faster duplicate checking
    source = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)
    content = Column(Text, nullable=True)
    tickers_detected = Column(String, nullable=True)  # Comma-separated
    topics_detected = Column(String, nullable=True)   # Comma-separated
    
    # Relationships
    summaries = relationship("ProcessedSummary", back_populates="article", cascade="all, delete-orphan")

class ProcessedSummary(Base):
    __tablename__ = "processed_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("raw_articles.id"), nullable=False)
    stock_ticker = Column(String, nullable=True)
    summary = Column(Text, nullable=False)
    sentiment = Column(String, nullable=True)  # bullish/bearish/neutral
    impact_level = Column(String, nullable=True)  # low/medium/high
    impact_explanation = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)  # 1-10
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    article = relationship("RawArticle", back_populates="summaries")
