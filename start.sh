#!/bin/bash
# Render startup script

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the FastAPI application on Render's port (defaults to 10000)
PORT=${PORT:-10000}
echo "Starting server on port $PORT..."
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
