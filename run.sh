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

# Determine Python executable
PYTHON_EXEC="python"
if [ -f .venv/bin/activate ]; then
    echo "[INFO] Activating virtual environment..."
    source .venv/bin/activate
    PYTHON_EXEC="$(pwd)/.venv/bin/python"
else
    echo "[WARNING] .venv not found. Running with system python..."
fi

# Check dependencies
echo "[INFO] Checking for missing dependencies..."
pip install -r requirements.txt > /dev/null
playwright install > /dev/null

# Run Database Migrations
echo "[INFO] Running database migrations..."
$PYTHON_EXEC src/scripts/migrate_to_db.py

# NOTE: The following commands open new terminal windows using 'gnome-terminal'.
# If you use a different terminal (e.g., konsole, xterm, or on macOS),
# you will need to modify these lines.
KEEP_TERMINAL_OPEN_CMD="echo; echo 'Process finished or crashed. Press Enter to close terminal.'; read"

# Start Server (API)
echo "[INFO] Starting API Server..."
SERVER_CMD="export PYTHONPATH=$(pwd); $PYTHON_EXEC src/server.py; $KEEP_TERMINAL_OPEN_CMD"
gnome-terminal --title="YouTube Auto: Server" -- bash -c "$SERVER_CMD" &

# Wait a few seconds for server to initialize
sleep 5

# Start Automation Engine (Loop)
echo "[INFO] Starting Automation Engine..."
ENGINE_CMD="export PYTHONPATH=$(pwd); $PYTHON_EXEC main.py; $KEEP_TERMINAL_OPEN_CMD"
gnome-terminal --title="YouTube Auto: Engine" -- bash -c "$ENGINE_CMD" &

# Start Telegram Bot
echo "[INFO] Starting Telegram Bot..."
BOT_CMD="export PYTHONPATH=$(pwd); $PYTHON_EXEC src/telegram_bot.py; $KEEP_TERMINAL_OPEN_CMD"
gnome-terminal --title="YouTube Auto: Bot" -- bash -c "$BOT_CMD" &

echo "##########################################"
echo "# Processes started in separate windows.   #"
echo "# Use Telegram Bot to control.           #"
echo "##########################################"
