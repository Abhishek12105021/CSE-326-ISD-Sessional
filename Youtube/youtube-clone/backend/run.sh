#!/bin/bash

# YouTube Clone Backend Setup and Run Script

echo "Installing dependencies..."
pip install -r requirements.txt

PORT="${BACKEND_PORT:-8123}"

echo "Starting server on http://127.0.0.1:${PORT} ..."
python -m uvicorn app.main:app --reload --port "${PORT}"
