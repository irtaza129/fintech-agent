# Quick Start Script for Fintech AI Agent

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Fintech AI Agent - Quick Start" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "Checking Python installation..." -ForegroundColor Yellow
python --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: Python not found. Please install Python 3.8 or higher." -ForegroundColor Red
    exit 1
}
Write-Host "OK" -ForegroundColor Green
Write-Host ""

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "Virtual environment created!" -ForegroundColor Green
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
}
Write-Host ""

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
.\venv\Scripts\Activate.ps1
Write-Host "OK" -ForegroundColor Green
Write-Host ""

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error installing dependencies." -ForegroundColor Red
    exit 1
}
Write-Host "Dependencies installed!" -ForegroundColor Green
Write-Host ""

# Check .env file
Write-Host "Checking configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "IMPORTANT: Please edit .env file and add your API keys!" -ForegroundColor Red
    Write-Host ""
} else {
    Write-Host ".env file exists." -ForegroundColor Green
}
Write-Host ""

# Run tests
Write-Host "Running setup tests..." -ForegroundColor Yellow
python test_setup.py
Write-Host ""

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env file and add your API keys" -ForegroundColor White
Write-Host "2. Run the backend: python backend/main.py" -ForegroundColor White
Write-Host "3. Open frontend/index.html in your browser" -ForegroundColor White
Write-Host ""
Write-Host "Or run the backend now with: python backend/main.py" -ForegroundColor Cyan
Write-Host ""
