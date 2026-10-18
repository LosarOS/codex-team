"""Bounded, local, source-backed project intelligence. Never executes repository code."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import time
from .workspace import WorkspaceManager

EXCLUDED = {"node_modules", "vendor", "dist", "build", ".venv", "venv", "__pycache__", ".git", "coverage", "target"}
CATEGORIES = {"verified_fact", "derived_finding", "ai_suggestion", "decision"}

def safe_name(name):
    path = Path(name)
    return not (WorkspaceManager.sensitive(name) or any(p.lower() in EXCLUDED for p in path.parts) or re.search(r"(?i)(secret|credential|token|password|private.?key|id_rsa|id_ed25519)|\.(pem|p12|pfx|key)$", name))

def clean(text):
    text = re.sub(r"(?i)(api[_-]?key|password|secret|token)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", text)
    return re.sub(r"(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----)", "[REDACTED]", text)

# On Windows, neither st_ctime nor FILE_BASIC_INFO.ChangeTime reliably advances
# for immediate writes followed by restored mtime. Never trust metadata alone.
_WINDOWS = os.name == "nt"


def _change_time(path, stat):
    return None if _WINDOWS else stat.st_ctime_ns


class IntelligenceService:
    MAX_FILES = 4000
    MAX_FILE_BYTES = 65536
    def __init__(self, root, store, suite=None):
        from .suite_store import SuiteStore
        self.root, self.store = Path(root), store
        self.suite = suite or SuiteStore(store)
        self.workspace = WorkspaceManager(self.root)

    def project_root(self, project_id):
        return self.workspace.validate(Path(self.store.project(project_id)["path"]))

    def _catalog(self, root):
        """Fingerprint Git/index, metadata, and bounded content when required.

        POSIX change metadata avoids reading clean file contents. Windows hashes
        every eligible file: its timestamps and Git's stat cache can both miss
        immediate same-size writes with restored mtime. Dirty files are always
        hashed, as are files whose change metadata is unavailable.
        Git ignore enumeration is recomputed so local/global exclude changes apply.
        """
        index = self.workspace._git(root, "ls-files", "-z", "--stage", "--cached", "--exclude-standard")["stdout"]
        ignored = set(self.workspace._git(root, "ls-files", "-z", "--cached", "--ignored", "--exclude-standard")["stdout"].split("\0"))
        status = self.workspace._git(root, "-c", "core.fsmonitor=false", "status", "--porcelain=v1", "-z", "--untracked-files=no")["stdout"]
        dirty = {part[3:] for part in status.split("\0") if len(part) > 3}
        candidates, metadata = [], []
        for record in index.split("\0"):
            if "\t" not in record:
                continue
            name = record.split("\t", 1)[1]
            if name in ignored or not safe_name(name):
                continue
            try:
                path = self.workspace.resolve_inside(root, name)
                parents = [root / Path(*Path(name).parts[:i]) for i in range(1, len(Path(name).parts)+1)]
                if any(parent.is_symlink() for parent in parents):
                    continue
                stat = path.stat()
                if not path.is_file() or stat.st_size > self.MAX_FILE_BYTES:
                    continue
                change_time = _change_time(path, stat)
                digest = None
                if _WINDOWS or name in dirty or change_time is None:
                    # Recheck the read bound even if the file grows after stat().
                    with path.open("rb") as stream:
                        content = stream.read(self.MAX_FILE_BYTES + 1)
                    if len(content) > self.MAX_FILE_BYTES:
                        continue
                    digest = hashlib.sha256(content).hexdigest()
                metadata.append((name, stat.st_mtime_ns, change_time, stat.st_size, stat.st_mode, stat.st_ino, digest))
                candidates.append(name)
            except (ValueError, OSError):
                continue
            # Bound even repositories dominated by binary files.
            if len(candidates) >= self.MAX_FILES:
                break
        fingerprint = hashlib.sha256(json.dumps([index, sorted(ignored), status, metadata]).encode()).hexdigest()
        return sorted(set(candidates)), fingerprint

    def _files(self, root, candidates=None):
        if candidates is None:
            candidates, _ = self._catalog(root)
        result = []
        for name in candidates:
            try:
                path = self.workspace.resolve_inside(root, name)
                with path.open("rb") as stream:
                    if b"\0" not in stream.read(4096):
                        result.append(name)
            except (ValueError, OSError):
                continue
        return result

    def analyze(self, project_id, refresh=False):
        started = time.monotonic()
        root = self.project_root(project_id)
        candidates, fingerprint = self._catalog(root)
        head = self.workspace._git(root, "rev-parse", "--verify", "HEAD", check=False)["stdout"].strip() or None
        previous = self.get(project_id)
        if not refresh and previous and previous["data"].get("fingerprint") == fingerprint and previous["data"].get("head") == head:
            return previous
        files = self._files(root, candidates)
        technologies, dependencies = [], []
        adapters = {"pyproject.toml": "Python", "requirements.txt": "Python", "package.json": "JavaScript / Node.js", "Cargo.toml": "Rust", "go.mod": "Go"}
        for name in files:
            base = Path(name).name
            technology = adapters.get(base) or (".NET" if base.endswith(".csproj") else None)
            if technology:
                technologies.append({"name": technology, "source": name, "category": "verified_fact", "confidence": "high"})
            if base == "package.json":
                try:
                    manifest = json.loads((root/name).read_text(encoding="utf-8"))
                    for dep in list(manifest.get("dependencies", {}))[:100]:
                        dependencies.append({"name": clean(dep), "source": name, "kind": "declared"})
                except (ValueError, OSError):
                    pass
        modules = [{"path": name, "files": sum(f.startswith(name + "/") for f in files), "category": "derived_finding", "confidence": "medium", "source": "git ls-files"} for name in sorted({f.split('/')[0] for f in files if '/' in f})[:100]]
        data = {"head": head, "fingerprint": fingerprint, "files": files, "technologies": technologies, "modules": modules, "dependencies": dependencies, "limited": len(files) >= self.MAX_FILES, "duration_ms": round((time.monotonic()-started)*1000), "summary": f"Доступно {len(files)} текстовых файлов Git; модулей верхнего уровня: {len(modules)}.", "limitations": "Статический анализ деклараций; зависимости времени выполнения и точная семантика модулей не определяются."}
        return self.suite.put("architecture", project_id, data)

    def get(self, project_id):
        self.project_root(project_id)
        rows = self.suite.page("architecture", project_id, limit=1)["items"]
        return rows[0] if rows else None

    def source(self, project_id, path):
        root = self.project_root(project_id)
        if path not in self._files(root):
            raise ValueError("Источник исключён или не отслеживается Git")
        return {"path": path, "content": clean(self.workspace.resolve_inside(root,path).read_text(encoding="utf-8", errors="replace")[:8000]), "truncated": (root/path).stat().st_size > 8000}

    def search(self, project_id, q="", limit=50, offset=0):
        self.project_root(project_id)
        return self.suite.page("knowledge", project_id, limit=min(100,max(1,limit)), offset=max(0,offset), q=q)

    def save_entry(self, project_id, category, title, content, sources=None, approved=False, record_id=None, expected_version=None):
        root = self.project_root(project_id)
        if category not in CATEGORIES or not title.strip() or len(title)>300 or len(content)>12000:
            raise ValueError("Некорректная запись знаний")
        sources = sources or []
        allowed = set(self._files(root))
        if any(s not in allowed for s in sources):
            raise ValueError("Недоступный источник")
        if category == "verified_fact" and not sources:
            raise ValueError("Подтверждённому факту необходим источник")
        if record_id and self.suite.get("knowledge",record_id)["project_id"] != project_id:
            raise ValueError("Запись другого проекта")
        return self.suite.put("knowledge",project_id,{"category":category,"title":clean(title),"content":clean(content),"sources":sources,"approved":bool(approved)},record_id=record_id,expected_version=expected_version)

    def delete_entry(self, record_id, expected_version=None):
        row=self.suite.get("knowledge",record_id)
        self.project_root(row["project_id"])
        return self.suite.delete("knowledge",record_id,expected_version=expected_version)

    def context(self, project_id, query, max_chars=12000):
        snapshot = self.analyze(project_id)["data"]
        words = {w.lower() for w in re.findall(r"[\w-]{3,}", query)}
        ranked = sorted(snapshot["files"], key=lambda f: (-sum(w in f.lower() for w in words),f))
        relevant = [f for f in ranked if any(w in f.lower() for w in words)][:30]
        entries = [r["data"] for r in self.search(project_id,limit=100)["items"] if r["data"]["category"] == "verified_fact" or (r["data"]["category"] == "decision" and r["data"].get("approved"))]
        entries = [e for e in entries if any(w in (e["title"]+e["content"]).lower() for w in words)][:10]
        payload = {"head":snapshot["head"],"technologies":snapshot["technologies"][:20],"relevant_files":relevant,"knowledge":entries}
        limit = max(512,min(12000,max_chars))
        while len(clean(json.dumps(payload,ensure_ascii=False))) > limit:
            if payload["knowledge"]: payload["knowledge"].pop()
            elif payload["relevant_files"]: payload["relevant_files"].pop()
            elif payload["technologies"]: payload["technologies"].pop()
            else: break
        return clean(json.dumps(payload,ensure_ascii=False))
