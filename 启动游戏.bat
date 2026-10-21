@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -3 -m venv .venv
    if errorlevel 1 goto failure
    .venv\Scripts\python.exe -m pip install pygame-ce==2.5.8
    if errorlevel 1 goto failure
)
.venv\Scripts\python.exe game.py --gui %*
if errorlevel 1 goto failure
exit /b 0
:failure
echo 启动失败。请确认已安装 Python 3.11 或更高版本。
pause
exit /b 1
