"""Local student activity analysis. No machine-learning or verified engagement claims."""
from __future__ import annotations
import bisect
import csv
import io
import math
import zipfile
from pathlib import Path
from statistics import mean
from flask import Flask, jsonify, render_template, request
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024
MAX_ROWS = 10000

@app.get("/health")
def health():
    return jsonify(status="ok")
FEATURES = [
    ('assignments_completed', 'Assignments completed', None),
    ('course_progress_percent', 'Course progress', 100),
    ('video_completion_rate', 'Video completion rate', 1),
    ('video_watch_percent', 'Video watched', 100),
    ('forum_interactions', 'Forum interactions', None),
    ('avg_session_minutes', 'Average session minutes', None),
    ('lms_logins_past_month', 'LMS logins / month', None),
    ('login_frequency_per_week', 'Logins / week', None),
]

class DataError(ValueError):
    pass

def read_rows(raw: bytes, filename: str):
    """Parse only CSV or bounded XLSX; ignore empty rows, not incomplete records."""
    suffix = Path(filename).suffix.lower()
    if suffix == '.xlsx':
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if sum(i.file_size for i in z.infolist()) > 60 * 1024 * 1024:
                    raise DataError('The expanded workbook exceeds 60 MB. Upload a smaller dataset.')
            book = load_workbook(io.BytesIO(raw), read_only=True, data_only=True, keep_links=False)
            sheet = book['Dataset'] if 'Dataset' in book.sheetnames else book.worksheets[0]
            rows = []
            for row_number, values in enumerate(sheet.iter_rows(values_only=True), 1):
                if any(v is not None and str(v).strip() for v in values):
                    rows.append((row_number, list(values)))
                if len(rows) > MAX_ROWS + 1:
                    raise DataError(f'Please upload no more than {MAX_ROWS:,} data rows.')
            book.close()
        except DataError:
            raise
        except Exception as e:
            raise DataError('Could not read this XLSX file. Ensure it is a valid, unencrypted workbook.') from e
    elif suffix == '.csv':
        try:
            text = raw.decode('utf-8-sig')
            rows = []
            for row_number, values in enumerate(csv.reader(io.StringIO(text)), 1):
                if any(v.strip() for v in values):
                    rows.append((row_number, values))
                if len(rows) > MAX_ROWS + 1:
                    raise DataError(f'Please upload no more than {MAX_ROWS:,} data rows.')
        except UnicodeDecodeError as e:
            raise DataError('Please save your CSV with UTF-8 encoding.') from e
    else:
        raise DataError('Choose a .xlsx or UTF-8 .csv file.')
    if len(rows) < 2:
        raise DataError('The file needs a header row and at least one student record.')
    headers = [str(v).strip() if v is not None else '' for v in rows[0][1]]
    if len(set(h for h in headers if h)) != len([h for h in headers if h]):
        raise DataError('Duplicate column names found. Give each column a unique name.')
    required = ['student_id'] + [f[0] for f in FEATURES]
    missing = [k for k in required if k not in headers]
    if missing:
        raise DataError('Missing required columns: ' + ', '.join(missing) + '. Use the supplied workbook or CSV template. Column names are case-sensitive.')
    return [dict(zip(headers, row), __source_row=number) for number, row in rows[1:]]

def options(payload):
    if not isinstance(payload, dict):
        raise DataError('Analysis settings must be a JSON object.')
    try:
        threshold = float(payload.get('threshold', 50.2))
        if not math.isfinite(threshold) or not 0 <= threshold <= 100:
            raise ValueError
        incoming = payload.get('weights', {})
        if not isinstance(incoming, dict):
            raise ValueError
        weights = {k: float(incoming.get(k, 1)) for k, _, _ in FEATURES}
        if any(not math.isfinite(v) or not 0 <= v <= 100 for v in weights.values()) or sum(weights.values()) == 0:
            raise ValueError
        return threshold, weights
    except (TypeError, ValueError):
        raise DataError('Threshold must be 0–100. Weights must be 0–100, with at least one positive weight.')

def analyse(rows, filename, threshold=50.2, weights=None):
    weights = weights or {k: 1 for k, _, _ in FEATURES}
    records = []
    identity_conflicts = 0
    for i, raw in enumerate(rows, 2):
        sid = str(raw.get('student_id') or '').strip()
        problems = [] if sid else ['Missing student_id']
        values = {}
        for key, label, maximum in FEATURES:
            try:
                original = raw.get(key)
                if original is None or isinstance(original, bool) or str(original).strip() == '':
                    raise ValueError
                value = float(original)
                if not math.isfinite(value) or value < 0 or (maximum is not None and value > maximum):
                    raise ValueError
                values[key] = value
            except (TypeError, ValueError):
                values[key] = None
                problems.append(f'{label}: missing or invalid value')
        original_label = str(raw.get('Engagement_Level') or '').strip()
        source_label = {'active': 'Active', 'passive': 'Passive'}.get(original_label.lower(), 'Unlabelled')
        if raw.get('Student_ID') is not None and str(raw['Student_ID']).strip() != sid:
            identity_conflicts += 1
        records.append({'row': raw.get('__source_row', i), 'student_id': sid or f'Missing ID (row {i})',
                        'course': str(raw.get('course_category') or 'Unspecified'),
                        'values': values, 'issues': problems, 'source_label': source_label,
                        'source_method': str(raw.get('Engagement_Label_Method') or 'Not specified in the uploaded file'),
                        'source_proxy': raw.get('Engagement_Score_Proxy') if isinstance(raw.get('Engagement_Score_Proxy'), (float, int)) else None,
                        'score': None, 'rule_label': 'Insufficient data', 'percentiles': {}})
    # Use complete records only for a consistent reference cohort across all indicators.
    complete = [r for r in records if not r['issues']]
    columns = {k: sorted(r['values'][k] for r in complete) for k, _, _ in FEATURES}
    for r in complete:
        for k, _, _ in FEATURES:
            v, col = r['values'][k], columns[k]
            # Average rank for ties, divided by cohort size, then scaled to 0–100.
            r['percentiles'][k] = (bisect.bisect_left(col, v) + 1 + bisect.bisect_right(col, v)) / 2 / len(complete) * 100
        r['score'] = round(sum(r['percentiles'][k] * weights[k] for k, _, _ in FEATURES) / sum(weights.values()), 2)
        r['rule_label'] = 'Active' if r['score'] >= threshold else 'Passive'
    ids = [r['student_id'] for r in records if not r['student_id'].startswith('Missing ID')]
    warnings = []
    if identity_conflicts:
        warnings.append(f'{identity_conflicts} rows have conflicting Student_ID and student_id values. The lowercase student_id field is used; records are not merged.')
    if len(ids) != len(set(ids)):
        warnings.append(f'{len(ids)-len(set(ids))} repeated student_id entries found. Rows are analysed separately; totals count records, not unique students.')
    if len(complete) != len(records):
        warnings.append(f'{len(records)-len(complete)} rows have missing or invalid required values. They are not scored and are excluded from the percentile reference cohort.')
    if len(complete) < 20:
        warnings.append('The valid cohort has fewer than 20 records. Relative rankings may be unstable; use with care.')
    if any(r['source_label'] != 'Unlabelled' and 'proxy' in r['source_method'].lower() for r in records):
        warnings.append('The workbook describes its labels as generated proxies, not verified ground truth. Agreement with them is not real-world accuracy.')
    return {'filename': filename, 'records': records, 'warnings': warnings,
            'total': len(records), 'unique_students': len(set(ids)), 'valid': len(complete),
            'threshold': threshold, 'weights': weights,
            'features': [{'key': k, 'label': label, 'maximum': maximum} for k, label, maximum in FEATURES],
            'has_source_labels': any(r['source_label'] != 'Unlabelled' for r in records),
            'averages': {k: round(mean(r['values'][k] for r in complete), 4) if complete else None for k, _, _ in FEATURES}}

@app.get('/')
def index():
    return render_template('index.html')

@app.post('/api/demo')
def demo():
    threshold, weights = options(request.get_json(silent=True) or {})
    path = ROOT / 'data' / 'demo_students.csv'
    return jsonify(analyse(read_rows(path.read_bytes(), path.name), path.name, threshold, weights))

@app.post('/api/upload')
def upload():
    file = request.files.get('file')
    if not file or not file.filename:
        raise DataError('Choose a CSV or XLSX dataset first.')
    import json
    try:
        payload = json.loads(request.form.get('settings', '{}'))
    except ValueError:
        raise DataError('Invalid analysis settings.')
    threshold, weights = options(payload)
    return jsonify(analyse(read_rows(file.read(), file.filename), Path(file.filename).name, threshold, weights))

@app.errorhandler(DataError)
def invalid(error):
    return jsonify(error=str(error)), 400

@app.errorhandler(413)
def too_large(error):
    return jsonify(error='File too large. Maximum upload size is 8 MB.'), 413

if __name__ == '__main__':
    print('\nEngage Lab Analytics → http://127.0.0.1:5000\nKeep this terminal open. Press Ctrl+C to stop.\n')
    app.run(host='127.0.0.1', port=5000, debug=False)
