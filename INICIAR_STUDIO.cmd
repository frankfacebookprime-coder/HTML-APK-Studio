@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 studio.py
) else (
    python studio.py
)
if errorlevel 1 (
    echo.
    echo Error al iniciar. Revisa Python 3.10+ y Tkinter.
    pause
)
