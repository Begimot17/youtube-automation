@echo off
setlocal enabledelayedexpansion

echo ##########################################
echo #   YouTube Automation Startup Script    #
echo ##########################################

:: Check if .env exists
if not exist .env (
    echo [ERROR] .env file not found! 
    echo Please copy .env.example to .env and fill in your credentials.
    pause
    exit /b 1
)

:: Set PYTHONPATH to current directory
set PYTHONPATH=%CD%

:: Activate virtual environment if it exists
if exist .venv\Scripts\activate.bat (
    echo [INFO] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo [WARNING] .venv not found. Running with system python...
)

:: Check dependencies
echo [INFO] Checking for missing dependencies...
pip install -r requirements.txt > nul
playwright install > nul

:: Run Database Migrations
echo [INFO] Running database migrations...
python src/scripts/migrate_to_db.py

:: Start Server (API)
echo [INFO] Starting API Server...
start "YouTube Auto: Server" cmd /k "python src/server.py"

:: Wait a few seconds for server to initialize
timeout /t 5 /nobreak > nul

:: Start Automation Engine (Loop)
echo [INFO] Starting Automation Engine...
start "YouTube Auto: Engine" cmd /k "python main.py"

:: Start Telegram Bot
echo [INFO] Starting Telegram Bot...
start "YouTube Auto: Bot" cmd /k "python src/telegram_bot.py"

echo ##########################################
echo # Processes started in separate windows. #
echo # Use Telegram Bot to control.           #
echo ##########################################
pause
