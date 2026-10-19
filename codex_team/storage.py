import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SENSITIVE_KEYS = re.compile(r"^(access_?token|refresh_?token|id_?token|api_?key|authorization|password|cookie|secret|aws_secret_access_key|database_url)$", re.I)
TOKEN = re.compile(r"(?i)(?:Bearer\s+[A-Za-z0-9._~+/-]+|sk-[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)")
ASSIGNMENT = re.compile(r"(?im)(\b(?:[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)[A-Z0-9_]*|DATABASE_URL|accessToken|refreshToken|apiKey|password)\s*[:=]\s*)([^\r\n,}]+)")

def sanitize(value):
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if SENSITIVE_KEYS.match(str(k)) else sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        return ASSIGNMENT.sub(r"\1[REDACTED]", TOKEN.sub("[REDACTED]", value))
    return value

def now():
    return datetime.now(timezone.utc).isoformat()


def _usage_summary(entries, calls):
    """Sum observed per-call counters; completeness refers to total-token coverage."""
    totals = dict.fromkeys(('input', 'output', 'cached', 'total'))
    complete = isinstance(entries, list) and type(calls) is int and calls >= 0 and len(entries) == calls
    for entry in entries if isinstance(entries, list) else []:
        last = entry.get('last') if isinstance(entry, dict) else None
        last = last if isinstance(last, dict) else {}
        values = {}
        for key, aliases in (('input', ('inputTokens', 'input_tokens')),
                             ('output', ('outputTokens', 'output_tokens')),
                             ('cached', ('cachedInputTokens', 'cached_input_tokens')),
                             ('total', ('totalTokens', 'total_tokens'))):
            values[key] = next((last[name] for name in aliases if type(last.get(name)) is int and last[name] >= 0), None)
        if values['total'] is None and values['input'] is not None and values['output'] is not None:
            values['total'] = values['input'] + values['output']
        complete = complete and values['total'] is not None
        for key, value in values.items():
            if value is not None:
                totals[key] = (totals[key] or 0) + value
    return {'usage_total': totals, 'usage_available': any(value is not None for value in totals.values()),
            'usage_complete': complete}


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=30)
        # SQLite LIKE/lower only fold ASCII. This pure function is used only
        # for explicit searches; ordinary polling does not call it.
        self.db.create_function("codex_casefold", 1, lambda value: value.casefold() if isinstance(value, str) else "", deterministic=True)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL,type TEXT,role TEXT,payload TEXT,created_at TEXT);
        CREATE INDEX IF NOT EXISTS events_run ON events(run_id,id);
        CREATE TABLE IF NOT EXISTS agents(name TEXT PRIMARY KEY,data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,status TEXT NOT NULL,data TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS actions_run ON actions(run_id,status);
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,path TEXT UNIQUE NOT NULL,data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS packs(name TEXT PRIMARY KEY,data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS run_notebooks(
            run_id TEXT PRIMARY KEY, revision INTEGER NOT NULL CHECK(revision>=1),
            favorite INTEGER NOT NULL CHECK(favorite IN (0,1)), note TEXT NOT NULL,
            updated_at TEXT NOT NULL);
        """)
        self.db.commit()

    def save_run(self, run: dict):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO runs VALUES (?,?)", (run["id"], json.dumps(sanitize(run), ensure_ascii=False)))
            self.db.commit()

    def run(self, run_id: str):
        with self.lock:
            row = self.db.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise KeyError(run_id)
        return json.loads(row[0])

    def runs(self):
        with self.lock:
            rows = self.db.execute("SELECT data FROM runs ORDER BY rowid DESC").fetchall()
        return [json.loads(r[0]) for r in rows]

    def run_page(self, limit=20, offset=0, q="", state="", project="", mode="", date="", archived=False, favorite=False):
        clauses, values = [], []
        if not archived:
            clauses.append("COALESCE(json_extract(data,'$.archived'),0)=0")
        if q:
            clauses.append("(instr(codex_casefold(json_extract(data,'$.task')),?)>0 OR instr(codex_casefold(json_extract(data,'$.workspace')),?)>0)")
            values += [q.casefold(), q.casefold()]
        for value, path in ((state,'state'),(project,'original_workspace'),(mode,'mode')):
            if value:
                clauses.append(f"json_extract(data,'$.{path}')=?")
                values.append(value)
        if date:
            clauses.append("substr(json_extract(data,'$.created_at'),1,10)=?")
            values.append(date)
        if favorite:
            clauses.append("EXISTS (SELECT 1 FROM run_notebooks n WHERE n.run_id=runs.id AND n.favorite=1)")
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        with self.lock:
            total = self.db.execute('SELECT count(*) FROM runs' + where,values).fetchone()[0]
            # Strip large artifacts/diffs inside SQLite before Python/HTTP decoding.
            rows = self.db.execute("SELECT json_remove(data,'$.results','$.result_history','$.diff','$.diff_stat','$.executions','$.agents','$.instructions','$.checkpoint_git'), COALESCE(n.revision,0), COALESCE(n.favorite,0), COALESCE(n.note<>'',0), n.updated_at FROM runs LEFT JOIN run_notebooks n ON n.run_id=runs.id" + where + ' ORDER BY runs.rowid DESC LIMIT ? OFFSET ?', [*values,limit,offset]).fetchall()
        items = [json.loads(row[0]) for row in rows]
        for run, row in zip(items, rows):
            run.update(_usage_summary(run.pop('usage', []), run.get('calls')))
            run['task'] = run['task'][:400] if isinstance(run.get('task'), str) else ''
            run['changed_files_count'] = len(run['changed_files']) if isinstance(run.get('changed_files'), list) else None
            run['notebook'] = {'revision': row[1], 'favorite': bool(row[2]), 'has_note': bool(row[3]), 'updated_at': row[4]}
        return {'items':items,'total':total}

    def event_page(self, run_id, after=0, limit=100, meaningful=False):
        excluded = " AND lower(type) NOT LIKE '%delta%' AND type NOT IN ('thread/tokenUsage/updated','item/started')" if meaningful else ''
        with self.lock:
            rows = self.db.execute('SELECT id,type,role,payload,created_at FROM events WHERE run_id=? AND id>?' + excluded + ' ORDER BY id LIMIT ?', (run_id,after,limit+1)).fetchall()
            maximum = self.db.execute('SELECT COALESCE(max(id),?) FROM events WHERE run_id=?',(after,run_id)).fetchone()[0]
        more = len(rows)>limit
        rows = rows[:limit]
        return {'items':[dict(id=r[0],type=r[1],role=r[2],payload=json.loads(r[3]),created_at=r[4]) for r in rows],
                'next_cursor':rows[-1][0] if more else maximum,'has_more':more}

    def event(self, run_id: str, kind: str, payload=None, role=None):
        with self.lock:
            self.db.execute("INSERT INTO events(run_id,type,role,payload,created_at) VALUES (?,?,?,?,?)",
                            (run_id, kind, role, json.dumps(sanitize(payload or {}), ensure_ascii=False), now()))
            self.db.commit()

    def events(self, run_id: str, after=0):
        with self.lock:
            rows = self.db.execute("SELECT id,type,role,payload,created_at FROM events WHERE run_id=? AND id>? ORDER BY id LIMIT 500", (run_id, after)).fetchall()
        return [dict(id=r[0], type=r[1], role=r[2], payload=json.loads(r[3]), created_at=r[4]) for r in rows]

    def agents(self):
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute("SELECT data FROM agents ORDER BY name")]

    def save_agent(self, agent: dict):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO agents VALUES (?,?)", (agent["name"], json.dumps(sanitize(agent))))
            self.db.commit()

    def delete_agent(self, name):
        with self.lock:
            self.db.execute("DELETE FROM agents WHERE name=?", (name,))
            self.db.commit()

    def save_action(self, action):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO actions VALUES (?,?,?,?)",
                            (action["id"], action["run_id"], action["status"], json.dumps(sanitize(action), ensure_ascii=False)))
            self.db.commit()

    def action(self, action_id):
        with self.lock:
            row = self.db.execute("SELECT data FROM actions WHERE id=?", (action_id,)).fetchone()
        if not row:
            raise KeyError(action_id)
        return json.loads(row[0])

    def actions(self, run_id=None, status=None):
        clauses, values = [], []
        if run_id:
            clauses.append("run_id=?")
            values.append(run_id)
        if status:
            clauses.append("status=?")
            values.append(status)
        query = "SELECT data FROM actions" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY rowid DESC LIMIT 500"
        with self.lock:
            rows = self.db.execute(query, values).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_pack(self, pack):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO packs VALUES (?,?)", (pack["name"], json.dumps(sanitize(pack), ensure_ascii=False)))
            self.db.commit()

    def packs(self):
        with self.lock:
            rows = self.db.execute("SELECT data FROM packs ORDER BY name").fetchall()
        return [json.loads(row[0]) for row in rows]

    def delete_pack(self, name):
        with self.lock:
            self.db.execute("DELETE FROM packs WHERE name=?", (name,))
            self.db.commit()

    def save_project(self, project):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO projects VALUES (?,?,?)", (project["id"], project["path"], json.dumps(sanitize(project), ensure_ascii=False)))
            self.db.commit()

    def projects(self):
        with self.lock:
            rows = self.db.execute("SELECT data FROM projects ORDER BY rowid DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def project(self, project_id):
        with self.lock:
            row = self.db.execute("SELECT data FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise KeyError(project_id)
        return json.loads(row[0])

    def delete_project(self, project_id):
        with self.lock:
            self.db.execute("DELETE FROM projects WHERE id=?", (project_id,))
            self.db.commit()

    def settings(self):
        with self.lock:
            return {r[0]: json.loads(r[1]) for r in self.db.execute("SELECT key,data FROM settings")}

    def save_settings(self, settings):
        with self.lock:
            for k, v in settings.items():
                self.db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (k, json.dumps(sanitize(v))))
            self.db.commit()

    def recover(self):
        # A persisted request cannot approve a new SDK session after a crash.
        for action in self.actions(status="pending"):
            action.update(status="expired", resolved_at=now(), limitation="The previous SDK session ended. Resume to request permission again.")
            self.save_action(action)
        for run in self.runs():
            if run["state"] in {"RUNNING", "QUEUED", "PAUSING", "STOPPING"}:
                run["state"] = "INTERRUPTED"
                run["error"] = "Application restarted. Resume reruns the interrupted stage; partial edits are preserved."
                self.save_run(run)
                self.event(run["id"], "recovered", {"state": "INTERRUPTED"})

    def close(self):
        with self.lock:
            self.db.close()
