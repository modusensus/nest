"""工作台 MCP server（stdio / JSON-RPC，零依赖手写实现）。

被 Claude Code 通过 --mcp-config 拉起，作为子进程运行：stdin 收 JSON-RPC 请求，
stdout 回 JSON-RPC 响应。工具执行复用 agent_tools.dispatch，与对话端点完全一致。

注意：在 TRAE 沙箱下，claude 写 MCP 日志会被拦截导致 MCP server 标记为 failed；
对话端点因此改用「claude -p 文本协议」走 agent_tools.dispatch。本文件保留，供在
非沙箱环境（本机直连 / Docker）下使用标准 MCP 集成。
"""
import json
import sys
import traceback
from pathlib import Path

# 确保能 import app 包（无论以 `python -m app.mcp_server` 还是直接运行）
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from . import agent_tools  # noqa: E402


# ------------------------------------------------------------------
# 工具 schema（供 tools/list 返回结构化参数定义）
# ------------------------------------------------------------------

SCHEMAS = {
    "list_projects": ("列出所有进行中的项目及其任务完成情况", {}),
    "create_project": ("创建一个新项目", {
        "name": ("项目名称", "string"),
        "description": ("项目描述，可省略", "string"),
    }, ["name"]),
    "update_project": ("更新项目名称/描述/状态", {
        "project_id": ("项目 ID", "string"),
        "name": ("新名称", "string"),
        "description": ("新描述", "string"),
        "status": ("状态：active / archived", "string"),
    }, ["project_id"]),
    "delete_project": ("删除项目（其下任务解除关联，不删除）", {"project_id": ("项目 ID", "string")}, ["project_id"]),
    "list_tasks": ("查询任务列表，可按项目名或状态(todo/doing/done)过滤", {
        "project_name": ("按项目名过滤，可省略", "string"),
        "status": ("按状态过滤，可省略", "string"),
    }),
    "create_task": ("创建任务，可归属到某个项目", {
        "title": ("任务标题", "string"),
        "project_name": ("所属项目名称，可省略", "string"),
        "due_date": ("截止日期 YYYY-MM-DD，可省略", "string"),
    }, ["title"]),
    "update_task": ("更新任务状态/标题/截止日期（task_title_or_id 支持模糊匹配标题）", {
        "task_title_or_id": ("任务标题或 ID", "string"),
        "status": ("新状态：todo / doing / done", "string"),
        "title": ("新标题", "string"),
        "due_date": ("新截止日期", "string"),
    }, ["task_title_or_id"]),
    "delete_task": ("删除任务", {"task_id": ("任务 ID", "string")}, ["task_id"]),
    "list_habits": ("列出所有打卡习惯、连续天数和今日是否已打卡", {}),
    "habit_logs": ("查询近期打卡记录", {"days": ("最近多少天，默认 90", "number")}),
    "create_habit": ("新建一个打卡习惯", {"name": ("习惯名称，如：健身、阅读", "string")}, ["name"]),
    "delete_habit": ("删除习惯", {"habit_id": ("习惯 ID", "string")}, ["habit_id"]),
    "checkin": ("为习惯打卡（默认今天，重复调用取消）", {
        "habit_name": ("习惯名称（支持模糊匹配）", "string"),
        "date": ("日期 YYYY-MM-DD，可省略为今天", "string"),
    }, ["habit_name"]),
    "list_articles": ("列出所有文章（不含正文）", {}),
    "get_article": ("获取单篇文章的完整正文", {"article_id": ("文章 ID", "string")}, ["article_id"]),
    "create_article": ("新建文章", {"title": ("标题", "string"), "content": ("正文（支持 Markdown）", "string")}),
    "update_article": ("更新文章标题/正文/状态(draft/published)", {
        "article_id": ("文章 ID", "string"),
        "title": ("新标题", "string"),
        "content": ("新正文", "string"),
        "status": ("状态：draft / published", "string"),
    }, ["article_id"]),
    "delete_article": ("删除文章", {"article_id": ("文章 ID", "string")}, ["article_id"]),
    "list_countdowns": ("列出所有目标倒计时及剩余天数", {}),
    "create_countdown": ("新建目标倒计时", {"title": ("标题，如：考研", "string"), "target_date": ("目标日期 YYYY-MM-DD", "string")}, ["title", "target_date"]),
    "delete_countdown": ("删除倒计时", {"countdown_id": ("倒计时 ID", "string")}, ["countdown_id"]),
    "get_profile": ("读取个人信息（名称、Agent ID、头像）", {}),
    "update_profile": ("更新个人名称 / Agent ID", {"name": ("名称", "string"), "agent_id": ("Agent ID", "string")}, ["name"]),
    "get_overview": ("获取工作台整体概况：项目、进行中任务、今日打卡", {}),
}


def _props(props):
    return {k: {"type": t, "description": d} for k, (d, t) in props.items()} if props else {}


def _build_tool_list():
    tools = []
    for name, spec in SCHEMAS.items():
        if len(spec) == 3:
            desc, props, required = spec
        else:
            desc, props = spec
            required = None
        schema = {"type": "object", "properties": _props(props)}
        if required:
            schema["required"] = required
        tools.append({"name": name, "description": desc, "inputSchema": schema})
    return tools


# ------------------------------------------------------------------
# JSON-RPC 循环（强制 UTF-8 读写，避免 Windows cp936）
# ------------------------------------------------------------------

def _send(obj):
    sys.stdout.buffer.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def _result(req_id, result):
    _send({"jsonrpc": "2.0", "id": req_id, "result": result})


def _error(req_id, code, message):
    _send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def handle(line):
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return
    if not isinstance(msg, dict) or "method" not in msg:
        return
    req_id = msg.get("id")
    method, params = msg["method"], msg.get("params") or {}

    if method == "initialize":
        _result(req_id, {
            "protocolVersion": params.get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "workbench", "version": "1.0"},
        })
        return
    if method == "notifications/initialized":
        return
    if method == "ping":
        _result(req_id, {})
        return
    if method == "tools/list":
        _result(req_id, {"tools": _build_tool_list()})
        return
    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments") or {}
        result = agent_tools.dispatch(name, args)
        _result(req_id, {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, default=str)}],
            "isError": bool(result.get("error")),
        })
        return
    if req_id is not None:
        _error(req_id, -32601, f"未实现的方法：{method}")


def main():
    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            handle(line)
        except Exception:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":
    main()
