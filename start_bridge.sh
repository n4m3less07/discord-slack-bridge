#!/bin/bash

echo "starting slds"

if ! redis-cli ping > /dev/null 2>&1; then
    echo "redis is not running."
    exit 1
fi

echo "redis is running"

if [ ! -f .env ]; then
    echo ".env file not found"
    exit 1
fi

echo "environment file found"

if [ -d "venv" ]; then
    source venv/bin/activate
    echo "venv activated"
fi

echo "starting Discord bot"
python src/discord/bot.py &
DISCORD_PID=$!

sleep 2

echo "startin slack listner"
python src/slack/listener.py &
SLACK_PID=$!

echo "bridge is runinng"
echo "discord bot PID: $DISCORD_PID"
echo "slack listener PID: $SLACK_PID"

cleanup() {
    echo ""
    echo "stopping services..."
    kill $DISCORD_PID 2>/dev/null
    kill $SLACK_PID 2>/dev/null
    echo "✅ Services stopped"
    exit 0
}

trap cleanup SIGINT

wait