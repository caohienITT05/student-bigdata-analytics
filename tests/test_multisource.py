"""Integration checks against full Spark exports and the running application."""
import csv
import json
import hashlib
import re
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.prepare import checksum, transfer, inside
from multisource import store
from multisource.catalog import source_catalog


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request('http://127.0.0.1:8000' + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read()
        def invalid(value):
            raise AssertionError('Invalid JSON number: ' + value)
        return json.loads(raw, parse_constant=invalid), len(raw)


class FullBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = store.report('sources_manifest')
        cls.status = request('/api/multi/status')[0]
        if not cls.status['ready']:
            raise AssertionError('Full batch required; sample output is insufficient')
        cls.db = sqlite3.connect(store.DATABASE)
        cls.db.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_dashboard_uses_current_frontend_version(self):
        version = hashlib.sha256((ROOT / 'static/multisource.jsx').read_bytes()).hexdigest()[:12]
        with urllib.request.urlopen('http://127.0.0.1:8000/dashboard') as response:
            html = response.read().decode('utf-8')
            self.assertEqual(response.headers.get('Cache-Control'), 'no-store')
        script = re.search(r'src="(/static/multisource\.jsx\?v=[a-f0-9]+)"', html)
        self.assertIsNotNone(script)
        self.assertEqual(script.group(1), '/static/multisource.jsx?v=' + version)
        for path in (script.group(1), '/static/index.html'):
            with urllib.request.urlopen('http://127.0.0.1:8000' + path) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get('Cache-Control'), 'no-store')

    def test_source_and_legacy_checksums(self):
        for item in self.manifest['files']:
            self.assertEqual(checksum(ROOT / item['file']), {k: item[k] for k in ('bytes', 'sha256')})
        for path, expected in self.manifest['legacy'].items():
            self.assertEqual(checksum(ROOT / path), expected, path)
        self.assertFalse((ROOT / 'train.csv').exists())
        self.assertFalse((ROOT / 'test.csv').exists())
        self.assertFalse((ROOT / 'open+university+learning+analytics+dataset').exists())

    def test_source_catalog_matches_all_ten_csv_headers(self):
        catalog, size = request('/api/multi/catalog')
        self.assertLess(size, 100_000)
        self.assertEqual([s['key'] for s in catalog['sources']], ['original','kaggle','oulad'])
        self.assertEqual([len(s['files']) for s in catalog['sources']], [1,2,7])
        files = [f for source in catalog['sources'] for f in source['files']]
        entries = {r['file']: r for r in self.manifest['files'] if r.get('csv')}
        self.assertEqual({f['path'] for f in files}, set(entries))
        for file in files:
            with self.subTest(file=file['name']):
                entry = entries[file['path']]
                with (ROOT / file['path']).open(encoding=entry['csv']['encoding'], newline='') as stream:
                    header = next(csv.reader(stream, delimiter=entry['csv']['delimiter']))
                self.assertEqual(file['rows'], entry['csv']['rows'])
                self.assertEqual(file['column_count'], len(header))
                self.assertEqual(len(file['fields']), len(header))
                self.assertEqual({f['key'] for f in file['fields']}, set(header))
                self.assertTrue(all(f['label'] and f['type'] and f['group'] in catalog['groups'] for f in file['fields']))
        by_key = {file['key']: file for file in files}
        self.assertNotIn('Target', {f['key'] for f in by_key['test']['fields']})
        self.assertNotIn('StudentID', {f['key'] for f in by_key['original']['fields']})
        oulad = {f['key'] for f in by_key['studentInfo']['fields']}
        self.assertIn('age_band', oulad)
        self.assertIn('region', oulad)
        self.assertNotIn('Nacionality', oulad)

    def test_catalog_missing_metadata_and_future_fields(self):
        with patch.object(store, 'report', return_value=None):
            with self.assertRaises(Exception) as context:
                source_catalog()
            self.assertEqual(context.exception.status_code, 503)
        manifest = json.loads(json.dumps(self.manifest))
        entry = next(item for item in manifest['files'] if item['source'] == 'original')
        entry['csv']['columns'].append('new_unannotated_field')
        with patch.object(store, 'report', return_value=manifest), patch.object(store, 'DATABASE', ROOT / 'missing.sqlite'):
            catalog = source_catalog()
            original = catalog['sources'][0]['files'][0]
            self.assertEqual(original['column_count'], 36)
            self.assertEqual(original['fields'][-1], {'key':'new_unannotated_field','label':'new_unannotated_field',
                'type':'Chưa có chú giải','group':'other'})

    def test_academic_source_filter_and_unlabelled_test(self):
        expected = sum(x['csv']['rows'] for x in self.manifest['files'] if x['source'] != 'oulad')
        full, size = request('/api/multi/academic/summary')
        self.assertEqual(full['totals']['records'], expected)
        self.assertLess(size, 100_000)
        self.assertEqual(set(full), {'sources', 'targets', 'histograms', 'totals', 'filters'})
        for source in ('original', 'kaggle_train', 'kaggle_test'):
            result = request('/api/multi/academic/summary?source=' + source)[0]
            sql_count = self.db.execute('SELECT SUM(records) FROM a_summary WHERE source=?', (source,)).fetchone()[0]
            self.assertEqual(result['totals']['records'], sql_count)
            self.assertEqual(result['filters'], {'source': source})
        test = request('/api/multi/academic/summary?source=kaggle_test')[0]
        self.assertEqual(test['totals']['labelled'], 0)
        self.assertTrue(all(r['target'] is None for r in test['targets']))
        self.assertTrue(all(r['dropout_percent'] is None for r in test['sources']))

    def test_removed_routes_filters_and_metadata(self):
        for path, expected in (
            ('/api/multi/academic/table?table=codes', 404),
            ('/api/multi/academic/table?table=ratios', 404),
            ('/api/multi/oulad/table?table=assessments', 404),
            ('/api/multi/academic/summary?labels=labelled', 422),
            ('/api/multi/academic/summary?kind=observed', 422),
            ('/api/multi/oulad/summary?scope=day30', 422),
            ('/api/multi/academic/summary?source=bad', 422),
            ('/api/multi/oulad/summary?module=bad', 422),
        ):
            with self.assertRaises(urllib.error.HTTPError) as context:
                request(path)
            self.assertEqual(context.exception.code, expected, path)
        schema = request('/openapi.json')[0]
        self.assertNotIn('/api/multi/academic/table', schema['paths'])
        self.assertNotIn('/api/multi/oulad/table', schema['paths'])
        for route, removed in (('academic', {'labels','kind'}), ('oulad', {'scope'})):
            parameters = schema['paths']['/api/multi/' + route + '/summary']['get']['parameters']
            self.assertFalse(removed & {p['name'] for p in parameters})
        self.assertEqual(set(self.status['metadata']['tables']), set(store.ACTIVE_TABLES))
        self.assertNotIn('analysis', self.status['metadata'])
        self.assertFalse(any('day30' in k or 'cutoff' in k for k in self.status['quality']['joins']))
        for name in self.status['quality']['reports']:
            request('/api/multi/reports/' + name)

    def test_oulad_full_course_rollups_and_sql(self):
        join = self.status['quality']['joins']
        self.assertEqual(join['input_vle_rows'], join['joined_vle_rows'])
        for query, module, presentation in (('', None, None), ('?module=AAA&presentation=2013J', 'AAA', '2013J'), ('?module=AAA', 'AAA', None)):
            result, size = request('/api/multi/oulad/summary' + query)
            population = result['population']
            where = "scope='full' AND code_module IS ? AND code_presentation IS ?"
            expected = dict(self.db.execute('SELECT * FROM b_population WHERE ' + where, (module,presentation)).fetchone())
            for key, value in population.items():
                self.assertEqual(value, expected[key])
            self.assertEqual(sum(r['enrolments'] for r in result['outcomes']), population['enrolments'])
            self.assertNotIn('scope', result['filters'])
            forbidden = {'mean_enrolment_score','late_submissions','low_activity_enrolments','banked_records','submissions'}
            self.assertFalse(forbidden & population.keys())
            self.assertTrue(all(not forbidden & row.keys() for row in result['outcomes']))
            self.assertLess(size, 100_000)
            sql_clicks = self.db.execute('SELECT SUM(clicks) FROM b_weekly WHERE ' + where, (module,presentation)).fetchone()[0]
            self.assertEqual(sum(r['clicks'] for r in result['weekly']), sql_clicks)
        full = request('/api/multi/oulad/summary')[0]['population']
        self.assertEqual(full['enrolments'], join['enrolments'])
        self.assertEqual(full['unique_learners'], join['unique_learners'])
        self.assertGreater(full['no_activity_enrolments'], 0)

    def test_old_statistics_search_filter_and_predictions(self):
        with (ROOT / 'student_predictions.csv').open(encoding='utf-8-sig', newline='') as stream:
            records = list(csv.DictReader(stream))
        stats = request('/api/stats')[0]
        self.assertEqual(stats['total_students'], len(records))
        self.assertEqual(stats['dropout_predicted'], sum(r['Predicted_Target'] == 'Dropout' for r in records))
        student = records[0]['StudentID']
        search = request('/api/students?search=' + student)[0]
        self.assertEqual(len(search), 1)
        self.assertEqual(str(search[0]['StudentID']), student)
        risk = request('/api/students?risk_only=true&limit=100')[0]
        self.assertTrue(risk and all(r['Predicted_Target'] == 'Dropout' for r in risk))
        mapping = {'Marital_status':'Marital_status', 'Nationality':'Nationality', 'Gender':'Gender', 'Age_at_enrollment':'Age_at_enrollment',
                   'Debtor':'Debtor', 'Tuition_fees_up_to_date':'Tuition fees up to date', 'Scholarship_holder':'Scholarship holder',
                   'Curricular_units_1st_sem_grade':'Curricular units 1st sem (grade)', 'Curricular_units_2nd_sem_grade':'Curricular units 2nd sem (grade)'}
        for label in ('Dropout', 'Enrolled', 'Graduate'):
            row = next(r for r in records if r['Predicted_Target'] == label)
            payload = {key: float(row[column]) if 'grade' in key else int(float(row[column])) for key, column in mapping.items()}
            prediction = request('/api/predict', payload)[0]
            self.assertEqual(prediction['prediction'], label)
            self.assertEqual(prediction['is_at_risk'], label == 'Dropout')

    def test_prediction_input_limits_and_independent_financial_flags(self):
        invalid = {
            'Age_at_enrollment': [-1, 0, 16, 71, 999, 20.5, '', None, True],
            'Curricular_units_1st_sem_grade': [-2.5, 20.01, '', None, True, 'NaN', float('nan'), float('inf')],
            'Curricular_units_2nd_sem_grade': [-0.1, 22.4, '', None, False, float('-inf')],
            'Debtor': [-1, 2, '', None, True],
            'Tuition_fees_up_to_date': [-1, 2, '', None, False],
            'Scholarship_holder': [-1, 2],
            'Gender': [-1, 2],
        }
        for field, values in invalid.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(urllib.error.HTTPError) as context:
                        request('/api/predict', {field: value})
                    self.assertEqual(context.exception.code, 422)
                    error = json.loads(context.exception.read())
                    self.assertTrue(any(row['loc'][-1] == field for row in error['detail']))
        for age in (17, 20, 70):
            for first, second in ((0, 20), (20, 0), (12.3456, 13.75)):
                result = request('/api/predict', {'Age_at_enrollment': age,
                    'Curricular_units_1st_sem_grade': first, 'Curricular_units_2nd_sem_grade': second})[0]
                self.assertIn(result['prediction'], ('Dropout','Enrolled','Graduate'))
        for debtor in (0, 1):
            for tuition in (0, 1):
                result = request('/api/predict', {'Debtor': debtor, 'Tuition_fees_up_to_date': tuition})[0]
                self.assertIn(result['prediction'], ('Dropout','Enrolled','Graduate'))

    def test_missing_export_and_protected_moves(self):
        with patch.object(store, 'DATABASE', ROOT / 'data/curated/nonexistent.sqlite'):
            self.assertFalse(store.ready())
            with self.assertRaises(Exception) as context:
                with store.database():
                    pass
            self.assertEqual(context.exception.status_code, 503)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'incoming.csv').write_text('a\n1\n')
            (root / 'different.csv').write_text('a\n2\n')
            with self.assertRaises(ValueError):
                transfer(root, 'incoming.csv', 'different.csv', False)
            self.assertEqual((root / 'different.csv').read_text(), 'a\n2\n')
            with self.assertRaises(ValueError):
                inside(root, '../outside.csv')


if __name__ == '__main__':
    unittest.main(verbosity=2)
