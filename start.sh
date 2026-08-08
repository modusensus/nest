#!/usr/bin/env bash
set -e

echo
echo "  ◈  个人 AI 工作台 · 一键启动"
echo "  ───────────────────────────────"
echo

# 检查 Docker
if ! command -v docker &>/dev/null; then
    echo "  [错误] 未检测到 Docker，请先安装："
    echo "  macOS: https://docs.docker.com/desktop/install/mac-install/"
    echo "  Linux: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

# 首次运行：自动创建 .env
if [ ! -f "backend/.env" ]; then
    echo "  [初始化] 首次运行，正在创建配置文件..."
    cp backend/.env.example backend/.env
    echo "  [完成] 已创建 backend/.env"
    echo
    echo "  ⚠ 请编辑 backend/.env，填入你的 API Key 和密码后再重新运行本脚本。"
    exit 0
fi

echo "  [启动] 正在构建并启动容器..."
echo

docker compose up --build -d

echo
echo "  ───────────────────────────────"
echo "  ✓ 启动成功！"
echo
echo "  打开浏览器访问: http://localhost:8000"
echo
echo "  手机访问：同一局域网下，用电脑 IP 替换 localhost 即可"
echo "  例如: http://192.168.1.100:8000"
echo
echo "  添加到手机主屏幕：浏览器菜单 → 添加到主屏幕"
echo "  ───────────────────────────────"
echo

# 自动打开浏览器
if command -v open &>/dev/null; then
    open http://localhost:8000
elif command -v xdg-open &>/dev/null; then
    xdg-open http://localhost:8000
fi