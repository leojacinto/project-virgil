#!/bin/bash

echo "🎨 Starting ServiceNow Architecture Generator Frontend..."
echo ""

cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing Node dependencies (this may take a few minutes)..."
    npm install
    
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ npm install failed. Please check your internet connection and try again."
        exit 1
    fi
    
    echo "✓ Dependencies installed"
else
    echo "✓ Dependencies already installed"
fi

# Start the development server
echo ""
echo "🌐 Starting React development server on http://localhost:3000"
echo "   The browser will open automatically"
echo "   Press Ctrl+C to stop"
echo ""
npm start
