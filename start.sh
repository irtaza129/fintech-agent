#!/bin/bash
# Render startup script

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the FastAPI application
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
