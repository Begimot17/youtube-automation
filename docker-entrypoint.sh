#!/bin/sh
set -e

echo "Starting Xvfb virtual display..."
Xvfb :99 -screen 0 1280x720x24 &
XVFB_PID=$!
export DISPLAY=:99

echo "Waiting for Xvfb to start..."
sleep 2

echo "Starting Window Manager and VNC server..."
fluxbox &
x11vnc -display :99 -nopw -forever &

echo "Running database migration..."
python src/scripts/migrate_to_db.py

echo "Starting main application..."
exec "$@"
