# Agent Task Manager

AI-powered task management system with Telegram bot integration using LangGraph and LangChain.

## Quick Start

### Prerequisites
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js is required for localtunnel (Telegram webhooks to localhost without registration)
# https://nodejs.org
```

### Setup
```bash
# Clone and setup
git clone https://github.com/yourusername/agent-taskmanager.git
cd agent-taskmanager

# Install dependencies
uv sync
```

### Local Development (with Telegram Dev Bot)

**Step 1: Create a dev bot**
1. Open [@BotFather](https://t.me/botfather) in Telegram
2. Send `/newbot` and follow instructions
3. Save the bot token

**Step 2: Configure environment**
```bash
cp .env.local .env
# Edit .env and set TELEGRAM_TOKEN to your dev bot token
```

**Step 3: Run everything (automated)**
```bash
./scripts/run-dev.sh
```

This script will:
- Start LangGraph API on `localhost:2024`
- Start Chatbot server on `localhost:5050` (override with `CHATBOT_PORT`)
- Create localtunnel and set Telegram webhook automatically

**Alternative: Manual setup (3 terminals)**
```bash
# Terminal 1: LangGraph API
cd langgraph-app && uv run python -m langgraph_cli dev

# Terminal 2: Chatbot Server
cd chatbot && uv run python main.py

# Terminal 3: localtunnel (no registration)
npx --yes localtunnel --port 5050
# Copy the https URL and run:
./scripts/set-webhook.sh https://YOUR-TUNNEL.loca.lt
```

### Debugging

View logs in real-time:
```bash
tail -f logs/langgraph.log   # LangGraph API
tail -f logs/chatbot.log      # Chatbot server
tail -f logs/localtunnel.log  # localtunnel
```

### Stop Services

If using `run-dev.sh`: Press `Ctrl+C`

If running manually:
```bash
# Stop LangGraph
pkill -f "langgraph_cli dev"

# Stop Chatbot
pkill -f "chatbot/main.py"

# Remove webhook (optional)
curl "https://api.telegram.org/bot<YOUR_TOKEN>/deleteWebhook"
```

## Architecture

- **chatbot/** - Telegram bot service (python-telegram-bot + Quart)
- **langgraph-app/** - LangGraph AI workflows (OpenAI GPT-4)
- **libs/conversation_states/** - Shared state management library
- **admin-panel/** - Web admin interface (Vue 3) for thread and user management

## Deployment

Deploy to Heroku using local scripts:

```bash
# Deploy everything
./scripts/deploy/deploy.sh all

# Deploy only chatbot
./scripts/deploy/deploy.sh chatbot

# Deploy only LangGraph app
./scripts/deploy/deploy.sh langgraph
```

**Prerequisites:**
- [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed
- [Docker](https://docs.docker.com/get-docker/) installed (for LangGraph deployment)
- [LangGraph CLI](https://langchain-ai.github.io/langgraph/cloud/reference/cli/) installed: `pip install -U langgraph-cli`
- Logged in to Heroku: `heroku login`

**Environment variables:**
- `HEROKU_BOT_NAME` - Chatbot app name (default: `victorai`)
- `HEROKU_APP_NAME` - LangGraph app name (default: `langgraph-server`)

**Example with custom app names:**
```bash
HEROKU_BOT_NAME=my-bot HEROKU_APP_NAME=my-langgraph ./scripts/deploy/deploy.sh all
```

## Admin Panel

Web-based admin interface for managing threads and viewing user intro status.

**Features:**
- 📋 Browse and filter threads by status
- 👥 View all users with intro completion status (✅/❌)
- 💬 View conversation history
- 📝 Access thread metadata and state

**Setup:**
```bash
cd admin-panel
npm install
npm run dev  # Runs at http://localhost:3000
```

See [admin-panel/README.md](admin-panel/README.md) for detailed documentation.

## License

GPL-3.0 - see [LICENSE](LICENSE)
