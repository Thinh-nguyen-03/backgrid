@echo off
echo Starting Backgrid UI for RapidTrader Testing
echo.
echo Starting backend server...
start cmd /k "uvicorn src.api:app --reload"
echo.
echo Waiting for backend to initialize...
timeout /t 3 /nobreak >nul
echo.
echo Starting frontend dev server...
cd frontend
start cmd /k "npm run dev"
cd ..
echo.
echo Backgrid UI starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Press any key to exit (servers will continue running)
pause >nul
