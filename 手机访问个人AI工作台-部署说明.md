# 手机访问个人 AI 工作台：云服务器部署说明

手机是控制面板；云服务器运行工作台后端和 Claude Code CLI。

```text
手机浏览器 / 添加到主屏幕
  → HTTPS 域名
  → 云服务器上的工作台后端
  → 服务器本机的 Claude Code CLI
  → 服务器项目目录
```

## 1. 准备服务器

安装 Python 3.11+、Node.js 20+、Caddy 和 Claude Code，并执行：

```bash
claude auth login
```

将项目放在 `/opt/personal-ai-workbench`。

## 2. 配置工作台

```bash
cd /opt/personal-ai-workbench
cp backend/.env.example backend/.env
nano backend/.env
```

至少填写：

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=你的DeepSeek密钥
LLM_MODEL=deepseek-chat
WORKBENCH_PASSWORD=换成一个强密码
WORKBENCH_SESSION_SECRET=换成至少32位随机字符串
COOKIE_SECURE=true
CLAUDE_WORKSPACES=我的项目=/srv/my-project
```

生成随机会话密钥：`openssl rand -hex 32`。

## 3. 安装并构建

```bash
cd /opt/personal-ai-workbench/backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cd ../frontend
npm install
npm run build
```

## 4. 常驻运行

编辑项目的 `deploy/personal-ai-workbench.service`，将 `YOUR_LINUX_USER` 改为服务器用户名：

```bash
sudo cp /opt/personal-ai-workbench/deploy/personal-ai-workbench.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now personal-ai-workbench
```

## 5. 域名与 HTTPS

将域名 A 记录指向服务器 IP。编辑 `deploy/Caddyfile`，填入真实域名：

```bash
sudo cp /opt/personal-ai-workbench/deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

手机访问 `https://你的域名` 并登录，然后在浏览器菜单选择“添加到主屏幕”。

## 安全清单

- 不直接开放 8000 端口，只通过 Caddy 的 HTTPS 访问。
- 立刻替换访问密码和会话密钥。
- 白名单只填写允许 Claude Code 操作的目录。
- 仅自己使用时，建议通过 Tailscale 私有网络访问。

## 排查

```bash
sudo journalctl -u personal-ai-workbench -f
claude -p "只回复：连接正常" --output-format text
sudo systemctl restart personal-ai-workbench
```
