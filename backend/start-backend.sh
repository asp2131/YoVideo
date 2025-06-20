#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- 1. Start Redis using Docker ---
echo "Starting Redis container..."
if [ "$(docker ps -q -f name=videothingy-redis)" ]; then
    echo "Redis container is already running."
else
    if [ "$(docker ps -aq -f status=exited -f name=videothingy-redis)" ]; then
        echo "Restarting existing Redis container..."
        docker start videothingy-redis
    else
        echo "Creating and starting new Redis container..."
        docker run -d --name videothingy-redis -p 6379:6379 redis:7
    fi
fi

# --- 2. Start the Celery Worker ---
echo "Starting Celery worker..."
# Make sure to activate the virtual environment
source .venv/bin/activate

# Start the worker in the background
./.venv/bin/celery -A app.core.celery_app worker --loglevel=info > celery_logs.txt 2>&1 &
CELERY_PID=$!
echo "Celery worker started with PID: $CELERY_PID"

# --- 3. Start the FastAPI Application ---
echo "Starting FastAPI application..."

# Set default RELOAD to true if not set
RELOAD=${RELOAD:-true}

# Start Uvicorn server with conditional reload
echo "Starting Uvicorn with reload=$RELOAD..."
if [ "$RELOAD" = "true" ]; then
    ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > fastapi_logs.txt 2>&1 &
else
    ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-reload > fastapi_logs.txt 2>&1 &
fi
UVICORN_PID=$!
echo "FastAPI app started with PID: $UVICORN_PID (reload=$RELOAD)"

echo "\nBackend services are starting up."
echo "- Redis is running in Docker"
echo "- Celery logs are being written to celery_logs.txt"
echo "- FastAPI logs are being written to fastapi_logs.txt"

# --- Function to stop services ---
cleanup() {
    echo "\nStopping services..."
    kill $CELERY_PID
    kill $UVICORN_PID
    # Optional: stop the redis container
    # echo "Stopping Redis container..."
    # docker stop videothingy-redis
    echo "Services stopped."
}

# Trap SIGINT (Ctrl+C) and call cleanup
trap cleanup SIGINT

# Wait for background processes to finish
wait $CELERY_PID
wait $UVICORN_PID
