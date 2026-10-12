@echo off
setlocal
cd /d "%~dp0"
python -m unittest discover -s tests -v
if errorlevel 1 goto fail
python cli.py doctor
python cli.py validate examples\demo
python cli.py prepare examples\demo --name "Prueba Studio" --package com.misapps.pruebatest --dest "%TEMP%\htmlapk_preparado_%RANDOM%"
echo.
echo Se preparo un proyecto Gradle, NO un APK. Para compilar: ejecuta la interfaz o cli.py build.
pause
exit /b 0
:fail
echo Fallaron las pruebas; no compiles hasta revisar el error.
pause
exit /b 1
