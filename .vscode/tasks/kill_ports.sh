# .vscode/tasks/kill_port.sh
#!/bin/bash

PORT=5000

echo -e "\033[36m[$(date)] Scanning port $PORT...\033[0m"

PIDS=$(lsof -ti :$PORT)

if [ -z "$PIDS" ]; then
    echo -e "\033[32m[$(date)] Port $PORT is free.\033[0m"
    exit 0
fi

echo -e "\033[33m[$(date)] Found process(es) on port $PORT: $PIDS\033[0m"

for pid in $PIDS; do
    PROC_INFO=$(ps -p $pid -o pid,cmd --no-headers)
    echo -e "\033[31mKilling:\033[0m $PROC_INFO"
    kill -9 "$pid"
done

echo -e "\033[32m[$(date)] All processes on port $PORT killed.\033[0m"