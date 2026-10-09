import argparse
import json
from pathlib import Path
from .engine import Engine
from .models import RunRequest
from .provider import CodexProvider
from .storage import Store

def main():
    parser = argparse.ArgumentParser(prog="ai-team", description="Local official Codex multi-agent orchestrator")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "audit", "plan"):
        p = sub.add_parser(command)
        p.add_argument("task")
        p.add_argument("--workspace", default=str(Path.cwd()))
        p.add_argument("--mode", choices=["quick", "standard", "deep", "audit", "plan", "implement"], default="standard")
        p.add_argument("--pack", default="software-development")
        p.add_argument("--shared", action="store_true")
        p.add_argument("--auto-commit", action="store_true")
        p.add_argument("--max-agent-calls", type=int, default=15)
    p = sub.add_parser("resume"); p.add_argument("run_id")
    p = sub.add_parser("status"); p.add_argument("run_id", nargs="?")
    p = sub.add_parser("diff"); p.add_argument("run_id")
    p = sub.add_parser("login"); p.add_argument("--device", action="store_true")
    p = sub.add_parser("serve"); p.add_argument("--port", type=int, default=8765)
    sub.add_parser("models")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        from .server import create_app
        uvicorn.run(create_app(args.root), host="127.0.0.1", port=args.port)
        return
    if args.command in {"login", "models"}:
        provider = CodexProvider(args.root)
        try:
            if args.command == "models":
                print(json.dumps(provider.model_list(), ensure_ascii=False, indent=2))
            else:
                fields = provider.authenticate("chatgptDeviceCode" if args.device else "chatgpt")
                print(json.dumps(fields, ensure_ascii=False, indent=2))
                print("Complete official browser login. Waiting; Ctrl+C cancels.")
                provider.client.wait_for_login_completed(fields["loginId"])
                print("ChatGPT login completed")
        finally:
            provider.close()
        return
    store = Store(args.root / ".ai-team" / "team.sqlite3")
    engine = Engine(args.root, store)
    try:
        if args.command in {"run", "audit", "plan"}:
            request = RunRequest(workspace=args.workspace, task=args.task, mode=args.mode if args.command == "run" else args.command,
                                 pack=args.pack, isolated=not args.shared, auto_commit=args.auto_commit, max_agent_calls=args.max_agent_calls)
            run = engine.create(request)
            print(f"Run {run['id']} — {', '.join(run['pipeline'])}", flush=True)
            result = engine.launch(run["id"], background=False)
        elif args.command == "resume":
            result = engine.launch(args.run_id, background=False)
        elif args.command == "diff":
            run = store.run(args.run_id)
            print(engine.workspace.diff(Path(run["worktree"] or run["workspace"]), run.get("baseline"))["diff"])
            return
        else:
            result = store.run(args.run_id) if args.run_id else store.runs()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if isinstance(result, dict) and result.get("state") != "DONE" and args.command in {"run", "audit", "plan", "resume"}:
            raise SystemExit(1)
    except KeyboardInterrupt:
        engine.close()
        print("Interrupted. Partial edits and history preserved.")
    finally:
        engine.close()
        store.close()

if __name__ == "__main__":
    main()
