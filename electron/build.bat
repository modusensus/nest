@echo off
chcp 65001 >nul
title 个人 AI 工作台 · 安装包构建

echo.
echo   ◈  个人 AI 工作台 · 安装包构建
echo   ───────────────────────────────
echo.

:: 1. 构建前端
echo   [1/3] 构建前端...
cd /d "%~dp0..\frontend"
if not exist "node_modules\" (
    echo   安装前端依赖...
    call npm install
)
call npx vite build
if %errorlevel% neq 0 (
    echo   [错误] 前端构建失败
    pause
    exit /b 1
)
echo   前端构建完成

:: 2. 构建后端 .exe
echo.
echo   [2/3] 构建后端 EXE...
cd /d "%~dp0.."
if not exist "backend\.venv\" (
    echo   创建虚拟环境...
    python -m venv backend\.venv
)
call backend\.venv\Scripts\activate.bat
pip install -r backend\requirements.txt pyinstaller
python electron\build_backend.py
if %errorlevel% neq 0 (
    echo   [错误] 后端打包失败
    pause
    exit /b 1
)

:: 3. 打包安装包
echo.
echo   [3/3] 打包安装程序...
cd /d "%~dp0"
if not exist "node_modules\" (
    echo   安装 Electron 依赖...
    call npm install
)
:: 使用 electron-builder 创建 unpacked 目录
set ELECTRON_CACHE=%~dp0cache
set ELECTRON_BUILDER_CACHE=%~dp0cache\builder
set CSC_IDENTITY_AUTO_DISCOVERY=false
call node node_modules/electron-builder/out/cli/cli.js --win --dir
if %errorlevel% neq 0 (
    echo   [错误] 安装包构建失败
    pause
    exit /b 1
)
:: 打包为便携版 zip
echo   正在创建便携版 zip...
powershell -Command "Compress-Archive -Path '%~dp0dist\win-unpacked\*' -DestinationPath '%~dp0dist\个人AI工作台-便携版.zip' -Force"

echo.
echo   ───────────────────────────────
echo   ✓ 构建完成！
echo.
echo   便携版: electron\dist\个人AI工作台-便携版.zip
echo   解压即用: 解压后双击 "个人 AI 工作台.exe" 启动
echo   ───────────────────────────────
echo.

explorer "%~dp0dist"
pause