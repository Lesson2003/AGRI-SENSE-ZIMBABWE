:: File: STOP_PLATFORM.bat
@echo off
echo Stopping all services...
pm2 stop all
pm2 delete all
echo Done.
pause