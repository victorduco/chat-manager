#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Run the development environment with localtunnel (no registration)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Agent Task Manager - Dev Environment Setup ===${NC}\n"

# localtunnel is executed via npx, so we only need Node/npm present.
if ! command -v npx &> /dev/null; then
    echo -e "${RED}Error: npx is not available${NC}"
    echo -e "Install Node.js (includes npm/npx): ${YELLOW}https://nodejs.org${NC}"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo -e "Copy .env.local to .env and configure your dev bot token:"
    echo -e "${YELLOW}cp .env.local .env${NC}"
    echo -e "Then edit .env and set TELEGRAM_TOKEN to your dev bot token"
    exit 1
fi

# Check if dev bot token is configured
source .env
if [ "$TELEGRAM_TOKEN" == "YOUR_DEV_BOT_TOKEN_HERE" ] || [ -z "$TELEGRAM_TOKEN" ]; then
    echo -e "${RED}Error: TELEGRAM_TOKEN not configured${NC}"
    echo -e "Get a dev bot token from @BotFather and update .env"
    exit 1
fi

echo -e "${GREEN}✓${NC} Environment configured"
echo -e "${BLUE}Starting services...${NC}\n"

# Ports (override if needed)
LANGGRAPH_PORT="${LANGGRAPH_PORT:-2024}"
# macOS often has services on 5000; default to a safer port.
CHATBOT_PORT="${CHATBOT_PORT:-5050}"
ADMIN_PANEL_PORT="${ADMIN_PANEL_PORT:-3000}"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    jobs -p | xargs -r kill
    exit
}
trap cleanup INT TERM

# Start LangGraph in background
echo -e "${BLUE}[1/4] Starting LangGraph API on port ${LANGGRAPH_PORT}...${NC}"
uv run --all-packages --directory langgraph-app \
    python -m langgraph_cli dev --port "${LANGGRAPH_PORT}" > logs/langgraph.log 2>&1 &
LANGGRAPH_PID=$!

# Wait for LangGraph to start
sleep 5
if ! curl -s "http://localhost:${LANGGRAPH_PORT}" > /dev/null; then
    echo -e "${RED}Error: LangGraph failed to start${NC}"
    echo -e "Check logs/langgraph.log for details"
    kill $LANGGRAPH_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}✓${NC} LangGraph API running on http://localhost:${LANGGRAPH_PORT}"

# Start chatbot server in background
echo -e "\n${BLUE}[2/4] Starting Chatbot server on port ${CHATBOT_PORT}...${NC}"
PORT="${CHATBOT_PORT}" LANGGRAPH_API_URL="http://localhost:${LANGGRAPH_PORT}" \
    uv run --all-packages --directory chatbot python main.py > logs/chatbot.log 2>&1 &
CHATBOT_PID=$!

# Wait for chatbot to start
sleep 3
if ! curl -s "http://localhost:${CHATBOT_PORT}" > /dev/null; then
    echo -e "${RED}Error: Chatbot server failed to start${NC}"
    echo -e "Check logs/chatbot.log for details"
    kill $LANGGRAPH_PID $CHATBOT_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}✓${NC} Chatbot server running on http://localhost:${CHATBOT_PORT}"

# Start admin panel in background
echo -e "\n${BLUE}[3/4] Starting Admin Panel on port ${ADMIN_PANEL_PORT}...${NC}"
cd admin-panel && npm run dev > ../logs/admin-panel.log 2>&1 &
ADMIN_PANEL_PID=$!
cd ..

# Wait for admin panel to start
sleep 3
if ! curl -s "http://localhost:${ADMIN_PANEL_PORT}" > /dev/null; then
    echo -e "${RED}Error: Admin Panel failed to start${NC}"
    echo -e "Check logs/admin-panel.log for details"
    kill $LANGGRAPH_PID $CHATBOT_PID $ADMIN_PANEL_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}✓${NC} Admin Panel running on http://localhost:${ADMIN_PANEL_PORT}"

# Start localtunnel
echo -e "\n${BLUE}[4/4] Starting localtunnel...${NC}"

# Optional: request a stable subdomain (may fail if already taken)
# Example: LOCALTUNNEL_SUBDOMAIN=my-dev-bot ./scripts/run-dev.sh
# localtunnel writes the URL to stdout; keep full logs for debugging.
LT_ARGS=(--port "${CHATBOT_PORT}")
if [ -n "${LOCALTUNNEL_SUBDOMAIN:-}" ]; then
    LT_ARGS+=(--subdomain "${LOCALTUNNEL_SUBDOMAIN}")
fi

npx --yes localtunnel "${LT_ARGS[@]}" > logs/localtunnel.log 2>&1 &
LOCALTUNNEL_PID=$!

# Wait for localtunnel to print URL
LOCALTUNNEL_URL=""
for _ in $(seq 1 50); do
    LOCALTUNNEL_URL=$(rg -o "https://[^ ]+" logs/localtunnel.log | head -n 1 || true)
    if [ -n "$LOCALTUNNEL_URL" ]; then
        break
    fi
    sleep 0.2
done

if [ -z "$LOCALTUNNEL_URL" ]; then
    echo -e "${RED}Error: Could not get localtunnel URL${NC}"
    echo -e "Check logs/localtunnel.log for details"
    kill $LANGGRAPH_PID $CHATBOT_PID $ADMIN_PANEL_PID $LOCALTUNNEL_PID 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✓${NC} localtunnel: ${YELLOW}$LOCALTUNNEL_URL${NC}"

# Set Telegram webhook
WEBHOOK_URL="$LOCALTUNNEL_URL/$TELEGRAM_TOKEN"
echo -e "\n${BLUE}Setting Telegram webhook...${NC}"
echo -e "Webhook URL: ${YELLOW}$WEBHOOK_URL${NC}"

RESPONSE=$(curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook?url=$WEBHOOK_URL")

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo -e "${GREEN}✓${NC} Webhook configured successfully"
else
    echo -e "${RED}Error setting webhook:${NC}"
    echo "$RESPONSE"
    kill $LANGGRAPH_PID $CHATBOT_PID $ADMIN_PANEL_PID $LOCALTUNNEL_PID 2>/dev/null
    exit 1
fi

# Display status
echo -e "\n${GREEN}=== Development Environment Running ===${NC}"
echo -e "${BLUE}Services:${NC}"
echo -e "  • LangGraph API: ${YELLOW}http://localhost:${LANGGRAPH_PORT}${NC}"
echo -e "  • Chatbot Server: ${YELLOW}http://localhost:${CHATBOT_PORT}${NC}"
echo -e "  • Admin Panel: ${YELLOW}http://localhost:${ADMIN_PANEL_PORT}${NC}"
echo -e "  • localtunnel: ${YELLOW}$LOCALTUNNEL_URL${NC}"
echo -e "\n${BLUE}Logs:${NC}"
echo -e "  • LangGraph: ${YELLOW}tail -f logs/langgraph.log${NC}"
echo -e "  • Chatbot: ${YELLOW}tail -f logs/chatbot.log${NC}"
echo -e "  • Admin Panel: ${YELLOW}tail -f logs/admin-panel.log${NC}"
echo -e "  • localtunnel: ${YELLOW}tail -f logs/localtunnel.log${NC}"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}\n"

# Keep script running
wait
