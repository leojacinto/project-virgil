#!/bin/bash

echo "🚀 ServiceNow Architecture Generator"
echo "===================================="
echo ""

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start backend in background
echo "📡 Starting Backend Server..."
echo "----------------------------"
./start_backend.sh &
BACKEND_PID=$!

# Wait for backend to be ready
echo ""
echo "⏳ Waiting for backend to be ready..."
RETRY_COUNT=0
MAX_RETRIES=60

until curl -s http://localhost:8000/api/health > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ Backend failed to start after ${MAX_RETRIES} seconds"
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
    echo "   Still installing dependencies... ($RETRY_COUNT/${MAX_RETRIES}s)"
    sleep 1
done

echo "✅ Backend is ready!"

echo ""
echo "🎨 Starting Frontend Server..."
echo "----------------------------"
./start_frontend.sh &
FRONTEND_PID=$!

echo ""
echo "✅ Both servers are starting!"
echo ""
echo "📍 Backend:  http://localhost:8000"
echo "📍 Frontend: http://localhost:3000 (opens automatically)"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for both processes
wait
