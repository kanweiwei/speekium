#!/bin/bash

echo "=================================================="
echo "Speekium Development Mode Launcher"
echo "=================================================="
echo ""

# Check if in correct directory
if [ ! -f "web/package.json" ]; then
    echo "❌ Error: Must run in project root directory"
    echo "   Current directory: $(pwd)"
    exit 1
fi

# Clean up old processes
echo "[1/5] Cleaning up old processes..."
pkill -f "vite.*dev"
pkill -f "web_app.py"

# Get port from environment or default to 5173
PORT=${SPEEKIUM_PORT:-5173}

# Port strategy: try multiple ports
PORTS=(5173 5174 5175 5176 5177 5178 5179 5180)
FOUND_PORT=""

echo "[2/5] Checking port availability..."
for TEST_PORT in "${PORTS[@]}"; do
    if lsof -ti:$TEST_PORT > /dev/null 2>&1; then
        echo "   Port $TEST_PORT: ⚫ In use (will be checked)"
    else
        echo "   Port $TEST_PORT: Available"
        FOUND_PORT=$TEST_PORT
        break
    fi
done

# If all ports in use, use default 5173
if [ -z "$FOUND_PORT" ]; then
    echo ""
    echo "⚠ Warning: All ports are in use"
    echo "   Using default port: 5173"
    echo ""
    PORT=5173
    FOUND_PORT=$PORT
fi

PORT=$FOUND_PORT

# Start frontend development server
echo "[3/5] Starting frontend dev server..."
echo "   Port: $PORT"
cd web
echo "   Starting Vite dev server..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Waiting for Vite to start listening on port $PORT..."
echo "Checking LISTEN status..."

# Poll for port LISTEN status (max 30 seconds)
for i in {1..10}; do
    lsof -i :$PORT -sTCP:LISTEN > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "✅ Vite is listening on port $PORT"
        echo "   PID: $FRONTEND_PID"
        break
    fi
    echo "   Checking... ($i/10)"
    sleep 1
done

# Start pywebview
echo ""
echo "=================================================="
echo "Starting pywebview..."
echo "=================================================="

# Save PID for cleanup
echo $FRONTEND_PID > .frontend_dev.pid

# Return to root directory
cd ..

# Start pywebview (in foreground, let user control it) with --dev flag
python web_app.py --dev --port $PORT
