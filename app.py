"""StudyTrack — run with: python -m streamlit run app.py."""
from datetime import date, timedelta
from pathlib import Path
import os
import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from studytrack.analytics import duration, export_csv, streaks, weekly_totals
from studytrack.db import Store
from studytrack.demo import seed_demo
from studytrack.timer import FocusTimer

ROOT = Path(__file__).resolve().parent
TODAY = date.today()
st.set_page_config(page_title='StudyTrack | Make progress daily', page_icon='📚', layout='wide')
st.markdown('''<style>
    .block-container {padding-top:2.4rem; max-width:1260px; padding-bottom:3rem;}
    h1,h2,h3 {letter-spacing:-0.035em;}
    h1 {font-size:2.6rem !important; font-weight:750 !important;}
    [data-testid="stMetric"] {background:white; border:1px solid #E7E9F2;
        padding:20px; border-radius:16px; box-shadow:0 3px 14px #20233804;}
    [data-testid="stMetricLabel"] {color:#70758D; font-size:0.85rem;}
    [data-testid="stMetricValue"] {font-size:1.9rem; font-weight:700;}
    [data-testid="stSidebar"] {border-right:1px solid #E7E9F2;}
    .eyebrow {font-size:.72rem; font-weight:700; letter-spacing:.17em; color:#6C63FF;}
    .hero {background:linear-gradient(115deg,#242244,#3B326C); color:white;
        border-radius:20px; padding:26px 30px; margin:0 0 24px;}
    .hero h2 {color:white; margin:0; font-size:1.6rem;}
    .hero p {color:#D6D1ED; margin:6px 0 0;}
    .clock {font-size:4.4rem; letter-spacing:-.04em; font-weight:700;
        text-align:center; color:#6C63FF; font-variant-numeric:tabular-nums; padding:24px 0;}
    div.stButton > button {border-radius:10px;}
    [data-testid="stForm"] {background:#FFFFFF; border-radius:16px;}
</style>''', unsafe_allow_html=True)

with st.sidebar:
    st.markdown('## 📚 StudyTrack')
    st.caption('Small steps. Visible progress.')
    st.divider()
    demo = st.toggle('Try demo data', help='Uses a separate database. Your personal records stay separate.')
    page = st.radio('Workspace', ['Overview', 'Log & focus', 'Daily tasks', 'Subjects', 'History'],
                    label_visibility='collapsed')
    st.divider()
    st.caption('LOCAL WORKSPACE')
    st.caption('Python · Streamlit · SQLite')
    st.caption('Your study records are stored on this computer.')

db_path = Path(os.environ.get('STUDYTRACK_DB', str(ROOT / 'data' / 'studytrack.db')))
if demo:
    db_path = db_path.with_name('studytrack-demo.db')
try:
    store = Store(db_path)
    if demo:
        seed_demo(store)
    subjects = store.subjects()
    sessions = store.sessions()
    tasks = store.tasks()
except (sqlite3.Error, OSError) as exc:
    st.error(f'Unable to open your study database: {exc}')
    st.stop()

# The mode-specific key prevents a demo timer from being saved as a real session.
timer_key = f'focus_timer:{db_path.resolve()}'
timer = st.session_state.get(timer_key)
flash = st.session_state.pop('flash', None)
if flash:
    st.success(flash)
if demo:
    st.info('Demo workspace · Changes here affect only demo records. Turn off “Try demo data” to use your own workspace.')
if timer is not None and page != 'Log & focus':
    st.info('A focus timer is active or paused. Open “Log & focus” to manage or save it.')


def finish(message):
    st.session_state['flash'] = message
    st.rerun()


def subject_picker(label, key):
    return st.selectbox(label, [s['id'] for s in subjects],
                        format_func=lambda sid: next(s['name'] for s in subjects if s['id'] == sid), key=key)


def require_subjects():
    if not subjects:
        st.info('Add your first subject on the Subjects page, then come back here.')
        st.stop()


def style_chart(fig):
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family='Arial', color='#70758D'),
                      margin=dict(l=10, r=10, t=20, b=10), height=300,
                      showlegend=False)
    fig.update_yaxes(gridcolor='#E8EAF2', zeroline=False)
    fig.update_xaxes(showgrid=False)
    return fig


def overview():
    st.markdown('<span class="eyebrow">YOUR LEARNING WORKSPACE</span>', unsafe_allow_html=True)
    st.title('Make today count.')
    st.caption(TODAY.strftime('%A, %d %B %Y') + ' · Every focused session moves you forward.')
    st.markdown('''<div class="hero"><h2>Build consistency, one session at a time.</h2>
                <p>Plan something achievable. Focus on it. Watch your progress grow.</p></div>''',
                unsafe_allow_html=True)
    today_seconds = sum(r['seconds'] for r in sessions if r['study_date'] == TODAY.isoformat())
    week = weekly_totals(sessions, TODAY)
    week_seconds = round(sum(r['hours'] for r in week) * 3600)
    current, best = streaks(sessions, TODAY)
    today_tasks = [t for t in tasks if t['due_date'] == TODAY.isoformat()]
    completed = sum(t['completed'] for t in today_tasks)
    cols = st.columns(4)
    for col, label, value, help_text in zip(cols,
            ['Studied today', 'Last 7 days', 'Current streak', 'Today’s tasks'],
            [duration(today_seconds), duration(week_seconds), f'{current} days', f'{completed}/{len(today_tasks)}'],
            ['Completed study sessions', 'Today and the previous six days',
             f'Best streak: {best} days. Any saved study session counts; yesterday keeps your streak alive until today ends.',
             'Tasks with a due date of today']):
        col.metric(label, value, help=help_text)
    st.write('')
    left, right = st.columns([1.6, 1], gap='large')
    with left:
        st.subheader('Your weekly rhythm')
        st.caption('Study hours · rolling 7 days')
        frame = pd.DataFrame(week)
        frame['day'] = pd.to_datetime(frame['date']).dt.strftime('%a %d')
        fig = px.bar(frame, x='day', y='hours', labels={'hours': 'Hours', 'day': ''},
                     color_discrete_sequence=['#6C63FF'])
        fig.update_traces(marker_cornerradius=7, hovertemplate='%{x}<br>%{y:.2f} hours<extra></extra>')
        st.plotly_chart(style_chart(fig), use_container_width=True)
    with right:
        st.subheader('Today’s focus goal')
        goal = store.goal(TODAY)
        progress = today_seconds / (goal * 60)
        st.progress(min(progress, 1.0), text=f'{duration(today_seconds)} of {duration(goal * 60)} · {progress:.0%}')
        with st.form('goal'):
            target = st.number_input('Daily target (minutes)', min_value=1, max_value=1440, value=goal, step=15)
            if st.form_submit_button('Update goal', use_container_width=True):
                store.set_goal(TODAY, int(target))
                finish('Today’s goal updated.')
        st.caption('This target applies to today. New days start with a 2-hour target.')
    left, right = st.columns([1.6, 1], gap='large')
    with left:
        st.subheader('Where your time went')
        recent = [s for s in sessions if (TODAY - timedelta(days=6)).isoformat() <= s['study_date'] <= TODAY.isoformat()]
        if recent:
            df = pd.DataFrame(recent).groupby(['subject', 'color'], as_index=False)['seconds'].sum()
            df['hours'] = df['seconds'] / 3600
            fig = px.bar(df, y='subject', x='hours', orientation='h', color='subject',
                         color_discrete_map=dict(zip(df['subject'], df['color'])),
                         labels={'subject': '', 'hours': 'Hours'})
            st.plotly_chart(style_chart(fig), use_container_width=True)
        else:
            st.info('Your first saved session will start this chart. Add a subject, then log some study time.')
    with right:
        st.subheader('Up next')
        pending = [t for t in tasks if not t['completed'] and t['due_date'] <= TODAY.isoformat()]
        if not pending:
            st.caption('All clear. Add a task on the Daily tasks page.')
        for task in pending[:5]:
            with st.container(border=True):
                st.write(task['title'])
                st.caption(f"{task['subject']} · Due {task['due_date']}")
        if len(pending) > 5:
            st.caption(f'{len(pending) - 5} more tasks on the Daily tasks page.')


@st.fragment(run_every='1s')
def timer_panel():
    active = st.session_state.get(timer_key)
    if active is None:
        st.caption('Start a focused session. Pause anytime, then save when you finish.')
        sid = subject_picker('Focus subject', 'timer_subject')
        if st.button('▶ Start focus', type='primary', use_container_width=True):
            active = FocusTimer(sid, TODAY.isoformat())
            active.start()
            st.session_state[timer_key] = active
            st.rerun()
        return
    all_subjects = {s['id']: s['name'] for s in store.subjects(True)}
    st.write(f"Focusing on: **{all_subjects.get(active.subject_id, 'Subject')}**")
    elapsed = int(active.elapsed())
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    st.markdown(f'<div class="clock">{hours:02d}:{minutes:02d}:{seconds:02d}</div>', unsafe_allow_html=True)
    st.caption('Running' if active.started is not None else 'Paused')
    a, b = st.columns(2)
    if active.started is not None:
        if a.button('Pause', use_container_width=True):
            active.pause()
            st.rerun()
    elif a.button('Resume', use_container_width=True):
        active.start()
        st.rerun()
    note = st.text_input('Session note (optional)', max_chars=500, key=f'timer_note_{active.token}')
    if b.button('Save session', type='primary', use_container_width=True, disabled=elapsed < 1):
        active.pause()
        count = int(active.elapsed())
        try:
            store.add_session(active.subject_id, active.study_date, count, note, 'timer', active.token)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state[timer_key] = None
            finish(f'Focus session saved: {duration(count)}.')
    discard = st.checkbox('Confirm discard of this timer', key=f'discard_timer_{active.token}')
    if st.button('Discard timer', disabled=not discard):
        st.session_state[timer_key] = None
        finish('Timer discarded.')
    if elapsed > 86400:
        st.warning('Sessions are limited to 24 hours. Discard this timer and log the actual study time manually.')
    st.caption('Save before closing or refreshing the tab. Unsaved timers are kept only in this browser session. '
               'Paused time is excluded. Time while running counts even if you switch tabs. '
               'A session is assigned to the date it started; split it manually if you study across midnight.')


def log_focus():
    st.title('Give learning your attention.')
    st.caption('Capture a completed session, or start a focus timer.')
    require_subjects()
    left, right = st.columns(2, gap='large')
    with left:
        st.subheader('Log a session')
        with st.form('session_form', clear_on_submit=True):
            sid = subject_picker('Subject', 'log_subject')
            day = st.date_input('Study date', value=TODAY, max_value=TODAY)
            minutes = st.number_input('Minutes studied', min_value=1, max_value=1440, value=45, step=5)
            note = st.text_area('What did you work on?', max_chars=500, placeholder='e.g. IELTS Task 2: essay structure')
            if st.form_submit_button('Save study session', type='primary', use_container_width=True):
                try:
                    store.add_session(sid, day, int(minutes) * 60, note)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    finish('Study session saved.')
    with right:
        st.subheader('Focus timer')
        with st.container(border=True):
            timer_panel()


def daily_tasks():
    st.title('A little structure goes a long way.')
    st.caption('Turn big goals into clear daily actions.')
    if subjects:
        with st.expander('＋ Add a task', expanded=True):
            with st.form('new_task', clear_on_submit=True):
                title = st.text_input('Task', max_chars=160, placeholder='Solve 3 DSA problems')
                a, b = st.columns(2)
                with a:
                    sid = subject_picker('Subject', 'task_subject')
                with b:
                    day = st.date_input('Due date', value=TODAY)
                if st.form_submit_button('Add task', type='primary'):
                    try:
                        store.add_task(sid, title, day)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        finish('Task added.')
    else:
        st.info('Add or restore a subject on the Subjects page to create new tasks.')
    a, b = st.columns(2)
    view = a.selectbox('Show', ['Today', 'Overdue', 'Upcoming', 'All dates'])
    status = b.selectbox('Status', ['All', 'Pending', 'Completed'])
    visible = []
    for task in tasks:
        day = task['due_date']
        matches = (view == 'All dates' or view == 'Today' and day == TODAY.isoformat()
                   or view == 'Overdue' and day < TODAY.isoformat() and not task['completed']
                   or view == 'Upcoming' and day > TODAY.isoformat())
        if matches and (status == 'All' or bool(task['completed']) == (status == 'Completed')):
            visible.append(task)
    if not visible:
        st.info('No tasks match these filters.')
    for task in visible:
        with st.container(border=True):
            a, b = st.columns([5, 1])
            checked = a.checkbox(task['title'], value=bool(task['completed']),
                                 key=f"task_{db_path.resolve()}_{task['id']}")
            a.caption(f"{task['subject']} · Due {task['due_date']}")
            if checked != bool(task['completed']):
                store.complete_task(task['id'], checked)
                st.rerun()
            with b.popover('Delete'):
                st.caption('Permanently remove this task?')
                if st.button('Delete task', key=f"delete_task_{task['id']}"):
                    store.delete_task(task['id'])
                    finish('Task deleted.')


def manage_subjects():
    st.title('Make space for what you’re learning.')
    st.caption('IELTS, DSA, C++, college subjects — organize your own learning path.')
    with st.form('new_subject', clear_on_submit=True):
        a, b = st.columns([4, 1])
        name = a.text_input('Subject name', max_chars=60, placeholder='e.g. IELTS Writing')
        color = b.color_picker('Chart color', '#6C63FF')
        if st.form_submit_button('Add subject', type='primary'):
            try:
                store.add_subject(name, color)
            except ValueError as exc:
                st.error(str(exc))
            else:
                finish('Subject added.')
    if not subjects:
        st.info('Start with one subject. You can add more anytime.')
    st.subheader('Active subjects')
    for subject in subjects:
        with st.container(border=True):
            a, b = st.columns([5, 1])
            a.write(subject['name'])
            total = sum(s['seconds'] for s in sessions if s['subject_id'] == subject['id'])
            a.caption(f'{duration(total)} studied · all time')
            blocked = timer is not None and timer.subject_id == subject['id']
            if b.button('Archive', key=f"archive_{subject['id']}", disabled=blocked):
                store.archive_subject(subject['id'])
                finish('Subject archived. Your sessions and tasks are preserved.')
    st.caption('Archiving hides a subject from new sessions and tasks. Existing history and tasks remain available. '
               'Save or discard a subject’s focus timer before archiving it.')
    archived = [s for s in store.subjects(True) if s['archived']]
    if archived:
        with st.expander(f'Archived subjects ({len(archived)})'):
            for subject in archived:
                a, b = st.columns([5, 1])
                a.write(subject['name'])
                if b.button('Restore', key=f"restore_{subject['id']}"):
                    store.archive_subject(subject['id'], False)
                    finish('Subject restored.')


def history():
    st.title('Look how far you’ve come.')
    st.caption('Review saved sessions and export the history you need.')
    a, b, c = st.columns(3)
    earliest = min([date.fromisoformat(s['study_date']) for s in sessions], default=TODAY)
    start = a.date_input('From', value=earliest, max_value=TODAY)
    end = b.date_input('Through', value=TODAY, max_value=TODAY)
    all_subjects = {s['id']: s['name'] for s in store.subjects(True)}
    selected = c.selectbox('Subject', [None] + list(all_subjects),
                           format_func=lambda sid: 'All subjects' if sid is None else all_subjects[sid])
    if start > end:
        st.error('The start date must be on or before the end date.')
        return
    rows = [s for s in sessions if start.isoformat() <= s['study_date'] <= end.isoformat()
            and (selected is None or s['subject_id'] == selected)]
    st.caption(f"{len(rows)} sessions · {duration(sum(s['seconds'] for s in rows))} studied")
    if not rows:
        st.info('No study sessions in this range.')
        return
    frame = pd.DataFrame(rows)
    frame['minutes'] = (frame['seconds'] / 60).round(2)
    st.dataframe(frame[['id', 'study_date', 'subject', 'minutes', 'note', 'source']],
                 hide_index=True, use_container_width=True,
                 column_config={'id': 'ID', 'study_date': 'Date', 'subject': 'Subject',
                                'minutes': 'Minutes', 'note': 'Note', 'source': 'Source'})
    st.download_button('↓ Export filtered history as CSV', export_csv(rows),
                       file_name=f'studytrack-{start}-{end}.csv', mime='text/csv', use_container_width=True)
    with st.expander('Remove a session'):
        chosen = st.selectbox('Session to remove', [s['id'] for s in rows],
                             format_func=lambda ident: next(
                                 f"#{s['id']} · {s['study_date']} · {s['subject']} · {duration(s['seconds'])}"
                                 for s in rows if s['id'] == ident))
        confirmed = st.checkbox('Permanently delete this session')
        if st.button('Delete selected session', disabled=not confirmed):
            store.delete_session(chosen)
            finish('Session deleted.')


try:
    {'Overview': overview, 'Log & focus': log_focus, 'Daily tasks': daily_tasks,
     'Subjects': manage_subjects, 'History': history}[page]()
except sqlite3.Error:
    st.error('The database operation could not finish. Try again, and make sure the data folder is writable.')
st.divider()
st.caption('STUDYTRACK  /  Plan with intention. Learn with focus.')
