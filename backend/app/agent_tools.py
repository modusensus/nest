"""工作台 Agent 工具：供对话端点（claude -p 协议）与 MCP server 共用。

每个工具接收一个 dict 参数，返回可 JSON 序列化的 dict。直接复用 workbench.py 的数据函数，
读写同一份 SQLite，因此无论从对话页还是 MCP 调用，效果一致、手机端实时可见。
"""
import json
import os
import uuid
from datetime import date, timedelta
from pathlib import Path

from .database import get_connection, ROOT as BACKEND_ROOT
from . import workbench as wb

MEMORY_DIR = Path(os.getenv("MEMORY_DIR", BACKEND_ROOT / "memories")).resolve()


def _row(row):
    return dict(row) if row else None


def _new_id() -> str:
    return str(uuid.uuid4())


# ------------------------------------------------------------------
# 读
# ------------------------------------------------------------------

def t_list_projects(_):
    return {"projects": wb.list_projects()}


def t_list_tasks(args):
    return {"tasks": wb.list_tasks(args.get("project_name", ""), args.get("status", ""))}


def t_list_habits(_):
    return {"habits": wb.list_habits()}


def t_habit_logs(args):
    days = max(1, min(int(args.get("days", 90)), 400))
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with get_connection() as db:
        rows = db.execute(
            "SELECT h.name AS habit, l.check_date FROM habit_logs l "
            "JOIN habits h ON h.id = l.habit_id WHERE l.check_date >= ? "
            "ORDER BY l.check_date DESC",
            (since,),
        ).fetchall()
    return {"logs": [_row(r) for r in rows]}


def t_list_articles(_):
    with get_connection() as db:
        rows = db.execute(
            "SELECT id, title, status, created_at, updated_at FROM articles ORDER BY updated_at DESC"
        ).fetchall()
    return {"articles": [_row(r) for r in rows]}


def t_get_article(args):
    with get_connection() as db:
        row = db.execute("SELECT * FROM articles WHERE id = ?", (args.get("article_id", ""),)).fetchone()
    if not row:
        raise ValueError("文章不存在")
    return {"article": _row(row)}


def t_list_countdowns(_):
    with get_connection() as db:
        rows = db.execute("SELECT * FROM countdowns ORDER BY target_date").fetchall()
    today = date.today()
    out = []
    for r in rows:
        item = _row(r)
        try:
            item["days_left"] = (date.fromisoformat(item["target_date"]) - today).days
        except ValueError:
            item["days_left"] = None
        out.append(item)
    return {"countdowns": out}


def t_get_profile(_):
    return {"profile": wb.get_profile()}


def t_get_overview(_):
    return wb.get_overview()


# ------------------------------------------------------------------
# 写
# ------------------------------------------------------------------

def t_create_project(args):
    return {"project": wb.create_project(args.get("name", ""), args.get("description", ""))}


def t_update_project(args):
    pid = args.get("project_id", "")
    fields, values = [], []
    if args.get("name") is not None:
        fields.append("name = ?"); values.append(args["name"].strip() or "未命名项目")
    if args.get("description") is not None:
        fields.append("description = ?"); values.append(args["description"])
    if args.get("status") is not None:
        if args["status"] not in {"active", "archived"}:
            raise ValueError("状态只能是 active / archived")
        fields.append("status = ?"); values.append(args["status"])
    if not fields:
        raise ValueError("没有要更新的内容")
    values.append(pid)
    with get_connection() as db:
        if not db.execute(f"UPDATE projects SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values).rowcount:
            raise ValueError("项目不存在")
        return {"project": _row(db.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone())}


def t_delete_project(args):
    with get_connection() as db:
        db.execute("UPDATE tasks SET project_id = NULL WHERE project_id = ?", (args.get("project_id", ""),))
        if not db.execute("DELETE FROM projects WHERE id = ?", (args.get("project_id", ""),)).rowcount:
            raise ValueError("项目不存在")
    return {"ok": True}


def t_create_task(args):
    return {"task": wb.create_task(args.get("title", ""), args.get("project_name", ""), args.get("due_date", ""))}


def t_update_task(args):
    return {"task": wb.update_task(
        args.get("task_title_or_id", ""),
        status=args.get("status", ""),
        title=args.get("title", ""),
        due_date=args.get("due_date", ""),
    )}


def t_delete_task(args):
    with get_connection() as db:
        if not db.execute("DELETE FROM tasks WHERE id = ?", (args.get("task_id", ""),)).rowcount:
            raise ValueError("任务不存在")
    return {"ok": True}


def t_create_habit(args):
    return {"habit": wb.create_habit(args.get("name", ""))}


def t_delete_habit(args):
    with get_connection() as db:
        if not db.execute("DELETE FROM habits WHERE id = ?", (args.get("habit_id", ""),)).rowcount:
            raise ValueError("习惯不存在")
    return {"ok": True}


def t_checkin(args):
    return wb.toggle_checkin(args.get("habit_name", ""), args.get("date", ""))


def t_create_article(args):
    aid = _new_id()
    with get_connection() as db:
        db.execute("INSERT INTO articles (id, title, content) VALUES (?, ?, ?)",
                   (aid, (args.get("title") or "未命名文章").strip(), args.get("content", "")))
        row = db.execute("SELECT * FROM articles WHERE id = ?", (aid,)).fetchone()
    return {"article": _row(row)}


def t_update_article(args):
    aid = args.get("article_id", "")
    fields, values = [], []
    if args.get("title") is not None:
        fields.append("title = ?"); values.append(args["title"].strip() or "未命名文章")
    if args.get("content") is not None:
        fields.append("content = ?"); values.append(args["content"])
    if args.get("status") is not None:
        if args["status"] not in {"draft", "published"}:
            raise ValueError("状态只能是 draft / published")
        fields.append("status = ?"); values.append(args["status"])
    if not fields:
        raise ValueError("没有要更新的内容")
    values.append(aid)
    with get_connection() as db:
        if not db.execute(f"UPDATE articles SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values).rowcount:
            raise ValueError("文章不存在")
        row = db.execute("SELECT * FROM articles WHERE id = ?", (aid,)).fetchone()
    return {"article": _row(row)}


def t_delete_article(args):
    with get_connection() as db:
        if not db.execute("DELETE FROM articles WHERE id = ?", (args.get("article_id", ""),)).rowcount:
            raise ValueError("文章不存在")
    return {"ok": True}


def t_create_countdown(args):
    title = (args.get("title") or "").strip()
    target = args.get("target_date", "")
    if not title:
        raise ValueError("标题不能为空")
    try:
        date.fromisoformat(target)
    except ValueError:
        raise ValueError("目标日期格式应为 YYYY-MM-DD")
    cid = _new_id()
    with get_connection() as db:
        db.execute("INSERT INTO countdowns (id, title, target_date) VALUES (?, ?, ?)", (cid, title, target))
        row = db.execute("SELECT * FROM countdowns WHERE id = ?", (cid,)).fetchone()
    return {"countdown": _row(row)}


def t_delete_countdown(args):
    with get_connection() as db:
        if not db.execute("DELETE FROM countdowns WHERE id = ?", (args.get("countdown_id", ""),)).rowcount:
            raise ValueError("倒计时不存在")
    return {"ok": True}


def t_update_profile(args):
    name = (args.get("name") or "").strip()
    if not name:
        raise ValueError("名称不能为空")
    with get_connection() as db:
        wb.get_profile()
        db.execute("UPDATE profile SET name = ?, agent_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                   (name, (args.get("agent_id") or "").strip()))
    return {"profile": wb.get_profile()}


# ------------------------------------------------------------------
# 记忆库：文件读取 + 提案审批 + 跨聊天记忆
# ------------------------------------------------------------------

def _safe_memory_path(file_path: str) -> Path:
    """把用户/agent 提供的相对路径解析到 MEMORY_DIR 内，禁止穿越。"""
    clean = (file_path or "").strip().lstrip("/")
    target = (MEMORY_DIR / clean).resolve()
    if MEMORY_DIR not in target.parents and target != MEMORY_DIR:
        raise ValueError("路径越界，禁止访问记忆库之外的文件")
    if not clean:
        raise ValueError("文件路径不能为空")
    return target


def t_list_memory_files(_):
    files = []
    for path in sorted(MEMORY_DIR.rglob("*.md")):
        rel = str(path.relative_to(MEMORY_DIR)).replace("\\", "/")
        files.append({"path": rel, "name": path.name, "size": path.stat().st_size})
    return {"files": files}


def t_get_memory_file(args):
    target = _safe_memory_path(args.get("path", ""))
    if not target.is_file():
        raise ValueError("记忆文件不存在")
    return {"path": str(target.relative_to(MEMORY_DIR)).replace("\\", "/"), "content": target.read_text(encoding="utf-8")}


def t_propose_memory_file(args):
    """Agent 提议创建/更新一个记忆库 md 文件，需用户审批后生效。"""
    path = (args.get("path", "")).strip()
    content = args.get("content", "")
    reason = (args.get("reason", "")).strip()
    if not path:
        raise ValueError("path 不能为空")
    if not path.lower().endswith(".md"):
        raise ValueError("只支持 .md 文件")
    target = _safe_memory_path(path)
    action = "update" if target.exists() else "create"
    pid = _new_id()
    with get_connection() as db:
        db.execute(
            "INSERT INTO memory_proposals (id, action, file_path, content, reason) VALUES (?, ?, ?, ?, ?)",
            (pid, action, path, content, reason),
        )
    return {"proposal_id": pid, "action": action, "path": path, "reason": reason,
            "message": f"已提交{('更新' if action == 'update' else '创建')}提案，等待用户在记忆库页面审批"}


def t_propose_delete_memory_file(args):
    """Agent 提议删除一个记忆库文件，需用户审批。"""
    path = (args.get("path", "")).strip()
    reason = (args.get("reason", "")).strip()
    if not path:
        raise ValueError("path 不能为空")
    target = _safe_memory_path(path)
    if not target.exists():
        raise ValueError("文件不存在，无需删除")
    pid = _new_id()
    with get_connection() as db:
        db.execute(
            "INSERT INTO memory_proposals (id, action, file_path, content, reason) VALUES (?, 'delete', ?, '', ?)",
            (pid, path, reason),
        )
    return {"proposal_id": pid, "action": "delete", "path": path, "reason": reason,
            "message": "已提交删除提案，等待用户在记忆库页面审批"}


def t_list_memory_facts(_):
    with get_connection() as db:
        rows = db.execute("SELECT * FROM memory_facts ORDER BY created_at DESC").fetchall()
    return {"facts": [_row(r) for r in rows]}


def t_save_memory_fact(args):
    """跨聊天记忆：保存一条全局事实，会在所有后续对话中自动注入。"""
    content = (args.get("content", "")).strip()
    category = (args.get("category", "general") or "general").strip()
    if not content:
        raise ValueError("记忆内容不能为空")
    fid = _new_id()
    with get_connection() as db:
        db.execute("INSERT INTO memory_facts (id, content, category) VALUES (?, ?, ?)", (fid, content, category))
        row = db.execute("SELECT * FROM memory_facts WHERE id = ?", (fid,)).fetchone()
    return {"fact": _row(row)}


def t_delete_memory_fact(args):
    with get_connection() as db:
        if not db.execute("DELETE FROM memory_facts WHERE id = ?", (args.get("fact_id", ""),)).rowcount:
            raise ValueError("记忆不存在")
    return {"ok": True}


# ------------------------------------------------------------------
# 注册表
# ------------------------------------------------------------------

HANDLERS = {
    "list_projects": t_list_projects,
    "create_project": t_create_project,
    "update_project": t_update_project,
    "delete_project": t_delete_project,
    "list_tasks": t_list_tasks,
    "create_task": t_create_task,
    "update_task": t_update_task,
    "delete_task": t_delete_task,
    "list_habits": t_list_habits,
    "habit_logs": t_habit_logs,
    "create_habit": t_create_habit,
    "delete_habit": t_delete_habit,
    "checkin": t_checkin,
    "list_articles": t_list_articles,
    "get_article": t_get_article,
    "create_article": t_create_article,
    "update_article": t_update_article,
    "delete_article": t_delete_article,
    "list_countdowns": t_list_countdowns,
    "create_countdown": t_create_countdown,
    "delete_countdown": t_delete_countdown,
    "get_profile": t_get_profile,
    "update_profile": t_update_profile,
    "get_overview": t_get_overview,
    "list_memory_files": t_list_memory_files,
    "get_memory_file": t_get_memory_file,
    "propose_memory_file": t_propose_memory_file,
    "propose_delete_memory_file": t_propose_delete_memory_file,
    "list_memory_facts": t_list_memory_facts,
    "save_memory_fact": t_save_memory_fact,
    "delete_memory_fact": t_delete_memory_fact,
}

# 工具名 → 中文标签（前端工具卡片用）
TOOL_LABELS = {
    "list_projects": "读取项目列表", "create_project": "创建项目", "update_project": "更新项目",
    "delete_project": "删除项目", "list_tasks": "查询任务", "create_task": "创建任务",
    "update_task": "更新任务", "delete_task": "删除任务", "list_habits": "读取习惯",
    "habit_logs": "查询打卡记录", "create_habit": "创建习惯", "delete_habit": "删除习惯",
    "checkin": "记录打卡", "list_articles": "读取文章列表", "get_article": "读取文章",
    "create_article": "创建文章", "update_article": "更新文章", "delete_article": "删除文章",
    "list_countdowns": "读取倒计时", "create_countdown": "创建倒计时", "delete_countdown": "删除倒计时",
    "get_profile": "读取资料", "update_profile": "更新资料", "get_overview": "汇总工作台概况",
    "list_memory_files": "读取记忆库文件", "get_memory_file": "读取记忆库文件内容",
    "propose_memory_file": "提议创建/更新记忆库文件", "propose_delete_memory_file": "提议删除记忆库文件",
    "list_memory_facts": "读取跨聊天记忆", "save_memory_fact": "保存跨聊天记忆", "delete_memory_fact": "删除跨聊天记忆",
}

# 协议文本：拼进 claude 的 system-prompt-file，告诉它有哪些工具、怎么调用
TOOL_PROTOCOL = """\
【工具调用规则·必须严格遵守】
需要查询或修改数据时，你的完整回复必须且只能是一行 JSON，格式如下：
{"tool":"工具名","arguments":{参数}}
绝对不要在 JSON 前后添加任何文字、解释、markdown 代码块标记。不要说"我来调用"或"正在查询"之类的话。直接输出 JSON 本身。
我会在下一轮把工具执行结果告诉你，届时你再用中文简洁汇报结果。
完全不涉及数据时，直接用中文回答。

示例——用户问"列出项目"，你只回复：
{"tool":"list_projects","arguments":{}}

可用工具：
- list_projects() 列出项目及任务进度
- create_project(name, description?) / update_project(project_id, name?, description?, status?) / delete_project(project_id)
- list_tasks(project_name?, status?) / create_task(title, project_name?, due_date?) / update_task(task_title_or_id, status?, title?, due_date?) / delete_task(task_id)
- list_habits() / habit_logs(days?) / create_habit(name) / delete_habit(habit_id) / checkin(habit_name, date?)  # date 省略为今天，重复调用取消
- list_articles() / get_article(article_id) / create_article(title?, content?) / update_article(article_id, title?, content?, status?) / delete_article(article_id)
- list_countdowns() / create_countdown(title, target_date) / delete_countdown(countdown_id)
- get_profile() / update_profile(name, agent_id?)
- get_overview() 汇总项目/任务/打卡概况
- list_memory_files() 列出记忆库中的 md 文件 / get_memory_file(path) 读取文件内容
- propose_memory_file(path, content, reason) 提议创建或更新记忆库 md 文件（需用户审批）
- propose_delete_memory_file(path, reason) 提议删除记忆库文件（需用户审批）
- list_memory_facts() 读取所有跨聊天记忆 / save_memory_fact(content, category?) 保存一条跨聊天记忆（自动在所有对话中生效） / delete_memory_fact(fact_id)
说明：status 取值——项目 active/archived，任务 todo/doing/done，文章 draft/published；日期格式 YYYY-MM-DD；task_title_or_id、habit_name、project_name 支持模糊匹配。
记忆库说明：记忆库文件只能通过对话由你提议修改，用户在记忆库页面审批后生效。跨聊天记忆（memory_facts）是你在对话中了解到的用户长期偏好、背景、重要事项等，保存后会在所有新对话中自动注入，无需审批。当用户分享个人信息、偏好或重要决定时，主动用 save_memory_fact 保存。"""


def dispatch(name: str, args: dict) -> dict:
    """执行一个工具，返回可序列化 dict。出错时返回 {"error": ...} 而非抛异常。"""
    handler = HANDLERS.get(name)
    if not handler:
        return {"error": f"未知工具：{name}"}
    try:
        return handler(args or {})
    except ValueError as error:
        return {"error": str(error)}
    except Exception as error:  # noqa: BLE001
        return {"error": f"工具执行失败：{error}"}


def parse_tool_call(text: str):
    """从 claude 的回复里提取工具调用 JSON。返回 (name, args) 或 None。"""
    import re
    # 去掉 markdown 代码块标记
    cleaned = re.sub(r'```(?:json)?\s*', '', text).strip()
    # 找第一个 {...}，尽量贪婪到行尾的 }（避免截断嵌套对象）
    m = re.search(r'\{[\s\S]*\}', cleaned)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if isinstance(obj, dict) and "tool" in obj and isinstance(obj["tool"], str):
        return obj["tool"], obj.get("arguments") or {}
    return None
