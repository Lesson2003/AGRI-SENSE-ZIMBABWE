:: File: START_PLATFORM.bat
:: Double-click this file to start everything

@echo off
echo Starting Zimbabwe Maize Yield Platform...
echo.

:: Activate virtual environment
call C:\Users\lesson\OneDrive\Desktop\YIELD\maize_env\Scripts\activate.bat

:: Start all services with PM2
cd C:\Users\lesson\OneDrive\Desktop\YIELD
pm2 start ecosystem.config.json

echo.
echo All services started!
echo.
echo API        : http://127.0.0.1:8000
echo Streamlit  : http://localhost:8501
echo API Docs   : http://127.0.0.1:8000/docs
echo ngrok UI   : http://127.0.0.1:4040
echo.
echo To stop all:  pm2 stop all
echo To restart:   pm2 restart all
echo To see logs:  pm2 logs
echo.
pause