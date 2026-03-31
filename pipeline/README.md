# Stage 2 Pipeline

This folder contains the first Stage 2 implementation for KALS:

- Playwright reads the browser-side `kjt_events` buffer
- Python validates raw events against the frozen Stage 1 contract
- DuckDB stores validated raw events in a local analytical database

## Install

Create a virtual environment if you want:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

```bash
python3 -m pip install -r pipeline/requirements.txt
python3 -m playwright install chromium
```

## Run

Default run:

```bash
python3 pipeline/ingest_events.py
```

This will:

- open the local app pages with Playwright
- read `localStorage.kjt_events`
- validate and deduplicate events
- write valid events into `data/kals.duckdb`
- write invalid records into `validation_issues`

Refresh and query the first analytical views:

```bash
.venv/bin/python pipeline/query_insights.py --refresh-views
```

This prints:

- event counts by app
- recent raw events
- weak items
- confusion pairs
- first-pass accuracy by item
- item recency summaries
- prioritized review candidates
- next-session app summary

## Notes

- This script is intentionally local-first and small.
- It uses the frozen Stage 1 event contract from `STAGE1_EVENT_REFERENCE.md`.
- Existing local app progress stores are not touched.
- Playwright uses its own persistent browser profile in `.playwright-profile`.
- Data created in your normal browser profile is separate from the Playwright profile.

## Use The Playwright Browser For Stage 2

To create data that the Stage 2 pipeline can read reliably, open an app through the persistent Playwright profile:

```bash
.venv/bin/python pipeline/open_app.py alphabet
```

Then practice in that browser window. When you are done:

1. close the browser or stop the script with `Ctrl+C`
2. run the ingest:

```bash
.venv/bin/python pipeline/ingest_events.py
```

This keeps the browser context reproducible and makes the browser-to-Python bridge explicit.
