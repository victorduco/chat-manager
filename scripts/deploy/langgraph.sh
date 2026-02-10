#!/usr/bin/env bash
# Deploy LangGraph app to Heroku using LangGraph CLI
# Usage: ./scripts/deploy/langgraph.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LANGGRAPH_DIR="$PROJECT_ROOT/langgraph-app"

HEROKU_APP_NAME="${HEROKU_APP_NAME:-langgraph-server}"

echo "🚀 Deploying LangGraph app to Heroku..."
echo "📦 App name: $HEROKU_APP_NAME"
echo "📁 LangGraph dir: $LANGGRAPH_DIR"

# Verify we're in the langgraph-app directory
cd "$LANGGRAPH_DIR"

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Error: Heroku CLI is not installed"
    echo "Install it with: curl https://cli-assets.heroku.com/install.sh | sh"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Install it from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if langgraph CLI is installed
if ! command -v langgraph &> /dev/null; then
    echo "❌ Error: LangGraph CLI is not installed"
    echo "Install it with: pip install -U langgraph-cli"
    exit 1
fi

# Check if we're logged in to Heroku
if ! heroku auth:whoami &> /dev/null; then
    echo "❌ Error: Not logged in to Heroku"
    echo "Run: heroku login"
    exit 1
fi

# Verify the app exists
if ! heroku apps:info -a "$HEROKU_APP_NAME" &> /dev/null; then
    echo "❌ Error: Heroku app '$HEROKU_APP_NAME' not found"
    exit 1
fi

# Login to Heroku Container Registry
echo "🔐 Logging in to Heroku Container Registry..."
heroku container:login

# Build Docker image using LangGraph CLI for linux/amd64 (Heroku platform)
echo "🏗️  Building LangGraph Docker image for linux/amd64..."
langgraph build --tag "registry.heroku.com/$HEROKU_APP_NAME/web" --platform linux/amd64

# Verify the image was built
if ! docker images "registry.heroku.com/$HEROKU_APP_NAME/web" | grep -q web; then
    echo "❌ Error: Docker image was not built successfully"
    exit 1
fi

echo "📦 Docker images:"
docker images "registry.heroku.com/$HEROKU_APP_NAME/web"

# Push Docker image to Heroku
echo "📤 Pushing Docker image to Heroku..."
docker push "registry.heroku.com/$HEROKU_APP_NAME/web"

# Release the image on Heroku
echo "🚀 Releasing Docker image on Heroku..."
heroku container:release web --app "$HEROKU_APP_NAME"

echo "✅ LangGraph app deployed successfully!"
echo "🔗 URL: https://$HEROKU_APP_NAME.herokuapp.com"
echo ""
echo "📊 View logs with: heroku logs --tail -a $HEROKU_APP_NAME"
echo "🔍 Check status with: heroku ps -a $HEROKU_APP_NAME"
