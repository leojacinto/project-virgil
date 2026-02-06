#!/bin/bash

echo "Starting ServiceNow Architecture Generator Frontend..."

cd frontend

if [ ! -d "node_modules" ]; then
    echo "Node modules not found. Installing..."
    npm install
fi

echo "Starting React development server..."
npm start
