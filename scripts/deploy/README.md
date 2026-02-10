# Deployment Scripts

Local deployment scripts for Agent Task Manager to Heroku.

## Scripts

### `deploy.sh` - Main deployment script
Deploy one or all components to Heroku.

```bash
# Deploy everything
./scripts/deploy/deploy.sh all

# Deploy only chatbot
./scripts/deploy/deploy.sh chatbot

# Deploy only LangGraph app
./scripts/deploy/deploy.sh langgraph

# Show help
./scripts/deploy/deploy.sh --help
```

### `chatbot.sh` - Chatbot deployment
Deploys the Telegram chatbot to Heroku using git subtree.

**What it does:**
1. Verifies Heroku CLI is installed and authenticated
2. Checks if the Heroku app exists
3. Adds/updates git remote for Heroku
4. Uses `git subtree split` to push only the `chatbot/` directory
5. Force pushes to Heroku's main branch

**Requirements:**
- Git repository
- Heroku CLI installed and logged in
- Heroku app created (e.g., `victorai`)

**Environment variables:**
- `HEROKU_BOT_NAME` - Heroku app name (default: `victorai`)

### `langgraph.sh` - LangGraph app deployment
Deploys the LangGraph app to Heroku using Docker containers and LangGraph CLI.

**What it does:**
1. Verifies required tools (Heroku CLI, Docker, LangGraph CLI)
2. Logs in to Heroku Container Registry
3. Generates a Dockerfile via `langgraph dockerfile`
4. Builds a single-platform `linux/amd64` image and `--load`s it into the local Docker engine
5. Pushes the image to Heroku (single image manifest; avoids manifest lists)
6. Releases the image on Heroku

**Requirements:**
- Docker installed and running
- LangGraph CLI installed: `pip install -U langgraph-cli`
- Heroku CLI installed and logged in
- Heroku app created (e.g., `langgraph-server`)

**Environment variables:**
- `HEROKU_APP_NAME` - Heroku app name (default: `langgraph-server`)

## Prerequisites

### Install Required Tools

**Heroku CLI:**
```bash
curl https://cli-assets.heroku.com/install.sh | sh
heroku login
```

**Docker:**
- macOS: [Docker Desktop](https://docs.docker.com/desktop/install/mac-install/)
- Linux: [Docker Engine](https://docs.docker.com/engine/install/)
- Windows: [Docker Desktop](https://docs.docker.com/desktop/install/windows-install/)

**LangGraph CLI:**
```bash
pip install -U langgraph-cli
```

### Create Heroku Apps

If you haven't created the Heroku apps yet:

```bash
# Create chatbot app
heroku create victorai

# Create LangGraph app
heroku create langgraph-server

# Add required addons for LangGraph
heroku addons:create upstash-redis:free -a langgraph-server
heroku addons:create heroku-postgresql:essential-0 -a langgraph-server
```

### Set Environment Variables

Set required environment variables for your apps:

```bash
# For chatbot
heroku config:set TELEGRAM_BOT_TOKEN=your_token -a victorai
heroku config:set LANGGRAPH_URL=https://langgraph-server.herokuapp.com -a victorai

# For LangGraph app
heroku config:set OPENAI_API_KEY=your_key -a langgraph-server
heroku config:set LANGSMITH_API_KEY=your_key -a langgraph-server
```

## Troubleshooting

### Git subtree issues
If you get errors with git subtree:
```bash
# Clear any cached subtree splits
git subtree split --prefix chatbot --rejoin
```

### Docker build failures
```bash
# Check Docker is running
docker info

# Clean up Docker images
docker system prune -a
```

### Heroku login issues
```bash
# Re-authenticate
heroku logout
heroku login
```

### LangGraph build issues
```bash
# Update LangGraph CLI
pip install -U langgraph-cli

# Check LangGraph configuration
cd langgraph-app
langgraph dockerfile --help
```

## Monitoring

After deployment, monitor your apps:

```bash
# View logs
heroku logs --tail -a victorai
heroku logs --tail -a langgraph-server

# Check dyno status
heroku ps -a victorai
heroku ps -a langgraph-server

# Open app in browser
heroku open -a victorai
heroku open -a langgraph-server
```
