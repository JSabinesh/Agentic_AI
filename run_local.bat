@echo off
title NextRole Copilot (Zero-Docker Local Runner)
echo ========================================================
echo   NextRole — AI Career & Interview Copilot (Local)
echo ========================================================
echo.
echo Checking dependencies and starting server...
echo.

cd /d "%~dp0"

uv run --with fastapi --with uvicorn --with google-genai --with tavily-python --with llama-cloud --with llama-parse --with pypdf --with python-docx --with rendercv --with reportlab --with python-multipart --with python-dotenv python -m uvicorn local_app.main:app --host 0.0.0.0 --port 8000 --reload

pause
