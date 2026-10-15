import json
import threading
import time
import uuid
import hashlib
from pathlib import Path
from codex_team.budget_guardian import BudgetGuardian, evaluate, validate_policy
from codex_team.context import ContextManager
from codex_team.models import AgentResult, RunRequest, parse_result
from codex_team.provider import CodexProvider, ProviderError
from codex_team.registry import Registry, CORE
from codex_team.storage import now, sanitize
from codex_team.workspace import WorkspaceManager, WorkspaceError
from codex_team.lease import AppLease
from codex_team.evidence import successful_test_execution, is_test_execution
from codex_team.actions import ActionCenter, COMMAND, FILE, PERMISSIONS, decline
from codex_team.permission_profiles import requested_capabilities, PermissionProfileError
from codex_team.secrets import WindowsSecretStore

TERMINAL = {"DONE", "FAILED", "USER_DECISION_REQUIRED", "AUTH_REQUIRED", "USAGE_LIMIT", "PAUSED", "STOPPED", "INTERRUPTED"}
RESUMABLE = TERMINAL - {"DONE"}

class Engine:
    def __init__(self, root: Path, store, provider_factory=None, secret_store=None):
        self.root, self.store = root, store
        self.registry = Registry(root, store)
        self.workspace = WorkspaceManager(root)
        self.context = ContextManager()
        self.provider_factory = provider_factory
        self.secret_store = secret_store if secret_store is not None else WindowsSecretStore(root)
        self.actions = ActionCenter(store)
        self.lock = threading.RLock()
        self.active = {}
        self.lease = None
        self.persistent_lease = False
        self.closed = False

    def acquire_session(self):
        with self.lock:
            if self.lease is None:
                self.lease = AppLease(self.root)
            self.persistent_lease = True

    def _file_hashes(self, cwd, change):
        hashes = {}
        for relative in change["changed_files"]:
            file = self.workspace.resolve_inside(cwd, relative)
            if file.is_file():
                digest = hashlib.sha256()
                with file.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                hashes[relative] = digest.hexdigest()
            else:
                hashes[relative] = None
        return hashes

    def _checkpoint(self, cwd, baseline, change=None):
        snap = self.workspace.snapshot(cwd)
        change = change if change is not None else self.workspace.diff(cwd, baseline)
        snap["diff_hash"] = hashlib.sha256(change["diff"].encode("utf-8")).hexdigest()
        snap["file_hashes"] = self._file_hashes(cwd, change)
        return snap

    def create(self, request: RunRequest):
        workspace = self.workspace.validate(request.workspace)
        pipeline = self.registry.pipeline(request.mode, request.pack, request.specialists)
        run_id = "run_" + uuid.uuid4().hex[:12]
        run = {**request.model_dump(), "workspace": str(workspace), "original_workspace": str(workspace), "id": run_id,
               "state": "QUEUED", "pipeline": pipeline, "stage": 0, "iteration": 1,
               "calls": 0, "threads": {}, "results": {}, "result_history": [], "usage": [],
               "created_at": now(), "current_role": None, "instructions": [], "error": None,
               "worktree": None, "elapsed_seconds": 0, "agents": {n: self.registry.get(n) for n in pipeline}}
        defaults = self.store.settings()
        backend = defaults.get("execution_backend", "codex_chatgpt")
        if backend not in {"codex_chatgpt", "openai_api"}:
            raise ValueError("Unsupported provider; automatic fallback is disabled")
        run["execution_backend"] = backend
        project = next((project for project in self.store.projects() if Path(project["path"]).resolve() == workspace), None)
        run["project_id"] = project["id"] if project else None
        policy = BudgetGuardian(self.store).project_policy(project["id"]) if project else {}
        explicit = getattr(request, "model_fields_set", set())
        for key, value in policy.items():
            if key not in explicit:
                run[key] = value
        run["budget_policy"] = {"max_agent_calls": run["max_agent_calls"], "max_total_tokens": run.get("max_total_tokens")}
        run["project_commands"] = project.get("commands", {}) if project else {}
        for spec in run["agents"].values():
            self._apply_role_defaults(spec, defaults)
        self.store.save_run(run)
        self.store.event(run_id, "created", {"pipeline": pipeline})
        return run

    @staticmethod
    def _apply_role_defaults(spec, defaults):
        role = defaults.get("role_model_defaults", {}).get(spec["name"], {})
        spec["model"] = spec.get("model") or role.get("model") or defaults.get("model")
        spec["reasoning_effort"] = spec.get("reasoning_effort") or role.get("reasoning_effort") or defaults.get("reasoning_effort")

    def _provider(self, run):
        if self.provider_factory is not None:
            return self.provider_factory()  # Preserve explicit zero-argument test factories.
        return CodexProvider(self.root, backend=run.get("execution_backend", "codex_chatgpt"), secret_store=self.secret_store)

    def _approval(self, run_id, role, agent, control, method, params):
        # Native transport owns permission scope; this gate may only narrow it.
        params = dict(params or {})
        denied = None
        write = method == FILE
        network = bool(params.get("networkApprovalContext"))
        if method == PERMISSIONS:
            try:
                capability = requested_capabilities(params.get("permissions") or {})
                write, network = capability["write"], capability["network"]
            except PermissionProfileError as exc:
                denied = str(exc)
        if method == COMMAND and not agent.get("can_execute", True):
            denied = "Execution is disabled for this role."
        if write and (agent.get("permission") != "workspace-write" or role != "developer"):
            denied = "This role cannot receive project write permission."
        if network and (not agent.get("can_network", False) or (role in CORE and role != "developer")):
            denied = "Network permission is disabled for this role."
        if control["cancel"].is_set():
            return decline(method)
        return self.actions.request(run_id, role, method, params, cancel=control["cancel"],
                                    grant_allowed=denied is None, limitation=denied)

    def _stage_event(self, run_id, role, cwd, control, kind, payload):
        self.store.event(run_id, kind, payload, role)
        item = payload.get("item", {}) if isinstance(payload, dict) else {}
        if kind != "item/completed" or item.get("type") != "fileChange" or item.get("status") != "completed":
            return
        for change in item.get("changes", []):
            try:
                path = Path(change["path"])
                relative = path.relative_to(cwd) if path.is_absolute() else path
                self.workspace.resolve_inside(cwd, relative)
                name = relative.as_posix()
                control.setdefault("owned_paths", set()).add(name)
                control.setdefault("owned_hashes", {}).update(self._file_hashes(cwd, {"changed_files": [name]}))
            except (ValueError, KeyError, TypeError):
                continue

    def _preserve_interrupted_edits(self, run, control):
        before = control.get("stage_before")
        if (run["state"] not in {"STOPPED", "INTERRUPTED"} or control.get("stage_writer") is not True or
                not before or not control.get("owned_paths")):
            return
        cwd = Path(run.get("worktree") or run["workspace"])
        try:
            change = self.workspace.diff(cwd, run.get("baseline"))
            after = self._checkpoint(cwd, run.get("baseline"), change)
            changed = {path for path in set(before["file_hashes"]) | set(after["file_hashes"])
                       if before["file_hashes"].get(path) != after["file_hashes"].get(path)}
            if (before["head"] == after["head"] and changed and changed <= control["owned_paths"] and
                    all(after["file_hashes"].get(path) == control.get("owned_hashes", {}).get(path) for path in changed)):
                run.update(change)
                run["checkpoint_git"] = after
                self.store.event(run["id"], "owned_partial_checkpoint", {"changed_files": sorted(changed)}, run.get("current_role"))
        except WorkspaceError:
            pass  # Unknown/external changes stay outside the accepted checkpoint.

    def _save(self, run):
        with self.lock:
            saved = self.store.run(run["id"])
            run["instructions"] = saved.get("instructions", [])
            self.store.save_run(run)
            artifact = self.root / ".ai-team" / "runs" / run["id"]
            artifact.mkdir(parents=True, exist_ok=True)
            temp = artifact / "state.json.tmp"
            temp.write_text(json.dumps(sanitize(run), ensure_ascii=False, indent=2), encoding="utf-8")
            for attempt in range(8):
                try:
                    temp.replace(artifact / "state.json")
                    break
                except PermissionError:
                    if attempt == 7:
                        raise
                    time.sleep(0.05 * (attempt + 1))  # Brief Windows scanner/OneDrive locks.

    def launch(self, run_id, background=True):
        with self.lock:
            if self.closed:
                raise ValueError("Engine is closed")
            if self.active:
                raise ValueError("Another run is active. Stop or pause it first; one writer at a time.")
            run = self.store.run(run_id)
            if run.get("worktree_deleted"):
                raise ValueError("This run's worktree was deleted; it cannot be resumed")
            if run["state"] != "QUEUED" and run["state"] not in RESUMABLE:
                raise ValueError("Run cannot be resumed in its current state")
            if self.lease is None:
                self.lease = AppLease(self.root)
            try:
                provider = self._provider(run)
            except Exception:
                if not self.persistent_lease and self.lease:
                    self.lease.close()
                    self.lease = None
                raise
            control = {"cancel": threading.Event(), "pause": False, "stop": False, "provider": provider}
            self.active[run_id] = control
        if background:
            worker = threading.Thread(target=self._work, args=(run_id, control), daemon=True, name=run_id)
            control["worker"] = worker
            worker.start()
        else:
            self._work(run_id, control)
        return self.store.run(run_id)

    def _work(self, run_id, control):
        run = self.store.run(run_id)
        run["state_before_resume"] = run["state"]
        started = time.monotonic()
        prior_elapsed = run.get("elapsed_seconds", 0)
        deadline = run["max_run_duration"] - prior_elapsed
        timer = None
        provider = control["provider"]
        try:
            if deadline <= 0:
                raise ProviderError("USER_DECISION_REQUIRED", "Run duration budget exhausted")
            def expire():
                control["timeout"] = True
                control["cancel"].set()
                self.actions.cancel_run(run_id)
                try:
                    provider.interrupt()
                finally:
                    # Close also releases stalled pre-turn/account RPCs.
                    provider.close()
            timer = threading.Timer(deadline, expire)
            timer.daemon = True
            timer.start()
            run["state"], run["error"] = "RUNNING", None
            self._save(run)
            if provider.account_status()["status"] != "CONNECTED":
                raise ProviderError("AUTH_REQUIRED", "Connect the selected provider in Settings. Automatic fallback is disabled.")
            if not run.get("prepared"):
                prepared = self.workspace.prepare(run["workspace"], run_id, isolated=run["isolated"])
                run.update({k: v for k, v in prepared.items() if k != "workspace"})
                run["prepared"] = True
                run["checkpoint_git"] = self._checkpoint(Path(run["worktree"] or run["workspace"]), run.get("baseline"))
                self._save(run)
            cwd = Path(run["worktree"] or run["workspace"])
            current = self._checkpoint(cwd, run.get("baseline"))
            expected = run.get("checkpoint_git", {})
            if expected.get("head") != current.get("head"):
                raise ProviderError("USER_DECISION_REQUIRED", "Workspace HEAD changed since checkpoint. Review before resume.")
            if expected.get("diff_hash") != current.get("diff_hash") or expected.get("file_hashes", {}) != current.get("file_hashes", {}):
                raise ProviderError("USER_DECISION_REQUIRED", "Workspace files changed outside the saved checkpoint. Review before resume.")
            self.workspace.resume(cwd, run["baseline"])
            while run["stage"] < len(run["pipeline"]):
                if control["stop"]:
                    run["state"] = "STOPPED"
                    break
                if control["pause"]:
                    run["state"] = "PAUSED"
                    break
                self._budget_events(run)
                exhausted = evaluate(run)["reached"]
                if exhausted:
                    raise ProviderError("USER_DECISION_REQUIRED", "Бюджет запуска исчерпан (budget): " + ", ".join(exhausted) + ". Следующий этап не запущен; контрольная точка сохранена.")
                if control.get("timeout"):
                    raise ProviderError("USER_DECISION_REQUIRED", "Run duration budget exhausted")
                role = run["pipeline"][run["stage"]]
                agent = run["agents"][role]
                # Audit and plan modes never give a role workspace write access.
                if run["mode"] in {"audit", "plan"}:
                    agent = {**agent, "permission": "read-only"}
                before = run["checkpoint_git"]
                control.update(stage_before=before, stage_writer=agent["permission"] == "workspace-write", owned_paths=set(), owned_hashes={})
                run["current_role"] = role
                run["calls"] += 1
                self._save(run)
                self.store.event(run_id, "agent_started", {"iteration": run["iteration"], "call": run["calls"]}, role)
                diff = self.workspace.diff(cwd, run.get("baseline"))
                if (hashlib.sha256(diff["diff"].encode("utf-8")).hexdigest() != before["diff_hash"] or
                        self._file_hashes(cwd, diff) != before["file_hashes"]):
                    raise ProviderError("USER_DECISION_REQUIRED", "Workspace files changed outside the saved checkpoint. Review before the next stage.")
                run["instructions"] = self.store.run(run_id).get("instructions", [])
                prompt = self.context.build(run, role, diff)
                def on_thread(tid):
                    run["threads"][role] = tid
                    self._save(run)
                provider.approval_handler = lambda method, params, current_role=role, current_agent=agent: self._approval(run_id, current_role, current_agent, control, method, params)
                response = provider.execute(agent, str(cwd), prompt, AgentResult.model_json_schema(), run["threads"].get(role),
                                            lambda kind, payload: self._stage_event(run_id, role, cwd, control, kind, payload),
                                            on_thread, control["cancel"])
                # Preserve usage even when output parsing/verdict validation fails.
                if response.get("usage"):
                    raw = response["usage"]
                    totals = raw.get("total")
                    if totals:
                        previous = run.setdefault("thread_usage_totals", {}).get(role, {})
                        delta = {k: max(0, v - previous.get(k, 0)) for k, v in totals.items() if isinstance(v, int)}
                        run["thread_usage_totals"][role] = totals
                        run["usage"].append({"agent": role, "iteration": run["iteration"], "last": delta,
                                             "total": totals, "sdk_last": raw.get("last")})
                    else:
                        run["usage"].append({"agent": role, "iteration": run["iteration"], **raw})
                if response.get("usage"):
                    run["usage"][-1].setdefault("completed_at", now())
                self._budget_events(run)
                self._save(run)
                # A returned stage owns its permitted edits. Capture them before
                # verdict/evidence errors so a same-thread resume can continue.
                # Failed preflight/integrity checks never enter this update.
                change = self.workspace.diff(cwd, run.get("baseline"))
                after = self._checkpoint(cwd, run.get("baseline"), change)
                if before["head"] != after["head"]:
                    raise ProviderError("USER_DECISION_REQUIRED", "Workspace HEAD changed during the stage; checkpoint was not advanced.")
                if agent["permission"] != "workspace-write" and before != after:
                    raise ProviderError("USER_DECISION_REQUIRED", "Workspace changed during a read-only stage; checkpoint was not advanced.")
                run.update(change)
                run["checkpoint_git"] = after
                self._save(run)
                if control["stop"]:
                    run["state"] = "STOPPED"
                    break
                result = parse_result(response["text"], role)
                run.setdefault("executions", {})[role] = response.get("executions", [])
                run["results"][role] = result
                run.setdefault("artifact_snapshots", {})[role] = {"workspace": str(cwd.resolve()), "head": after["head"], "diff_hash": after["diff_hash"]}
                run["result_history"].append({"role": role, "iteration": run["iteration"], "result": result})
                self.store.event(run_id, "agent_completed", {"verdict": result["verdict"], "summary": result["summary"]}, role)
                if response.get("denied") or result["verdict"] == "USER_DECISION_REQUIRED":
                    raise ProviderError("USER_DECISION_REQUIRED", result["summary"])
                if role == "coordinator" and run["mode"] in {"deep", "audit"}:
                    # Coordinator can select only enabled read-only registry specialists.
                    additions = []
                    for name in result["specialists"]:
                        spec = self.registry.get(name)
                        if (spec["permission"] != "read-only" or name in run["pipeline"] or
                                run["mode"] not in spec.get("enabled_modes", [])):
                            continue
                        self._apply_role_defaults(spec, self.store.settings())
                        additions.append(name)
                        run["agents"][name] = spec
                    run["pipeline"][2:2] = additions[:max(0, run["max_agent_calls"] - len(run["pipeline"]))]
                verdict = result["verdict"]
                if verdict in {"FAIL", "CHANGES_REQUIRED"}:
                    if run["mode"] in {"audit", "plan"}:
                        # Findings are the output of an audit; no automatic code edits.
                        run["stage"] += 1
                    elif run["iteration"] >= run["max_iterations"]:
                        raise ProviderError("USER_DECISION_REQUIRED", "Repair iteration limit exhausted; findings retained")
                    else:
                        run["iteration"] += 1
                        if role not in {"qa", "reviewer", "final-audit"}:
                            rechecks = run.setdefault("pending_rechecks", [])
                            if role not in rechecks:
                                rechecks.append(role)
                            developer_stage = run["pipeline"].index("developer")
                            for skipped in run["pipeline"][run["stage"] + 1:developer_stage]:
                                if skipped not in run["results"] and skipped not in rechecks:
                                    rechecks.append(skipped)
                        # Rerun the full validation tail after the next developer turn.
                        run["stage"] = run["pipeline"].index("developer")
                        self.store.event(run_id, "repair_requested", {"by": role, "iteration": run["iteration"]}, role)
                else:
                    if role == "qa" and run["mode"] not in {"audit", "plan"}:
                        if not result["tests"] or any(t["exit_code"] != 0 for t in result["tests"]):
                            raise ProviderError("USER_DECISION_REQUIRED", "QA PASS has no successful test evidence")
                        if any(is_test_execution(c) and not successful_test_execution(c) for c in response.get("executions", [])):
                            raise ProviderError("USER_DECISION_REQUIRED", "QA native test ledger contains an unsuccessful test run")
                        if not any(successful_test_execution(c) for c in response.get("executions", [])):
                            raise ProviderError("USER_DECISION_REQUIRED", "QA PASS is not backed by successful native test execution events")
                    run["stage"] += 1
                    if role == "developer" and run.get("pending_rechecks"):
                        # Validate repaired specialist findings after edits and
                        # before QA, rather than carrying a stale FAIL to DONE.
                        rechecks = run.pop("pending_rechecks")
                        remaining = run["pipeline"][run["stage"]:]
                        run["pipeline"][run["stage"]:run["stage"]] = [n for n in rechecks if n not in remaining]
                self._save(run)
                self.workspace.memory(Path(run.get("original_workspace", run["workspace"])), run_id, sanitize(run))
            else:
                if run["mode"] not in {"audit", "plan"}:
                    missing = set(run["pipeline"]) - set(run["results"])
                    if missing:
                        raise ProviderError("USER_DECISION_REQUIRED", "Required stages have no result: " + ", ".join(sorted(missing)))
                    unresolved = [role for role, result in run["results"].items() if result["verdict"] in {"FAIL", "CHANGES_REQUIRED", "USER_DECISION_REQUIRED"}]
                    if unresolved:
                        raise ProviderError("USER_DECISION_REQUIRED", "Unresolved required verdicts: " + ", ".join(unresolved))
                run.update(self.workspace.diff(cwd, run.get("baseline")))
                if run["auto_commit"] and run["mode"] not in {"audit", "plan"}:
                    run["commit"] = self.workspace.commit(cwd, run["task"])
                run["state"] = "DONE"
        except ProviderError as exc:
            run["state"] = "STOPPED" if control["stop"] else exc.code if exc.code in TERMINAL else "FAILED"
            run["error"] = str(exc)
        except WorkspaceError as exc:
            run["state"], run["error"] = "USER_DECISION_REQUIRED", str(exc)
        except Exception as exc:
            run["state"], run["error"] = ("STOPPED" if control["stop"] else "FAILED"), str(exc)
        finally:
            if timer:
                timer.cancel()
            if control.get("timeout") and not control["stop"]:
                run["state"], run["error"] = "USER_DECISION_REQUIRED", "Run duration budget exhausted"
            run["elapsed_seconds"] = prior_elapsed + time.monotonic() - started
            provider.close()
            self._preserve_interrupted_edits(run, control)
            self.actions.cancel_run(run_id)
            self._save(run)
            self.store.event(run_id, "run_state", {"state": run["state"], "error": run.get("error")})
            with self.lock:
                self.active.pop(run_id, None)
                if not self.persistent_lease and self.lease:
                    self.lease.close()
                    self.lease = None
                if run["state"] not in {"DONE", "STOPPED", "PAUSED"} and run.get("error"):
                    self.actions.product_request(run_id, run.get("current_role"), run["state"], run["error"])

    def _budget_events(self, run):
        status = evaluate(run)
        emitted = run.setdefault("budget_thresholds_emitted", [])
        for metric, thresholds in status["thresholds"].items():
            limit = status["max_agent_calls" if metric == "calls" else "max_total_tokens"]
            for threshold in thresholds:
                identity = f"{metric}/{limit}/{threshold}"
                if identity not in emitted:
                    self.store.event(run["id"], "budget_threshold", {"metric": metric, "threshold": threshold, "limit": limit, "observed": status["calls" if metric == "calls" else "measured_tokens"]})
                    emitted.append(identity)
        self._save(run)

    def set_budget_policy(self, run_id, policy):
        policy = validate_policy(policy)
        with self.lock:
            if run_id in self.active:
                raise ValueError("Сначала приостановите запуск перед изменением бюджета")
            run = self.store.run(run_id)
            run.update(policy)
            run["budget_policy"] = {"max_agent_calls": run["max_agent_calls"], "max_total_tokens": run.get("max_total_tokens")}
            self.store.save_run(run)
            self.store.event(run_id, "budget_policy_updated", run["budget_policy"])
            return run

    def control(self, run_id, action, instruction=None):
        run = self.store.run(run_id)
        if action == "resume":
            if instruction is not None:
                self.control(run_id, "queue", instruction)
            return self.launch(run_id)
        with self.lock:
            control = self.active.get(run_id)
            if action in {"steer", "queue"}:
                if not instruction or len(instruction) > 10000:
                    raise ValueError("A nonempty instruction up to 10000 characters is required")
                run = self.store.run(run_id)
                run["instructions"].append(instruction)
                self.store.save_run(run)
                if action == "steer" and control:
                    control["provider"].steer(instruction)
                self.store.event(run_id, "user_instruction", {"instruction": instruction, "action": action})
            elif action == "pause" and control:
                control["pause"] = True
                self.store.event(run_id, "pause_requested", {"at": "next completed stage"})
            elif action == "stop" and control:
                control["stop"] = True
                control["cancel"].set()
                self.actions.cancel_run(run_id)
                try:
                    control["provider"].interrupt()
                finally:
                    control["provider"].close()
                self.store.event(run_id, "stop_requested")
            else:
                raise ValueError("Control unavailable for this run")
        return self.store.run(run_id)

    def resolve_action(self, action_id, decision, instruction=None, answers=None, confirmed=False, budget=None):
        with self.lock:
            card = self.store.action(action_id)
            if card.get("kind") != "product":
                if budget is not None or instruction is not None:
                    raise ValueError("Instructions and budgets apply only to product Resume decisions")
                return self.actions.resolve(action_id, decision, answers, confirmed)
            if card["status"] != "pending" or decision not in card["allowed_decisions"]:
                raise ValueError("This product decision is no longer available")
            run_id = card["run_id"]
            run = self.store.run(run_id)
            if decision == "stop":
                if budget is not None or instruction is not None:
                    raise ValueError("Stop does not change instructions or budgets")
                if run_id in self.active:
                    self.active[run_id]["stop"] = True
                    self.active[run_id]["cancel"].set()
                    completed = self.actions.complete_product(action_id, decision)
                    self.control(run_id, "stop")
                else:
                    run["state"] = "STOPPED"
                    self._save(run)
                    completed = self.actions.complete_product(action_id, decision)
                    self.actions.cancel_run(run_id)
                return completed
            if self.active:
                raise ValueError("Pause or stop the active run before resuming a product decision")
            if run["state"] not in RESUMABLE:
                raise ValueError("This run cannot resume")
            if instruction is not None and (not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 10000):
                raise ValueError("A nonempty instruction up to 10000 characters is required")
            if decision == "explain":
                if budget is not None:
                    raise ValueError("Explain does not change budgets")
                instruction = "Explain why this run is blocked and what safe user action is required before continuing. " + card["reason"][:6000] + ("\n" + instruction if instruction else "")
            if budget is not None:
                if decision != "resume":
                    raise ValueError("Explicit total budgets apply only to Resume")
                limits = {"max_iterations": (1, 10), "max_agent_calls": (1, 100), "max_run_duration": (30, 86400), "max_total_tokens": (1, 10**12)}
                if not isinstance(budget, dict) or not budget or set(budget) - set(limits):
                    raise ValueError("Unsupported run budget fields")
                for key, value in budget.items():
                    lower, upper = limits[key]
                    if type(value) is not int or not lower <= value <= upper:
                        raise ValueError(f"Budget {key} must be between {lower} and {upper}")
                if budget.get("max_iterations", run["max_iterations"]) < run["iteration"]:
                    raise ValueError("Iteration total cannot be below completed progress")
                if budget.get("max_agent_calls", run["max_agent_calls"]) <= run["calls"]:
                    raise ValueError("Call total must leave room for the unfinished stage")
                if budget.get("max_run_duration", run["max_run_duration"]) <= run.get("elapsed_seconds", 0):
                    raise ValueError("Duration total must exceed elapsed run time")
                if budget.get("max_total_tokens") is not None and budget["max_total_tokens"] <= (evaluate(run)["measured_tokens"] or 0):
                    raise ValueError("Token total must exceed measured usage")
            previous = dict(run)
            if instruction:
                run["instructions"] = [*run.get("instructions", []), instruction]
            run.update(budget or {})
            run["budget_policy"] = {"max_agent_calls": run["max_agent_calls"], "max_total_tokens": run.get("max_total_tokens")}
            self.store.save_run(run)
            try:
                self.launch(run_id)
            except Exception:
                self.store.save_run(previous)
                raise
            # The worker's final product-card creation also holds this lock;
            # it cannot supersede this card before accepted launch is recorded.
            return self.actions.complete_product(action_id, decision)

    def delete_worktree(self, run_id):
        with self.lock:
            run = self.store.run(run_id)
            if run_id in self.active or run["state"] not in {"DONE", "FAILED", "STOPPED", "INTERRUPTED", "USER_DECISION_REQUIRED"}:
                raise ValueError("Only an inactive finished or stopped worktree can be deleted")
            if self.store.actions(run_id, "pending"):
                raise ValueError("Resolve pending decisions before deleting a worktree")
            if run.get("worktree_deleted"):
                return run
            if not run.get("worktree"):
                raise ValueError("This run has no isolated worktree")
            original = self.workspace.validate(run.get("original_workspace", run["workspace"]))
            relative = Path(".ai-team/worktrees") / self.workspace._run_id(run_id)
            expected = original / relative
            for component in (original / ".ai-team", original / ".ai-team/worktrees", expected):
                if component.is_symlink() or component.is_junction():
                    raise WorkspaceError("Linked worktree paths cannot be deleted")
            target = Path(run["worktree"])
            if not target.is_absolute() or target.resolve() != expected.resolve() or not expected.is_dir():
                raise WorkspaceError("Worktree deletion target does not match its exact run path")
            self.workspace.resolve_inside(original, relative)
            if self.workspace.snapshot(target)["dirty"]:
                raise WorkspaceError("Dirty worktrees are preserved; commit or review changes before deletion")
            self.workspace._git(original, "worktree", "remove", str(target))
            run.update(worktree_deleted=True, worktree_deleted_at=now())
            self._save(run)
            self.store.event(run_id, "worktree_deleted", {"worktree": run["worktree"]})
            return run

    def close(self):
        with self.lock:
            self.closed = True
            active = list(self.active.items())
        self.actions.close()
        for run_id, control in active:
            control["stop"] = True
            control["cancel"].set()
            try:
                control["provider"].interrupt()
            finally:
                control["provider"].close()
        for _, control in active:
            worker = control.get("worker")
            if worker:
                worker.join(timeout=10)
        with self.lock:
            if self.lease:
                self.lease.close()
                self.lease = None
