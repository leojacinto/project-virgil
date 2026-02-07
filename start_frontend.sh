#!/bin/bash

echo "🎨 Starting ServiceNow Architecture Generator Frontend..."
echo ""

# Check for existing process on port 3000
EXISTING_PID=$(lsof -ti:3000 2>/dev/null)
if [ ! -z "$EXISTING_PID" ]; then
    echo "⚠️  Found existing frontend process on port 3000 (PID: $EXISTING_PID)"
    read -p "   Kill this process? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kill -9 $EXISTING_PID 2>/dev/null
        echo "   ✓ Process killed"
        sleep 1
    else
        echo "   ❌ Cannot start frontend - port 3000 is in use"
        exit 1
    fi
fi
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
