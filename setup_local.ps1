# PowerShell script để setup local environment
# Chạy: .\setup_local.ps1

Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host "=" * 58 -ForegroundColor Cyan
Write-Host "🚀 Setup RAG Student Handbook - Local Development" -ForegroundColor Green
Write-Host "=" * 59 -ForegroundColor Cyan

# Check Python version
Write-Host "`n1️⃣  Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
Write-Host "   $pythonVersion"

if ($pythonVersion -match "3\.1[2-9]") {
    Write-Host "   ✓ Python 3.12+ detected" -ForegroundColor Green
} else {
    Write-Host "   ⚠ Python 3.12+ recommended" -ForegroundColor Yellow
}

# Check/Create virtual environment
Write-Host "`n2️⃣  Checking virtual environment..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "   ✓ .venv exists" -ForegroundColor Green
} else {
    Write-Host "   Creating .venv..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "   ✓ .venv created" -ForegroundColor Green
}

# Activate venv
Write-Host "`n3️⃣  Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1
Write-Host "   ✓ Virtual environment activated" -ForegroundColor Green

# Upgrade pip
Write-Host "`n4️⃣  Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
Write-Host "   ✓ pip upgraded" -ForegroundColor Green

# Install dependencies
Write-Host "`n5️⃣  Installing dependencies (this may take a few minutes)..." -ForegroundColor Yellow
Write-Host "   Installing from requirements.txt..."
pip install -r requirements.txt --quiet
Write-Host "   ✓ Dependencies installed" -ForegroundColor Green

# Set PYTHONPATH
Write-Host "`n6️⃣  Setting PYTHONPATH..." -ForegroundColor Yellow
$env:PYTHONPATH = $PWD.Path
Write-Host "   PYTHONPATH = $env:PYTHONPATH" -ForegroundColor Cyan
Write-Host "   ✓ PYTHONPATH set" -ForegroundColor Green

# Test imports
Write-Host "`n7️⃣  Testing imports..." -ForegroundColor Yellow
python test_local.py

# Check .env file
Write-Host "`n8️⃣  Checking .env configuration..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "   ✓ .env file exists" -ForegroundColor Green
    Write-Host "`n   Current configuration:" -ForegroundColor Cyan
    Get-Content .env | Select-String "^[^#]" | Select-Object -First 5 | ForEach-Object {
        $line = $_ -replace "=.*", "=***"
        Write-Host "   - $line" -ForegroundColor Gray
    }
} else {
    Write-Host "   ⚠ .env file not found" -ForegroundColor Yellow
    Write-Host "   Copy .env.example to .env and configure:" -ForegroundColor Yellow
    Write-Host "   cp .env.example .env" -ForegroundColor Cyan
}

Write-Host "`n" + "=" * 59 -ForegroundColor Cyan
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host "=" * 59 -ForegroundColor Cyan

Write-Host "`n📝 Quick start:" -ForegroundColor Yellow
Write-Host "   1. Ensure .env is configured with API keys" -ForegroundColor White
Write-Host "   2. Start services:" -ForegroundColor White
Write-Host "      docker-compose up -d postgres redis qdrant neo4j" -ForegroundColor Cyan
Write-Host "   3. Run migrations:" -ForegroundColor White
Write-Host "      alembic upgrade head" -ForegroundColor Cyan
Write-Host "   4. Start app:" -ForegroundColor White
Write-Host "      uvicorn main:app --reload" -ForegroundColor Cyan
Write-Host "   5. Open browser:" -ForegroundColor White
Write-Host "      http://localhost:8000/docs" -ForegroundColor Cyan

Write-Host "`n💡 Tip: Keep this terminal open (venv is activated)" -ForegroundColor Yellow
