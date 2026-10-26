# Package validation

Validation performed on 26 October 2026:

- Python source compilation.
- Twelve core tests for SQLite persistence, the 45 + 60 minute example, subject uniqueness and archival, input rejection, task lifecycle, per-date goals, stopwatch pause/resume, idempotent timer saves, streak boundaries, zero-filled weekly totals, CSV escaping, separate demo records, and foreign key protection.
- Review of Streamlit's official fragment and AppTest documentation for the timer update and UI test design.

The local environment did not include Streamlit or Plotly, and package downloads were blocked. Therefore the two Streamlit interaction tests were skipped, and a running browser layout and Windows launcher execution could not be verified here. Those tests are included for execution after installing dependencies, and in the supplied GitHub Actions workflow. Core tests use only Python's standard library and can run independently.

## After setup

1. Run `python -m unittest discover -s tests -v` and confirm the UI tests run instead of skipping.
2. Launch `run_app.bat`; check all five pages at your screen size.
3. Use demo mode to review charts and verify switching it off returns to your personal workspace.
4. Test a short timer: start, pause, resume, then save. Check the resulting session in History.
5. Export CSV and open it in Excel. Stop and restart the app to confirm records persist.

Official references:

- https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment
- https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest
