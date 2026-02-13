# Agent Task Manager

Agent Task Manager is a Telegram-first workspace for team communication and lightweight automation.
It includes a chatbot, a LangGraph backend, a miniapp, and an admin panel.

## Components
- `chatbot`: Telegram bot server and event handlers.
- `langgraph-app`: Graph workflows, tools, and automation logic.
- `miniapp`: Telegram WebApp client.
- `admin-panel`: thread, users, messages, records, and highlights management.
- `secure_api`: validation and API proxy utilities.

## What It Does
- Processes Telegram chat updates.
- Stores and manages thread state in LangGraph.
- Supports highlights, intro handling, and moderation flows.
- Runs daily digests with text, image, and optional voice delivery.

## Run
Use project scripts in `scripts/` for local startup and deployment.
Production deploy is done with `scripts/deploy-heroku/deploy.sh`.
