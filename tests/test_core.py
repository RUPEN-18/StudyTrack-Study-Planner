import csv
from datetime import date, timedelta
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest

from studytrack.analytics import export_csv, streaks, weekly_totals
from studytrack.db import Store
from studytrack.demo import seed_demo
from studytrack.timer import FocusTimer


class StudyTrackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'study.db')
        self.sid = self.store.add_subject('IELTS Writing')
        self.today = date.today()

    def test_two_sessions_total_one_hour_45_and_persist(self):
        cpp = self.store.add_subject('C++')
        self.store.add_session(self.sid, self.today, 45 * 60)
        self.store.add_session(cpp, self.today, 60 * 60)
        rows = Store(self.store.path).sessions()
        self.assertEqual(sum(s['seconds'] for s in rows), 6300)
        self.assertEqual(weekly_totals(rows, self.today)[-1]['hours'], 1.75)

    def test_subject_uniqueness_and_archive_preserves_history(self):
        with self.assertRaises(ValueError):
            self.store.add_subject('ielts writing')
        self.store.add_session(self.sid, self.today, 60)
        self.store.archive_subject(self.sid)
        self.assertFalse(self.store.subjects())
        self.assertEqual(len(self.store.sessions()), 1)
        with self.assertRaises(ValueError):
            self.store.add_session(self.sid, self.today, 60)
        self.store.archive_subject(self.sid, False)
        self.assertEqual(len(self.store.subjects()), 1)

    def test_invalid_input_does_not_create_records(self):
        for minutes in [0, -1, 86401, 1.5, True]:
            with self.subTest(minutes=minutes), self.assertRaises(ValueError):
                self.store.add_session(self.sid, self.today, minutes)
        with self.assertRaises(ValueError):
            self.store.add_session(self.sid, self.today + timedelta(days=1), 60)
        with self.assertRaises(ValueError):
            self.store.add_subject('  ')
        with self.assertRaises(ValueError):
            self.store.add_task(self.sid, '  ', self.today)
        with self.assertRaises(ValueError):
            self.store.add_session(999, self.today, 60)
        self.assertEqual(self.store.sessions(), [])

    def test_tasks_can_be_completed_reopened_and_deleted(self):
        ident = self.store.add_task(self.sid, 'Write one essay', self.today)
        self.store.complete_task(ident, True)
        self.assertEqual(self.store.tasks()[0]['completed'], 1)
        self.store.complete_task(ident, False)
        self.assertEqual(self.store.tasks()[0]['completed'], 0)
        self.store.delete_task(ident)
        self.assertFalse(self.store.tasks())

    def test_daily_goal_updates_only_selected_day(self):
        self.store.set_goal(self.today, 90)
        self.store.set_goal(self.today, 150)
        self.assertEqual(self.store.goal(self.today), 150)
        self.assertEqual(self.store.goal(self.today + timedelta(days=1)), 120)
        with self.assertRaises(ValueError):
            self.store.set_goal(self.today, 0)

    def test_timer_excludes_pauses_and_resists_repeated_start(self):
        timer = FocusTimer(self.sid, str(self.today))
        timer.start(now=100)
        timer.start(now=110)
        self.assertEqual(timer.elapsed(now=130), 30)
        timer.pause(now=145)
        self.assertEqual(timer.elapsed(now=900), 45)
        timer.start(now=1000)
        timer.pause(now=1015)
        self.assertEqual(timer.elapsed(now=5000), 60)

    def test_timer_retry_does_not_double_count(self):
        first = self.store.add_session(self.sid, self.today, 60, source='timer', token='abc')
        second = self.store.add_session(self.sid, self.today, 60, source='timer', token='abc')
        self.assertEqual(first, second)
        self.assertEqual(len(self.store.sessions()), 1)

    def test_streak_handles_duplicates_gaps_and_yesterday(self):
        def rows(offsets):
            return [{'study_date': str(self.today - timedelta(days=n)), 'seconds': 60} for n in offsets]
        self.assertEqual(streaks(rows([]), self.today), (0, 0))
        self.assertEqual(streaks(rows([1, 2, 3, 3, 6, 7]), self.today), (3, 3))
        self.assertEqual(streaks(rows([2, 3, 4]), self.today), (0, 3))
        self.assertEqual(streaks(rows([0, 1, 2, 4, 5, 6, 7]), self.today), (3, 4))

    def test_week_is_seven_days_including_zeros(self):
        self.store.add_session(self.sid, self.today - timedelta(days=7), 3600)
        self.store.add_session(self.sid, self.today, 1800)
        week = weekly_totals(self.store.sessions(), self.today)
        self.assertEqual(len(week), 7)
        self.assertEqual(sum(r['hours'] for r in week), .5)
        self.assertEqual(week[0]['hours'], 0)

    def test_csv_preserves_unicode_quotes_and_neutralizes_formulas(self):
        sid = self.store.add_subject('=HYPERLINK("bad")')
        self.store.add_session(sid, self.today, 90, ' @SUM(1,2)\nதமிழ், "essay"')
        raw = export_csv(self.store.sessions()).decode('utf-8-sig')
        rows = list(csv.DictReader(io.StringIO(raw)))
        self.assertTrue(rows[0]['subject'].startswith("'="))
        self.assertTrue(rows[0]['note'].startswith("'@"))
        self.assertIn('தமிழ், "essay"', rows[0]['note'])
        self.assertEqual(rows[0]['minutes'], '1.5')

    def test_demo_seed_is_idempotent_and_separate(self):
        demo = Store(Path(self.temp.name) / 'demo.db')
        seed_demo(demo)
        seed_demo(demo)
        self.assertEqual(len(demo.sessions()), 7)
        self.assertEqual(len(demo.tasks()), 3)
        self.assertFalse(self.store.sessions())

    def test_foreign_keys_prevent_orphan_rows(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.connection() as con:
                con.execute("INSERT INTO tasks(subject_id,title,due_date) VALUES (999,'bad','2026-01-01')")


if __name__ == '__main__':
    unittest.main()
