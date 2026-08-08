"""Demo 用的 OpenAI 兼容模拟模型服务（支持 function calling）。

仅用于本地演示个人 AI 工作台的流式聊天与 Agent 工具调用效果，不调用任何真实模型。
启动：python mock_llm.py  （监听 :9000）

演示脚本（按用户消息关键词触发）：
- 包含「打卡」→ 调用 checkin 工具（识别 健身/阅读/早起 等常见习惯名）
- 包含「建/创建」+「项目」→ 调用 create_project
- 包含「任务」+「建/加/创建」→ 调用 create_task
- 包含「进展/概况/怎么样/汇报」→ 调用 get_overview
- 收到 tool 结果后 → 生成中文确认文本
- 其他消息 → 普通流式回复
"""
import json
import re
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

KNOWN_HABITS = ["健身", "阅读", "早起", "跑步", "学习", "冥想", "喝水"]

PLAIN_REPLY = (
    "我是演示模型（本地模拟服务，不消耗真实额度）。\n\n"
    "可以试试这些指令，我会调用工作台工具真的去执行：\n"
    "· 「帮我建一个网站项目」\n"
    "· 「给网站项目加个任务：写部署文档」\n"
    "· 「今天健身打卡」\n"
    "· 「我现在进展怎么样」"
)


def last_user_message(messages):
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
        if msg.get("role") == "tool":
            return ""
    return ""


def decide_tool_call(user_msg):
    """根据演示关键词返回 (tool_name, arguments) 或 None。"""
    if "打卡" in user_msg:
        habit = next((h for h in KNOWN_HABITS if h in user_msg), None)
        if not habit:
            match = re.search(r"([一-龥]{1,6})打卡", user_msg)
            habit = match.group(1) if match else "健身"
        return "checkin", {"habit_name": habit}
    if any(w in user_msg for w in ("进展", "概况", "怎么样", "汇报", "总结")):
        return "get_overview", {}
    if "项目" in user_msg and any(w in user_msg for w in ("建", "创建", "新建")):
        match = re.search(r"(?:建|创建|新建)(?:一个|个)?([一-龥A-Za-z0-9]{1,12}?)项目", user_msg)
        name = (match.group(1) + "项目") if match and match.group(1) else "新项目"
        return "create_project", {"name": name, "description": "由演示 Agent 创建"}
    if "任务" in user_msg and any(w in user_msg for w in ("建", "加", "创建", "新建")):
        match = re.search(r"任务[：:是为]?\s*([一-龥A-Za-z0-9]{2,20})", user_msg)
        title = match.group(1) if match else "新任务"
        args = {"title": title}
        match = re.search(r"(?:给|到)([一-龥A-Za-z0-9]{1,12}?项目)", user_msg)
        if match:
            args["project_name"] = match.group(1)
        return "create_task", args
    return None


def summarize_tool_result(result):
    """把工具执行结果转成一句中文确认。"""
    if result.get("error"):
        return f"操作没有成功：{result['error']}"
    if "checked" in result:
        action = "完成" if result["checked"] else "取消"
        return f"好的，已为你{action}「{result['habit']}」{result['date']} 的打卡。右侧打卡面板已经同步更新。"
    if "project" in result:
        return f"项目「{result['project']['name']}」已创建，可以在「项目」页面看到它。"
    if "task" in result:
        return f"任务「{result['task']['title']}」已就绪（状态：{result['task']['status']}），任务看板已同步。"
    if "projects" in result or "tasks_doing" in result:
        projects = result.get("projects", [])
        doing = result.get("tasks_doing", [])
        habits = result.get("habits", [])
        lines = ["这是你目前的工作台概况："]
        for p in projects:
            lines.append(f"· 项目「{p['name']}」：完成 {p['task_done']}/{p['task_total']} 个任务")
        lines.append(f"· 进行中的任务 {len(doing)} 个")
        done = sum(1 for h in habits if h.get("checked_today"))
        lines.append(f"· 今日打卡 {done}/{len(habits)} 个习惯")
        return "\n".join(lines)
    return "操作已完成。"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _sse(self, payload):
        self.wfile.write(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _stream_text(self, text):
        for i in range(0, len(text), 4):
            self._sse({"choices": [{"delta": {"content": text[i:i + 4]}}]})
            time.sleep(0.03)

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        messages = body.get("messages", [])

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        if messages and messages[-1].get("role") == "tool":
            # 第二轮：根据工具结果生成确认文本
            try:
                result = json.loads(messages[-1].get("content") or "{}")
            except json.JSONDecodeError:
                result = {}
            self._stream_text(summarize_tool_result(result))
        else:
            tool_call = decide_tool_call(last_user_message(messages))
            if tool_call and body.get("tools"):
                name, args = tool_call
                self._sse({"choices": [{"delta": {"tool_calls": [{
                    "index": 0,
                    "id": "call_demo_1",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
                }]}}]})
            else:
                self._stream_text(PLAIN_REPLY)

        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


if __name__ == "__main__":
    print("mock llm (function-calling demo) on :9000")
    HTTPServer(("127.0.0.1", 9000), Handler).serve_forever()
