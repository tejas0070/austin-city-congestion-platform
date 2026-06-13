# Starts the React + kepler.gl frontend on http://localhost:3000
# Run from anywhere:  .\run-frontend.ps1
# Start the backend (run-backend.ps1) FIRST, or kepler will show its empty
# "add data" state because no data reaches the map.
Set-Location -Path (Join-Path $PSScriptRoot 'frontend')
Write-Host "Starting frontend from $(Get-Location) ..." -ForegroundColor Cyan
npm start
