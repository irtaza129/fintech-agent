# Fintech AI Agent 📊

A personal AI-powered fintech agent that delivers daily news digests for your portfolio stocks and selected financial topics.

**Deployed on Render + Triggered by GitHub Actions**

## 🏗️ Architecture

```
Render (Free Web Service)
    ├── Frontend (Jinja templates)
    ├── Backend (FastAPI)
    ├── AI API Calls (OpenAI)
    ├── SQLite DB
    └── Digest Endpoint

GitHub Actions
    └── Daily Cron Trigger (7 AM UTC)
```

## 🎯 Features

- **Portfolio Management**: Track multiple stocks (TSLA, AAPL, etc.)
- **Topic Selection**: Follow macro trends, regulations, sector news, and risk events
- **RSS News Fetching**: Free news from Yahoo Finance, Google News, CNBC, MarketWatch
- **AI Summarization**: GPT-4o-mini analyzes articles with sentiment & impact scoring
- **Daily Email Digest**: Beautiful HTML emails with actionable insights
- **Low Cost**: ~$5-15/month (OpenAI API only, hosting is FREE)

## 📁 Project Structure

```
Fintech_Agent/
├── backend/
│   ├── main.py              # FastAPI app (serves frontend + API)
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database setup
│   ├── models.py            # SQLAlchemy models
│   ├── rss_fetcher.py       # RSS feed fetching
│   ├── llm_processor.py     # LLM integration
│   ├── email_sender.py      # Email digest
│   └── utils.py             # Utility functions
├── templates/
│   └── index.html           # Jinja2 dashboard template
├── .github/workflows/
│   └── daily-digest.yml     # GitHub Actions cron job
├── requirements.txt         # Python dependencies
├── render.yaml             # Render deployment config
├── .env.example            # Local environment template
├── .env.render             # Render environment guide
├── DEPLOYMENT.md           # Deployment guide
└── README.md               # This file
```

## 🚀 Quick Start

### 1. Clone & Setup

```bash
cd Fintech_Agent
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy the example env file
copy .env.example .env

# Edit .env with your settings:
# - Add your OpenAI API key (or Groq API key)
# - Configure email SMTP settings
# - Adjust other settings as needed
```

### 4. Initialize Database

```bash
cd backend
python -c "from database import init_db; init_db()"
```

### 5. Run the Backend

```bash
python main.py
```

The API will be available at `http://localhost:8000`

### 6. Open Dashboard

Open `frontend/index.html` in your browser, or serve it:

```bash
# Simple HTTP server
cd frontend
python -m http.server 8080
```

Then visit `http://localhost:8080`

### 7. Test the Pipeline (Optional)

Run the daily pipeline manually to test:

```bash
python scheduler.py
```

## 📧 Email Setup (Gmail Example)

1. Enable 2-Factor Authentication on Gmail
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Add to `.env`:
   ```
   EMAIL_SENDER=your.email@gmail.com
   EMAIL_PASSWORD=your_app_password_here
   ```

## 🔑 API Keys

### OpenAI (Recommended)
- Sign up: https://platform.openai.com
- Model: `gpt-4o-mini` (cheapest, best for this use case)
- Cost: ~$0.15 per 1M input tokens, $0.60 per 1M output tokens

### Groq (Free Alternative)
- Sign up: https://console.groq.com
- Free tier available
- Models: Mixtral, Llama 2

## 📊 Database Schema

### Tables

- **users**: User accounts
- **portfolio_stocks**: Stocks in user portfolios
- **selected_topics**: Topics user wants to track
- **raw_articles**: Fetched RSS articles
- **processed_summaries**: LLM-analyzed summaries

## 🔄 Daily Workflow

1. **7:00 AM** (configurable): Scheduler triggers
2. **Fetch RSS**: Pull latest 24h articles from feeds
3. **Filter**: Match articles to user stocks/topics
4. **Process**: Send to LLM for analysis
5. **Store**: Save summaries to database
6. **Email**: Send digest to all users

## 🎨 Dashboard Features

### Tab 1: Portfolio Stocks
- Add/remove stock tickers
- Auto-detect company names

### Tab 2: Financial Topics
- Select from 24 predefined topics
- Categories: Macro, Regulation, Market Structure, Sectors, Risk Events

### Tab 3: Latest Digest
- View recent summaries
- Sentiment indicators (Bullish/Bearish/Neutral)
- Impact levels (High/Medium/Low)
- Confidence scores

## 🛠️ API Endpoints

### Users
- `POST /users` - Create user
- `GET /users/{id}` - Get user

### Stocks
- `POST /users/{id}/stocks` - Add stock
- `GET /users/{id}/stocks` - List stocks
- `DELETE /users/{id}/stocks/{stock_id}` - Remove stock

### Topics
- `GET /topics/available` - List all available topics
- `POST /users/{id}/topics` - Add topic
- `GET /users/{id}/topics` - List user's topics
- `DELETE /users/{id}/topics/{topic_id}` - Remove topic

### Summaries
- `GET /users/{id}/summaries` - Get processed summaries

## 💰 Cost Optimization Tips

1. **Use GPT-4o-mini**: Cheapest OpenAI model
2. **RSS Feeds Only**: No paid news API subscriptions
3. **SQLite**: No database hosting costs
4. **Local Hosting**: Run on your machine or free tier cloud
5. **Batch Processing**: Process once daily, not real-time

## 🔧 Advanced Configuration

### Custom RSS Feeds
Edit `backend/config.py` and modify the `RSS_FEEDS` list.

### Change Schedule Time
Edit `.env`:
```
DIGEST_HOUR=7    # 7 AM
DIGEST_MINUTE=0  # 0 minutes
```

### Add More Topics
Edit `backend/config.py` and add to `AVAILABLE_TOPICS` list.

## 🐛 Troubleshooting

### Backend won't start
- Check all dependencies installed: `pip install -r requirements.txt`
- Verify `.env` file exists with required keys

### No emails sent
- Check `EMAIL_ENABLED=true` in `.env`
- Verify SMTP credentials
- For Gmail, use App Password, not regular password

### No articles found
- Wait 24 hours for RSS feeds to populate
- Check stocks/topics are added
- Verify RSS feeds are accessible

### Database errors
- Delete `fintech_agent.db` and reinitialize
- Run: `python -c "from database import init_db; init_db()"`

## 📝 To-Do / Future Enhancements

- [ ] User authentication system
- [ ] Real-time stock price integration
- [ ] Customizable email templates
- [ ] Mobile app
- [ ] Webhook notifications (Telegram, Slack)
- [ ] Historical performance tracking
- [ ] Portfolio analytics dashboard

## 📄 License

This project is for personal use. Modify as needed!

## 🤝 Contributing

Feel free to fork and improve! This is a learning project focused on:
- Building practical AI agents
- Cost-effective solutions
- Clean architecture
- Real-world financial tools

## ⚠️ Disclaimer

This tool provides news summaries and sentiment analysis for informational purposes only. It is NOT financial advice. Always do your own research before making investment decisions.

---

Built with ❤️ using FastAPI, GPT-4o-mini, and Tailwind CSS
