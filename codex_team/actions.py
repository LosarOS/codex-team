"""Durable user requests; only a live official SDK request can grant permission."""
import copy
import re
import threading
import time
import uuid
from .storage import now, sanitize
from .permission_profiles import validate_permission_profile, PermissionProfileError

COMMAND = "item/commandExecution/requestApproval"
FILE = "item/fileChange/requestApproval"
PERMISSIONS = "item/permissions/requestApproval"
INPUT = "item/tool/requestUserInput"
ELICITATION = "mcpServer/elicitation/request"


def decline(method):
    if method == PERMISSIONS:
        return {"permissions": {}, "scope": "turn"}
    if method == INPUT:
        return {"answers": {}}
    if method == ELICITATION:
        return {"action": "decline", "content": None}
    return {"decision": "decline"}


def role_title(role):
    return {"coordinator":"Координатор", "analyst":"Аналитик", "developer":"Разработчик", "qa":"Тестировщик", "reviewer":"Проверка кода", "architect":"Архитектор"}.get(role, role or "Агент")


def describe_error(code, message):
    categories = {
        "AUTH_REQUIRED": ("AUTH_REQUIRED", "Подключите учётную запись ChatGPT", "Откройте настройки и выполните официальный вход."),
        "USER_DECISION_REQUIRED": ("USER_ACTION_REQUIRED", "Требуется ваше решение", "Просмотрите запрос и выберите способ продолжения."),
        "PERMISSION_REQUIRED": ("PERMISSION_REQUIRED", "Требуется разрешение", "Проверьте запрошенные разрешения в центре действий."),
        "CONFIGURATION_REQUIRED": ("CONFIGURATION_REQUIRED", "Требуется настройка проекта", "Проверьте среды выполнения и команды проекта."),
        "USAGE_LIMIT": ("USER_ACTION_REQUIRED", "Достигнут лимит использования Codex", "Дождитесь обновления лимита учётной записи и продолжите запуск. Смена провайдера требует отдельного действия."),
        "INTERRUPTED": ("RECOVERABLE_ERROR", "Сеанс прерван", "Продолжите запуск из истории, когда будете готовы."),
        "FAILED": ("RECOVERABLE_ERROR", "Не удалось продолжить запуск", "Просмотрите подробности и журналы, затем повторите или продолжите запуск."),
    }
    category, title, remedy = categories.get(code, ("RECOVERABLE_ERROR", "Не удалось завершить действие", "Просмотрите подробности и повторите попытку. Если ошибка повторится, откройте журналы."))
    return {"category": category, "title": title, "message": sanitize(str(message)), "remedy": remedy}


class ActionCenter:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.pending = {}
        self.closed = False

    def product_request(self, run_id, role, code, message, choices=None):
        """A durable product decision has no native permission-grant semantics."""
        for prior in self.store.actions(run_id, "pending"):
            if prior.get("kind") == "product":
                prior.update(status="superseded", resolved_at=now())
                self.store.save_action(prior)
        description = describe_error(code, message)
        card = {"id":"action_" + uuid.uuid4().hex[:16],"run_id":run_id,"role":role,
                "kind":"product","category":description["category"],"title":description["title"],
                "reason":description["message"],"details":description,"scope":"Контрольная точка текущего запуска",
                "command":"","risk":"low","requires_confirmation":False,"status":"pending","created_at":now(),
                "method":"product/decision","questions":[],"choices":sanitize(choices or []),
                "allowed_decisions":["resume","stop","explain"],"sdk_supported":True,
                "limitation":"Продолжение повторно запускает незавершённый этап. Оно не выдаёт разрешений и не увеличивает бюджет запуска."}
        self.store.save_action(card)
        self.store.event(run_id,"action_required",card,role)
        return card

    def complete_product(self, request_id, decision):
        card = self.store.action(request_id)
        if card.get("kind") != "product" or card["status"] != "pending" or decision not in card["allowed_decisions"]:
            raise ValueError("Это решение больше недоступно.")
        card.update(status="resolved",decision=decision,resolved_at=now())
        self.store.save_action(card)
        self.store.event(card["run_id"],"action_resolved",{"id":request_id,"decision":decision},card.get("role"))
        return card

    def request(self, run_id, role, method, params, cancel=None, timeout=900, grant_allowed=True, limitation=None):
        """Wait outside database/transport locks, while HTTP UI remains responsive."""
        params = copy.deepcopy(params or {})
        profile_error = None
        if method == PERMISSIONS:
            try:
                params["permissions"] = validate_permission_profile(params.get("permissions") or {})
            except PermissionProfileError as exc:
                profile_error = str(exc)
        supported = method in {COMMAND, FILE, PERMISSIONS, INPUT}
        command = params.get("command") or ""
        hidden_command = sanitize(command) != command
        supported = supported and not hidden_command and grant_allowed and not profile_error
        network = params.get("networkApprovalContext") or {}
        raw_permissions = params.get("permissions") or {}
        permissions = raw_permissions if isinstance(raw_permissions,dict) else {}
        category = "user_decision" if method == INPUT else "network_access" if network or permissions.get("network") else "file_access" if method in {FILE, PERMISSIONS} else "command_execution"
        if re.search(r"(?i)\b(pip\s+install|npm\s+(?:install|ci)|cargo\s+install|dotnet\s+restore)\b", command):
            category = "package_installation"
        risk = "high" if method in {COMMAND, FILE, PERMISSIONS} else "low"
        if re.search(r"(?i)\b(git\s+(?:reset|clean|push|rebase|merge)|remove-item|rmdir|rm|del|format|drop\s+(?:table|database))\b", command):
            risk = "high"
        available = params.get("availableDecisions")
        decisions = ["deny", "cancel"]
        if supported:
            if method == INPUT:
                decisions = ["answer", "cancel"]
            else:
                if available is None or "accept" in available:
                    decisions.insert(0, "allow_once")
                if available is None or "acceptForSession" in available:
                    decisions.insert(1, "allow_run")
        request_id = "action_" + uuid.uuid4().hex[:16]
        card = {"id": request_id, "run_id": run_id, "role": role, "kind": "decision" if method == INPUT else "permission",
                "title": f"{role_title(role)}: {'требуется ваш ответ' if method == INPUT else 'требуется разрешение'}", "reason": sanitize(params.get("reason") or "Официальный сеанс Codex запросил решение."),
                "command": sanitize(command), "cwd": params.get("cwd"), "scope": "Только разрешения, запрошенные официальным сеансом Codex",
                "risk": risk, "requires_confirmation": risk == "high", "status": "pending", "created_at": now(),
                "method": method, "category": category, "questions": sanitize(params.get("questions", [])), "choices": [],
                "details": sanitize(params), "allowed_decisions": decisions, "sdk_supported": supported,
                "limitation": "Разрешение на запуск действует только в текущем сеансе этого агента. Разрешения остальных агентов не меняются." if supported and method != INPUT else ""}
        if not supported:
            card["limitation"] = "В команде скрыты секретные значения. Попросите агента использовать существующую переменную окружения и показать полную операцию перед подтверждением." if hidden_command else "Codex Team не поддерживает выдачу разрешения для этого типа запроса SDK. Запрос будет отклонён."
        if limitation:
            card["limitation"] = limitation
        if profile_error:
            card["limitation"] = "Запрошенные разрешения не поддерживаются: " + profile_error + ". Запрос будет отклонён."
        waiter = {"event": threading.Event(), "response": None, "card": card, "params": params}
        with self.lock:
            if self.closed:
                return decline(method)
            self.pending[request_id] = waiter
            self.store.save_action(card)
        self.store.event(run_id, "action_required", card, role)
        if not supported or self.store.settings().get("permission_policy", {}).get(category) == "deny":
            self.resolve(request_id, "deny")
        deadline = time.monotonic() + timeout
        while not waiter["event"].wait(0.1):
            if self.closed or (cancel and cancel.is_set()) or time.monotonic() >= deadline:
                try:
                    self.resolve(request_id, "cancel")
                except ValueError:
                    pass
        with self.lock:
            self.pending.pop(request_id, None)
        return waiter["response"] or decline(method)

    def resolve(self, request_id, decision, answers=None, confirmed=False):
        with self.lock:
            waiter = self.pending.get(request_id)
            if not waiter or waiter["event"].is_set():
                raise ValueError("Этот запрос больше не ожидает ответа в активном сеансе Codex.")
            card, params = waiter["card"], waiter["params"]
            if decision not in card["allowed_decisions"]:
                raise ValueError("Официальный запрос не поддерживает это решение.")
            if decision in {"allow_once", "allow_run"} and card["requires_confirmation"] and not confirmed:
                raise ValueError("Перед выдачей разрешения подтвердите его область действия.")
            method = card["method"]
            response = decline(method)
            if decision in {"allow_once", "allow_run"}:
                if method == PERMISSIONS:
                    response = {"permissions": copy.deepcopy(params.get("permissions") or {}), "scope": "session" if decision == "allow_run" else "turn"}
                else:
                    response = {"decision": "acceptForSession" if decision == "allow_run" else "accept"}
            elif decision == "answer":
                answers = answers or {}
                if not isinstance(answers, dict):
                    raise ValueError("Ответы должны соответствовать идентификаторам вопросов.")
                known = {q["id"]: q for q in params.get("questions", []) if isinstance(q, dict) and "id" in q}
                if set(answers) - set(known):
                    raise ValueError("Неизвестный идентификатор вопроса.")
                normalized = {}
                for key, values in answers.items():
                    if not isinstance(values, list) or not values or any(not isinstance(v, str) or len(v) > 10000 for v in values):
                        raise ValueError("Каждый ответ должен содержать текст допустимой длины.")
                    if known[key].get("isSecret"):
                        raise ValueError("Для секретных данных используйте настройки провайдера или официальный вход.")
                    normalized[key] = {"answers": values}
                if set(normalized) != set(known):
                    raise ValueError("Ответьте на каждый вопрос перед продолжением.")
                response = {"answers": normalized}
            elif decision == "cancel" and method in {COMMAND, FILE}:
                response = {"decision": "cancel"}
            card.update(status="resolved", decision=decision, resolved_at=now())
            # Do not persist free text answers or secrets as approval metadata.
            self.store.save_action(card)
            self.store.event(card["run_id"], "action_resolved", {"id": request_id, "decision": decision}, card["role"])
            waiter["response"] = response
            waiter["event"].set()
            return card

    def cancel_run(self, run_id):
        with self.lock:
            ids = [key for key, value in self.pending.items() if value["card"]["run_id"] == run_id and not value["event"].is_set()]
        for key in ids:
            try:
                self.resolve(key, "cancel")
            except ValueError:
                pass

    def close(self):
        with self.lock:
            self.closed = True
            run_ids = {v["card"]["run_id"] for v in self.pending.values()}
        for run_id in run_ids:
            self.cancel_run(run_id)
