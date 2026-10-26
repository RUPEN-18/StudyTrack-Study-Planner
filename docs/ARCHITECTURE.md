# Architecture

StudyTrack is a local, single-user Streamlit application. The interface calls a small Python storage layer for all writes and uses pure analytics functions for the dashboard and export.

| Layer | Responsibility |
| --- | --- |
| `app.py` | Forms, navigation, filters, Plotly charts, timer controls |
| `studytrack/db.py` | Parameterized SQL, input validation, persistence |
| `studytrack/analytics.py` | Duration formatting, 7-day totals, streaks, CSV |
| `studytrack/timer.py` | Monotonic elapsed time, pause/resume, save token |
| `studytrack/demo.py` | Opt-in sample data in a separate database |

## Persistent model

| Table | Important columns | Relationships |
| --- | --- | --- |
| `subjects` | id, name, color, archived | Referenced by sessions and tasks |
| `sessions` | id, subject_id, study_date, seconds, note, source, token | Foreign key to subjects |
| `tasks` | id, subject_id, title, due_date, completed | Foreign key to subjects |
| `goals` | study_date, minutes | One goal per date |

Foreign keys are enabled for every SQLite connection. Subject names are case-insensitive unique using SQLite's built-in NOCASE collation (ASCII case folding). Subjects are archived rather than removed. Date indexes support future date-filtered SQL queries, while this small first version loads records into memory for filtering and charts.

Each storage call owns its connection and commits or rolls back before closing. SQL parameters keep subject names, notes, and task text out of SQL syntax. A unique timer token makes repeated saves of the same timer idempotent. CSV text fields that start with formula characters are prefixed with an apostrophe for safer opening in spreadsheet programs.

## Timer lifecycle

A new timer stores a subject, start date, unique token, accumulated seconds, and monotonic start time in Streamlit Session State. Pause folds the running interval into accumulated time. Resume starts another interval. Save pauses, validates the elapsed duration, commits a session, and removes the active timer. Only saved sessions enter analytics.

A Streamlit fragment refreshes the timer once per second while its page is active. Elapsed time is calculated from the clock rather than a count of refresh events. The timer survives navigation inside the app; closing or refreshing a tab may lose unsaved state. Each database path has its own timer state to isolate demo and personal workspaces.

## Boundaries

This project intentionally stays small: no external APIs, user accounts, background scheduler, or cloud sync. Daily dates use the server's local calendar; a locally run app therefore follows the user's computer. A public multi-user deployment requires authentication, per-user data isolation, durable storage, and deployment-specific configuration.
