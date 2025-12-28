#!/bin/sh
set -e

echo "Running database migration..."
python src/scripts/migrate_to_db.py

echo "Starting main application..."
exec "$@"
