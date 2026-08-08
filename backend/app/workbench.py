"""工作台业务模块：项目、任务、打卡的 REST API 与 Agent 工具。

- REST 路由挂在 /api 下，供前端视图直接调用。
- TOOLS / run_tool 供聊天接口做 function calling，让 Agent 能操作同一套数据。
"""
import json
import uuid
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .database import DATA_DIR, get_connection

router = APIRouter(prefix="/api")


def _row(row):
    return dict(row) if row else None


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------- 数据访问 ----------

def list_projects() -> list[dict]:
    with get_connection() as db:
        rows = db.execute(
            """SELECT p.*,
                      COUNT(t.id) AS task_total,
                      SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS task_done
               FROM projects p LEFT JOIN tasks t ON t.project_id = p.id
               WHERE p.status = 'active'
               GROUP BY p.id ORDER BY p.updated_at DESC"""
        ).fetchall()
    result = []
    for row in rows:
        item = _row(row)
        item["task_total"] = item["task_total"] or 0
        item["task_done"] = item["task_done"] or 0
        result.append(item)
    return result


def create_project(name: str, description: str = "") -> dict:
    name = name.strip()
    if not name:
        raise ValueError("项目名不能为空")
    with get_connection() as db:
        project_id = _new_id()
        db.execute("INSERT INTO projects (id, name, description) VALUES (?, ?, ?)", (project_id, name, description.strip()))
        return _row(db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())


def find_project(db, name_or_id: str):
    """按 id 精确匹配，或按名称模糊匹配（取最近更新的一个）。"""
    row = db.execute("SELECT * FROM projects WHERE id = ?", (name_or_id,)).fetchone()
    if row:
        return row
    return db.execute(
        "SELECT * FROM projects WHERE name LIKE ? ORDER BY updated_at DESC LIMIT 1", (f"%{name_or_id}%",)
    ).fetchone()


def list_tasks(project_name: str = "", status: str = "") -> list[dict]:
    sql = """SELECT t.*, p.name AS project_name FROM tasks t
             LEFT JOIN projects p ON p.id = t.project_id"""
    conditions, params = [], []
    if project_name:
        conditions.append("p.name LIKE ?")
        params.append(f"%{project_name}%")
    if status:
        conditions.append("t.status = ?")
        params.append(status)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY CASE t.status WHEN 'doing' THEN 0 WHEN 'todo' THEN 1 ELSE 2 END, t.updated_at DESC"
    with get_connection() as db:
        return [_row(r) for r in db.execute(sql, params).fetchall()]


def create_task(title: str, project_name: str = "", due_date: str = "") -> dict:
    title = title.strip()
    if not title:
        raise ValueError("任务标题不能为空")
    with get_connection() as db:
        project_id = None
        if project_name:
            project = find_project(db, project_name)
            if not project:
                raise ValueError(f"找不到项目「{project_name}」")
            project_id = project["id"]
        task_id = _new_id()
        db.execute(
            "INSERT INTO tasks (id, project_id, title, due_date) VALUES (?, ?, ?, ?)",
            (task_id, project_id, title, due_date.strip()),
        )
        return _row(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())


def update_task(task_title_or_id: str, status: str = "", title: str = "", due_date: str = "") -> dict:
    if status and status not in {"todo", "doing", "done"}:
        raise ValueError("状态只能是 todo / doing / done")
    with get_connection() as db:
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_title_or_id,)).fetchone()
        if not row:
            row = db.execute(
                "SELECT * FROM tasks WHERE title LIKE ? ORDER BY updated_at DESC LIMIT 1", (f"%{task_title_or_id}%",)
            ).fetchone()
        if not row:
            raise ValueError(f"找不到任务「{task_title_or_id}」")
        fields, values = [], []
        if status:
            fields.append("status = ?"); values.append(status)
        if title.strip():
            fields.append("title = ?"); values.append(title.strip())
        if due_date:
            fields.append("due_date = ?"); values.append(due_date.strip())
        if not fields:
            raise ValueError("没有要更新的内容")
        values.append(row["id"])
        db.execute(f"UPDATE tasks SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
        return _row(db.execute("SELECT * FROM tasks WHERE id = ?", (row["id"],)).fetchone())


def list_habits() -> list[dict]:
    today = date.today().isoformat()
    with get_connection() as db:
        habits = [_row(r) for r in db.execute("SELECT * FROM habits ORDER BY created_at").fetchall()]
        for habit in habits:
            logs = db.execute("SELECT check_date FROM habit_logs WHERE habit_id = ?", (habit["id"],)).fetchall()
            days = {r["check_date"] for r in logs}
            habit["checked_today"] = today in days
            habit["total_days"] = len(days)
            streak = 0
            cursor = date.today() if today in days else date.today() - timedelta(days=1)
            while cursor.isoformat() in days:
                streak += 1
                cursor -= timedelta(days=1)
            habit["streak"] = streak
            start = date.today() - timedelta(days=34)
            habit["recent"] = sorted(d for d in days if d >= start.isoformat())
    return habits


def create_habit(name: str) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("习惯名称不能为空")
    with get_connection() as db:
        habit_id = _new_id()
        db.execute("INSERT INTO habits (id, name) VALUES (?, ?)", (habit_id, name))
        return _row(db.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone())


def toggle_checkin(habit_name_or_id: str, check_date: str = "") -> dict:
    target_date = check_date or date.today().isoformat()
    with get_connection() as db:
        habit = db.execute("SELECT * FROM habits WHERE id = ?", (habit_name_or_id,)).fetchone()
        if not habit:
            habit = db.execute(
                "SELECT * FROM habits WHERE name LIKE ? ORDER BY created_at LIMIT 1", (f"%{habit_name_or_id}%",)
            ).fetchone()
        if not habit:
            raise ValueError(f"找不到习惯「{habit_name_or_id}」，可以先创建它")
        existing = db.execute(
            "SELECT id FROM habit_logs WHERE habit_id = ? AND check_date = ?", (habit["id"], target_date)
        ).fetchone()
        if existing:
            db.execute("DELETE FROM habit_logs WHERE id = ?", (existing["id"],))
            checked = False
        else:
            db.execute(
                "INSERT INTO habit_logs (id, habit_id, check_date) VALUES (?, ?, ?)",
                (_new_id(), habit["id"], target_date),
            )
            checked = True
    return {"habit": habit["name"], "date": target_date, "checked": checked}


def get_overview() -> dict:
    """右侧状态面板 / Agent 共用的汇总数据。"""
    projects = list_projects()
    tasks = list_tasks()
    habits = list_habits()
    return {
        "projects": [
            {"id": p["id"], "name": p["name"], "task_total": p["task_total"], "task_done": p["task_done"]}
            for p in projects
        ],
        "tasks_doing": [t for t in tasks if t["status"] == "doing"],
        "tasks_todo_count": sum(1 for t in tasks if t["status"] == "todo"),
        "tasks_done_count": sum(1 for t in tasks if t["status"] == "done"),
        "habits": [
            {"id": h["id"], "name": h["name"], "streak": h["streak"], "checked_today": h["checked_today"]}
            for h in habits
        ],
    }


# ---------- REST API ----------

class ProjectIn(BaseModel):
    name: str
    description: str = ""


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class TaskIn(BaseModel):
    title: str
    project_id: str | None = None
    due_date: str = ""


class TaskPatch(BaseModel):
    title: str | None = None
    status: str | None = None
    project_id: str | None = None
    due_date: str | None = None


class HabitIn(BaseModel):
    name: str


class CheckinIn(BaseModel):
    date: str = ""


@router.get("/projects")
def api_list_projects():
    return list_projects()


@router.post("/projects", status_code=201)
def api_create_project(payload: ProjectIn):
    try:
        return create_project(payload.name, payload.description)
    except ValueError as error:
        raise HTTPException(400, str(error))


@router.patch("/projects/{project_id}")
def api_update_project(project_id: str, payload: ProjectPatch):
    fields, values = [], []
    if payload.name is not None:
        fields.append("name = ?"); values.append(payload.name.strip() or "未命名项目")
    if payload.description is not None:
        fields.append("description = ?"); values.append(payload.description)
    if payload.status is not None:
        if payload.status not in {"active", "archived"}:
            raise HTTPException(400, "状态只能是 active / archived")
        fields.append("status = ?"); values.append(payload.status)
    if not fields:
        raise HTTPException(400, "没有可更新的内容")
    values.append(project_id)
    with get_connection() as db:
        result = db.execute(f"UPDATE projects SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
        if not result.rowcount:
            raise HTTPException(404, "项目不存在")
        return _row(db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())


@router.delete("/projects/{project_id}")
def api_delete_project(project_id: str):
    with get_connection() as db:
        db.execute("UPDATE tasks SET project_id = NULL WHERE project_id = ?", (project_id,))
        result = db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        if not result.rowcount:
            raise HTTPException(404, "项目不存在")
    return {"ok": True}


@router.get("/tasks")
def api_list_tasks(project_id: str = "", status: str = ""):
    if project_id:
        with get_connection() as db:
            project = find_project(db, project_id)
            if not project:
                return []
        return list_tasks(project_name=project["name"], status=status)
    return list_tasks(status=status)


@router.post("/tasks", status_code=201)
def api_create_task(payload: TaskIn):
    try:
        project_name = ""
        if payload.project_id:
            with get_connection() as db:
                project = find_project(db, payload.project_id)
                if not project:
                    raise HTTPException(404, "项目不存在")
                project_name = project["name"]
        return create_task(payload.title, project_name, payload.due_date)
    except ValueError as error:
        raise HTTPException(400, str(error))


@router.patch("/tasks/{task_id}")
def api_update_task(task_id: str, payload: TaskPatch):
    try:
        if payload.project_id is not None:
            with get_connection() as db:
                if payload.project_id and not find_project(db, payload.project_id):
                    raise HTTPException(404, "项目不存在")
                current = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if not current:
                    raise HTTPException(404, "任务不存在")
                db.execute("UPDATE tasks SET project_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                           (payload.project_id or None, task_id))
        return update_task(task_id, status=payload.status or "", title=payload.title or "", due_date=payload.due_date or "")
    except ValueError as error:
        raise HTTPException(400, str(error))


@router.delete("/tasks/{task_id}")
def api_delete_task(task_id: str):
    with get_connection() as db:
        result = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if not result.rowcount:
            raise HTTPException(404, "任务不存在")
    return {"ok": True}


@router.get("/habits")
def api_list_habits():
    return list_habits()


@router.post("/habits", status_code=201)
def api_create_habit(payload: HabitIn):
    try:
        return create_habit(payload.name)
    except ValueError as error:
        raise HTTPException(400, str(error))


@router.delete("/habits/{habit_id}")
def api_delete_habit(habit_id: str):
    with get_connection() as db:
        result = db.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
        if not result.rowcount:
            raise HTTPException(404, "习惯不存在")
    return {"ok": True}


@router.post("/habits/{habit_id}/checkin")
def api_checkin(habit_id: str, payload: CheckinIn):
    try:
        return toggle_checkin(habit_id, payload.date)
    except ValueError as error:
        raise HTTPException(400, str(error))


@router.get("/habit-logs")
def api_habit_logs(days: int = 371):
    """聚合所有习惯的打卡记录，按天计数，供总热力图使用。"""
    since = (date.today() - timedelta(days=max(1, min(days, 400)) - 1)).isoformat()
    with get_connection() as db:
        rows = db.execute(
            "SELECT check_date, COUNT(*) AS count FROM habit_logs WHERE check_date >= ? GROUP BY check_date",
            (since,),
        ).fetchall()
    return [{"date": r["check_date"], "count": r["count"]} for r in rows]


# ---------- 个人信息 ----------

DEFAULT_PROFILE = {"name": "Modusensus' Home", "agent_id": "Ivresse"}
AVATAR_TYPES = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"GIF8": ".gif",
    b"RIFF": ".webp",
}


def get_profile() -> dict:
    with get_connection() as db:
        row = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        if not row:
            avatar_ext = ".jpg" if (DATA_DIR / "avatar.jpg").is_file() else ""
            db.execute(
                "INSERT INTO profile (id, name, agent_id, avatar_ext) VALUES (1, ?, ?, ?)",
                (DEFAULT_PROFILE["name"], DEFAULT_PROFILE["agent_id"], avatar_ext),
            )
            row = db.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    profile = _row(row)
    profile["avatar_url"] = (
        f"/api/profile/avatar?v={profile['updated_at'].replace(' ', 'T')}" if profile["avatar_ext"] else ""
    )
    return profile


class ProfileIn(BaseModel):
    name: str
    agent_id: str = ""


@router.get("/profile")
def api_get_profile():
    profile = get_profile()
    return {"name": profile["name"], "agent_id": profile["agent_id"], "avatar_url": profile["avatar_url"]}


@router.put("/profile")
def api_update_profile(payload: ProfileIn):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    with get_connection() as db:
        get_profile()
        db.execute(
            "UPDATE profile SET name = ?, agent_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            (name, payload.agent_id.strip()),
        )
    return api_get_profile()


@router.post("/profile/avatar")
async def api_upload_avatar(request: Request):
    """接收原始图片字节（前端直接 send File），按魔数识别格式保存。"""
    data = await request.body()
    if not data or len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "图片不能为空且不能超过 5MB")
    ext = next((e for magic, e in AVATAR_TYPES.items() if data.startswith(magic)), None)
    if not ext:
        raise HTTPException(400, "只支持 JPG / PNG / GIF / WebP 图片")
    for old in DATA_DIR.glob("avatar.*"):
        old.unlink()
    (DATA_DIR / f"avatar{ext}").write_bytes(data)
    with get_connection() as db:
        get_profile()
        db.execute("UPDATE profile SET avatar_ext = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (ext,))
    return api_get_profile()


@router.get("/profile/avatar")
def api_get_avatar():
    profile = get_profile()
    target = DATA_DIR / f"avatar{profile['avatar_ext']}"
    if not profile["avatar_ext"] or not target.is_file():
        raise HTTPException(404, "还没有设置头像")
    return FileResponse(target, headers={"Cache-Control": "no-cache"})


# ---------- 写作（公众号 / 博客文章） ----------

ARTICLE_IMAGE_DIR = DATA_DIR / "article-images"


def _article_with_platforms(row) -> dict:
    article = _row(row)
    try:
        article["platforms"] = json.loads(article.get("platforms") or "{}")
    except json.JSONDecodeError:
        article["platforms"] = {}
    return article


class ArticleIn(BaseModel):
    title: str = "未命名文章"
    content: str = ""


class ArticlePatch(BaseModel):
    title: str | None = None
    content: str | None = None
    status: str | None = None
    platforms: dict | None = None


@router.get("/articles")
def api_list_articles():
    with get_connection() as db:
        rows = db.execute(
            "SELECT id, title, status, platforms, created_at, updated_at FROM articles ORDER BY updated_at DESC"
        ).fetchall()
    return [_article_with_platforms(r) for r in rows]


@router.post("/articles", status_code=201)
def api_create_article(payload: ArticleIn):
    article_id = _new_id()
    with get_connection() as db:
        db.execute(
            "INSERT INTO articles (id, title, content) VALUES (?, ?, ?)",
            (article_id, payload.title.strip() or "未命名文章", payload.content),
        )
        row = db.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    return _article_with_platforms(row)


@router.get("/articles/{article_id}")
def api_get_article(article_id: str):
    with get_connection() as db:
        row = db.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if not row:
        raise HTTPException(404, "文章不存在")
    return _article_with_platforms(row)


@router.patch("/articles/{article_id}")
def api_update_article(article_id: str, payload: ArticlePatch):
    fields, values = [], []
    if payload.title is not None:
        fields.append("title = ?"); values.append(payload.title.strip() or "未命名文章")
    if payload.content is not None:
        fields.append("content = ?"); values.append(payload.content)
    if payload.status is not None:
        if payload.status not in {"draft", "published"}:
            raise HTTPException(400, "状态只能是 draft / published")
        fields.append("status = ?"); values.append(payload.status)
    if payload.platforms is not None:
        fields.append("platforms = ?"); values.append(json.dumps(payload.platforms, ensure_ascii=False))
    if not fields:
        raise HTTPException(400, "没有可更新的内容")
    values.append(article_id)
    with get_connection() as db:
        result = db.execute(f"UPDATE articles SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
        if not result.rowcount:
            raise HTTPException(404, "文章不存在")
        row = db.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    return _article_with_platforms(row)


@router.delete("/articles/{article_id}")
def api_delete_article(article_id: str):
    with get_connection() as db:
        result = db.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        if not result.rowcount:
            raise HTTPException(404, "文章不存在")
    return {"ok": True}


@router.post("/articles/images", status_code=201)
async def api_upload_article_image(request: Request):
    """文章配图上传：原始字节 + 魔数识别，返回可引用的图片 URL。"""
    data = await request.body()
    if not data or len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片不能为空且不能超过 10MB")
    ext = next((e for magic, e in AVATAR_TYPES.items() if data.startswith(magic)), None)
    if not ext:
        raise HTTPException(400, "只支持 JPG / PNG / GIF / WebP 图片")
    ARTICLE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{_new_id()}{ext}"
    (ARTICLE_IMAGE_DIR / name).write_bytes(data)
    return {"url": f"/api/articles/images/{name}"}


@router.get("/articles/images/{name}")
def api_get_article_image(name: str):
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "非法文件名")
    target = (ARTICLE_IMAGE_DIR / name).resolve()
    if ARTICLE_IMAGE_DIR.resolve() not in target.parents or not target.is_file():
        raise HTTPException(404, "图片不存在")
    return FileResponse(target)


# ---------- 目标日倒计时 ----------

class CountdownIn(BaseModel):
    title: str
    target_date: str  # YYYY-MM-DD


@router.get("/countdowns")
def api_list_countdowns():
    with get_connection() as db:
        rows = db.execute("SELECT * FROM countdowns ORDER BY target_date").fetchall()
    return [_row(r) for r in rows]


@router.post("/countdowns", status_code=201)
def api_create_countdown(payload: CountdownIn):
    title = payload.title.strip()
    try:
        date.fromisoformat(payload.target_date)
    except ValueError:
        raise HTTPException(400, "目标日期格式应为 YYYY-MM-DD")
    if not title:
        raise HTTPException(400, "标题不能为空")
    countdown_id = _new_id()
    with get_connection() as db:
        db.execute("INSERT INTO countdowns (id, title, target_date) VALUES (?, ?, ?)",
                   (countdown_id, title, payload.target_date))
        return _row(db.execute("SELECT * FROM countdowns WHERE id = ?", (countdown_id,)).fetchone())


@router.delete("/countdowns/{countdown_id}")
def api_delete_countdown(countdown_id: str):
    with get_connection() as db:
        result = db.execute("DELETE FROM countdowns WHERE id = ?", (countdown_id,))
        if not result.rowcount:
            raise HTTPException(404, "倒计时不存在")
    return {"ok": True}


@router.get("/overview")
def api_overview():
    return get_overview()


# ---------- Agent 工具（function calling） ----------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": "列出所有进行中的项目及任务完成情况",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_project",
            "description": "创建一个新项目",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "项目名称"},
                    "description": {"type": "string", "description": "项目描述，可省略"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "创建任务，可以归属到某个项目",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "任务标题"},
                    "project_name": {"type": "string", "description": "所属项目名称，可省略"},
                    "due_date": {"type": "string", "description": "截止日期，格式 YYYY-MM-DD，可省略"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "查询任务列表，可按项目名或状态过滤",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "按项目名过滤，可省略"},
                    "status": {"type": "string", "enum": ["todo", "doing", "done"], "description": "按状态过滤，可省略"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "更新任务状态（开始/完成/放回待办）或修改标题",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_title": {"type": "string", "description": "任务标题（支持模糊匹配）"},
                    "status": {"type": "string", "enum": ["todo", "doing", "done"], "description": "新状态"},
                },
                "required": ["task_title", "status"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_habits",
            "description": "列出所有打卡习惯、连续天数和今日是否已打卡",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_habit",
            "description": "新建一个打卡习惯",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "习惯名称，如：健身、阅读"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "checkin",
            "description": "为某个习惯打今天的卡（重复调用会取消打卡）",
            "parameters": {
                "type": "object",
                "properties": {"habit_name": {"type": "string", "description": "习惯名称（支持模糊匹配）"}},
                "required": ["habit_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_overview",
            "description": "获取工作台整体概况：项目进度、进行中的任务、今日打卡情况",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

TOOL_LABELS = {
    "list_projects": "读取项目列表",
    "create_project": "创建项目",
    "create_task": "创建任务",
    "list_tasks": "查询任务",
    "update_task": "更新任务状态",
    "list_habits": "读取打卡习惯",
    "create_habit": "创建习惯",
    "checkin": "记录打卡",
    "get_overview": "汇总工作台概况",
}


def run_tool(name: str, arguments: str) -> dict:
    """执行一个 Agent 工具，返回可序列化结果（供模型与前端展示）。"""
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {"error": "工具参数解析失败"}
    try:
        if name == "list_projects":
            return {"projects": list_projects()}
        if name == "create_project":
            return {"project": create_project(args.get("name", ""), args.get("description", ""))}
        if name == "create_task":
            return {"task": create_task(args.get("title", ""), args.get("project_name", ""), args.get("due_date", ""))}
        if name == "list_tasks":
            return {"tasks": list_tasks(args.get("project_name", ""), args.get("status", ""))}
        if name == "update_task":
            return {"task": update_task(args.get("task_title", ""), status=args.get("status", ""))}
        if name == "list_habits":
            return {"habits": list_habits()}
        if name == "create_habit":
            return {"habit": create_habit(args.get("name", ""))}
        if name == "checkin":
            return toggle_checkin(args.get("habit_name", ""))
        if name == "get_overview":
            return get_overview()
        return {"error": f"未知工具 {name}"}
    except ValueError as error:
        return {"error": str(error)}
