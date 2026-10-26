"""Explicit opt-in demo records; never inserted into the personal database."""
from datetime import date, timedelta


def seed_demo(store):
    with store.connection() as con:
        con.execute('CREATE TABLE IF NOT EXISTS demo_meta (version INTEGER PRIMARY KEY)')
        if con.execute('SELECT 1 FROM demo_meta').fetchone():
            return
        today = date.today()
        subjects = [('IELTS Writing', '#6C63FF'), ('DSA', '#14B8A6'),
                    ('C++', '#F59E0B'), ('College', '#EC4899')]
        for name, color in subjects:
            con.execute('INSERT OR IGNORE INTO subjects(name,color) VALUES (?,?)', (name, color))
        ids = [r[0] for r in con.execute('SELECT id FROM subjects ORDER BY id')]
        for offset, minutes in enumerate([105, 75, 120, 55, 90, 135, 60]):
            day = (today - timedelta(days=offset)).isoformat()
            con.execute('INSERT INTO sessions(subject_id,study_date,seconds,note,source) VALUES (?,?,?,?,?)',
                        (ids[offset % 4], day, minutes * 60, 'Demo study session', 'manual'))
        for sid, title, done in [(ids[0], 'Write one Task 2 essay', 1),
                                  (ids[1], 'Solve 3 array problems', 0),
                                  (ids[2], 'Revise STL containers', 0)]:
            con.execute('INSERT INTO tasks(subject_id,title,due_date,completed) VALUES (?,?,?,?)',
                        (sid, title, today.isoformat(), done))
        con.execute('INSERT INTO demo_meta(version) VALUES (1)')
