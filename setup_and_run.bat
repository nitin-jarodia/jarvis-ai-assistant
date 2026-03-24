@echo off
title Jarvis AI Assistant
color 0B

echo ========================================================
echo               JARVIS AI ASSISTANT
echo ========================================================
echo.

echo [1/3] Checking Python dependencies...
python -m pip install -r requirements.txt >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Failed to install dependencies!
    echo     Please make sure Python is installed and added to PATH.
    pause
    exit /b
)
echo [OK] Dependencies verified.
echo.

echo [2/3] Checking Ollama AI Engine...
ollama --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Ollama is not installed or not running!
    echo     Please install Ollama from https://ollama.com
    pause
    exit /b
)
echo [OK] Ollama is installed.
echo [~] Ensuring 'tinyllama' model is downloaded (this may take a moment if it's your first time)...
ollama pull tinyllama >nul 2>&1
echo [OK] AI Model ready.
echo.

echo [3/3] Starting Jarvis API Server...
echo.
echo ========================================================
echo  Server is launching in a new window...
echo  Please KEEP THE NEW WINDOW OPEN while using Jarvis.
echo ========================================================
echo.

:: Start the Uvicorn backend in a new command prompt window
start "Jarvis API Backend" cmd /c "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

:: Give the server 3 seconds to boot up before opening the browser
timeout /t 3 /nobreak >nul

:: Open the frontend UI in the default web browser
start http://127.0.0.1:8000

exit
