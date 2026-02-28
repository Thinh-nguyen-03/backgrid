#!/bin/bash
echo "Starting Backgrid UI for RapidTrader Testing"
echo ""
echo "Starting backend server..."
uvicorn src.api:app --reload &
BACKEND_PID=$!
echo ""
echo "Waiting for backend to initialize..."
sleep 3
echo ""
echo "Starting frontend dev server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..
echo ""
echo "Backgrid UI started!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all servers"
wait
