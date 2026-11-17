"""Run three prepared interview queries against an existing SQLite database.

Only Python's standard library is required. No extraction, rebuild, or API calls.
"""
import argparse
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent
FILES = {'weekly': 'weekly_counts.sql', 'peak': 'peak_nausea.sql',
         'medication': 'after_medication_change.sql'}
NOTES = {
    'weekly': 'Eligible reported counts only; partial reports are not complete-day totals. NULL is not zero.',
    'peak': 'Highest usable daily-worst nausea rating (1-5); all tied dates retained. Vomiting eligibility is separate.',
    'medication': 'Timing relative to recorded medication changes, not individual doses or causation. Rows are observation/change pairs.',
}


def query_sql(name, report_id=None):
    sql = (ROOT / 'sql' / FILES[name]).read_text().strip().rstrip(';')
    if name == 'peak':
        return sql
    order = 'week_start' if name == 'weekly' else 'changed_utc, event_date IS NULL, event_date, event_time, report_id, observation_id'
    report_filter = ' AND report_id = :report_id' if report_id else ''
    return f'SELECT * FROM (\n{sql}\n) AS prepared_query\nWHERE patient_id = :patient_id{report_filter}\nORDER BY {order}'


def run_query(db, name, run_id, patient_id, report_id=None):
    if report_id and name != 'medication':
        raise ValueError('--report is available only for the medication query.')
    if not db.is_file():
        raise ValueError('Database not found. Complete the offline setup in docs/demo_walkthrough.md before the interview.')
    connection = sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        if not connection.execute('SELECT 1 FROM analyses WHERE run_id=?', (run_id,)).fetchone():
            raise ValueError(f'No completed analysis for run {run_id!r}. Check --run-id.')
        if not connection.execute('SELECT 1 FROM run_patients WHERE run_id=? AND patient_id=?', (run_id, patient_id)).fetchone():
            raise ValueError(f'Patient {patient_id!r} is not in run {run_id!r}.')
        if report_id and not connection.execute(
            'SELECT 1 FROM report_results rr JOIN reports r ON r.report_id=rr.report_id '
            'WHERE rr.run_id=? AND rr.report_id=? AND r.patient_id=?',
            (run_id, report_id, patient_id)).fetchone():
            raise ValueError(f'Report {report_id!r} is not in this run and patient selection.')
        params = {'run_id': run_id, 'patient_id': patient_id, 'report_id': report_id}
        return [dict(row) for row in connection.execute(query_sql(name, report_id), params)]
    finally:
        connection.close()


def table(name, rows):
    if not rows:
        return 'No eligible matching rows. This does not mean no symptoms occurred.'
    if name == 'weekly':
        headers = ['Week of', 'Count', 'Coverage', 'Review days', 'Missing days', 'Partial days', 'Full days']
        cells = [[r['week_start'], r['reported_vomiting_count'],
                  f"{r['count_covered_days']}/{r['followup_days']}", r['review_days'],
                  r['missing_count_days'], r['partial_count_days'], r['completed_count_days']] for r in rows]
    elif name == 'peak':
        headers = ['Date', 'Nausea /5', 'Vomiting count', 'Count status', 'Source reports']
        cells = [[r['event_date'], r['nausea_severity'], r['vomiting_count'], r['count_status'],
                  ', '.join(json.loads(r['source_report_ids_json']))] for r in rows]
    else:
        headers = ['Source', 'Change', 'Medication', 'Changed at', 'Symptom', 'Symptom date', 'Time', 'Order', 'Review']
        cells = [[r['report_id'], r['change_id'], r['medication'], r['changed_at'], r['symptom'],
                  r['event_date'], r['event_time'], r['timing_status'],
                  'yes' if r['has_review_items'] else 'no'] for r in rows]
    # Escape controls so data cannot alter terminal formatting.
    clean = lambda v: 'NULL' if v is None else str(v).encode('unicode_escape').decode('ascii')
    cells = [[clean(v) for v in row] for row in cells]
    widths = [max(len(h), *(len(row[i]) for row in cells)) for i, h in enumerate(headers)]
    render = lambda row: ' | '.join(v.ljust(w) for v, w in zip(row, widths))
    return '\n'.join([render(headers), '-+-'.join('-' * w for w in widths), *(render(r) for r in cells)])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query', choices=FILES)
    parser.add_argument('--db', type=Path, default=ROOT / 'artifacts/longitudinal-text-demo/patient_reports.sqlite')
    parser.add_argument('--run-id', default='longitudinal-text-v1')
    parser.add_argument('--patient', default='P001')
    parser.add_argument('--report', help='Optional source report filter for medication timing')
    parser.add_argument('--format', choices=['table', 'json'], default='table')
    parser.add_argument('--show-sql', action='store_true', help='Show parameterized SQL and bound inputs before the table')
    args = parser.parse_args(argv)
    if args.show_sql and args.format == 'json':
        parser.error('--show-sql requires --format table; JSON output stays machine-readable.')
    try:
        rows = run_query(args.db, args.query, args.run_id, args.patient, args.report)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(2, f'{exc}\n')
    if args.format == 'json':
        print(json.dumps(rows, indent=2))
    else:
        print(f'Query: {args.query} | Patient: {args.patient} | Run: {args.run_id}')
        print(f'Database (read-only): {args.db.resolve()}')
        if args.show_sql:
            print(query_sql(args.query, args.report) + ';')
            print('Bound inputs:', json.dumps({'run_id': args.run_id, 'patient_id': args.patient, 'report_id': args.report}))
        print(table(args.query, rows))
        print(NOTES[args.query])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
