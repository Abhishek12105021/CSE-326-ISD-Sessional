#!/bin/bash

# YouTube Clone Backend Setup and Run Script

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Starting server..."
python -m uvicorn app.main:app --reload --port 8000
