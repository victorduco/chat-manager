#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Set Telegram webhook to ngrok URL

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <ngrok-url>"
    echo "Example: $0 https://abc123.ngrok.io"
    exit 1
fi

NGROK_URL="$1"

# Load TELEGRAM_TOKEN from .env
if [ ! -f ".env" ]; then
    echo "Error: .env file not found"
    exit 1
fi

source .env

if [ -z "$TELEGRAM_TOKEN" ]; then
    echo "Error: TELEGRAM_TOKEN not set in .env"
    exit 1
fi

WEBHOOK_URL="$NGROK_URL/$TELEGRAM_TOKEN"

echo "Setting webhook to: $WEBHOOK_URL"

RESPONSE=$(curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/setWebhook?url=$WEBHOOK_URL")

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo "✓ Webhook configured successfully"
    echo "Response: $RESPONSE"
else
    echo "✗ Error setting webhook"
    echo "Response: $RESPONSE"
    exit 1
fi
