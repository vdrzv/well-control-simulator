@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment was not found. Creating .venv...
    py -3 -m venv .venv
    if errorlevel 1 (
        python -m venv .venv
        if errorlevel 1 (
            echo Failed to create virtual environment.
            echo Try installing Python or create .venv manually.
            pause
            exit /b 1
        )
    )
)

if not exist "node_modules" (
    echo node_modules was not found. Installing npm dependencies...
    npm install
    if errorlevel 1 (
        echo npm install failed.
        pause
        exit /b 1
    )
)

echo Starting FastAPI and npm dev servers...

start "FastAPI backend" cmd /k "cd /d ""%~dp0"" && call .venv\Scripts\activate.bat && set FRONTEND_DEV_MODE=true && set VITE_DEV_SERVER_URL=http://localhost:5173 && python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001"
start "npm frontend" cmd /k "cd /d ""%~dp0"" && npm run dev"

echo.
echo FastAPI: http://127.0.0.1:8001
echo Vite:    http://localhost:5173
echo.
echo Servers were opened in separate windows. Close those windows or press Ctrl+C inside them to stop.
pause
