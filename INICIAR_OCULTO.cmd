@echo off
cd /d "%~dp0"
where pyw >nul 2>&1
if not errorlevel 1 (
  pyw -3 "%~dp0studio.py"
) else (
  pythonw "%~dp0studio.py"
)
