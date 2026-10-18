"""Loopback-only UI API; no arbitrary command endpoint or external CORS."""
import asyncio
import json
from typing import Literal
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field
from .engine import Engine
from .models import AgentSpec, AgentPack, RunRequest
from .provider import CodexProvider, ProviderError
from .storage import Store, sanitize, now
from .settings import Settings
from .projects import Projects
from .secrets import WindowsSecretStore
from .api_provider import ProviderSettings
from .actions import describe_error, role_title
from . import __version__

class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    instruction: str | None = None
    access_level: Literal["standard", "read-only", "full-access"] | None = None
    confirmed_full_access: bool = False

class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: str = "chatgpt"

class ActionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["allow_once","allow_run","deny","cancel","answer","resume","stop","explain"]
    answers: dict[str,list[str]] = Field(default_factory=dict)
    instruction: str | None = Field(default=None,max_length=10000)
    confirmed: bool = False
    budget: dict[str,int] | None = None

class ProviderChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["codex_chatgpt","openai_api"]
    acknowledge_billing: bool = False

class ProviderKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1,max_length=2400)

class ProjectChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1,max_length=4096)

class ProjectCreate(ProjectChoice):
    name: str = Field(min_length=1,max_length=120)

class ProjectCommands(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commands: dict[str,list[str]]

class Confirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool = False

def create_app(root=None, store=None, provider_factory=None, static_root=None, desktop_context=None, secret_store=None, qa_runner=None):
    root = Path(root or Path(__file__).resolve().parents[1])
    static_root = Path(static_root or root / "codex_team/static")
    db = store or Store(root / ".ai-team" / "team.sqlite3")
    secrets = secret_store or WindowsSecretStore(root)
    engine = Engine(root, db, provider_factory, secret_store=secrets)
    auth = CodexProvider(root)
    providers = ProviderSettings(db,secrets,auth)
    projects = Projects(root,db)
    @asynccontextmanager
    async def lifespan(app):
        engine.acquire_session()
        suite["qa"].recover()
        db.recover()
        yield
        await asyncio.to_thread(suite["architect"].close)
        await asyncio.to_thread(suite["qa"].close)
        await asyncio.to_thread(engine.close)
        auth.close()
        if store is None:
            db.close()
    app = FastAPI(title="Codex Team", lifespan=lifespan)
    app.state.engine, app.state.store = engine, db
    app.state.providers, app.state.projects = providers, projects
    from .suite_api import install_suite
    suite=install_suite(app,root,db,engine,qa_runner)
    from .task_drafts import create_draft_router
    app.include_router(create_draft_router(db))
    from .productivity import create_productivity_router
    app.include_router(create_productivity_router(db))
    @app.get("/health")
    def health():
        import shutil
        import sqlite3
        database_ok = True
        try:
            with db.lock:
                db.db.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except sqlite3.Error:
            database_ok = False
        git_ok = bool(shutil.which("git"))
        result = {"status": "ok" if database_ok and git_ok else "degraded", "app": "Codex Team", "version": (desktop_context or {}).get("version", __version__),
                "instance": (desktop_context or {}).get("instance"), "active_runs": list(engine.active),
                "checks": {"backend": True, "database": database_ok, "git": git_ok, "codex": True}}
        return JSONResponse(result, status_code=200 if database_ok and git_ok else 503)

    @app.post("/desktop/shutdown")
    def desktop_shutdown(request: Request):
        import secrets
        if not desktop_context or not secrets.compare_digest(request.headers.get("X-Codex-Team-Desktop", ""), desktop_context["token"]):
            raise HTTPException(status_code=403, detail="Это действие доступно только настольному приложению.")
        desktop_context["shutdown"]()
        return {"ok": True}
    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.headers.get("host", "")
        parsed = urlparse("http://" + host)
        if parsed.hostname not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "Разрешено подключение только к локальному приложению."}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != "http://" + host:
            return JSONResponse({"detail": "Запросы из другого источника запрещены."}, status_code=403)
        if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return JSONResponse({"detail": "Требуется формат application/json."}, status_code=415)
            if request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}:
                return JSONResponse({"detail": "Межсайтовые запросы запрещены."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(ValueError)
    async def bad_request(request, exc):
        return JSONResponse({"detail":sanitize(str(exc)),"error":describe_error("CONFIGURATION_REQUIRED",str(exc))}, status_code=400)
    @app.exception_handler(RequestValidationError)
    async def invalid_input(request,exc):
        # Keep the existing detail string and expose only safe structured metadata
        # for localized field guidance. Pydantic's raw input must never be echoed.
        errors=[]
        for error in exc.errors()[:20]:
            context={key:value for key,value in error.get("ctx",{}).items()
                     if key in {"min_length","max_length","ge","le","gt","lt"} and isinstance(value,(int,float))}
            errors.append({"loc":error["loc"],"type":error["type"],"msg":sanitize(error["msg"]),"ctx":context})
        return JSONResponse({"detail":"Проверьте поля ввода.","validation_errors":errors},status_code=422)
    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({"detail": "Запрошенный элемент не найден."}, status_code=404)

    @app.exception_handler(ProviderError)
    async def provider_failed(request, exc):
        message = sanitize(str(exc))
        return JSONResponse({"detail": message, "error": describe_error(exc.code, message)}, status_code=400)

    @app.exception_handler(Exception)
    async def unexpected_failure(request, exc):
        message = "Не удалось завершить запрос. Откройте диагностику и повторите попытку."
        return JSONResponse({"detail": message, "error": describe_error("FATAL_ERROR", message)}, status_code=500)

    def effective_settings():
        # Status is the first settings consumer during startup; expose the same
        # defaults as the settings page without overwriting legacy preferences.
        return {**Settings().model_dump(exclude={"execution_backend"}),
                "execution_backend":"codex_chatgpt", **db.settings()}

    @app.get("/api/status")
    def status():
        try:
            account = auth.account_status()
        except Exception as exc:
            account = {"status": "UNAVAILABLE", "account": None, "error": "Codex не ответил. Проверьте настройки и повторите попытку.","details":sanitize(str(exc))}
        return {"auth": account, "capabilities": auth.capabilities, "settings": effective_settings()}

    @app.post("/api/login")
    def login(body: Login):
        return auth.authenticate(body.method)

    @app.get("/api/models")
    def models():
        if db.settings().get("execution_backend") == "openai_api":
            provider = CodexProvider(root,backend="openai_api",secret_store=secrets)
            try:
                return provider.model_list()
            finally:
                provider.close()
        return auth.model_list()

    @app.get("/api/usage")
    def usage():
        try:
            return auth.read_usage()
        except Exception as exc:
            return {"unavailable": str(exc)}

    @app.get("/api/agents")
    def agents():
        return engine.registry.agents()

    @app.post("/api/agents")
    def agent(body: AgentSpec):
        if body.name in {"coordinator", "analyst", "qa", "reviewer", "architect", "final-audit"} and body.permission != "read-only":
            raise ValueError("Основные роли проверки должны иметь доступ только для чтения.")
        existing = next((a for a in db.agents() if a["name"] == body.name), None)
        if existing:
            raise ValueError("Агент с таким идентификатором уже существует. Измените его инструкции или выберите другой идентификатор.")
        if (body.permission == "workspace-write" or body.can_network) and not body.confirmed_permissions:
            raise ValueError("Перед сохранением подтвердите доступ пользовательского агента к записи или сети.")
        db.save_agent(body.model_dump())
        return body.model_dump()

    @app.get("/api/packs")
    def packs():
        return engine.registry.packs()

    @app.put("/api/agents/{name}")
    def update_agent(name: str, body: AgentSpec):
        if body.name != name:
            raise ValueError("Идентификатор агента нельзя изменить.")
        if not any(a["name"] == name for a in db.agents()):
            raise ValueError("Агент не найден.")
        if name in {"coordinator", "analyst", "qa", "reviewer", "architect", "final-audit"} and body.permission != "read-only":
            raise ValueError("Основные роли проверки должны иметь доступ только для чтения.")
        previous = next(a for a in db.agents() if a["name"] == name)
        if ((body.permission == "workspace-write" and previous.get("permission") != "workspace-write") or (body.can_network and not previous.get("can_network",False))) and not body.confirmed_permissions:
            raise ValueError("Перед сохранением подтвердите новые разрешения агента на запись или сеть.")
        from .registry import CORE
        if name in CORE:
            (root / "agents" / f"{name}.md").write_text(body.instructions, encoding="utf-8")
        db.save_agent(body.model_dump())
        return body.model_dump()

    @app.delete("/api/agents/{name}")
    def delete_agent(name: str):
        from .registry import CORE
        if name in CORE:
            raise ValueError("Встроенные агенты защищены. Создайте копию роли или отключите её.")
        if not any(a["name"]==name for a in db.agents()):
            raise KeyError(name)
        references=[p["name"] for p in engine.registry.packs() if name in p.get("agents",[]) or name in p.get("specialists",[])]
        if references:
            raise ValueError("Сначала удалите агента из наборов: " + ", ".join(references))
        db.delete_agent(name)
        return {"ok":True}

    @app.post("/api/packs")
    def create_pack(body: AgentPack):
        if any(p["name"]==body.name for p in engine.registry.packs()):
            raise ValueError("Набор с таким идентификатором уже существует.")
        engine.registry.save_pack(body.model_dump())
        return body.model_dump()

    @app.put("/api/packs/{name}")
    def update_pack(name: str, body: AgentPack):
        if name != body.name:
            raise ValueError("Идентификатор набора нельзя изменить.")
        if not any(p["name"]==name for p in engine.registry.packs()):
            raise KeyError(name)
        engine.registry.save_pack(body.model_dump())
        return body.model_dump()

    @app.delete("/api/packs/{name}")
    def delete_pack(name: str):
        pack = next((p for p in engine.registry.packs() if p["name"]==name),None)
        if not pack:
            raise KeyError(name)
        if pack.get("builtin"):
            raise ValueError("Встроенные наборы защищены. Создайте копию, которую можно будет удалить.")
        db.delete_pack(name)
        return {"ok":True}

    @app.get("/api/settings")
    def get_settings():
        return effective_settings()

    @app.post("/api/settings")
    def settings(body: Settings):
        changes = body.model_dump(exclude_unset=True)
        if "execution_backend" in changes and changes["execution_backend"] != db.settings().get("execution_backend","codex_chatgpt"):
            raise ValueError("Смена провайдера через этот запрос запрещена. Используйте выбор ИИ-провайдера с подтверждением условий оплаты.")
        # Nested preferences remain partial as well.
        for key in ("notifications","permission_policy","role_model_defaults"):
            if key in changes:
                changes[key] = {**db.settings().get(key,{}),**changes[key]}
        db.save_settings(changes)
        return db.settings()

    @app.get("/api/providers")
    def provider_status():
        return providers.status()

    def idle_provider_change():
        if engine.active:
            raise ValueError("Приостановите или остановите активный запуск перед сменой провайдера или его учётных данных.")

    @app.post("/api/providers/select")
    def select_provider(body: ProviderChoice):
        idle_provider_change()
        return providers.select(body.provider,body.acknowledge_billing)

    @app.post("/api/providers/openai/key")
    def save_key(body: ProviderKey):
        idle_provider_change()
        return providers.save(body.key)

    @app.delete("/api/providers/openai/key")
    def remove_key():
        idle_provider_change()
        return providers.remove()

    @app.post("/api/providers/openai/test")
    def test_key():
        result = providers.test()
        if result["status"] == "ERROR":
            raise ValueError(result["error"])
        return result

    @app.get("/api/actions")
    def actions(run_id: str | None=None,status: str | None=None):
        return db.actions(run_id,status)

    @app.post("/api/actions/{action_id}/resolve")
    def resolve_action(action_id: str,body: ActionDecision):
        return engine.resolve_action(action_id,**body.model_dump())

    @app.get("/api/projects")
    def list_projects():
        items=[]
        for project in db.projects():
            try:
                items.append(projects.inspect(project["id"]))
            except Exception as exc:
                items.append({**project,"ready":False,"error":describe_error("CONFIGURATION_REQUIRED",str(exc)),"runtime_status":None})
        return items

    @app.post("/api/projects")
    def add_project(body: ProjectChoice):
        return projects.add(body.path)

    @app.post("/api/projects/create")
    def create_project(body: ProjectCreate):
        return projects.create(body.path, body.name)

    @app.get("/api/projects/{project_id}")
    def inspect_project(project_id: str):
        return projects.inspect(project_id)

    @app.put("/api/projects/{project_id}")
    def save_commands(project_id: str,body: ProjectCommands):
        return projects.save_commands(project_id,body.commands)

    @app.get("/api/projects/{project_id}/diff")
    def project_diff(project_id: str):
        return sanitize(projects.diff(project_id))

    @app.delete("/api/projects/{project_id}")
    def remove_project(project_id: str):
        db.project(project_id)
        db.delete_project(project_id)
        return {"ok":True,"files_retained":True}

    @app.get("/api/runs")
    def runs(summary: bool=False,limit: int=Query(20,ge=1,le=100),offset: int=Query(0,ge=0),q: str=Query("",max_length=1000),state: str="",project: str="",mode: str="",date: str="",archived: bool=False):
        if summary:
            return db.run_page(limit,offset,q,state,project,mode,date,archived)
        return db.runs()

    @app.post("/api/runs")
    def start(body: RunRequest):
        with engine.lock:
            if engine.active:
                raise ValueError("Другой запуск уже выполняется.")
            run = engine.create(body)
            return engine.launch(run["id"])

    @app.get("/api/runs/{run_id}")
    def run(run_id: str):
        return db.run(run_id)

    @app.get("/api/runs/{run_id}/events")
    def events(run_id: str, after: int = Query(0,ge=0),limit: int=Query(100,ge=1,le=500),meaningful: bool=False):
        db.run(run_id)
        if meaningful:
            return db.event_page(run_id,after,limit,True)
        return db.events(run_id, after)

    @app.get("/api/runs/{run_id}/diff")
    def run_diff(run_id: str,offset: int=Query(0,ge=0),limit: int=Query(1000,ge=1,le=5000)):
        run = db.run(run_id)
        lines = run.get("diff","").splitlines(keepends=True)
        return {"diff":"".join(lines[offset:offset+limit]),"diff_stat":run.get("diff_stat",""),"total_lines":len(lines),"has_more":offset+limit<len(lines)}

    @app.post("/api/runs/{run_id}/archive")
    def archive_run(run_id: str):
        with engine.lock:
            if run_id in engine.active:
                raise ValueError("Перед архивацией приостановите или остановите запуск.")
            run=db.run(run_id)
            run["archived"]=True
            db.save_run(run)
        return {"ok":True,"history_retained":True}

    @app.delete("/api/runs/{run_id}/worktree")
    def delete_worktree(run_id: str,body: Confirm):
        if not body.confirmed:
            raise ValueError("Подтвердите удаление чистой неактивной рабочей копии.")
        return engine.delete_worktree(run_id)

    @app.get("/api/desktop/state")
    def desktop_state(after: int=Query(0,ge=0)):
        active=None
        with engine.lock:
            if engine.active:
                run=db.run(next(iter(engine.active)))
                active={k:run.get(k) for k in ("id","state","current_role","stage")}
        kinds=["run_state","action_required","agent_completed"]
        with db.lock:
            maximum=db.db.execute("SELECT COALESCE(max(id),0) FROM events").fetchone()[0]
            rows=db.db.execute("SELECT id,run_id,type,role,payload FROM events WHERE id>? AND type IN (?,?,?) ORDER BY id DESC LIMIT 100",(after,*kinds)).fetchall()
        preferences={"task_complete":True,"needs_attention":True,"stage_complete":False,**db.settings().get("notifications",{})}
        notifications=[]
        for event_id,run_id,kind,role,payload in reversed(rows):
            payload=json.loads(payload)
            state=payload.get("state")
            if kind=="run_state" and state=="DONE" and preferences["task_complete"]:
                title,message="Задача завершена","Результат, тесты и изменения доступны в истории."
            elif kind=="action_required" and preferences["needs_attention"]:
                title,message="Требуется действие",payload.get("title","Требуется ваше решение")
            elif kind=="run_state" and state in {"FAILED","AUTH_REQUIRED","USAGE_LIMIT","USER_DECISION_REQUIRED","STOPPED"} and preferences["needs_attention"]:
                title,message="Запуск требует внимания",describe_error(state,payload.get("error") or state)["title"]
            elif kind=="agent_completed" and payload.get("verdict") in {"FAIL","CHANGES_REQUIRED"} and preferences["needs_attention"]:
                title,message="Проверка выявила проблему",f"{role_title(role)}: просмотрите замечания этого запуска."
            elif kind=="agent_completed" and preferences["stage_complete"]:
                title,message="Этап завершён",f"{role_title(role)}: " + {"PASS":"Проверка пройдена", "FAIL":"Проверка не пройдена", "PLAN":"План подготовлен", "CHANGES_REQUIRED":"Требуются исправления", "DONE":"Готово", "IMPLEMENTED":"Изменения внесены"}.get(payload.get("verdict"), "Этап завершён")
            else:
                continue
            notification_type = "completed" if kind == "run_state" and state == "DONE" else "stage_complete" if kind == "agent_completed" and payload.get("verdict") not in {"FAIL", "CHANGES_REQUIRED"} else "needs_attention"
            notifications.append({"id":event_id,"event_id":event_id,"run_id":run_id,"type":notification_type,"title":title,"message":message})
        pending=[{"id":a["id"],"run_id":a["run_id"]} for a in db.actions(status="pending")]
        return {"active_run":active,"pending_actions":pending,"notifications":notifications,"next_cursor":maximum}

    @app.post("/api/runs/{run_id}/control")
    def control(run_id: str, body: Control):
        if body.action == "set_access":
            if body.instruction is not None:
                raise ValueError("Изменение доступа не отправляет указания агенту.")
            return engine.set_access(run_id, body.access_level, body.confirmed_full_access)
        if body.access_level is not None or body.confirmed_full_access:
            raise ValueError("Уровень доступа изменяется отдельным действием перед продолжением.")
        return engine.control(run_id, body.action, body.instruction)

    @app.get("/")
    def home():
        return FileResponse(static_root / "index.html")

    @app.get("/api-client.js")
    def shared_api_script():
        return FileResponse(static_root / "api-client.js", media_type="text/javascript")

    @app.get("/design-system.css")
    def design_system_styles():
        return FileResponse(static_root / "design-system.css", media_type="text/css")

    @app.get("/suite.js")
    def suite_script():
        return FileResponse(static_root / "suite.js", media_type="text/javascript")

    @app.get("/suite.css")
    def suite_styles():
        return FileResponse(static_root / "suite.css", media_type="text/css")

    @app.get("/mission-control.js")
    def mission_control_script():
        return FileResponse(static_root / "mission-control.js", media_type="text/javascript")

    @app.get("/app.js")
    def js():
        return FileResponse(static_root / "app.js", media_type="text/javascript")

    @app.get("/style.css")
    def css():
        return FileResponse(static_root / "style.css", media_type="text/css")
    @app.get("/{asset_name}")
    def additional_ui_asset(asset_name: str):
        # Explicit whitelist: localization and local icons must work in the frozen
        # app as well as fixture servers; never expose arbitrary workspace files.
        assets = {"task-templates.js": "text/javascript", "task-templates.css": "text/css",
                  "run-comparison.js": "text/javascript", "run-comparison.css": "text/css",
                  "refresh-loop.js": "text/javascript", "task-draft.js": "text/javascript",
                  "command-palette.js": "text/javascript", "command-palette.css": "text/css",
                  "i18n.js": "text/javascript", "i18n-catalog.js": "text/javascript",
                  **{f"icon-{name}.svg": "image/svg+xml" for name in ("project", "run", "action", "tokens")}}
        if asset_name not in assets:
            raise HTTPException(status_code=404, detail="Ресурс интерфейса не найден.")
        return FileResponse(static_root / asset_name, media_type=assets[asset_name])

    return app
