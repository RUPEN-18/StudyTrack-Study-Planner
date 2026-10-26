"""End-to-end Streamlit widget interactions, using an isolated temporary DB."""
from datetime import date
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

from studytrack.db import Store


@unittest.skipIf(AppTest is None, 'Install requirements.txt to run Streamlit UI tests')
class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'app.db'
        self.env = patch.dict(os.environ, {'STUDYTRACK_DB': str(self.db)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20)

    def page(self, label):
        self.at.sidebar.radio[0].set_value(label).run()
        self.assertFalse(self.at.exception)

    def button(self, label):
        return next(b for b in self.at.button if b.label == label)

    def test_empty_workspace_and_complete_study_flow(self):
        self.at.run()
        self.assertFalse(self.at.exception)
        self.page('Subjects')
        self.at.text_input[0].set_value('IELTS Writing')
        self.button('Add subject').click().run()
        self.assertFalse(self.at.exception)
        self.page('Log & focus')
        self.at.number_input[0].set_value(45)
        self.button('Save study session').click().run()
        self.assertFalse(self.at.exception)
        self.page('Daily tasks')
        self.at.text_input[0].set_value('Write one essay')
        self.button('Add task').click().run()
        self.at.checkbox[0].check().run()
        self.assertFalse(self.at.exception)
        self.page('Overview')
        self.assertEqual(self.at.metric[0].value, '45m')
        self.assertEqual(self.at.metric[3].value, '1/1')
        self.page('History')
        self.assertEqual(len(self.at.dataframe[0].value), 1)

    def test_demo_toggle_isolates_records_and_all_pages_render(self):
        self.at.run()
        self.at.sidebar.toggle[0].set_value(True).run()
        for page in ['Overview', 'Log & focus', 'Daily tasks', 'Subjects', 'History']:
            self.page(page)
        self.assertEqual(len(Store(self.db.with_name('studytrack-demo.db')).sessions()), 7)
        self.assertFalse(Store(self.db).sessions())
        self.at.sidebar.toggle[0].set_value(False).run()
        self.page('Overview')
        self.assertEqual(self.at.metric[0].value, '0m')


if __name__ == '__main__':
    unittest.main()
