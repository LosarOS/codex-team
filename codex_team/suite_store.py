"""Additive, versioned local records for the workspace suite; existing tables stay intact."""
import json
import re
import uuid
from .storage import now, sanitize


class SuiteConflict(ValueError):
    pass


class SuiteStore:
    def __init__(self, store):
        self.store = store
        with store.lock:
            store.db.executescript('''
                CREATE TABLE IF NOT EXISTS suite_records(
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, project_id TEXT NOT NULL,
                    version INTEGER NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS suite_project_kind ON suite_records(project_id,kind,deleted);
                CREATE TABLE IF NOT EXISTS suite_revisions(
                    id TEXT NOT NULL, version INTEGER NOT NULL, kind TEXT NOT NULL,
                    project_id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(id,version));
            ''')
            if store.db.execute("PRAGMA user_version").fetchone()[0]<2:
                store.db.execute("PRAGMA user_version=2")
            store.db.commit()

    @staticmethod
    def _identifier(value):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
            raise ValueError('Некорректный идентификатор записи')
        return value

    @staticmethod
    def _record(row):
        return dict(id=row[0],kind=row[1],project_id=row[2],version=row[3],data=json.loads(row[4]),created_at=row[5],updated_at=row[6])

    def put(self, kind, project_id, data, record_id=None, expected_version=None):
        self._identifier(kind); self._identifier(project_id)
        record_id=self._identifier(record_id or f'{kind}_{uuid.uuid4().hex}')
        if not isinstance(data,dict):
            raise ValueError('Данные записи должны быть объектом')
        encoded=json.dumps(sanitize(data),ensure_ascii=False)
        if len(encoded.encode('utf-8'))>2_000_000:
            raise ValueError('Запись превышает допустимый размер')
        timestamp=now()
        with self.store.lock:
            row=self.store.db.execute('SELECT id,kind,project_id,version,data,created_at,updated_at,deleted FROM suite_records WHERE id=?',(record_id,)).fetchone()
            if row and (row[1]!=kind or row[2]!=project_id or row[7]):
                raise ValueError('Идентификатор уже принадлежит другой или удалённой записи')
            if expected_version is not None and (not row or row[3]!=expected_version):
                raise SuiteConflict('Запись изменена. Обновите данные перед сохранением.')
            version=row[3]+1 if row else 1
            created=row[5] if row else timestamp
            with self.store.db:
                self.store.db.execute('INSERT OR REPLACE INTO suite_records VALUES (?,?,?,?,?,?,?,0)',(record_id,kind,project_id,version,encoded,created,timestamp))
                self.store.db.execute('INSERT INTO suite_revisions VALUES (?,?,?,?,?,?)',(record_id,version,kind,project_id,encoded,timestamp))
        return self.get(kind,record_id)

    def get(self, kind, record_id):
        with self.store.lock:
            row=self.store.db.execute('SELECT id,kind,project_id,version,data,created_at,updated_at FROM suite_records WHERE id=? AND kind=? AND deleted=0',(record_id,kind)).fetchone()
        if not row: raise KeyError(record_id)
        return self._record(row)

    def page(self, kind, project_id=None, limit=50, offset=0, q=''):
        if not 1<=limit<=200 or offset<0 or len(q)>1000:
            raise ValueError('Некорректные параметры страницы')
        clauses=['kind=?','deleted=0']; values=[kind]
        if project_id:
            clauses.append('project_id=?'); values.append(project_id)
        if q:
            clauses.append("data LIKE ? ESCAPE '\\'")
            values.append('%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
        where=' AND '.join(clauses)
        with self.store.lock:
            total=self.store.db.execute('SELECT count(*) FROM suite_records WHERE '+where,values).fetchone()[0]
            rows=self.store.db.execute('SELECT id,kind,project_id,version,data,created_at,updated_at FROM suite_records WHERE '+where+' ORDER BY updated_at DESC,id LIMIT ? OFFSET ?',[*values,limit,offset]).fetchall()
        return {'items':[self._record(row) for row in rows],'total':total,'limit':limit,'offset':offset}

    def delete(self, kind, record_id, expected_version=None):
        with self.store.lock:
            record=self.get(kind,record_id)
            if expected_version is not None and record['version']!=expected_version:
                raise SuiteConflict('Запись изменена. Обновите данные.')
            with self.store.db:
                self.store.db.execute('UPDATE suite_records SET deleted=1,updated_at=? WHERE id=? AND kind=?',(now(),record_id,kind))
        return {'id':record_id,'deleted':True,'history_retained':True}

    def history(self, kind, record_id, limit=50, offset=0):
        self.get(kind,record_id)
        if not 1<=limit<=200 or offset<0: raise ValueError('Некорректные параметры страницы')
        with self.store.lock:
            rows=self.store.db.execute('SELECT version,data,created_at FROM suite_revisions WHERE id=? AND kind=? ORDER BY version DESC LIMIT ? OFFSET ?',(record_id,kind,limit,offset)).fetchall()
        return {'items':[dict(version=r[0],data=json.loads(r[1]),created_at=r[2]) for r in rows]}
