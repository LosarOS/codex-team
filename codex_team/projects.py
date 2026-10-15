"""Registered projects and user-owned argv hints; no host execution endpoint."""
import hashlib
import time
import copy
from pathlib import Path
from .storage import now, sanitize
from .workspace import WorkspaceManager


class Projects:
    def __init__(self, root, store):
        self.store = store
        self.workspace = WorkspaceManager(root)
        self.cache = {}

    def create(self, path, name):
        """Initialize only a new, explicitly selected directory; never publish it."""
        name = name.strip()
        if not name or any(ord(char) < 32 for char in name + path):
            raise ValueError('Укажите название и полный путь новой папки проекта.')
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            raise ValueError('Укажите полный путь новой папки проекта.')
        if candidate.exists() or candidate.is_symlink():
            raise ValueError('Эта папка уже существует. Выберите новую папку или подключите существующий репозиторий.')
        try:
            parent = candidate.parent.resolve(strict=True)
        except OSError as exc:
            raise ValueError('Родительская папка не найдена. Выберите существующую папку для проекта.') from exc
        if not parent.is_dir():
            raise ValueError('Родительский путь должен быть папкой.')
        if self.workspace._git(parent, 'rev-parse', '--show-toplevel', check=False)['exit_code'] == 0:
            raise ValueError('Создайте проект вне существующего Git-репозитория, чтобы не вложить один репозиторий в другой.')
        target = parent / candidate.name
        try:
            target.mkdir()
        except FileExistsError as exc:
            raise ValueError('Папка уже создана. Подключите её как существующий проект.') from exc
        except OSError as exc:
            raise ValueError('Не удалось создать папку. Проверьте путь и права записи.') from exc
        # No global identity edits, downloaded templates, hooks, signing or remote push.
        try:
            self.workspace._git(target, '-c', 'init.templateDir=', 'init', '-b', 'main', '.')
            (target / 'README.md').write_text('# ' + name + '\n', encoding='utf-8')
            (target / '.gitignore').write_text('.ai-team/\n.env\n.env.*\n__pycache__/\n', encoding='utf-8')
            import os
            self.workspace._git(target, 'add', '--', 'README.md', '.gitignore')
            self.workspace._git(target, '-c', 'core.hooksPath=' + os.devnull,
                                '-c', 'commit.gpgsign=false', '-c', 'user.name=Codex Team',
                                '-c', 'user.email=codex-team@localhost', 'commit', '-m', 'Создан проект')
        except Exception as exc:
            raise ValueError('Не удалось подготовить Git-проект. Новая папка сохранена; проверьте Git и подключите её после исправления ошибки.') from exc
        result = self.add(str(target))
        project = self.store.project(result['id'])
        project['name'] = name
        self.store.save_project(project)
        self.cache.pop(project['id'], None)
        return self.inspect(project['id'])

    def add(self, path):
        root = self.workspace.validate(path)
        project_id = 'project_' + hashlib.sha256(str(root).casefold().encode('utf-8')).hexdigest()[:16]
        existing = next((p for p in self.store.projects() if p['id'] == project_id), None)
        project = existing or {'id':project_id,'name':root.name,'path':str(root),'commands':{},'created_at':now()}
        self.store.save_project(project)
        return self.inspect(project_id)

    def inspect(self, project_id):
        from .runtimes import preflight
        project = self.store.project(project_id)
        cached = self.cache.get(project_id)
        if cached and time.monotonic() - cached[0] < 5:
            return copy.deepcopy(cached[1])
        snapshot = self.workspace.snapshot(Path(project['path']))
        changed = [name for _,name in self.workspace._status_records(snapshot['status']) if not self.workspace.sensitive(name)]
        with self.store.lock:
            last_run = self.store.db.execute("SELECT id FROM runs WHERE COALESCE(json_extract(data,'$.original_workspace'),json_extract(data,'$.workspace'))=? ORDER BY rowid DESC LIMIT 1",(project['path'],)).fetchone()
        memory = self.workspace.resolve_inside(Path(project['path']), '.ai-team/project_summary.md')
        result = {**project,'branch':snapshot['branch'],'head':snapshot['head'],'dirty':snapshot['dirty'],
                'changed_files':changed,'last_run':last_run[0] if last_run else None,
                'memory_status':'available' if memory.is_file() else 'empty','runtime_status':preflight(project['path']),
                'ready':bool(snapshot['head']) and not snapshot['dirty'],
                'readiness_message':'This repository has uncommitted changes. Review its Diff and commit or stash them yourself before creating an isolated run.' if snapshot['dirty'] else 'Create an initial Git commit before an isolated run.' if not snapshot['head'] else None}
        self.cache[project_id] = (time.monotonic(),result)
        return copy.deepcopy(result)

    def save_commands(self, project_id, commands):
        project = self.store.project(project_id)
        if not isinstance(commands,dict) or set(commands) - {'test','build','run'}:
            raise ValueError('Command categories are test, build and run')
        for argv in commands.values():
            if not isinstance(argv,list) or len(argv) > 64 or any(not isinstance(v,str) or not v or len(v)>4096 or any(c in v for c in '\x00\r\n') for v in argv):
                raise ValueError('Commands must be bounded JSON argv arrays')
            if sanitize(argv) != argv:
                raise ValueError('Do not save secrets in project commands; use secure provider settings')
        project['commands'] = {key:argv for key,argv in commands.items() if argv}
        self.store.save_project(project)
        self.cache.pop(project_id,None)
        return project

    def diff(self, project_id):
        project = self.store.project(project_id)
        return self.workspace.diff(Path(project['path']))
