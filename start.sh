#!/bin/bash
# Start the backend in background
cd /home/runner/workspace/backend && python3 main.py &
BACKEND_PID=$!

# Start the frontend (vite from workspace root)
cd /home/runner/workspace && node_modules/.bin/vite --config vite.config.js

# When frontend exits, kill backend
kill $BACKEND_PID 2>/dev/null
