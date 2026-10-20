@echo off
chcp 65001 >nul
title 海工智舱 · 后端服务
cd /d "%~dp0"
echo ============================================
echo   海工智舱 Marine AI - 启动/重启后端服务
echo   项目根: %~dp0
echo   访问:   http://127.0.0.1:8000
echo ============================================
echo.

REM 释放 8000 端口（若被占用）
set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  set FOUND=1
  echo [释放端口 8000] 结束进程 PID=%%a ...
  taskkill /f /pid %%a >nul 2>&1
)
if "%FOUND%"=="0" echo [端口 8000 空闲]
echo.

echo [启动] python run.py ...
echo 按 Ctrl+C 停止服务。关闭本窗口即停止。
echo.
python run.py
pause
