"""个人 AI 工作台 API：会话、流式聊天与本地记忆文件。"""
import json
import os
import uuid
import asyncio
import hmac
import shutil
import tempfile
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .database import get_connection, initialize_database
from .auth import COOKIE_NAME, create_session, valid_session
from .workbench import router as workbench_router, TOOLS, TOOL_LABELS, run_tool
from . import agent_tools

load_dotenv()
ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = Path(os.getenv("MEMORY_DIR", ROOT / "memories")).resolve()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="个人 AI 工作台", lifespan=lifespan)
app.include_router(workbench_router)


@app.middleware("http")
async def require_login(request: Request, call_next):
    """所有 API 默认受保护；登录页和静态文件可匿名访问。"""
    if request.url.path.startswith("/api/") and request.url.path not in {"/api/auth/login", "/api/auth/logout"}:
        if not valid_session(request.cookies.get(COOKIE_NAME)):
            return Response(content='{"detail":"请先登录"}', status_code=401, media_type="application/json")
    return await call_next(request)


class ConversationCreate(BaseModel):
    title: str = "新对话"


class ConversationUpdate(BaseModel):
    title: str | None = None
    system_prompt: str | None = None


class ChatRequest(BaseModel):
    content: str


class ClaudeRunRequest(BaseModel):
    prompt: str
    workspace_id: str
    mode: str = "plan"
    confirmed: bool = False


def row_dict(row):
    return dict(row) if row else None


def claude_workspaces() -> list[dict]:
    """仅列出服务端配置的目录，客户端不能提交任意路径。"""
    configured = os.getenv("CLAUDE_WORKSPACES", "").strip()
    entries = [("当前工作台", str(ROOT.parent))] if not configured else []
    for item in configured.split(";"):
        if "=" in item:
            name, path = item.split("=", 1)
            entries.append((name.strip(), path.strip()))
    result = []
    for index, (name, path) in enumerate(entries):
        target = Path(path).expanduser().resolve()
        if target.is_dir():
            result.append({"id": str(index), "name": name or target.name, "path": str(target)})
    return result


class LoginRequest(BaseModel):
    password: str


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response):
    """单用户登录：只比较服务器环境变量中的密码。"""
    expected = os.getenv("WORKBENCH_PASSWORD", "")
    if not expected or not hmac.compare_digest(payload.password, expected):
        raise HTTPException(401, "密码不正确，或服务器尚未设置 WORKBENCH_PASSWORD")
    response.set_cookie(COOKIE_NAME, create_session(), httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE", "false").lower() == "true", max_age=30 * 24 * 60 * 60)
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@app.get("/api/auth/me")
def current_user():
    return {"ok": True}


@app.get("/api/conversations")
def list_conversations(q: str = ""):
    """按更新时间返回会话；搜索同时匹配标题与消息。"""
    with get_connection() as db:
        if q.strip():
            pattern = f"%{q.strip()}%"
            rows = db.execute(
                """SELECT DISTINCT c.* FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id
                   WHERE c.title LIKE ? OR m.content LIKE ? ORDER BY c.updated_at DESC""",
                (pattern, pattern),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
    return [row_dict(row) for row in rows]


@app.post("/api/conversations")
def create_conversation(payload: ConversationCreate):
    conversation = {"id": str(uuid.uuid4()), "title": payload.title.strip() or "新对话"}
    with get_connection() as db:
        db.execute("INSERT INTO conversations (id, title) VALUES (?, ?)", (conversation["id"], conversation["title"]))
        row = db.execute("SELECT * FROM conversations WHERE id = ?", (conversation["id"],)).fetchone()
    return row_dict(row)


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    with get_connection() as db:
        conversation = db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if not conversation:
            raise HTTPException(404, "会话不存在")
        messages = db.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at", (conversation_id,)).fetchall()
    return {**row_dict(conversation), "messages": [row_dict(message) for message in messages]}


@app.patch("/api/conversations/{conversation_id}")
def update_conversation(conversation_id: str, payload: ConversationUpdate):
    fields, values = [], []
    if payload.title is not None:
        fields.append("title = ?"); values.append(payload.title.strip() or "新对话")
    if payload.system_prompt is not None:
        fields.append("system_prompt = ?"); values.append(payload.system_prompt)
    if not fields:
        raise HTTPException(400, "没有可更新的内容")
    values.append(conversation_id)
    with get_connection() as db:
        result = db.execute(f"UPDATE conversations SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
        if not result.rowcount:
            raise HTTPException(404, "会话不存在")
        row = db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return row_dict(row)


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    with get_connection() as db:
        result = db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        if not result.rowcount:
            raise HTTPException(404, "会话不存在")
    return {"ok": True}


AGENT_MAX_ROUNDS = 6

DEFAULT_SYSTEM_PROMPT = (
    "你是「个人 AI 工作台」里的全能助手。用户可以管理项目、任务和每日打卡习惯；"
    "当用户的请求涉及这些内容时，主动调用提供的工具完成操作，不要只给建议。"
    "工具执行成功后，用简洁的中文向用户确认结果。今天的日期是 {today}。"
)


@app.post("/api/conversations/{conversation_id}/chat")
async def chat(conversation_id: str, payload: ChatRequest):
    """保存用户消息，按后端配置分派到 Claude Code 或 OpenAI 兼容接口。"""
    text = payload.content.strip()
    if not text:
        raise HTTPException(400, "消息不能为空")
    with get_connection() as db:
        conversation = db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if not conversation:
            raise HTTPException(404, "会话不存在")
        db.execute("INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, 'user', ?)", (str(uuid.uuid4()), conversation_id, text))
        if conversation["title"] == "新对话":
            db.execute("UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (text[:24], conversation_id))
        history = db.execute("SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at", (conversation_id,)).fetchall()

    if _use_claude():
        return await _chat_claude(conversation_id, conversation, history)
    return await _chat_openai(conversation_id, conversation, history)


def _use_claude() -> bool:
    """是否用 Claude Code 文本协议作为对话后端（默认），否则回退 OpenAI。"""
    if os.getenv("AGENT_BACKEND", "claude").lower() == "openai":
        return False
    return shutil.which(os.getenv("CLAUDE_COMMAND", "claude")) is not None


_ISOLATED_CONFIG_DIR: str | None = None


def _get_isolated_config_dir() -> str:
    """创建一个空的 CLAUDE_CONFIG_DIR，阻止 Claude Code 加载用户插件/技能/CLAUDE.md。

    插件（如 webnovel-writer、docconvert）会注入大量 system prompt 内容，
    覆盖我们的角色定义。隔离配置目录后，Claude 只使用 --system-prompt-file 指定的内容。
    """
    global _ISOLATED_CONFIG_DIR
    if _ISOLATED_CONFIG_DIR and os.path.isdir(_ISOLATED_CONFIG_DIR):
        return _ISOLATED_CONFIG_DIR
    config_dir = ROOT / "data" / "claude_isolated_config"
    config_dir.mkdir(parents=True, exist_ok=True)
    # 复制认证凭据（如果存在），保证 OAuth 仍能工作
    real_claude_dir = Path.home() / ".claude"
    for cred_file in [".credentials.json", "credentials.json"]:
        src = real_claude_dir / cred_file
        if src.exists():
            dst = config_dir / cred_file
            if not dst.exists():
                shutil.copy2(src, dst)
    _ISOLATED_CONFIG_DIR = str(config_dir)
    return _ISOLATED_CONFIG_DIR


def _build_claude_prompt(turns: list[tuple[str, str]]) -> str:
    """把多轮对话历史拼成 claude -p 的 prompt 文本。"""
    if len(turns) == 1:
        # 单轮对话直接传用户消息，避免包装干扰
        return turns[0][1]
    lines = ["以下是之前的对话历史，最后一条是最新消息，请据此回复。"]
    tag_map = {"user": "用户", "assistant": "助手", "tool": "工具结果"}
    for role, content in turns:
        lines.append(f"\n[{tag_map.get(role, role)}]: {content}")
    return "".join(lines)


def _get_cross_chat_memory_block() -> str:
    """读取所有跨聊天记忆事实，拼成 system prompt 片段。"""
    with get_connection() as db:
        rows = db.execute("SELECT content, category FROM memory_facts ORDER BY created_at DESC LIMIT 50").fetchall()
    if not rows:
        return ""
    lines = ["\n\n【跨聊天记忆·你从之前对话中了解到的用户信息】"]
    for row in rows:
        lines.append(f"- [{row['category']}] {row['content']}")
    lines.append("（以上记忆会在所有对话中自动带入。当用户分享新的长期信息时，用 save_memory_fact 保存。）")
    return "\n".join(lines)


async def _chat_claude(conversation_id: str, conversation, history):
    """Claude Code 文本协议：每轮调用 claude -p，解析工具调用 JSON，循环执行。"""
    system_prompt = (conversation["system_prompt"] or "").strip() or DEFAULT_SYSTEM_PROMPT
    # 注入跨聊天记忆：让 agent 在所有对话中都能访问之前保存的用户信息
    memory_block = _get_cross_chat_memory_block()
    full_system = (
        "你是「个人 AI 工作台」的内置助手，管理用户的个人项目、任务、习惯、文章、倒计时等数据。\n"
        "你不是代码助手，不要分析文件或代码。\n"
        "用户提到「项目」「任务」「打卡」「习惯」「文章」「倒计时」「记忆库」时，你必须通过工具协议输出 JSON 调用对应工具。\n"
        "今天的日期是 " + date.today().isoformat() + "。\n\n"
        + system_prompt.replace("{today}", date.today().isoformat())
        + memory_block
        + "\n\n" + agent_tools.TOOL_PROTOCOL
    )
    turns: list[tuple[str, str]] = [(row["role"], row["content"]) for row in history]
    claude_cmd = os.getenv("CLAUDE_COMMAND", "claude")
    resolved = shutil.which(claude_cmd)
    # Windows 上 npm 全局命令是 .CMD，create_subprocess_exec 无法直接执行，需 cmd /c 包装
    if os.name == "nt" and resolved and resolved.lower().endswith((".cmd", ".bat")):
        base_argv = ["cmd", "/c", resolved]
    else:
        base_argv = [resolved or claude_cmd]
    # 用 --system-prompt-file 完全替换默认 system prompt
    sf = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
    sf.write(full_system)
    sf.close()
    system_file = sf.name
    # 隔离配置目录 + safe-mode + disable-slash-commands，阻止插件/技能注入内容
    isolated_config = _get_isolated_config_dir()
    claude_env = {**os.environ, "CLAUDE_CONFIG_DIR": isolated_config}

    async def event_stream():
        full_reply = ""
        try:
            for round_idx in range(AGENT_MAX_ROUNDS):
                prompt = _build_claude_prompt(turns)
                # prompt 通过 stdin 传递，避免 cmd /c 解析 JSON 特殊字符（{}、""）导致内容丢失
                cmd_args = [*base_argv, "-p",
                            "--disable-slash-commands",
                            "--tools", "",
                            "--system-prompt-file", system_file,
                            "--output-format", "text"]
                process = await asyncio.create_subprocess_exec(
                    *cmd_args,
                    cwd=tempfile.gettempdir(),
                    env=claude_env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                # 等待 claude 输出期间定期发心跳，防止前端 / proxy 超时断开
                comm_task = asyncio.ensure_future(process.communicate(input=prompt.encode("utf-8")))
                while True:
                    done, _ = await asyncio.wait({comm_task}, timeout=4)
                    if comm_task in done:
                        break
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                stdout_bytes, stderr_bytes = comm_task.result()
                output = stdout_bytes.decode("utf-8", errors="replace").strip()
                if process.returncode != 0:
                    err_detail = stderr_bytes.decode("utf-8", errors="replace").strip() or output
                    raise RuntimeError(f"claude 退出码 {process.returncode}：{err_detail[:500]}")

                tool_call = agent_tools.parse_tool_call(output)
                if not tool_call:
                    full_reply = output
                    yield f"data: {json.dumps({'content': output}, ensure_ascii=False)}\n\n"
                    break

                name, targs = tool_call
                call_id = f"call_{round_idx}"
                label = agent_tools.TOOL_LABELS.get(name, name)
                yield f"data: {json.dumps({'tool': {'id': call_id, 'name': name, 'label': label, 'status': 'running'}}, ensure_ascii=False)}\n\n"
                result = await asyncio.to_thread(agent_tools.dispatch, name, targs)
                yield f"data: {json.dumps({'tool': {'id': call_id, 'name': name, 'label': label, 'status': 'done', 'result': result}}, ensure_ascii=False)}\n\n"
                turns.append(("assistant", output))
                turns.append(("tool", json.dumps({"tool": name, "result": result}, ensure_ascii=False, default=str)))
            else:
                yield f"data: {json.dumps({'error': '已达到最大工具调用轮次，请缩小请求范围'}, ensure_ascii=False)}\n\n"
        except FileNotFoundError:
            yield f"data: {json.dumps({'error': '找不到 claude 命令，请确认 Claude Code CLI 已安装'}, ensure_ascii=False)}\n\n"
        except Exception as error:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'error': f'Claude 调用失败：{type(error).__name__}: {error}'}, ensure_ascii=False)}\n\n"
        finally:
            if full_reply:
                with get_connection() as db:
                    db.execute("INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, 'assistant', ?)", (str(uuid.uuid4()), conversation_id, full_reply))
                    db.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
            try:
                os.unlink(system_file)
            except OSError:
                pass
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _chat_openai(conversation_id: str, conversation, history):
    """OpenAI 兼容接口回退：function calling 循环驱动 Agent。"""
    base_url, api_key = os.getenv("LLM_BASE_URL", "").rstrip("/"), os.getenv("LLM_API_KEY", "")
    if not base_url or not api_key:
        raise HTTPException(400, "未配置 Claude Code CLI，也未设置 LLM_BASE_URL/LLM_API_KEY，无法对话")
    system_prompt = (conversation["system_prompt"] or "").strip() or DEFAULT_SYSTEM_PROMPT
    messages = [{"role": "system", "content": system_prompt.replace("{today}", date.today().isoformat())}]
    messages += [dict(row) for row in history]

    async def event_stream():
        full_reply = ""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                for _ in range(AGENT_MAX_ROUNDS):
                    request_data = {
                        "model": os.getenv("LLM_MODEL", "deepseek-chat"),
                        "messages": messages,
                        "tools": TOOLS,
                        "stream": True,
                    }
                    round_text = ""
                    tool_calls: dict[int, dict] = {}
                    async with client.stream("POST", f"{base_url}/v1/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json=request_data) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                delta = json.loads(data)["choices"][0].get("delta", {})
                            except (json.JSONDecodeError, IndexError, KeyError):
                                continue
                            content = delta.get("content")
                            if content:
                                round_text += content
                                full_reply += content
                                yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                            for call in delta.get("tool_calls") or []:
                                slot = tool_calls.setdefault(call.get("index", 0), {"id": "", "name": "", "arguments": ""})
                                if call.get("id"):
                                    slot["id"] = call["id"]
                                function = call.get("function") or {}
                                if function.get("name"):
                                    slot["name"] += function["name"]
                                if function.get("arguments"):
                                    slot["arguments"] += function["arguments"]

                    if not tool_calls:
                        break  # 模型直接给出文字回复，对话结束

                    # 执行本轮全部工具，把结果交还给模型继续推理
                    messages.append({
                        "role": "assistant",
                        "content": round_text or None,
                        "tool_calls": [
                            {"id": slot["id"] or f"call_{index}", "type": "function",
                             "function": {"name": slot["name"], "arguments": slot["arguments"]}}
                            for index, slot in sorted(tool_calls.items())
                        ],
                    })
                    for index, slot in sorted(tool_calls.items()):
                        call_id = slot["id"] or f"call_{index}"
                        label = TOOL_LABELS.get(slot["name"], slot["name"])
                        yield f"data: {json.dumps({'tool': {'id': call_id, 'name': slot['name'], 'label': label, 'status': 'running'}}, ensure_ascii=False)}\n\n"
                        result = await asyncio.to_thread(run_tool, slot["name"], slot["arguments"])
                        yield f"data: {json.dumps({'tool': {'id': call_id, 'name': slot['name'], 'label': label, 'status': 'done', 'result': result}}, ensure_ascii=False)}\n\n"
                        messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(result, ensure_ascii=False)})
        except httpx.HTTPError as error:
            yield f"data: {json.dumps({'error': f'模型请求失败：{error}'}, ensure_ascii=False)}\n\n"
        finally:
            if full_reply:
                with get_connection() as db:
                    db.execute("INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, 'assistant', ?)", (str(uuid.uuid4()), conversation_id, full_reply))
                    db.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/memories")
def list_memories():
    return [{"path": str(path.relative_to(MEMORY_DIR)).replace("\\", "/"), "name": path.name} for path in MEMORY_DIR.rglob("*.md")]


@app.get("/api/memories/{file_path:path}")
def get_memory(file_path: str):
    target = (MEMORY_DIR / file_path).resolve()
    if MEMORY_DIR not in target.parents or not target.is_file() or target.suffix.lower() != ".md":
        raise HTTPException(404, "记忆文件不存在")
    return {"path": file_path, "content": target.read_text(encoding="utf-8")}


# ---------- 记忆库提案：agent 提议 → 用户审批 ----------

@app.get("/api/memory-proposals")
def list_memory_proposals(status: str = ""):
    with get_connection() as db:
        if status:
            rows = db.execute("SELECT * FROM memory_proposals WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM memory_proposals ORDER BY created_at DESC").fetchall()
    return [row_dict(r) for r in rows]


@app.post("/api/memory-proposals/{proposal_id}/approve")
def approve_memory_proposal(proposal_id: str):
    with get_connection() as db:
        row = db.execute("SELECT * FROM memory_proposals WHERE id = ?", (proposal_id,)).fetchone()
        if not row:
            raise HTTPException(404, "提案不存在")
        if row["status"] != "pending":
            raise HTTPException(400, "该提案已处理")
        target = (MEMORY_DIR / row["file_path"]).resolve()
        if MEMORY_DIR not in target.parents and target != MEMORY_DIR:
            raise HTTPException(400, "文件路径越界")
        if row["action"] == "delete":
            if target.exists():
                target.unlink()
        else:  # create / update
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(row["content"], encoding="utf-8")
        db.execute("UPDATE memory_proposals SET status = 'approved' WHERE id = ?", (proposal_id,))
    return {"ok": True, "action": row["action"], "path": row["file_path"]}


@app.post("/api/memory-proposals/{proposal_id}/reject")
def reject_memory_proposal(proposal_id: str):
    with get_connection() as db:
        result = db.execute("UPDATE memory_proposals SET status = 'rejected' WHERE id = ? AND status = 'pending'", (proposal_id,))
        if not result.rowcount:
            raise HTTPException(404, "提案不存在或已处理")
    return {"ok": True}


# ---------- 跨聊天记忆 ----------

@app.get("/api/memory-facts")
def list_memory_facts():
    with get_connection() as db:
        rows = db.execute("SELECT * FROM memory_facts ORDER BY created_at DESC").fetchall()
    return [row_dict(r) for r in rows]


@app.delete("/api/memory-facts/{fact_id}")
def delete_memory_fact(fact_id: str):
    with get_connection() as db:
        if not db.execute("DELETE FROM memory_facts WHERE id = ?", (fact_id,)).rowcount:
            raise HTTPException(404, "记忆不存在")
    return {"ok": True}


@app.get("/api/claude/workspaces")
def list_claude_workspaces():
    return claude_workspaces()


@app.post("/api/claude/run")
async def run_claude(payload: ClaudeRunRequest):
    """在白名单工作目录中启动 Claude Code，并转发 stream-json 事件。"""
    if not payload.prompt.strip():
        raise HTTPException(400, "任务不能为空")
    if not payload.confirmed:
        raise HTTPException(400, "请确认本次执行")
    if payload.mode not in {"plan", "acceptEdits"}:
        raise HTTPException(400, "不支持的执行模式")
    workspace = next((item for item in claude_workspaces() if item["id"] == payload.workspace_id), None)
    if not workspace:
        raise HTTPException(400, "工作目录不在允许列表中")
    arguments = [os.getenv("CLAUDE_COMMAND", "claude"), "-p", payload.prompt.strip(), "--output-format", "stream-json", "--verbose", "--max-turns", "20", "--permission-mode", payload.mode]

    async def event_stream():
        try:
            # 不经过 shell，任务文本不会被系统命令解释。
            process = await asyncio.create_subprocess_exec(*arguments, cwd=workspace["path"], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        except FileNotFoundError:
            yield f"data: {json.dumps({'error': '找不到 claude 命令。请安装并登录 Claude Code。'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                raw = line.decode("utf-8", errors="replace").strip()
                if not raw:
                    continue
                try:
                    yield f"data: {json.dumps({'event': json.loads(raw)}, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    yield f"data: {json.dumps({'text': raw}, ensure_ascii=False)}\n\n"
            stderr = (await process.stderr.read()).decode("utf-8", errors="replace").strip()
            code = await process.wait()
            if code:
                yield f"data: {json.dumps({'error': stderr or f'Claude Code 退出，状态码 {code}'}, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# 项目/任务/打卡接口在 workbench.py；后续扩展预留：/api/notes、/api/reminders、/api/digests
FRONTEND_DIR = ROOT.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
