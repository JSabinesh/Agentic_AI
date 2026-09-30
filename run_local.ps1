# NextRole Local Runner (PowerShell)
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   NextRole — AI Career & Interview Copilot (Local)     " -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Zero-Docker Local Mode. Starting on http://localhost:8000 ...`n" -ForegroundColor Green

Set-Location $PSScriptRoot

uv run --with fastapi --with uvicorn --with google-genai --with tavily-python --with llama-cloud --with pypdf --with python-docx --with rendercv --with python-multipart --with python-dotenv python -m uvicorn local_app.main:app --host 0.0.0.0 --port 8000 --reload
