#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Run the development environment with ngrok tunnel

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Agent Task Manager - Dev Environment Setup ===${NC}\n"

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo -e "${RED}Error: ngrok is not installed${NC}"
    echo -e "Install ngrok from: ${YELLOW}https://ngrok.com/download${NC}"
    echo -e "Or via brew: ${YELLOW}brew install ngrok${NC}"
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

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    jobs -p | xargs -r kill
    exit
}
trap cleanup INT TERM

# Start LangGraph in background
echo -e "${BLUE}[1/3] Starting LangGraph API on port 2024...${NC}"
cd langgraph-app
uv run python -m langgraph_cli dev --port 2024 > ../logs/langgraph.log 2>&1 &
LANGGRAPH_PID=$!
cd ..

# Wait for LangGraph to start
sleep 5
if ! curl -s http://localhost:2024 > /dev/null; then
    echo -e "${RED}Error: LangGraph failed to start${NC}"
    echo -e "Check logs/langgraph.log for details"
    kill $LANGGRAPH_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}✓${NC} LangGraph API running on http://localhost:2024"

# Start chatbot server in background
echo -e "\n${BLUE}[2/3] Starting Chatbot server on port 5000...${NC}"
cd chatbot
uv run python main.py > ../logs/chatbot.log 2>&1 &
CHATBOT_PID=$!
cd ..

# Wait for chatbot to start
sleep 3
if ! curl -s http://localhost:5000 > /dev/null; then
    echo -e "${RED}Error: Chatbot server failed to start${NC}"
    echo -e "Check logs/chatbot.log for details"
    kill $LANGGRAPH_PID $CHATBOT_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}✓${NC} Chatbot server running on http://localhost:5000"

# Start ngrok tunnel
echo -e "\n${BLUE}[3/3] Starting ngrok tunnel...${NC}"
ngrok http 5000 --log=stdout > logs/ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to start and get URL
sleep 3
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | cut -d'"' -f4 | head -n1)

if [ -z "$NGROK_URL" ]; then
    echo -e "${RED}Error: Could not get ngrok URL${NC}"
    echo -e "Check logs/ngrok.log for details"
    kill $LANGGRAPH_PID $CHATBOT_PID $NGROK_PID 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✓${NC} Ngrok tunnel: ${YELLOW}$NGROK_URL${NC}"

# Set Telegram webhook
WEBHOOK_URL="$NGROK_URL/$TELEGRAM_TOKEN"
echo -e "\n${BLUE}Setting Telegram webhook...${NC}"
echo -e "Webhook URL: ${YELLOW}$WEBHOOK_URL${NC}"

RESPONSE=$(curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook?url=$WEBHOOK_URL")

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo -e "${GREEN}✓${NC} Webhook configured successfully"
else
    echo -e "${RED}Error setting webhook:${NC}"
    echo "$RESPONSE"
    kill $LANGGRAPH_PID $CHATBOT_PID $NGROK_PID 2>/dev/null
    exit 1
fi

# Display status
echo -e "\n${GREEN}=== Development Environment Running ===${NC}"
echo -e "${BLUE}Services:${NC}"
echo -e "  • LangGraph API: ${YELLOW}http://localhost:2024${NC}"
echo -e "  • Chatbot Server: ${YELLOW}http://localhost:5000${NC}"
echo -e "  • Ngrok Tunnel: ${YELLOW}$NGROK_URL${NC}"
echo -e "  • Ngrok Dashboard: ${YELLOW}http://localhost:4040${NC}"
echo -e "\n${BLUE}Logs:${NC}"
echo -e "  • LangGraph: ${YELLOW}tail -f logs/langgraph.log${NC}"
echo -e "  • Chatbot: ${YELLOW}tail -f logs/chatbot.log${NC}"
echo -e "  • Ngrok: ${YELLOW}tail -f logs/ngrok.log${NC}"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}\n"

# Keep script running
wait
