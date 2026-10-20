@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python。请先安装 Python 3.10+，安装时勾选 "Add python.exe to PATH"。
    pause
    exit /b 1
)

python -c "import fastapi, uvicorn, httpx, pypdf, docx, openpyxl, yaml" >nul 2>nul
if errorlevel 1 (
    echo [安装] 首次运行，正在安装依赖...
    python -m pip install -r requirements.txt
)

python run.py
pause
