#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Run the development environment with Cloudflare Tunnel (no registration)

set -e

# Always run from repository root, regardless of where script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Agent Task Manager - Dev Environment Setup ===${NC}\n"

# cloudflared exposes localhost via a public trycloudflare.com URL.
if ! command -v cloudflared &> /dev/null; then
    echo -e "${RED}Error: cloudflared is not available${NC}"
    echo -e "Install cloudflared: ${YELLOW}https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/${NC}"
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

# Ensure runtime log directory exists before any redirects/touch.
mkdir -p logs

# Ports (override if needed)
LANGGRAPH_PORT="${LANGGRAPH_PORT:-2024}"
# macOS often has services on 5000; default to a safer port.
CHATBOT_PORT="${CHATBOT_PORT:-5050}"
ADMIN_PANEL_PORT="${ADMIN_PANEL_PORT:-3000}"

# Free a TCP listening port if it is occupied.
free_port() {
    local port="$1"
    local service_name="$2"
    local pids

    pids=$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)
    if [ -z "${pids}" ]; then
        return 0
    fi

    echo -e "${YELLOW}⚠${NC}  Port ${port} is busy. Stopping ${service_name} process(es): ${pids}"
    kill ${pids} 2>/dev/null || true
    sleep 1

    # Escalate only if something is still listening.
    pids=$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "${pids}" ]; then
        echo -e "${YELLOW}⚠${NC}  Force killing remaining process(es) on port ${port}: ${pids}"
        kill -9 ${pids} 2>/dev/null || true
        sleep 1
    fi
}

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    jobs -p | xargs -r kill
    exit
}
trap cleanup INT TERM

# Start LangGraph in background
echo -e "${BLUE}[1/4] Starting LangGraph API on port ${LANGGRAPH_PORT}...${NC}"
free_port "${LANGGRAPH_PORT}" "LangGraph"

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

# Dev-only safety: clear stale queued/running runs restored from previous sessions.
# Without this, a leftover "running" run can block the single in-memory worker and
# keep all fresh thread runs in "pending"/"busy".
curl -s -X POST "http://localhost:${LANGGRAPH_PORT}/runs/cancel" \
    -H "Content-Type: application/json" \
    -d '{"status":"running"}' > /dev/null || true
curl -s -X POST "http://localhost:${LANGGRAPH_PORT}/runs/cancel" \
    -H "Content-Type: application/json" \
    -d '{"status":"pending"}' > /dev/null || true

# Start chatbot server in background
echo -e "\n${BLUE}[2/4] Starting Chatbot server on port ${CHATBOT_PORT}...${NC}"
free_port "${CHATBOT_PORT}" "Chatbot"

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
free_port "${ADMIN_PANEL_PORT}" "Admin Panel"

# Run in a subshell so the main script working directory never changes.
(cd admin-panel && npm run dev > ../logs/admin-panel.log 2>&1) &
ADMIN_PANEL_PID=$!

# Wait for admin panel to start
sleep 3
if ! curl -s "http://localhost:${ADMIN_PANEL_PORT}" > /dev/null; then
    echo -e "${RED}Error: Admin Panel failed to start${NC}"
    echo -e "Check logs/admin-panel.log for details"
    kill $LANGGRAPH_PID $CHATBOT_PID $ADMIN_PANEL_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}✓${NC} Admin Panel running on http://localhost:${ADMIN_PANEL_PORT}"

# Start cloudflared tunnel
echo -e "\n${BLUE}[4/4] Starting cloudflared tunnel...${NC}"

# Ensure log file exists
touch logs/cloudflared.log

cloudflared tunnel --no-autoupdate --url "http://localhost:${CHATBOT_PORT}" > logs/cloudflared.log 2>&1 &
CLOUDFLARED_PID=$!

# Wait for cloudflared to print URL
CLOUDFLARED_URL=""
for _ in $(seq 1 100); do
    CLOUDFLARED_URL=$(rg -o "https://[^ ]*trycloudflare\\.com" logs/cloudflared.log | head -n 1 || true)
    if [ -n "$CLOUDFLARED_URL" ]; then
        break
    fi
    sleep 0.3
done

if [ -z "$CLOUDFLARED_URL" ]; then
    echo -e "${RED}Error: Could not get cloudflared URL${NC}"
    echo -e "Check logs/cloudflared.log for details"
    kill $LANGGRAPH_PID $CHATBOT_PID $ADMIN_PANEL_PID $CLOUDFLARED_PID 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✓${NC} cloudflared: ${YELLOW}$CLOUDFLARED_URL${NC}"

# Wait until the tunnel hostname is resolvable/reachable from this machine.
# trycloudflare hostnames may appear in logs before DNS propagation completes.
for _ in $(seq 1 30); do
    if curl -sS -o /dev/null --max-time 3 "$CLOUDFLARED_URL"; then
        break
    fi
    sleep 1
done

# Set Telegram webhook
WEBHOOK_URL="$CLOUDFLARED_URL/$TELEGRAM_TOKEN"
echo -e "\n${BLUE}Setting Telegram webhook...${NC}"
echo -e "Webhook URL: ${YELLOW}$WEBHOOK_URL${NC}"
RESPONSE=""
for _ in $(seq 1 20); do
    RESPONSE=$(curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook?url=$WEBHOOK_URL")
    if echo "$RESPONSE" | grep -q '"ok":true'; then
        break
    fi
    sleep 1
done

if ! echo "$RESPONSE" | grep -q '"ok":true'; then
    echo -e "${RED}Error setting webhook:${NC}"
    echo "$RESPONSE"
    kill $LANGGRAPH_PID $CHATBOT_PID $ADMIN_PANEL_PID $CLOUDFLARED_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}✓${NC} Webhook configured successfully"

# Display status
echo -e "\n${GREEN}=== Development Environment Running ===${NC}"
echo -e "${BLUE}Services:${NC}"
echo -e "  • LangGraph API: ${YELLOW}http://localhost:${LANGGRAPH_PORT}${NC}"
echo -e "  • Chatbot Server: ${YELLOW}http://localhost:${CHATBOT_PORT}${NC}"
echo -e "  • Admin Panel: ${YELLOW}http://localhost:${ADMIN_PANEL_PORT}${NC}"
echo -e "  • cloudflared: ${YELLOW}$CLOUDFLARED_URL${NC}"
echo -e "\n${BLUE}Logs:${NC}"
echo -e "  • LangGraph: ${YELLOW}tail -f logs/langgraph.log${NC}"
echo -e "  • Chatbot: ${YELLOW}tail -f logs/chatbot.log${NC}"
echo -e "  • Admin Panel: ${YELLOW}tail -f logs/admin-panel.log${NC}"
echo -e "  • cloudflared: ${YELLOW}tail -f logs/cloudflared.log${NC}"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}\n"

# Keep script running
wait
