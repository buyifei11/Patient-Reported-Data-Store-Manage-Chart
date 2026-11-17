"""Query semantics and offline presentation behavior."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import run_queries
from src.demo import build


class InterviewQueryTests(unittest.TestCase):
    def fixture(self, path):
        c = sqlite3.connect(path)
        c.executescript('''
            CREATE TABLE analyses (run_id TEXT);
            CREATE TABLE run_patients (run_id TEXT, patient_id TEXT);
            CREATE TABLE daily_summary (
              run_id TEXT, patient_id TEXT, event_date TEXT, nausea_severity INTEGER,
              nausea_status TEXT, vomiting_count INTEGER, count_status TEXT,
              source_report_ids_json TEXT);
            INSERT INTO analyses VALUES ('run'), ('other');
            INSERT INTO run_patients VALUES ('run','P001'), ('run','P002'), ('other','P001');
        ''')
        c.executemany('INSERT INTO daily_summary VALUES (?,?,?,?,?,?,?,?)', [
            ('run','P001','2026-11-01',4,'usable',None,'review','["A"]'),
            ('run','P001','2026-11-02',4,'usable',0,'usable','["B"]'),
            ('run','P001','2026-11-03',5,'review',None,'review','["C"]'),
            ('run','P001','2026-11-04',None,'missing',None,'missing','[]'),
            ('run','P002','2026-11-01',5,'usable',1,'usable','["D"]'),
            ('other','P001','2026-11-01',5,'usable',1,'usable','["E"]'),
        ])
        c.commit()
        c.close()

    def test_peak_preserves_ties_scope_and_field_specific_eligibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'data?#.sqlite'
            self.fixture(db)
            before = hashlib.sha256(db.read_bytes()).digest()
            rows = run_queries.run_query(db, 'peak', 'run', 'P001')
            self.assertEqual([r['event_date'] for r in rows], ['2026-11-01','2026-11-02'])
            self.assertEqual([r['nausea_severity'] for r in rows], [4,4])
            self.assertIsNone(rows[0]['vomiting_count'])
            self.assertEqual(rows[1]['vomiting_count'], 0)
            rendered = run_queries.table('peak', rows)
            self.assertIn('NULL', rendered)
            self.assertIn('review', rendered)
            self.assertEqual(hashlib.sha256(db.read_bytes()).digest(), before)

    def test_no_eligible_rating_stays_empty_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'data.sqlite'
            self.fixture(db)
            c = sqlite3.connect(db)
            c.execute("UPDATE daily_summary SET nausea_status='missing' WHERE patient_id='P001'")
            c.commit(); c.close()
            rows = run_queries.run_query(db, 'peak', 'run', 'P001')
            self.assertEqual(rows, [])
            self.assertIn('does not mean no symptoms', run_queries.table('peak', rows))

    def test_bad_selection_and_missing_database_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'data.sqlite'
            with self.assertRaisesRegex(ValueError, 'Database not found'):
                run_queries.run_query(db, 'peak', 'run', 'P001')
            self.assertFalse(db.exists())
            self.fixture(db)
            for run, patient in [('unknown','P001'), ('run',"P001' OR 1=1 --")]:
                with self.subTest(run=run, patient=patient), self.assertRaises(ValueError):
                    run_queries.run_query(db, 'peak', run, patient)
            with self.assertRaisesRegex(ValueError, 'only for the medication'):
                run_queries.run_query(db, 'peak', 'run', 'P001', 'A')

    def test_three_queries_use_the_stored_run_and_reject_wrong_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'demo'
            build(out)
            db = out / 'patient_reports.sqlite'
            weekly = run_queries.run_query(db, 'weekly', 'longitudinal-v1', 'P001')
            self.assertEqual(len(weekly), 5)
            week = next(r for r in weekly if r['week_start'] == '2026-11-09')
            self.assertEqual((week['reported_vomiting_count'], week['count_covered_days'], week['review_days']), (15,6,1))
            med = run_queries.run_query(db, 'medication', 'longitudinal-v1', 'P002', 'R003')
            self.assertEqual(len(med), 1)
            self.assertEqual((med[0]['change_id'], med[0]['event_time'], med[0]['timing_status']), ('M003','14:20','after'))
            with self.assertRaisesRegex(ValueError, 'not in this run and patient'):
                run_queries.run_query(db, 'medication', 'longitudinal-v1', 'P001', 'R003')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(run_queries.main(['peak','--db',str(db),'--run-id','longitudinal-v1','--format','json']),0)
            self.assertEqual(json.loads(output.getvalue())[0]['nausea_severity'],5)


if __name__ == '__main__':
    unittest.main()
