# 个人 AI 工作台

一个本地优先的中文 Agent 工作台：以对话驱动 AI 助手管理你的项目、任务、打卡与写作，杂志编辑风界面，支持明暗双模式，可部署到云服务器用手机访问。

## 功能总览

- **主页**：报刊名板式总览。问候语、目标日倒计时（如考研倒计时，自动按天更新，表单常驻随时可添加）、当月日历卡片（左右并排）、坚持热力图（GitHub 风格，带年月标签）、今日打卡快捷按钮、项目进度、进行中任务、最近文章。杂志风瀑布流卡片布局。
- **对话**：多会话流式聊天。默认通过 Claude Code 文本协议（`claude -p`）驱动，未安装 CLI 时自动回退 OpenAI 兼容接口。助手可以直接帮你建项目、建任务、更新任务状态、打卡、查询工作台概况、管理记忆库，工具调用过程以卡片形式嵌在对话流里。
- **项目**：项目卡片 + 任务完成进度条，支持归档。
- **任务看板**：待办 / 进行中 / 已完成三列流转，可归属项目、设截止日期。
- **打卡**：习惯管理、连续天数、累计天数、近一年聚合热力图（53 周 + 月份标签）。
- **写作**：Markdown 双栏编辑器（实时预览、配图上传），文章状态管理，个人博客 / Substack / Medium 发布状态跟踪，一键导出 `.md`。
- **个人信息**：侧栏头像、名称、Agent ID，点击可修改，资料保存在服务端，多端一致。
- **主题**：杂志编辑风设计（华文中宋衬线标题、发丝线、编辑红点缀），浅色 / 深色模式一键切换并记忆。
- **侧栏**：可折叠为小图标栏；底部日刊/夜刊拨杆一键切换主题。
- **Claude Code 执行面板**（进阶）：在白名单目录里调用本机 Claude Code。
- **记忆库**：Agent 只能通过对话「提议」修改记忆库文件（创建/更新/删除需你在记忆库页面审批），跨聊天记忆（`memory_facts`）自动注入所有后续对话，类似 ChatGPT 的跨会话记忆。

## 技术选择

- 前端：React + Vite（PWA，可添加到手机主屏幕）
- 后端：FastAPI
- 数据：SQLite（本地文件 `backend/data/workbench.db`，头像与配图在 `backend/data/` 下）
- 模型：任何支持 function calling 的 OpenAI 兼容接口（已适配 DeepSeek）

## 最快启动（推荐）

确保已安装 Docker Desktop。先复制配置模板并填写模型密钥：

```powershell
Copy-Item backend/.env.example backend/.env
```

编辑 `backend/.env`：

```env
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=你的_DeepSeek_API_Key
LLM_MODEL=deepseek-chat
WORKBENCH_PASSWORD=换成一个强密码
WORKBENCH_SESSION_SECRET=换成至少32位随机字符串
```

然后在项目根目录运行：

```powershell
docker compose up --build
```

打开 `http://localhost:8000`。第一次启动会自动建立数据库。

## 本地开发启动

需要 Python 3.11+ 与 Node.js 20+。

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

前端（另开一个终端）：

```powershell
cd frontend
npm install
npm run dev
```

开发地址是 `http://localhost:5173`，它会自动转发 API 请求到后端。

### 没有模型密钥？用模拟模型跑演示

`work/mock_llm.py` 是一个本地的 OpenAI 兼容模拟服务，支持流式输出和演示用的工具调用（打卡、建项目、建任务、查概况），不消耗任何真实额度：

```powershell
python work/mock_llm.py   # 监听 :9000
```

把 `backend/.env` 里设为 `LLM_BASE_URL=http://localhost:9000`、`LLM_API_KEY=demo-key` 即可完整体验 Agent 对话。在对话里试试：「今天健身打卡」「帮我建一个网站项目」「我现在进展怎么样」。

## 使用说明

- **新建会话**：侧栏进入「对话」，点击“新建对话”。标题会在首次发送消息后自动使用消息前 24 个字。
- **系统提示词**：通过 `PATCH /api/conversations/{id}` 设置；未设置时使用内置的工作台助手提示词（含当日日期）。
- **搜索**：对话页的搜索会匹配会话标题和全部聊天内容。
- **打卡**：主页或打卡页点击习惯即可打/撤今天的卡；热力图按所有习惯聚合计数。
- **倒计时**：主页「目标倒计时」卡片添加名称与目标日期；过期后显示“N 天前已过”。
- **写作**：「插入配图」会上传图片并在光标处插入图片语法；发布到各平台后在底部勾选并粘贴文章链接留档。Substack 与公众号无公开 API，需手动发布后回标。
- **删除**：会话删除会一并删除其消息；习惯删除会一并删除其打卡记录。均不可恢复。

## 项目结构

```text
backend/              FastAPI、SQLite、Agent 工具与流式转发
  app/
    main.py           会话、聊天（function calling 循环）、记忆、Claude 面板
    workbench.py      项目/任务/打卡/倒计时/文章/个人信息的 REST API 与 Agent 工具
    database.py       建表与连接
    auth.py           单用户登录会话
  data/               数据库、头像、文章配图（已被 Git 忽略）
  memories/           你的本地 Markdown 记忆文件
frontend/             React 响应式界面
  src/views/          主页、对话、项目、看板、打卡、写作、记忆
  src/components/     热力图、概况栏、图标、个人信息弹窗
  public/photos/      主页卡片刊头照片
work/mock_llm.py      演示用模拟模型服务（可选）
docker-compose.yml    一条命令部署
deploy/               systemd 与 Caddy 配置示例
```

## Claude Code 执行面板（进阶）

先在本机安装并登录 Claude Code，然后打开侧栏的“Claude Code”。它使用官方 `claude -p` 的非交互执行模式和 `stream-json` 流式输出：[CLI 参考](https://docs.anthropic.com/en/docs/claude-code/cli-usage)。

默认仅允许操作本项目目录。若需增加项目，请在 `backend/.env` 设置目录白名单：

```env
CLAUDE_WORKSPACES=学习项目=C:\\Users\\你的名字\\Projects\\ai-learning;网站项目=D:\\projects\\my-site
```

每次执行都要求确认，可选择“仅规划”或“允许编辑文件”。应用不会使用 `--dangerously-skip-permissions`，且浏览器不能提交任意本机路径。请仅部署到可信设备和网络。

> 注意：Claude Code 是宿主机上的 CLI。要使用此面板，请按“本地开发启动”在安装了 Claude Code 的电脑上运行后端；默认 Docker 容器不能直接调用宿主机的 `claude` 命令。

## 云服务器 + 手机部署

详细步骤见 [手机访问个人AI工作台-部署说明.md](手机访问个人AI工作台-部署说明.md)。要点：

1. 将项目放到服务器，例如 `/opt/personal-ai-workbench`，安装 Node.js、Python 和已登录的 Claude Code。
2. 按“本地开发启动”安装后端依赖，并运行 `npm install && npm run build` 构建前端。
3. 复制 `backend/.env.example` 为 `.env`，设置强密码和随机会话密钥；生产环境必须设 `COOKIE_SECURE=true`。
4. 将 `deploy/personal-ai-workbench.service` 中的用户和路径改成实际值，复制到 `/etc/systemd/system/`，执行 `sudo systemctl enable --now personal-ai-workbench`。
5. 将 `deploy/Caddyfile` 中的域名改为自己的域名，配置 Caddy 自动启用 HTTPS；手机打开该 HTTPS 地址后，可在浏览器菜单选择“添加到主屏幕”。

不要直接开放 8000 端口；只通过 HTTPS 反向代理访问。所有 API 和 Claude Code 执行均需要登录。

## 安全提醒

`.env` 包含 API Key，已被 Git 忽略，请不要提交它。`backend/data/`（数据库、头像、配图）同样被忽略。聊天记录及所有数据始终保留在本机/你的服务器；仅在你点击发送后，消息会直接发往你配置的模型供应商。
