#!/usr/bin/env pwsh
# ─────────────────────────────────────────────────────────────────────────────
# Streamlit Dashboard Launcher
# Quick setup and run the Queueing Theory dashboard
# ─────────────────────────────────────────────────────────────────────────────

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "📊 Queueing Theory Dashboard Launcher" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# Get current directory
$scriptDir = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

Write-Host ""
Write-Host "📁 Working directory: $scriptDir" -ForegroundColor Yellow

# Step 1: Check if venv exists
Write-Host ""
Write-Host "Step 1: Checking Python environment..." -ForegroundColor Cyan

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "  ✅ Virtual environment found (.venv)" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Virtual environment not found. Creating..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ Created virtual environment" -ForegroundColor Green
    } else {
        Write-Host "  ❌ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

# Step 2: Activate venv
Write-Host ""
Write-Host "Step 2: Activating virtual environment..." -ForegroundColor Cyan
& ".\.venv\Scripts\Activate.ps1"
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "  ❌ Failed to activate environment" -ForegroundColor Red
    exit 1
}

# Step 3: Check requirements.txt
Write-Host ""
Write-Host "Step 3: Checking dependencies..." -ForegroundColor Cyan

if (Test-Path "requirements.txt") {
    Write-Host "  ✅ requirements.txt found" -ForegroundColor Green
    Write-Host "  📦 Installing/updating packages..." -ForegroundColor Yellow
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ All packages installed" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  Some packages may have failed to install" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ❌ requirements.txt not found" -ForegroundColor Red
    exit 1
}

# Step 4: Check if streamlit_app.py exists
Write-Host ""
Write-Host "Step 4: Verifying application files..." -ForegroundColor Cyan

if (Test-Path "legacy_streamlit\streamlit_app.py") {
    Write-Host "  ✅ streamlit_app.py found" -ForegroundColor Green
} else {
    Write-Host "  ❌ streamlit_app.py not found" -ForegroundColor Red
    exit 1
}

# Step 5: Launch dashboard
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🚀 Launching Streamlit Dashboard..." -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 Dashboard URL: http://localhost:8501" -ForegroundColor Cyan
Write-Host "📄 Quickstart: See STREAMLIT_QUICKSTART.md" -ForegroundColor Cyan
Write-Host "🏗️  Architecture: See ARCHITECTURE.md" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Launch streamlit
streamlit run legacy_streamlit\streamlit_app.py
