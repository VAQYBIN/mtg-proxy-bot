#!/bin/sh
set -e

echo "Starting API server..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
