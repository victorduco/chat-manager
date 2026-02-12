# Quick Start Guide - Local Development

## Prerequisites

```bash
# cloudflared is required (used for public tunnel to localhost)
# https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

# Install dependencies
uv sync
cd admin-panel && npm install && cd ..
```

## Running All Services

### Option 1: Automated (Recommended)

Run everything with one command:
```bash
./scripts/run-dev.sh
```

This will:
- Start LangGraph API on port 2024
- Start Chatbot server on port 5050 (override with `CHATBOT_PORT`)
- Start cloudflared tunnel and configure webhook automatically

### Option 2: Manual (3 Terminals)

**Terminal 1 - LangGraph API:**
```bash
cd langgraph-app
uv run python -m langgraph_cli dev --port 2024
```

**Terminal 2 - Chatbot Server:**
```bash
cd chatbot
uv run python main.py
```

**Terminal 3 - cloudflared (no registration):**
```bash
cloudflared tunnel --url http://localhost:5050
# Copy the HTTPS URL and set webhook:
./scripts/set-webhook.sh https://YOUR-TUNNEL.trycloudflare.com
```

**Terminal 4 (Optional) - Admin Panel:**
```bash
cd admin-panel
npm run dev
```

## Services Overview

| Service | Port | URL | Description |
|---------|------|-----|-------------|
| LangGraph API | 2024 | http://localhost:2024 | AI workflows engine |
| Chatbot Server | 5050 | http://localhost:5050 | Telegram bot webhook handler |
| cloudflared | - | https://xxxx.trycloudflare.com | Public tunnel to local server |
| Admin Panel | 3000 | http://localhost:3000 | Web UI for thread management |

## Environment Configuration

Your `.env` file should look like this for local dev:

```env
OPENAI_API_KEY=sk-...
TELEGRAM_TOKEN=1234567890:ABC...
# DO NOT set HEROKU_APP_NAME - this keeps DEV mode enabled
```

## Admin Panel

The admin panel has a DEV/PROD switcher in the header:

- **🔧 DEV**: Connects to `http://localhost:2024` (local LangGraph)
- **🚀 PROD**: Connects to `https://langgraph-server-611bd1822796.herokuapp.com`

Your selection is saved in browser localStorage.

## Monitoring

### View Logs
```bash
tail -f logs/langgraph.log    # LangGraph API logs
tail -f logs/chatbot.log       # Chatbot server logs
tail -f logs/cloudflared.log   # cloudflared logs
```

### Check Running Services
```bash
ps aux | grep -E "langgraph|chatbot|cloudflared" | grep -v grep
```

### Test Endpoints
```bash
curl http://localhost:2024     # LangGraph API
curl http://localhost:5050     # Chatbot server (should show "dev_env")
```

## Troubleshooting

### cloudflared fails to start
Try restarting services:
```bash
./scripts/run-dev.sh
```

### Port already in use
```bash
# Stop existing processes
pkill -f "langgraph_cli dev"
pkill -f "chatbot/main.py"
pkill -f "cloudflared"
```

### Webhook not receiving messages
1. Check cloudflared is running: `tail -f logs/cloudflared.log`
2. Verify webhook is set:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
   ```
3. Look for errors in chatbot logs: `tail -f logs/chatbot.log`

### Admin panel can't connect
1. Make sure LangGraph API is running on port 2024
2. Click the **🔧 DEV** button in admin panel header
3. Check browser console for CORS errors

## Stopping Services

### If using run-dev.sh
Press `Ctrl+C` to stop all services

### If running manually
```bash
pkill -f "langgraph_cli dev"
pkill -f "chatbot/main.py"
pkill -f "cloudflared"
pkill -f "vite"  # Stop admin panel
```

## Next Steps

1. Open http://localhost:3000 for admin panel
2. Message your bot on Telegram
3. Watch logs: `tail -f logs/chatbot.log`
4. Manage threads in admin panel

## Production vs Development

| Aspect | Development | Production |
|--------|------------|------------|
| LangGraph | localhost:2024 | Heroku |
| Chatbot | localhost:5050 | Heroku |
| Webhook | cloudflared | Direct HTTPS |
| Database | Local SQLite | Heroku Postgres |
| Environment | DEV_ENV=True | DEV_ENV=False |

---

For more details, see [README.md](README.md)
