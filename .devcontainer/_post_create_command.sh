#!/bin/bash

set -e  # Остановить скрипт при ошибке

echo "Starting development environment setup..."
echo "Installing uv..."
pip install uv || { echo "[Error] Failed to install uv."; exit 1; }

echo "Updating system packages..."
sudo apt-get update -y
sudo apt-get install -y tmux

echo "Syncing Python dependencies with uv..."
uv add --editable /workspaces/agent-taskmanager/libs/conversation_states
uv sync



echo "Setup complete. Environment is ready."
