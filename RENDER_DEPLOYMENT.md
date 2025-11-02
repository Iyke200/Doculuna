# DocuLuna Bot - Render Deployment Guide

## 🚀 Quick Deployment Steps

### 1. Prerequisites
- A [Render.com](https://render.com) account
- Your Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- (Optional) Paystack API keys for payment processing

### 2. Deploy to Render

#### Option A: Using render.yaml (Recommended)
1. Fork/clone this repository to your GitHub account
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click "New" → "Blueprint"
4. Connect your GitHub repository
5. Render will automatically detect `render.yaml`
6. Configure environment variables (see below)
7. Click "Apply" to deploy

#### Option B: Manual Setup
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New" → "Web Service"
3. Connect your repository
4. Configure:
   - **Name**: `doculuna-bot`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Plan**: Free (or choose your preferred plan)

### 3. Configure Environment Variables

Go to your service's "Environment" tab and add:

#### Required Variables:
```
ENVIRONMENT=production
BOT_TOKEN=your_telegram_bot_token_here
WEBHOOK_URL=https://your-app-name.onrender.com
```

#### Optional Variables:
```
ADMIN_USER_IDS=123456789,987654321
PAYSTACK_SECRET_KEY=your_paystack_secret_key
PAYSTACK_PUBLIC_KEY=your_paystack_public_key
```

### 4. Get Your Webhook URL

After deployment, your webhook URL will be:
```
https://your-service-name.onrender.com
```

Make sure to set this as your `WEBHOOK_URL` environment variable.

### 5. Verify Deployment

1. Check the logs in Render dashboard
2. Look for these success messages:
   ```
   ✓ Database initialized
   ✓ Handlers registered
   ✓ Webhook set to: https://your-app.onrender.com/webhook
   ✓ Webhook server started successfully
   ```
3. Test your bot by sending `/start` in Telegram

## 📝 Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `ENVIRONMENT` | Yes | Deployment environment | `production` |
| `BOT_TOKEN` | Yes | Telegram bot token from BotFather | `123456:ABCdef...` |
| `WEBHOOK_URL` | Yes | Your Render app URL (without /webhook) | `https://yourapp.onrender.com` |
| `PORT` | No | Port number (Render sets automatically) | `10000` |
| `ADMIN_USER_IDS` | No | Comma-separated admin Telegram user IDs | `123456,789012` |
| `PAYSTACK_SECRET_KEY` | No | Paystack secret key for payments | `sk_live_...` |
| `PAYSTACK_PUBLIC_KEY` | No | Paystack public key | `pk_live_...` |

## 🔧 Troubleshooting

### Bot not responding
1. Check Render logs for errors
2. Verify `WEBHOOK_URL` is correct (no trailing slash)
3. Ensure `BOT_TOKEN` is valid
4. Check webhook status: `https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo`

### Database issues
- Render's free tier has ephemeral storage
- Database resets on each deployment
- Consider upgrading to a paid plan with persistent disk

### Webhook errors
- Ensure your webhook URL is HTTPS
- Verify the `/webhook` endpoint is accessible
- Check if Telegram can reach your Render service

## 🎯 Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Configure valid `BOT_TOKEN`
- [ ] Set correct `WEBHOOK_URL`
- [ ] Add admin user IDs
- [ ] Enable health checks
- [ ] Monitor logs for errors
- [ ] Test all bot features
- [ ] Set up payment processing (if needed)

## 🔄 Updating Your Bot

Render automatically deploys when you push to your main branch:

1. Make changes to your code
2. Commit and push to GitHub
3. Render will automatically rebuild and deploy
4. Monitor the build logs in Render dashboard

## 💡 Tips

1. **Free Tier**: Render's free tier spins down after 15 minutes of inactivity
2. **Persistent Storage**: Upgrade to a paid plan for persistent disk storage
3. **Custom Domain**: You can add a custom domain in Render settings
4. **Monitoring**: Use Render's built-in metrics and logging
5. **Scaling**: Upgrade your plan to handle more traffic

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Aiogram Documentation](https://docs.aiogram.dev/)

## ⚠️ Important Notes

1. The bot uses webhook mode in production (not polling)
2. Render automatically provides HTTPS (required for webhooks)
3. Database is SQLite (stored on disk)
4. Free tier services sleep after inactivity
5. Health check endpoint is available at `/health`

## 🆘 Support

If you encounter issues:
1. Check Render logs first
2. Verify all environment variables
3. Test webhook connectivity
4. Review bot configuration
