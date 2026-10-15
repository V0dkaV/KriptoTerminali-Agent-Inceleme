import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, data_dir):
        self.path = Path(data_dir)
        self.path.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path / 'terminal.db', check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS ledger(id TEXT PRIMARY KEY, mode TEXT, kind TEXT, amount TEXT, payload TEXT, time REAL);
          CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, mode TEXT, kind TEXT, message TEXT, payload TEXT, time REAL);
          CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, payload TEXT NOT NULL, time REAL);
          CREATE TABLE IF NOT EXISTS signal_receipts(id TEXT PRIMARY KEY, mode TEXT, session_id TEXT, identity TEXT, time REAL);
        ''')
        self.db.commit()
        self._depth = 0

    def commit(self):
        if not self._depth:
            self.db.commit()

    @contextmanager
    def atomic(self):
        self._depth += 1
        try:
            yield
        except BaseException:
            self._depth -= 1
            if not self._depth: self.db.rollback()
            raise
        else:
            self._depth -= 1
            if not self._depth:
                try: self.db.commit()
                except BaseException:
                    self.db.rollback()
                    raise

    def get(self, key, default=None):
        row = self.db.execute('SELECT value FROM kv WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        self.db.execute('INSERT INTO kv VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                        (key, json.dumps(value, ensure_ascii=False, allow_nan=False)))
        self.commit()

    def ledger(self, id, mode, kind, amount, payload):
        cursor = self.db.execute('INSERT OR IGNORE INTO ledger VALUES (?,?,?,?,?,?)',
                                (id, mode, kind, str(amount), json.dumps(payload, ensure_ascii=False), time.time()))
        self.commit()
        return cursor.rowcount == 1

    def claim_signal(self, id, mode, session_id, identity):
        cursor=self.db.execute('INSERT OR IGNORE INTO signal_receipts VALUES (?,?,?,?,?)',(id,mode,session_id,identity,time.time()))
        self.commit()
        return cursor.rowcount==1

    def signal_processed(self, id):
        return self.db.execute('SELECT 1 FROM signal_receipts WHERE id=?',(id,)).fetchone() is not None

    def audit(self, mode, kind, message, payload=None):
        self.db.execute('INSERT INTO audit(mode,kind,message,payload,time) VALUES (?,?,?,?,?)',
                        (mode, kind, message, json.dumps(payload or {}, ensure_ascii=False), time.time()))
        self.commit()

    def audit_list(self, mode, limit=60):
        rows = self.db.execute('SELECT kind,message,time FROM audit WHERE mode=? ORDER BY id DESC LIMIT ?', (mode, limit)).fetchall()
        return [dict(kind=r[0], message=r[1], time=r[2]) for r in rows]

    def report(self, id, payload):
        self.db.execute('INSERT OR REPLACE INTO reports VALUES (?,?,?)', (id, json.dumps(payload, ensure_ascii=False, allow_nan=False), time.time()))
        self.commit()

    def reports(self):
        return [dict(id=r[0], **json.loads(r[1])) for r in self.db.execute('SELECT id,payload FROM reports ORDER BY time DESC LIMIT 30')]

    def backup(self):
        folder = self.path / 'backups'
        folder.mkdir(exist_ok=True)
        path = folder / ('terminal-' + time.strftime('%Y%m%d-%H%M%S') + '.db')
        dest = sqlite3.connect(path)
        self.db.backup(dest)
        dest.close()
        return str(path)
