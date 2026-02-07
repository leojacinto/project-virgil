#!/bin/bash

echo "🚀 ServiceNow Architecture Generator"
echo "===================================="
echo ""

# Check if we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

# Check for existing processes on ports
check_and_kill_port() {
    local port=$1
    local service=$2
    local pids=$(lsof -ti:$port 2>/dev/null)
    
    if [ ! -z "$pids" ]; then
        echo "⚠️  Found existing process(es) running on port $port ($service)"
        echo "   PIDs: $pids"
        read -p "   Kill these processes? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "$pids" | xargs kill -9 2>/dev/null
            echo "   ✓ Processes killed"
            sleep 1
        else
            echo "   ❌ Cannot start $service - port $port is in use"
            exit 1
        fi
    fi
}

# Check ports before starting
echo "🔍 Checking for existing processes..."
check_and_kill_port 8000 "Backend"
check_and_kill_port 3000 "Frontend"
echo ""

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
echo "   (First-time setup downloads ML models, may take 2-3 minutes)"
RETRY_COUNT=0
MAX_RETRIES=180

until curl -s http://localhost:8000/api/health > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo ""
        echo "⚠️  Backend health check timed out after ${MAX_RETRIES} seconds"
        echo "   Backend may still be starting - continuing anyway..."
        echo "   Check the backend terminal for progress"
        break
    fi
    
    # Show progress every 5 seconds to avoid spam
    if [ $((RETRY_COUNT % 5)) -eq 0 ]; then
        echo "   Still waiting... (${RETRY_COUNT}/${MAX_RETRIES}s)"
    fi
    sleep 1
done

if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Backend is ready!"
else
    echo "   Proceeding to start frontend..."
fi

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
