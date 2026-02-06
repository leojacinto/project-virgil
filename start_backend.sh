#!/bin/bash

echo "Starting ServiceNow Architecture Generator Backend..."

cd backend

if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
fi

source venv/bin/activate

if [ ! -f ".env" ]; then
    echo "Environment file not found. Copying from .env.example..."
    cp .env.example .env
    echo "Please edit backend/.env with your credentials before running again."
    exit 1
fi

echo "Installing/updating dependencies..."
pip install -q -r requirements.txt

if [ ! -f "jdbc/servicenow-jdbc.jar" ]; then
    echo "WARNING: ServiceNow JDBC JAR file not found at jdbc/servicenow-jdbc.jar"
    echo "Please place the JDBC driver in the jdbc/ directory."
fi

echo "Starting FastAPI server..."
python main.py
