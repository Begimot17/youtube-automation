#!/bin/bash

echo "##########################################"
echo "#   YouTube Automation Startup Script    #"
echo "##########################################"

# Exit on error
set -e

# Check if .env exists
if [ ! -f .env ]; then
    echo "[ERROR] .env file not found!"
    echo "Please copy .env.example to .env and fill in your credentials."
    read -p "Press any key to continue..."
    exit 1
fi

# Set PYTHONPATH
export PYTHONPATH="$(pwd)"

# Detect OS
OS="$(uname -s)"
echo "[INFO] Detected OS: $OS"

# Determine Python executable
PYTHON_EXEC="python3"
if [ -f ".venv/bin/activate" ]; then
    echo "[INFO] Activating virtual environment..."
    source .venv/bin/activate
    PYTHON_EXEC="$(pwd)/.venv/bin/python"
else
    echo "[WARNING] .venv not found. Using system python..."
fi

# Install dependencies
echo "[INFO] Checking dependencies..."
pip install -r requirements.txt > /dev/null
playwright install > /dev/null

# Run migrations
echo "[INFO] Running database migrations..."
$PYTHON_EXEC src/scripts/migrate_to_db.py

##########################################
# Terminal launcher (Linux / macOS)
##########################################

run_in_new_terminal () {
    TITLE="$1"
    CMD="$2"

    if [[ "$OS" == "Darwin" ]]; then
        # macOS (Terminal.app)
        osascript -e "tell application \"Terminal\" to do script \"cd $(pwd); export PYTHONPATH=$(pwd); $CMD\""
    else
        # Linux (gnome-terminal)
        gnome-terminal --title="$TITLE" -- bash -c "cd $(pwd); export PYTHONPATH=$(pwd); $CMD; exec bash"
    fi
}

##########################################
# Start services
##########################################

echo "[INFO] Starting API Server..."
run_in_new_terminal "YouTube Auto: Server" "$PYTHON_EXEC src/server.py"

sleep 5

echo "[INFO] Starting Automation Engine..."
run_in_new_terminal "YouTube Auto: Engine" "$PYTHON_EXEC main.py"

echo "[INFO] Starting Telegram Bot..."
run_in_new_terminal "YouTube Auto: Bot" "$PYTHON_EXEC src/telegram_bot.py"

echo "##########################################"
echo "# Processes started in separate windows  #"
echo "# Control via Telegram Bot               #"
echo "##########################################"
