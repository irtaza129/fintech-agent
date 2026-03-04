# Deployment Checklist for Render

## Prerequisites
- [ ] GitHub account
- [ ] Render account (free): https://render.com
- [ ] OpenAI API key: https://platform.openai.com
- [ ] Gmail with App Password (for emails)

## Step 1: Prepare GitHub Repository

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial deployment"

# Add remote (replace with your repo URL)
git remote add origin https://github.com/YOUR_USERNAME/fintech-agent.git

# Push to GitHub
git push -u origin main
```

## Step 2: Deploy to Render

1. **Go to Render Dashboard**
   - Visit: https://dashboard.render.com/
   - Sign in with GitHub

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Select "Build and deploy from a Git repository"
   - Click "Next"

3. **Connect Repository**
   - Connect to your GitHub account
   - Select your `fintech-agent` repository
   - Click "Connect"

4. **Configure Service**
   - Render will auto-detect `render.yaml`
   - Name: `fintech-ai-agent` (or your choice)
   - Branch: `main`
   - Root Directory: leave blank
   - Click "Apply"

5. **Add Environment Variables**
   - Click on your new service
   - Go to "Environment" tab
   - Add these variables:

   ```
   OPENAI_API_KEY=sk-your-key-here
   EMAIL_SENDER=your-email@gmail.com
   EMAIL_PASSWORD=your-gmail-app-password
   ```

   Optional:
   ```
   DIGEST_SECRET=your-random-secret-123
   LLM_PROVIDER=openai
   LLM_MODEL=gpt-4o-mini
   ```

6. **Deploy**
   - Click "Manual Deploy" → "Deploy latest commit"
   - Wait 2-5 minutes for deployment
   - Your app URL: `https://fintech-ai-agent-xxxx.onrender.com`

## Step 3: Setup GitHub Actions

1. **Add GitHub Secrets**
   - Go to your GitHub repo
   - Settings → Secrets and variables → Actions
   - Click "New repository secret"

   Add these secrets:
   ```
   RENDER_APP_URL = https://your-app.onrender.com
   DIGEST_SECRET = same-secret-as-render
   ```

2. **Enable GitHub Actions**
   - GitHub repo → Actions tab
   - Enable workflows if prompted

3. **Test Manual Trigger**
   - Actions → "Daily News Digest" → "Run workflow"
   - Check logs to see if it succeeded

## Step 4: Test Your Deployment

1. **Open Your App**
   - Visit your Render URL
   - Dashboard should load

2. **Create User Profile**
   - Enter your email
   - Click "Load Profile"

3. **Add Stocks**
   - Add 2-3 stocks (e.g., TSLA, AAPL, NVDA)

4. **Add Topics**
   - Select 2-3 topics (e.g., "AI Stocks", "Federal Reserve Policy")

5. **Manual Digest Test**
   - Run this command (replace URL):
   ```bash
   curl -X POST https://your-app.onrender.com/api/trigger-digest
   ```

6. **Check Email**
   - Wait a few minutes
   - Check your inbox for digest

## Step 5: Verify Daily Automation

- GitHub Actions will run daily at 7 AM UTC
- Check "Actions" tab the next day to verify
- Adjust cron schedule if needed in `.github/workflows/daily-digest.yml`

## Common Issues

### ❌ Deployment Failed
- Check Render logs: Dashboard → Service → Logs
- Verify all files committed to GitHub
- Ensure `requirements.txt` is present

### ❌ Environment Variables Not Working
- Double-check spelling (case-sensitive)
- No quotes around values in Render
- Redeploy after adding variables

### ❌ GitHub Actions Failing
- Check workflow file syntax
- Verify `RENDER_APP_URL` in secrets
- Ensure Render app is awake

### ❌ No Emails Received
- Verify Gmail App Password (not regular password)
- Check spam folder
- Look at Render logs for SMTP errors

### ❌ App Sleeping (Free Tier)
- Free tier sleeps after 15 min inactivity
- First request takes ~30 seconds to wake up
- GitHub Actions will wake it automatically
- Upgrade to paid tier ($7/mo) to avoid sleeping

## Monitoring

### Check Render Logs
```
Dashboard → Your Service → Logs (live tail)
```

### Check GitHub Actions Runs
```
Repository → Actions → Daily News Digest
```

### Check OpenAI Usage
```
https://platform.openai.com/usage
```

## Scaling Options

### Upgrade Render Plan
- **Free**: 750 hours/month, sleeps after 15 min
- **Starter ($7/mo)**: Always on, more resources

### Optimize Costs
- Use GPT-4o-mini (cheapest)
- Limit RSS feeds
- Reduce digest frequency

## Backup & Maintenance

### Backup Database
1. Render Dashboard → Service → Disk
2. Download SQLite file periodically
3. Store safely

### Update Dependencies
```bash
# Update requirements.txt
pip install --upgrade package-name

# Commit and push
git add requirements.txt
git commit -m "Update dependencies"
git push

# Render auto-deploys
```

## 🎉 Success!

Your Fintech AI Agent is now:
- ✅ Deployed to Render (free)
- ✅ Automated with GitHub Actions
- ✅ Sending daily email digests
- ✅ Costing only $5-15/month

**Next Steps:**
- Monitor for a few days
- Adjust stocks/topics as needed
- Share with friends!
