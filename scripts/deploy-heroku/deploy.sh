#!/usr/bin/env bash
# Main deployment script for Agent Task Manager
# Usage: ./scripts/deploy-heroku/deploy.sh [chatbot|langgraph|all]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function show_usage() {
    cat << EOF
Usage: ./scripts/deploy-heroku/deploy.sh [COMPONENT]

Deploy Agent Task Manager components to Heroku

COMPONENT:
    chatbot     Deploy only the Telegram chatbot
    langgraph   Deploy only the LangGraph app
    all         Deploy both components (default)

Environment variables:
    HEROKU_BOT_NAME   Heroku app name for chatbot (default: victorai)
    HEROKU_APP_NAME   Heroku app name for langgraph (default: langgraph-server)

Examples:
    ./scripts/deploy-heroku/deploy.sh chatbot
    ./scripts/deploy-heroku/deploy.sh langgraph
    ./scripts/deploy-heroku/deploy.sh all
    HEROKU_BOT_NAME=my-bot ./scripts/deploy-heroku/deploy.sh chatbot

EOF
}

COMPONENT="${1:-all}"

case "$COMPONENT" in
    chatbot)
        echo "🤖 Deploying chatbot..."
        bash "$SCRIPT_DIR/chatbot.sh"
        ;;
    langgraph)
        echo "🔗 Deploying LangGraph app..."
        bash "$SCRIPT_DIR/langgraph.sh"
        ;;
    all)
        echo "🚀 Deploying all components..."
        echo ""
        echo "═══════════════════════════════════════"
        echo "  1/2: Deploying LangGraph app"
        echo "═══════════════════════════════════════"
        bash "$SCRIPT_DIR/langgraph.sh"
        echo ""
        echo "═══════════════════════════════════════"
        echo "  2/2: Deploying Chatbot"
        echo "═══════════════════════════════════════"
        bash "$SCRIPT_DIR/chatbot.sh"
        echo ""
        echo "✅ All components deployed successfully!"
        ;;
    -h|--help|help)
        show_usage
        exit 0
        ;;
    *)
        echo "❌ Error: Unknown component '$COMPONENT'"
        echo ""
        show_usage
        exit 1
        ;;
esac
