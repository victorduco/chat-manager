#!/bin/bash

lsof -ti:2024 | xargs -r kill -9 || true

if nc -z localhost 2024 &>/dev/null; then
    echo -e "\033[31mWarning: Port 2024 is already in use\033[0m"
fi

PYTHONUNBUFFERED=1 uv run langgraph dev --host=0.0.0.0 --port=2024 --no-browser