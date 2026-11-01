# Student Engagement Analyzer

A Flask dashboard for exploring student activity using transparent Active/Passive proxy scores. The public demo uses **500 fictional records**. No original student workbook is included.

## Features

CSV/XLSX upload, data validation, configurable weights and threshold, visual summaries, searchable student records, individual explanations and CSV export.

## Run locally

Python 3.9+ is required. From this folder:

```bash
python3 run.py
```

The launcher prepares the environment on first use. Open http://127.0.0.1:5000.

## Publish with GitHub + Render

1. Create a GitHub repository named `student-engagement-analyzer` and upload the **contents** of this folder. `app.py`, `requirements.txt` and `render.yaml` must be at the repository root.
2. In Render, create a Blueprint from that repository. The included render.yaml defines a free Python web service.
3. Alternatively create a Web Service with build command `pip install -r requirements.txt` and start command `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120`.
4. Use the deployment URL returned by Render for your presentation. GitHub Pages cannot execute Flask.

The configuration requests the free service plan. Confirm the available plan in your Render account. Free services can sleep when inactive; open the live site before presenting to allow startup time.

## Analysis method

Eight indicators are converted to within-upload average percentile ranks (ties receive their average rank). Their weighted mean is rounded to two decimals. A score at least the configured threshold is labelled Active; otherwise Passive. Default: equal weights and a 50.2 threshold, an illustrative setting rather than a validated standard. Invalid rows remain visible but are not scored or used in the ranking reference cohort.

Required columns: student_id, assignments_completed, course_progress_percent (0–100), video_completion_rate (0–1), video_watch_percent (0–100), forum_interactions, avg_session_minutes, lms_logins_past_month, login_frequency_per_week. Other required numeric fields must be finite and nonnegative. An example CSV is included in data/upload_template.csv. XLSX uses the Dataset worksheet if present, otherwise its first worksheet. Maximum upload: 8 MB and 10,000 records.

Optional: course_category, Engagement_Level, Engagement_Label_Method, Engagement_Score_Proxy. Supplied labels are preserved separately from calculated labels. A repeated student ID is treated as separate records, not automatically merged.

## Interpretation and privacy

This is a descriptive project demonstration, not a trained ML model or verified student assessment. Synthetic labels are generated from the score itself; agreement with them is not accuracy against ground truth. Cohort-relative ranks change when the dataset changes. Recorded activity does not by itself establish understanding or motivation.

Uploads to a hosted version are sent to its Python server over the hosting provider's connection, processed in memory and returned to the uploading browser. They are not saved to disk by the app or shared through another visitor's dashboard. No third-party analytics or browser assets are loaded. Refresh restores the fictional demo. Do not upload confidential student data to a public demo without appropriate authorization. Use results for exploration, not grades or eligibility decisions.

## Testing

```bash
python -m unittest -v test_public.py
```

The GitHub workflow runs these tests after pushes and pull requests. Local tests do not verify a completed cloud deployment.
