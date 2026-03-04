"""
Email Sender - Send daily digest emails to users
"""
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session

from models import User, PortfolioStock, ProcessedSummary, SelectedTopic
from config import (
    EMAIL_ENABLED, EMAIL_PROVIDER, EMAIL_SENDER,
    RESEND_API_KEY, SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
)

class EmailDigestSender:
    def __init__(self):
        self.enabled = EMAIL_ENABLED
        self.provider = EMAIL_PROVIDER
        self.sender = EMAIL_SENDER
        
        # Resend config
        self.resend_api_key = RESEND_API_KEY
        self.resend_api_url = "https://api.resend.com/emails"
        
        # SMTP config (SendPulse, Gmail, etc.)
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.smtp_username = SMTP_USERNAME
        self.smtp_password = SMTP_PASSWORD
    
    def send_digest_to_user(self, user: User, db: Session) -> bool:
        """
        Send daily digest email to a single user
        """
        if not self.enabled:
            print("📧 Email sending is disabled in config")
            return False
        
        try:
            # Get user's portfolio stocks
            stocks = db.query(PortfolioStock).filter(
                PortfolioStock.user_id == user.id
            ).all()
            
            if not stocks:
                print(f"⚠️ User {user.email} has no stocks in portfolio, skipping...")
                return False
            
            # Get user's topics
            topics = db.query(SelectedTopic).filter(
                SelectedTopic.user_id == user.id
            ).all()
            
            # Get yesterday's summaries
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            stock_summaries = {}
            for stock in stocks:
                summaries = db.query(ProcessedSummary).filter(
                    ProcessedSummary.stock_ticker == stock.ticker,
                    ProcessedSummary.created_at >= yesterday
                ).all()
                
                if summaries:
                    stock_summaries[stock.ticker] = summaries
            
            if not stock_summaries:
                print(f"⚠️ No new summaries for user {user.email}, skipping...")
                return False
            
            # Build email
            subject = f"📊 Daily Portfolio News Digest – {datetime.now().strftime('%B %d, %Y')}"
            body = self._build_email_body(stock_summaries, topics)
            
            # Send email
            self._send_email(user.email, subject, body)
            
            print(f"✅ Sent digest to {user.email}")
            return True
            
        except Exception as e:
            print(f"❌ Error sending email to {user.email}: {str(e)}")
            return False
    
    def _build_email_body(self, stock_summaries: Dict, topics: List) -> str:
        """
        Build HTML email body
        """
        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }}
                .stock-section {{
                    background: #f8f9fa;
                    border-left: 4px solid #667eea;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .stock-ticker {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #667eea;
                    margin-bottom: 10px;
                }}
                .sentiment {{
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                    margin-right: 10px;
                }}
                .bullish {{ background: #d4edda; color: #155724; }}
                .bearish {{ background: #f8d7da; color: #721c24; }}
                .neutral {{ background: #e2e3e5; color: #383d41; }}
                .impact {{
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                    font-weight: bold;
                }}
                .high {{ background: #f8d7da; color: #721c24; }}
                .medium {{ background: #fff3cd; color: #856404; }}
                .low {{ background: #d1ecf1; color: #0c5460; }}
                .summary-points {{
                    margin: 15px 0;
                    padding-left: 20px;
                }}
                .summary-points li {{
                    margin: 8px 0;
                }}
                .explanation {{
                    background: white;
                    padding: 12px;
                    border-radius: 4px;
                    margin: 10px 0;
                    font-style: italic;
                }}
                .confidence {{
                    color: #666;
                    font-size: 14px;
                }}
                .article-link {{
                    display: inline-block;
                    margin-top: 10px;
                    color: #667eea;
                    text-decoration: none;
                }}
                .article-link:hover {{
                    text-decoration: underline;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 2px solid #e9ecef;
                    color: #6c757d;
                    font-size: 14px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Daily Portfolio News Digest</h1>
                <p>{datetime.now().strftime('%A, %B %d, %Y')}</p>
            </div>
        """
        
        # Add stock summaries
        for ticker, summaries in stock_summaries.items():
            html += f"""
            <div class="stock-section">
                <div class="stock-ticker">{ticker}</div>
            """
            
            for summary in summaries:
                sentiment_class = summary.sentiment.lower() if summary.sentiment else 'neutral'
                impact_class = summary.impact_level.lower() if summary.impact_level else 'low'
                
                html += f"""
                <div style="margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid #dee2e6;">
                    <div style="margin-bottom: 10px;">
                        <span class="sentiment {sentiment_class}">{summary.sentiment.upper()}</span>
                        <span class="impact {impact_class}">Impact: {summary.impact_level.upper()}</span>
                        <span class="confidence">Confidence: {summary.confidence_score}/10</span>
                    </div>
                    
                    <h3 style="margin: 10px 0;">{summary.article.title}</h3>
                    
                    <div class="summary-points">
                        {self._format_summary_bullets(summary.summary)}
                    </div>
                    
                    <div class="explanation">
                        <strong>Why it matters:</strong> {summary.impact_explanation}
                    </div>
                    
                    <a href="{summary.article.url}" class="article-link" target="_blank">
                        📰 Read full article →
                    </a>
                </div>
                """
            
            html += "</div>"
        
        # Add footer
        html += """
            <div class="footer">
                <p>This digest was generated by your Personal Fintech AI Agent</p>
                <p>Powered by GPT-4o-mini • RSS Feeds • FastAPI</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _format_summary_bullets(self, summary: str) -> str:
        """
        Convert bullet points to HTML list
        """
        lines = summary.split('\n')
        html_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Remove bullet markers
                line = line.lstrip('•-*').strip()
                html_lines.append(f"<li>{line}</li>")
        
        return '<ul>' + ''.join(html_lines) + '</ul>' if html_lines else summary
    
    def _send_email(self, recipient: str, subject: str, body: str):
        """
        Send email via configured provider (Resend API or SMTP)
        """
        if self.provider == "resend":
            self._send_via_resend(recipient, subject, body)
        else:  # smtp, sendpulse, gmail
            self._send_via_smtp(recipient, subject, body)
    
    def _send_via_resend(self, recipient: str, subject: str, body: str):
        """
        Send email via Resend API
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.resend_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "from": f"Fintech Agent <{self.sender}>",
                "to": [recipient],
                "subject": subject,
                "html": body
            }
            
            response = requests.post(
                self.resend_api_url,
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                raise Exception(f"Resend API error: {response.status_code} - {response.text}")
            
        except Exception as e:
            print(f"❌ Email Error (Resend): {str(e)}")
            raise
    
    def _send_via_smtp(self, recipient: str, subject: str, body: str):
        """
        Send email via SMTP (SendPulse, Gmail, etc.)
        """
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.sender
            message['To'] = recipient
            
            # Attach HTML body
            html_part = MIMEText(body, 'html')
            message.attach(html_part)
            
            # Connect to SMTP server and send
            if self.smtp_port == 465:
                # SSL
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(message)
            else:
                # TLS (port 587)
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(message)
            
        except Exception as e:
            print(f"❌ SMTP Error: {str(e)}")
            raise

def send_daily_digest(db: Session) -> int:
    """
    Send daily digest to all users
    Called by scheduler
    """
    sender = EmailDigestSender()
    
    # Get all users
    users = db.query(User).all()
    
    print(f"📧 Sending digest to {len(users)} users...")
    
    sent_count = 0
    for user in users:
        if sender.send_digest_to_user(user, db):
            sent_count += 1
    
    print(f"✅ Successfully sent {sent_count}/{len(users)} digests")
    
    return sent_count
