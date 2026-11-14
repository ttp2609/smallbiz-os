@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 goto err
echo.
echo SmallBiz OS Demo: http://127.0.0.1:8000
echo Login: demo@smallbiz.local  Password: demo123
echo Press Ctrl+C to stop.
py server.py
goto done
:err
echo Could not install requirements. Install Python 3.10+ first.
:done
pause
