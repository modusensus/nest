#!/bin/bash
# ────────────────────────────────────────────
#  个人 AI 工作台 · 云服务器一键部署脚本
#  测试环境：Ubuntu 22.04 / Debian 12
# ────────────────────────────────────────────
set -e

APP_DIR="/opt/ai-workbench"
DOMAIN=""
PASSWORD=""
SECRET=""

# ── 解析参数 ──
while [[ $# -gt 0 ]]; do
  case $1 in
    --domain) DOMAIN="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --secret) SECRET="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

if [ -z "$DOMAIN" ] || [ -z "$PASSWORD" ]; then
  echo "用法: bash setup.sh --domain ai.example.com --password 强密码 [--secret 随机密钥]"
  echo ""
  echo "  --domain    你的域名，如 ai.example.com（Caddy 会自动申请 HTTPS 证书）"
  echo "  --password  访问工作台的密码"
  echo "  --secret    会话加密密钥（可选，不填则自动生成 64 位随机字符串）"
  exit 1
fi

if [ -z "$SECRET" ]; then
  SECRET=$(openssl rand -hex 32)
fi

echo "┌──────────────────────────────────────────┐"
echo "│  个人 AI 工作台 · 云服务器部署           │"
echo "│  域名: $DOMAIN"
echo "│  目录: $APP_DIR"
echo "└──────────────────────────────────────────┘"

# ── 1. 安装 Docker ──
if ! command -v docker &> /dev/null; then
  echo "» 安装 Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

# ── 2. 安装 Caddy ──
if ! command -v caddy &> /dev/null; then
  echo "» 安装 Caddy..."
  apt update
  apt install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
  apt update
  apt install -y caddy
fi

# ── 3. 克隆项目 ──
if [ ! -d "$APP_DIR" ]; then
  echo "» 克隆项目..."
  git clone https://github.com/modusensus/nest.git "$APP_DIR"
fi
cd "$APP_DIR"

# ── 4. 创建 .env ──
echo "» 创建配置文件..."
cat > backend/.env << EOF
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=你的_DeepSeek_API_Key
LLM_MODEL=deepseek-chat
WORKBENCH_PASSWORD=$PASSWORD
WORKBENCH_SESSION_SECRET=$SECRET
COOKIE_SECURE=true
EOF

echo "⚠ 请编辑 $APP_DIR/backend/.env 填入你的 LLM API Key："
echo "   nano $APP_DIR/backend/.env"

# ── 5. 配置 Caddy ──
echo "» 配置 Caddy 反向代理..."
cat > /etc/caddy/Caddyfile << EOF
$DOMAIN {
    reverse_proxy 127.0.0.1:8000
}
EOF
systemctl reload caddy

# ── 6. 启动 Docker ──
echo "» 启动工作台..."
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "┌──────────────────────────────────────────┐"
echo "│  ✓ 部署完成！                           │"
echo "│                                          │"
echo "│  访问地址: https://$DOMAIN               │"
echo "│  登录密码: $PASSWORD                     │"
echo "│                                          │"
echo "│  手机 APP: 打开 https://$DOMAIN         │"
echo "│            → 添加到主屏幕               │"
echo "│                                          │"
echo "│  或使用 APK: 服务器地址填               │"
echo "│            https://$DOMAIN               │"
echo "│            密码: $PASSWORD               │"
echo "│                                          │"
echo "│  管理命令:                               │"
echo "│  docker compose -f docker-compose.prod.yml logs -f  │"
echo "│  docker compose -f docker-compose.prod.yml restart  │"
echo "│  docker compose -f docker-compose.prod.yml down     │"
echo "└──────────────────────────────────────────┘"