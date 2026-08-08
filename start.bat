@echo off
chcp 65001 >nul
title 个人 AI 工作台

echo.
echo   ◈  个人 AI 工作台 · 一键启动
echo   ───────────────────────────────
echo.

:: 检查 Docker
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo   [错误] 未检测到 Docker Desktop，请先安装：
    echo   https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

:: 首次运行：自动创建 .env
if not exist "backend\.env" (
    echo   [初始化] 首次运行，正在创建配置文件...
    copy "backend\.env.example" "backend\.env" >nul
    echo   [完成] 已创建 backend\.env
    echo.
    echo   ⚠ 请编辑 backend\.env，填入你的 API Key 和密码后再重新运行本脚本。
    start notepad "backend\.env"
    pause
    exit /b 0
)

echo   [启动] 正在构建并启动容器...
echo.

docker compose up --build -d

if %errorlevel% neq 0 (
    echo.
    echo   [错误] 启动失败，请检查 Docker 是否正常运行。
    pause
    exit /b 1
)

echo.
echo   ───────────────────────────────
echo   ✓ 启动成功！
echo.
echo   打开浏览器访问: http://localhost:8000
echo.
echo   手机访问：同一局域网下，用电脑 IP 替换 localhost 即可
echo   例如: http://192.168.1.100:8000
echo.
echo   添加到手机主屏幕：浏览器菜单 → 添加到主屏幕
echo   ───────────────────────────────
echo.

:: 自动打开浏览器
start http://localhost:8000

pause