#!/usr/bin/env bash
# Deploy chatbot to Heroku
# Usage: ./scripts/deploy-heroku/chatbot.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CHATBOT_DIR="$PROJECT_ROOT/chatbot"

HEROKU_APP_NAME="${HEROKU_BOT_NAME:-victorai}"

echo "🚀 Deploying chatbot to Heroku..."
echo "📦 App name: $HEROKU_APP_NAME"
echo "📁 Chatbot dir: $CHATBOT_DIR"

# Verify we're in the project root
cd "$PROJECT_ROOT"

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Error: Heroku CLI is not installed"
    echo "Install it with: curl https://cli-assets.heroku.com/install.sh | sh"
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

# Deploy using git subtree (only chatbot directory)
echo "📤 Pushing chatbot to Heroku..."
git push "https://git.heroku.com/$HEROKU_APP_NAME.git" "$(git subtree split --prefix chatbot HEAD):main" --force

echo "✅ Chatbot deployed successfully!"
echo "🔗 URL: https://$HEROKU_APP_NAME.herokuapp.com"
echo ""
echo "📊 View logs with: heroku logs --tail -a $HEROKU_APP_NAME"
echo "🔍 Check status with: heroku ps -a $HEROKU_APP_NAME"
