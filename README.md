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
```

## Architecture

- **chatbot/** - Telegram bot service (python-telegram-bot + Quart)
- **langgraph-app/** - LangGraph AI workflows (OpenAI GPT-4)
- **libs/conversation_states/** - Shared state management library


## License

GPL-3.0 - see [LICENSE](LICENSE)
