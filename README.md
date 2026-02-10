# Agent Task Manager

AI-powered task management system with Telegram bot integration using LangGraph and LangChain.

## Quick Start

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/yourusername/agent-taskmanager.git
cd agent-taskmanager
cp .env.example .env
# Edit .env with your API keys

# Install dependencies
uv sync

# Run services (in separate terminals)
cd langgraph-app && uv run python -m langgraph_cli dev  # Terminal 1
cd chatbot && uv run python main.py                      # Terminal 2
cd admin-panel && npm install && npm run dev             # Terminal 3 (optional)
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
