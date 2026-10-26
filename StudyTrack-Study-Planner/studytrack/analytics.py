"""Pure calculations shared by the dashboard and tests."""
import csv
import io
from datetime import date, timedelta


def duration(seconds):
    minutes = int(seconds) // 60
    hours, minutes = divmod(minutes, 60)
    if not hours and not minutes and seconds:
        return '<1m'
    return f'{hours}h {minutes:02d}m' if hours else f'{minutes}m'


def weekly_totals(sessions, today):
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    totals = {d.isoformat(): 0 for d in days}
    for row in sessions:
        if row['study_date'] in totals:
            totals[row['study_date']] += row['seconds']
    return [{'date': d, 'hours': seconds / 3600} for d, seconds in totals.items()]


def streaks(sessions, today):
    days = sorted({date.fromisoformat(r['study_date']) for r in sessions
                   if r['seconds'] > 0 and r['study_date'] <= today.isoformat()})
    best = run = 0
    previous = None
    for day in days:
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    active = set(days)
    cursor = today if today in active else today - timedelta(days=1)
    current = 0
    while cursor in active:
        current += 1
        cursor -= timedelta(days=1)
    return current, best


def export_csv(sessions):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['id', 'date', 'subject', 'minutes', 'note', 'source'])
    for row in sessions:
        def safe(value):
            # Prevent spreadsheet formula execution in user-entered text.
            value = str(value)
            return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
        writer.writerow([row['id'], row['study_date'], safe(row['subject']),
                         round(row['seconds'] / 60, 2), safe(row['note']), row['source']])
    return stream.getvalue().encode('utf-8-sig')
