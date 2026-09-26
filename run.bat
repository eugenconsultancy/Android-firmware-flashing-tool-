@echo off
REM Android Flasher - launch script (Windows)

setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

python app.py %*
endlocal
