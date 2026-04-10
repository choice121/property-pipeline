#!/bin/bash
# Start the backend in background
cd /home/runner/workspace/backend && python3 main.py &
BACKEND_PID=$!

# Start the frontend from its own directory
cd /home/runner/workspace/frontend && npm run dev

# When frontend exits, kill backend
kill $BACKEND_PID 2>/dev/null
