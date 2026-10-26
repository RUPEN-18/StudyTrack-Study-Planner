"""Local SQLite persistence. Each operation owns and closes its connection."""
from contextlib import contextmanager
from datetime import date
from pathlib import Path
import sqlite3


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS subjects (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    color TEXT NOT NULL DEFAULT '#6C63FF',
                    archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY,
                    subject_id INTEGER NOT NULL REFERENCES subjects(id),
                    study_date TEXT NOT NULL,
                    seconds INTEGER NOT NULL CHECK(seconds BETWEEN 1 AND 86400),
                    note TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL CHECK(source IN ('manual','timer')),
                    token TEXT UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY,
                    subject_id INTEGER NOT NULL REFERENCES subjects(id),
                    title TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS goals (
                    study_date TEXT PRIMARY KEY,
                    minutes INTEGER NOT NULL CHECK(minutes BETWEEN 1 AND 1440)
                );
                CREATE INDEX IF NOT EXISTS sessions_date ON sessions(study_date);
                CREATE INDEX IF NOT EXISTS tasks_date ON tasks(due_date);
            ''')

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            with con:
                yield con
        finally:
            con.close()

    def _read(self, sql, params=()):
        with self.connection() as con:
            return [dict(r) for r in con.execute(sql, params)]

    def _write(self, sql, params=()):
        with self.connection() as con:
            return con.execute(sql, params).lastrowid

    @staticmethod
    def _text(value, label, limit):
        value = str(value).strip()
        if not value or len(value) > limit:
            raise ValueError(f'{label} must contain 1–{limit} characters.')
        return value

    @staticmethod
    def _date(value):
        return date.fromisoformat(str(value)).isoformat()

    def add_subject(self, name, color='#6C63FF'):
        import re
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('Choose a valid color.')
        try:
            return self._write('INSERT INTO subjects(name,color) VALUES (?,?)',
                               (self._text(name, 'Subject', 60), color))
        except sqlite3.IntegrityError as exc:
            raise ValueError('That subject already exists, possibly in your archive.') from exc

    def subjects(self, include_archived=False):
        return self._read('SELECT * FROM subjects ' +
                          ('' if include_archived else 'WHERE archived=0 ') + 'ORDER BY name')

    def archive_subject(self, subject_id, archived=True):
        self._write('UPDATE subjects SET archived=? WHERE id=?', (int(archived), subject_id))

    def _active_subject(self, con, subject_id):
        if not con.execute('SELECT 1 FROM subjects WHERE id=? AND archived=0', (subject_id,)).fetchone():
            raise ValueError('Choose an active subject.')

    def add_session(self, subject_id, study_date, seconds, note='', source='manual', token=None):
        day = self._date(study_date)
        if day > date.today().isoformat():
            raise ValueError('Study sessions cannot be in the future.')
        if isinstance(seconds, bool) or not isinstance(seconds, int) or not 1 <= seconds <= 86400:
            raise ValueError('Duration must be between 1 second and 24 hours.')
        if len(note) > 500:
            raise ValueError('Notes must be at most 500 characters.')
        if source not in ('manual', 'timer'):
            raise ValueError('Unknown session source.')
        with self.connection() as con:
            self._active_subject(con, subject_id)
            # Retrying a timer save with the same token must never double count.
            if token:
                existing = con.execute('SELECT id FROM sessions WHERE token=?', (token,)).fetchone()
                if existing:
                    return existing['id']
            return con.execute('''INSERT INTO sessions(subject_id,study_date,seconds,note,source,token)
                                  VALUES (?,?,?,?,?,?)''',
                               (subject_id, day, seconds, note.strip(), source, token)).lastrowid

    def sessions(self):
        return self._read('''SELECT s.id, s.study_date, u.name AS subject, u.color,
                            s.subject_id, s.seconds, s.note, s.source
                            FROM sessions s JOIN subjects u ON u.id=s.subject_id
                            ORDER BY s.study_date DESC, s.id DESC''')

    def delete_session(self, session_id):
        self._write('DELETE FROM sessions WHERE id=?', (session_id,))

    def add_task(self, subject_id, title, due_date):
        with self.connection() as con:
            self._active_subject(con, subject_id)
            return con.execute('INSERT INTO tasks(subject_id,title,due_date) VALUES (?,?,?)',
                               (subject_id, self._text(title, 'Task', 160), self._date(due_date))).lastrowid

    def tasks(self):
        return self._read('''SELECT t.*, s.name AS subject FROM tasks t
                            JOIN subjects s ON s.id=t.subject_id ORDER BY t.due_date,t.id''')

    def complete_task(self, task_id, completed):
        self._write('UPDATE tasks SET completed=? WHERE id=?', (int(completed), task_id))

    def delete_task(self, task_id):
        self._write('DELETE FROM tasks WHERE id=?', (task_id,))

    def goal(self, day):
        rows = self._read('SELECT minutes FROM goals WHERE study_date=?', (self._date(day),))
        return rows[0]['minutes'] if rows else 120

    def set_goal(self, day, minutes):
        if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 1440:
            raise ValueError('Goal must be between 1 and 1,440 minutes.')
        self._write('''INSERT INTO goals(study_date,minutes) VALUES (?,?)
                       ON CONFLICT(study_date) DO UPDATE SET minutes=excluded.minutes''',
                    (self._date(day), minutes))
