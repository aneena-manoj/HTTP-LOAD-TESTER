#!/bin/sh

# Wait for the WebSocket server to be up
until nc -z localhost 8765; do
  echo "Waiting for WebSocket server..."
  sleep 2
done

# Wait for the FastAPI server to be up
until nc -z localhost 8000; do
  echo "Waiting for FastAPI server..."
  sleep 2
done

# Run the CLI command
python src/cli.py "$@"