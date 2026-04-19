@echo off
echo 🚀 BookBot Production Deployment Script
echo ========================================

REM Check if .env exists
if not exist .env (
    echo ⚠️ .env file not found!
    echo 📝 Creating from template...
    copy .env.example .env
    echo ✅ Please edit .env and add your API keys before continuing.
    echo    GROQ_API_KEY=your_key_here
    echo    SERP_API_KEY=your_key_here
    pause
    exit /b
)

echo ✅ Environment file found

echo.
echo Choose deployment method:
echo 1) Docker Compose (Recommended - includes Redis)
echo 2) Docker only (no Redis)
echo 3) Local Windows (Python + Gunicorn alternative)
set /p choice=Enter choice [1-3]:

IF "%choice%"=="1" (

    echo 🐳 Starting Docker Compose...

    docker-compose down
    docker-compose build
    docker-compose up -d

    echo ✅ Services started!
    timeout /t 10

    curl http://localhost:8000/api/health

    echo 🎉 Deployment complete!
    echo View logs: docker-compose logs -f app

)

IF "%choice%"=="2" (

    echo 🐳 Building Docker image...

    docker build -t bookbot-api .

    echo 🚀 Starting container...

    docker stop bookbot >nul 2>&1
    docker rm bookbot >nul 2>&1

    docker run -d ^
        -p 8000:8000 ^
        --env-file .env ^
        --name bookbot ^
        bookbot-api

    echo ✅ Container started!
    timeout /t 10

    curl http://localhost:8000/api/health

    echo 🎉 Deployment complete!
    echo View logs: docker logs -f bookbot

)

IF "%choice%"=="3" (

    echo 🐍 Setting up Python environment...

    REM Create virtual environment
    if not exist venv (
        python -m venv venv
    )

    call venv\Scripts\activate

    echo 📥 Installing dependencies...

    python -m pip install --upgrade pip
    pip install -r requirements.txt

    echo 🚀 Starting server...

    REM Windows does not use Gunicorn — use Waitress instead
    pip install waitress

    start cmd /k waitress-serve --port=8000 app:app

    timeout /t 5

    curl http://localhost:8000/api/health

    echo 🎉 Deployment complete!
    echo Server running at http://localhost:8000

)

pause