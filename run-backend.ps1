# Starts the FastAPI backend on http://localhost:8000
# Run from anywhere:  .\run-backend.ps1
# $PSScriptRoot is this file's folder (the project root), so the `backend`
# package is always importable regardless of your current directory.
Set-Location -Path $PSScriptRoot
Write-Host "Starting backend from $PSScriptRoot ..." -ForegroundColor Cyan
python -m uvicorn backend.main:app --reload
