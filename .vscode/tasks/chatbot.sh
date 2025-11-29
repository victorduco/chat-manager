#!/bin/bash

clear
echo "Initial Start..."

PORT=5000
PIDS=$(lsof -ti :$PORT)

for pid in $PIDS; do
    kill -9 "$pid"
done

uv run python main.py

uv run watchmedo shell-command \
  --patterns="*.py" \
  --recursive \
  --command='clear; echo "Restarting..."; uv run python main.py' \
  --wait \
  --debug-force-polling