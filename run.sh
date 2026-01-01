#!/bin/bash

echo "##########################################"
echo "#   YouTube Automation Startup Script    #"
echo "##########################################"

# Check if .env exists
if [ ! -f .env ]; then
    echo "[ERROR] .env file not found!"
    echo "Please copy .env.example to .env and fill in your credentials."
    read -p "Press any key to continue..."
    exit 1
fi

# Set PYTHONPATH to current directory
export PYTHONPATH=$(pwd)

# Activate virtual environment if it exists
if [ -f .venv/bin/activate ]; then
    echo "[INFO] Activating virtual environment..."
    source .venv/bin/activate
else
    echo "[WARNING] .venv not found. Running with system python..."
fi

# Check dependencies
echo "[INFO] Checking for missing dependencies..."
pip install -r requirements.txt > /dev/null
playwright install > /dev/null

# Run Database Migrations
echo "[INFO] Running database migrations..."
python src/scripts/migrate_to_db.py

# Start Server (API)
echo "[INFO] Starting API Server..."
python src/server.py &

# Wait a few seconds for server to initialize
sleep 5

# Start Automation Engine (Loop)
echo "[INFO] Starting Automation Engine..."
python main.py &

# Start Telegram Bot
echo "[INFO] Starting Telegram Bot..."
python src/telegram_bot.py &

echo "##########################################"
echo "# Processes started in the background.   #"
echo "# Use Telegram Bot to control.           #"
echo "##########################################"
