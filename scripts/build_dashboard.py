#!/usr/bin/env python3
"""
Build a static HTML dashboard of Colorado Legislature data.

Generates a self-contained HTML dashboard with three tabs:
- Bills: All bills with search, filter, sort
- Hearings: Committee recordings with transcript status
- Search: Cross-data full-text search (bills + transcripts)

Also generates public/transcripts.json for client-side transcript search.

Usage:
    python3 scripts/build_dashboard.py
    python3 scripts/build_dashboard.py --output public/index.html --open
"""
import argparse
import json
import html
import re
import sys
import os
import glob
import subprocess
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Suppress SSL warnings
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cache.manager import CacheManager
from scrapers.bills import list_bills
from scrapers.sessions import get_current_session

DATA_DIR = Path(__file__).parent.parent / 'data'
BILL_SUMMARIES_DIR = DATA_DIR / 'bill_summaries'
BASE_URL = "https://leg.colorado.gov"
SUMMARY_CACHE_HOURS = 24


def _fetch_one_bill_summary(bill_number, bill_url):
    """Fetch long title + summary for a single bill from its detail page.

    Returns dict with bill_number, long_title, summary, or None on failure.
    """
    url = bill_url or f"{BASE_URL}/bills/{bill_number.lower()}"
    try:
        resp = requests.get(url, timeout=20, verify=False)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')

    long_title = ''
    lt_elem = soup.find('p', class_='bill-long-title')
    if lt_elem:
        long_title = lt_elem.get_text(strip=True)

    summary = ''
    sw = soup.find('div', class_='bill-detail-bill-summary-wrapper')
    if sw:
        summary = sw.get_text(strip=True)
        # Remove heading and trailing note
        summary = summary.replace('Bill Summary:', '').strip()
        summary = re.sub(r'\(Note:.*?\)$', '', summary).strip()

    if not long_title and not summary:
        return None

    return {
        'bill_number': bill_number,
        'long_title': long_title,
        'summary': summary,
    }


def fetch_bill_summaries(bills, max_workers=10):
    """Fetch bill summaries for all bills, using a 24h file cache.

    Args:
        bills: List of bill dicts (from list_bills) with bill_number, url
        max_workers: Thread pool size for parallel fetching

    Returns:
        list of {bill_number, long_title, summary} dicts
    """
    BILL_SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.now() - timedelta(hours=SUMMARY_CACHE_HOURS)
    results = []
    to_fetch = []  # (bill_number, url, cache_path)

    for b in bills:
        bn = b['bill_number']
        cache_path = BILL_SUMMARIES_DIR / f"{bn}.json"
        if cache_path.exists():
            mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
            if mtime > cutoff:
                try:
                    data = json.loads(cache_path.read_text())
                    results.append(data)
                    continue
                except (json.JSONDecodeError, IOError):
                    pass
        to_fetch.append((bn, b.get('url', ''), cache_path))

    if not to_fetch:
        return results

    print(f"  Fetching {len(to_fetch)} bill summaries ({len(bills) - len(to_fetch)} cached)...")

    def _worker(item):
        bn, url, cache_path = item
        data = _fetch_one_bill_summary(bn, url)
        if data:
            try:
                cache_path.write_text(json.dumps(data, ensure_ascii=False))
            except IOError:
                pass
        return data

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_worker, item): item for item in to_fetch}
        done = 0
        for future in as_completed(futures):
            done += 1
            if done % 50 == 0:
                print(f"    {done}/{len(to_fetch)} fetched...")
            data = future.result()
            if data:
                results.append(data)

    return results


def build_bill_text_index(bills, summaries, output_path):
    """Build bills_text.json search index from bill summaries.

    Args:
        bills: List of bill dicts (from list_bills)
        summaries: List of summary dicts (from fetch_bill_summaries)
        output_path: Path to write bills_text.json

    Returns:
        int: Number of bills indexed
    """
    summary_map = {s['bill_number']: s for s in summaries}
    index = []
    for b in bills:
        bn = b['bill_number']
        s = summary_map.get(bn, {})
        entry = {
            'bill_number': bn,
            'title': b.get('title', ''),
            'long_title': s.get('long_title', ''),
            'summary': s.get('summary', ''),
            'sponsors': b.get('sponsors', []),
            'subjects': b.get('subjects', []),
            'url': b.get('url', f'{BASE_URL}/bills/{bn.lower()}'),
        }
        # Only include if we have some searchable text beyond the title
        if entry['long_title'] or entry['summary']:
            index.append(entry)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False), encoding='utf-8')
    return len(index)


def load_recordings():
    """Load all SLIQ recordings from cache, deduplicated and sorted by date."""
    recordings = []
    seen = set()
    rec_dir = DATA_DIR / 'recordings'
    if not rec_dir.exists():
        return recordings

    for f in sorted(rec_dir.glob('sliq_recordings_*.json')):
        with open(f) as fh:
            recs = json.load(fh)
        if isinstance(recs, list):
            for r in recs:
                cid = r.get('clip_id', '')
                if cid and cid not in seen:
                    seen.add(cid)
                    recordings.append(r)

    recordings.sort(key=lambda r: r.get('date', ''), reverse=True)
    return recordings


def load_transcripts():
    """Load transcript metadata and match to recordings."""
    transcripts = {}
    t_dir = DATA_DIR / 'transcripts'
    if not t_dir.exists():
        return transcripts

    for f in sorted(t_dir.glob('transcript_*.json')):
        with open(f) as fh:
            t = json.load(fh)
        clip_id = t.get('clip_id', '')
        if not clip_id:
            continue
        utts = t.get('utterances', [])
        # Check for real content: either multiple utterances OR substantial text
        has_content = len(utts) > 1 or len(t.get('text', '')) > 500
        transcripts[clip_id] = {
            'utterance_count': len(utts),
            'speaker_count': t.get('speaker_count', 0),
            'transcribed_at': t.get('transcribed_at', ''),
            'has_transcript': has_content,
        }

    return transcripts


def build_transcript_index(output_path):
    """Generate transcripts.json search index for client-side full-text search."""
    t_dir = DATA_DIR / 'transcripts'
    if not t_dir.exists():
        return 0

    index = []
    rec_map = {}
    # Load recording metadata for committee/date info
    rec_dir = DATA_DIR / 'recordings'
    if rec_dir.exists():
        for f in rec_dir.glob('sliq_recordings_*.json'):
            with open(f) as fh:
                recs = json.load(fh)
            if isinstance(recs, list):
                for r in recs:
                    rec_map[r.get('clip_id', '')] = r

    for f in sorted(t_dir.glob('transcript_*.json')):
        with open(f) as fh:
            t = json.load(fh)
        clip_id = t.get('clip_id', '')
        utts = t.get('utterances', [])
        full_text = t.get('text', '')

        # Skip if no real content
        if len(utts) <= 1 and len(full_text) < 500:
            continue

        rec = rec_map.get(clip_id, {})

        # For single-utterance transcripts (diarization failed), chunk the
        # full text into ~500-char segments so search can find matches
        if len(utts) <= 1 and len(full_text) >= 500:
            chunks = []
            for i in range(0, len(full_text), 500):
                chunks.append({
                    'speaker': '?',
                    'text': full_text[i:i+500],
                    'start': 0,
                })
            indexed_utts = chunks
        else:
            indexed_utts = [
                {
                    'speaker': u.get('speaker', '?'),
                    'text': u.get('text', '')[:500],
                    'start': u.get('start', 0),
                }
                for u in utts
            ]

        entry = {
            'clip_id': clip_id,
            'committee': rec.get('committee', ''),
            'committee_name': rec.get('committee_name', ''),
            'date': rec.get('date', ''),
            'title': rec.get('title', clip_id),
            'video_url': rec.get('video_url', ''),
            'utterances': indexed_utts,
        }
        index.append(entry)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False), encoding='utf-8')
    return len(index)


def format_ms(ms):
    """Format milliseconds as HH:MM:SS."""
    if not ms:
        return '00:00:00'
    total_s = int(ms / 1000)
    h, rem = divmod(total_s, 3600)
    m, s = divmod(rem, 60)
    return f'{h:02d}:{m:02d}:{s:02d}'


def build_dashboard(output_path: str, session: str = None):
    """Fetch all data and generate a tabbed HTML dashboard."""
    if not session:
        session = get_current_session()

    # --- Bills ---
    print(f"Fetching bills for session {session}...")
    cache = CacheManager()
    bills = list_bills(session=session, limit=9999, cache_manager=cache)
    print(f"  {len(bills)} bills")

    house_count = sum(1 for b in bills if b['bill_number'].startswith('H'))
    senate_count = sum(1 for b in bills if b['bill_number'].startswith('S'))

    all_subjects = sorted(set(
        s for b in bills for s in b.get('subjects', [])
    ))

    # --- Recordings + Transcripts ---
    print("Loading recordings and transcripts...")
    recordings = load_recordings()
    transcripts = load_transcripts()

    # Merge transcript info into recordings
    for r in recordings:
        cid = r.get('clip_id', '')
        t = transcripts.get(cid, {})
        r['has_transcript'] = t.get('has_transcript', False)
        r['utterance_count'] = t.get('utterance_count', 0)
        r['speaker_count'] = t.get('speaker_count', 0)

    transcribed_count = sum(1 for r in recordings if r.get('has_transcript'))
    total_hours = sum(r.get('duration_seconds', 0) for r in recordings) / 3600
    committees = sorted(set(r.get('committee_name', '') for r in recordings if r.get('committee_name')))

    print(f"  {len(recordings)} recordings, {transcribed_count} transcribed, {total_hours:.0f}h total")

    # --- Transcript search index ---
    transcript_index_path = str(Path(output_path).parent / 'transcripts.json')
    print("Building transcript search index...")
    idx_count = build_transcript_index(transcript_index_path)
    print(f"  {idx_count} transcripts indexed")

    # --- Bill summaries search index ---
    bill_text_index_path = str(Path(output_path).parent / 'bills_text.json')
    print("Fetching bill summaries...")
    summaries = fetch_bill_summaries(bills)
    print(f"  {len(summaries)} summaries fetched")
    bill_idx_count = build_bill_text_index(bills, summaries, bill_text_index_path)
    print(f"  {bill_idx_count} bills indexed in bills_text.json")

    # --- Generate HTML ---
    bills_json = json.dumps(bills, ensure_ascii=False)
    recordings_json = json.dumps(recordings, ensure_ascii=False)
    now = datetime.now().strftime('%B %d, %Y at %I:%M %p')
    year = session[:4] if len(session) >= 4 else str(datetime.now().year)

    html_content = _build_html(
        year=year,
        bills_json=bills_json,
        bills_count=len(bills),
        house_count=house_count,
        senate_count=senate_count,
        subjects_sorted=all_subjects,
        recordings_json=recordings_json,
        recordings_count=len(recordings),
        transcribed_count=transcribed_count,
        total_hours=total_hours,
        committees=committees,
        now=now,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_content, encoding='utf-8')

    idx_size = os.path.getsize(transcript_index_path) if os.path.exists(transcript_index_path) else 0
    bill_idx_size = os.path.getsize(bill_text_index_path) if os.path.exists(bill_text_index_path) else 0
    print(f"Dashboard: {out} ({len(html_content):,} bytes)")
    print(f"Transcript index: {transcript_index_path} ({idx_size:,} bytes)")
    print(f"Bill text index: {bill_text_index_path} ({bill_idx_size:,} bytes)")
    return str(out)


def _build_html(*, year, bills_json, bills_count, house_count, senate_count,
                subjects_sorted, recordings_json, recordings_count,
                transcribed_count, total_hours, committees, now):
    """Generate the full HTML dashboard."""

    subjects_options = ''.join(
        f'<option value="{html.escape(s)}">{html.escape(s)}</option>'
        for s in subjects_sorted
    )
    committee_options = ''.join(
        f'<option value="{html.escape(c)}">{html.escape(c)}</option>'
        for c in committees
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Colorado Legislature Monitor &mdash; {year} Session</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
body{{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
  margin:0;padding:0;background:#f0f2f5;color:#1a1a2e;line-height:1.5;
}}
.container{{max-width:1280px;margin:0 auto;padding:24px 20px}}
header{{
  background:linear-gradient(135deg,#1a365d 0%,#2563eb 100%);
  color:#fff;padding:28px 20px;text-align:center;
}}
header h1{{margin:0 0 4px;font-size:1.6rem;font-weight:700;letter-spacing:-0.02em}}
header p{{margin:0;opacity:0.85;font-size:0.9rem}}

/* Tabs */
.tab-bar{{
  display:flex;background:#1e293b;border-bottom:2px solid #2563eb;
}}
.tab-btn{{
  padding:12px 28px;border:none;background:transparent;color:#94a3b8;
  font-size:0.95rem;font-weight:600;cursor:pointer;transition:all 0.15s;
  border-bottom:3px solid transparent;margin-bottom:-2px;
}}
.tab-btn:hover{{color:#e2e8f0;background:rgba(255,255,255,0.05)}}
.tab-btn.active{{color:#fff;border-bottom-color:#2563eb;background:rgba(37,99,235,0.15)}}
.tab-content{{display:none}}
.tab-content.active{{display:block}}

/* Stats */
.stats-bar{{
  display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin:16px 0 20px;
}}
.stat{{
  background:#fff;border-radius:8px;padding:12px 20px;text-align:center;
  min-width:110px;box-shadow:0 1px 3px rgba(0,0,0,0.06);
}}
.stat .num{{font-size:1.4rem;font-weight:700;display:block;color:#1a365d}}
.stat .label{{font-size:0.75rem;text-transform:uppercase;letter-spacing:0.05em;color:#6b7280}}

/* Controls */
.controls{{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:16px}}
.search-wrapper{{flex:1;min-width:200px;position:relative}}
.search-box{{
  width:100%;padding:10px 14px;font-size:0.95rem;border:1px solid #d1d5db;
  border-radius:6px;outline:none;transition:border-color 0.15s;
}}
.search-box:focus{{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,0.1)}}
.search-status{{font-size:0.8rem;color:#6b7280;margin-top:4px;min-height:1.2em}}
.search-status.loading{{color:#2563eb}}
.search-status.error{{color:#dc2626}}
.filter-select{{
  padding:10px 14px;font-size:0.95rem;border:1px solid #d1d5db;
  border-radius:6px;background:#fff;cursor:pointer;min-width:140px;
}}
.toggle-group{{display:flex;border:1px solid #d1d5db;border-radius:6px;overflow:hidden}}
.toggle-btn{{
  padding:10px 16px;border:none;background:#fff;cursor:pointer;
  font-size:0.9rem;font-weight:500;color:#4b5563;transition:all 0.15s;
}}
.toggle-btn:not(:last-child){{border-right:1px solid #d1d5db}}
.toggle-btn.active{{background:#2563eb;color:#fff}}
.toggle-btn:hover:not(.active){{background:#f3f4f6}}
.results-count{{font-size:0.85rem;color:#6b7280;margin-bottom:8px}}

/* Tables */
table{{
  width:100%;border-collapse:collapse;background:#fff;border-radius:8px;
  overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);
}}
thead th{{
  background:#1e293b;color:#fff;padding:12px 14px;text-align:left;
  font-weight:600;font-size:0.82rem;text-transform:uppercase;letter-spacing:0.03em;
  cursor:pointer;user-select:none;white-space:nowrap;
}}
thead th:hover{{background:#334155}}
thead th .sort-arrow{{margin-left:4px;opacity:0.4;font-size:0.75rem}}
thead th.sorted .sort-arrow{{opacity:1}}
tbody td{{padding:10px 14px;border-bottom:1px solid #f1f5f9;font-size:0.9rem;vertical-align:top}}
tbody tr:hover{{background:#f8fafc}}
tbody tr:last-child td{{border-bottom:none}}
a{{color:#2563eb;text-decoration:none}}
a:hover{{text-decoration:underline}}
.bill-num,.clip-date{{font-weight:600;white-space:nowrap}}
.subjects-cell,.sponsors-cell{{font-size:0.8rem;color:#6b7280}}
.last-action-cell{{font-size:0.85rem;color:#4b5563}}

/* Badges */
.badge{{
  display:inline-block;padding:2px 8px;border-radius:4px;
  font-size:0.75rem;font-weight:600;
}}
.badge-yes{{background:#dcfce7;color:#166534}}
.badge-no{{background:#f1f5f9;color:#94a3b8}}
.badge-bill{{background:#dbeafe;color:#1e40af}}
.badge-hearing{{background:#fef3c7;color:#92400e}}

/* Expandable transcript preview */
.utterance-preview{{
  display:none;background:#f8fafc;border-top:1px solid #e2e8f0;
}}
.utterance-preview.open{{display:table-row}}
.utterance-preview td{{padding:16px 14px}}
.utterance-list{{margin:0;padding:0;list-style:none;font-size:0.85rem;line-height:1.6}}
.utterance-list li{{
  padding:4px 0;border-bottom:1px solid #f1f5f9;
}}
.utterance-list li:last-child{{border-bottom:none}}
.utt-speaker{{font-weight:600;color:#1a365d;margin-right:8px}}
.utt-time{{font-size:0.75rem;color:#9ca3af;margin-right:8px}}
.expand-btn{{
  background:none;border:none;color:#2563eb;cursor:pointer;font-size:0.85rem;
  padding:0;text-decoration:underline;
}}

/* Search results */
.search-section{{margin-bottom:32px}}
.search-section h3{{
  font-size:1rem;font-weight:600;color:#1e293b;margin:0 0 12px;
  padding-bottom:8px;border-bottom:2px solid #e2e8f0;
}}
.search-result{{
  padding:12px 16px;margin-bottom:8px;background:#fff;border-radius:6px;
  box-shadow:0 1px 2px rgba(0,0,0,0.04);border-left:3px solid #d1d5db;
}}
.search-result.type-bill{{border-left-color:#2563eb}}
.search-result.type-hearing{{border-left-color:#f59e0b}}
.sr-title{{font-weight:600;margin-bottom:4px}}
.sr-meta{{font-size:0.8rem;color:#6b7280;margin-bottom:4px}}
.sr-context{{font-size:0.85rem;color:#4b5563;line-height:1.5}}
.sr-context mark{{background:#fef3c7;padding:0 2px;border-radius:2px}}

.no-results{{text-align:center;padding:48px 20px;color:#6b7280;font-size:1rem}}
footer{{text-align:center;padding:32px 20px;font-size:0.8rem;color:#9ca3af}}
footer a{{color:#6b7280}}

@keyframes spin{{to{{transform:rotate(360deg)}}}}
.spinner{{
  display:inline-block;width:14px;height:14px;border:2px solid #d1d5db;
  border-top-color:#2563eb;border-radius:50%;animation:spin 0.6s linear infinite;
  vertical-align:middle;margin-right:6px;
}}
@media(max-width:768px){{
  header h1{{font-size:1.3rem}}
  .controls{{flex-direction:column}}
  .search-box,.filter-select{{width:100%}}
  .tab-btn{{padding:10px 14px;font-size:0.85rem}}
  thead th,tbody td{{padding:8px 10px;font-size:0.8rem}}
  .subjects-cell,.sponsors-cell{{display:none}}
}}
</style>
</head>
<body>

<header>
  <h1>Colorado Legislature Monitor</h1>
  <p>{year} Regular Session</p>
</header>

<div class="tab-bar">
  <button class="tab-btn active" data-tab="bills">Bills ({bills_count})</button>
  <button class="tab-btn" data-tab="hearings">Hearings ({recordings_count})</button>
  <button class="tab-btn" data-tab="search">Search</button>
</div>

<!-- ===== BILLS TAB ===== -->
<div class="tab-content active" id="tab-bills">
<div class="container">
  <div class="stats-bar">
    <div class="stat"><span class="num">{bills_count}</span><span class="label">Total Bills</span></div>
    <div class="stat"><span class="num">{house_count}</span><span class="label">House</span></div>
    <div class="stat"><span class="num">{senate_count}</span><span class="label">Senate</span></div>
  </div>
  <div class="controls">
    <div class="search-wrapper">
      <input type="text" class="search-box" id="billSearchBox"
             placeholder="Search by keyword, bill number, sponsor, subject...">
      <div class="search-status" id="billSearchStatus"></div>
    </div>
    <div class="toggle-group">
      <button class="toggle-btn active" data-chamber="all">All</button>
      <button class="toggle-btn" data-chamber="House">House</button>
      <button class="toggle-btn" data-chamber="Senate">Senate</button>
    </div>
    <select class="filter-select" id="subjectFilter">
      <option value="">All Subjects</option>
      {subjects_options}
    </select>
  </div>
  <div class="results-count" id="billResultsCount"></div>
  <table>
    <thead><tr>
      <th data-sort="bill_number" class="sorted">Bill # <span class="sort-arrow">&#9650;</span></th>
      <th data-sort="title">Title <span class="sort-arrow">&#9650;</span></th>
      <th data-sort="sponsors">Sponsors <span class="sort-arrow">&#9650;</span></th>
      <th data-sort="subjects">Subjects <span class="sort-arrow">&#9650;</span></th>
      <th data-sort="last_action">Last Action <span class="sort-arrow">&#9650;</span></th>
    </tr></thead>
    <tbody id="billsBody"></tbody>
  </table>
  <div class="no-results" id="billNoResults" style="display:none">No bills match your filters.</div>
</div>
</div>

<!-- ===== HEARINGS TAB ===== -->
<div class="tab-content" id="tab-hearings">
<div class="container">
  <div class="stats-bar">
    <div class="stat"><span class="num">{recordings_count}</span><span class="label">Recordings</span></div>
    <div class="stat"><span class="num">{transcribed_count}</span><span class="label">Transcribed</span></div>
    <div class="stat"><span class="num">{total_hours:.0f}h</span><span class="label">Total Audio</span></div>
    <div class="stat"><span class="num">{len(committees)}</span><span class="label">Committees</span></div>
  </div>
  <div class="controls">
    <select class="filter-select" id="committeeFilter">
      <option value="">All Committees</option>
      {committee_options}
    </select>
  </div>
  <div class="results-count" id="hearingResultsCount"></div>
  <table id="hearingsTable">
    <thead><tr>
      <th>Date</th>
      <th>Committee</th>
      <th>Duration</th>
      <th>Transcribed</th>
      <th>Speakers</th>
      <th>Utterances</th>
    </tr></thead>
    <tbody id="hearingsBody"></tbody>
  </table>
  <div class="no-results" id="hearingNoResults" style="display:none">No hearings match your filter.</div>
</div>
</div>

<!-- ===== SEARCH TAB ===== -->
<div class="tab-content" id="tab-search">
<div class="container">
  <div class="controls">
    <div class="search-wrapper">
      <input type="text" class="search-box" id="globalSearchBox"
             placeholder="Search across all bills and hearing transcripts...">
      <div class="search-status" id="globalSearchStatus"></div>
    </div>
  </div>
  <div id="searchResults">
    <div class="no-results">Type a keyword to search across bills and hearing transcripts.</div>
  </div>
</div>
</div>

<footer>
  Data from <a href="https://leg.colorado.gov" target="_blank" rel="noopener">leg.colorado.gov</a>
  &amp; <a href="https://sg001-harmony.sliq.net" target="_blank" rel="noopener">SLIQ</a> &middot;
  Last updated {now} &middot;
  Built with <a href="https://github.com/joelmcclurg/colorado-legislature-monitor" target="_blank" rel="noopener">Colorado Legislature Monitor</a>
</footer>

<script>
const BILLS = {bills_json};
const RECORDINGS = {recordings_json};
let transcriptIndex = null; // lazy-loaded

// ===== UTILITY =====
function esc(s) {{
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}}
function fmtMs(ms) {{
  if (!ms) return '00:00:00';
  const s = Math.floor(ms/1000);
  const h = Math.floor(s/3600);
  const m = Math.floor((s%3600)/60);
  const sec = s%60;
  return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(sec).padStart(2,'0');
}}

// ===== TABS =====
document.querySelectorAll('.tab-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
  }});
}});

// ===== BILLS TAB =====
let billChamber = 'all', billSubject = '', billSearch = '';
let billSort = 'bill_number', billSortAsc = true;
let billApiResults = null, billApiLoading = false, billSearchTimer = null;

function billSortKey(b) {{
  const m = b.bill_number.match(/^([HS])([A-Z]+)(\\d+)-(\\d+)$/);
  if (!m) return b.bill_number;
  return m[1]+m[2]+m[3].padStart(4,'0')+m[4].padStart(5,'0');
}}
function billVal(b, col) {{
  if (col==='bill_number') return billSortKey(b);
  if (col==='sponsors') return (b.sponsors||[]).join(', ').toLowerCase();
  if (col==='subjects') return (b.subjects||[]).join(', ').toLowerCase();
  return (b[col]||'').toLowerCase();
}}
function filterBills(list, textQ) {{
  return list.filter(b => {{
    if (billChamber==='House' && !b.bill_number.startsWith('H')) return false;
    if (billChamber==='Senate' && !b.bill_number.startsWith('S')) return false;
    if (billSubject && !(b.subjects||[]).some(s=>s===billSubject)) return false;
    if (textQ) {{
      const q = textQ.toLowerCase();
      const hay = [b.bill_number, b.title||'', (b.sponsors||[]).join(' '), (b.subjects||[]).join(' '), b.last_action||''].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }}
    return true;
  }});
}}
function renderBills() {{
  const tbody = document.getElementById('billsBody');
  const count = document.getElementById('billResultsCount');
  const noRes = document.getElementById('billNoResults');
  const status = document.getElementById('billSearchStatus');

  let list;
  if (!billSearch) {{
    billApiResults = null;
    status.textContent = '';
    status.className = 'search-status';
    list = filterBills(BILLS, '');
  }} else {{
    const local = filterBills(BILLS, billSearch);
    if (billApiResults !== null) {{
      const merged = [...local];
      const seen = new Set(merged.map(b=>b.bill_number));
      for (const b of billApiResults) {{
        if (!seen.has(b.bill_number)) {{
          if (billChamber==='House' && !b.bill_number.startsWith('H')) continue;
          if (billChamber==='Senate' && !b.bill_number.startsWith('S')) continue;
          if (billSubject && !(b.subjects||[]).some(s=>s===billSubject)) continue;
          seen.add(b.bill_number); merged.push(b);
        }}
      }}
      list = merged;
    }} else {{
      list = local;
    }}
  }}

  list.sort((a,b) => {{
    const va=billVal(a,billSort), vb=billVal(b,billSort);
    if (va<vb) return billSortAsc?-1:1;
    if (va>vb) return billSortAsc?1:-1;
    return 0;
  }});

  const label = billSearch
    ? 'Showing '+list.length+' results for "'+esc(billSearch)+'"'
      + (billApiLoading?' (searching full text...)':'')
    : 'Showing '+list.length+' of '+BILLS.length+' bills';
  count.textContent = label;

  if (!list.length) {{ tbody.innerHTML=''; noRes.style.display='block'; return; }}
  noRes.style.display='none';
  tbody.innerHTML = list.map(b => {{
    const url = b.url ? esc(b.url) : 'https://leg.colorado.gov/bills/'+b.bill_number.toLowerCase();
    return '<tr>'+
      '<td class="bill-num"><a href="'+url+'" target="_blank">'+esc(b.bill_number)+'</a></td>'+
      '<td>'+esc(b.title||'')+'</td>'+
      '<td class="sponsors-cell">'+esc((b.sponsors||[]).join(', '))+'</td>'+
      '<td class="subjects-cell">'+esc((b.subjects||[]).join(', '))+'</td>'+
      '<td class="last-action-cell">'+esc(b.last_action||'')+'</td></tr>';
  }}).join('');
}}

function doBillApiSearch(q) {{
  if (!q) return;
  billApiLoading = true; billApiResults = null;
  const status = document.getElementById('billSearchStatus');
  status.innerHTML = '<span class="spinner"></span>Searching full bill text...';
  status.className = 'search-status loading';
  fetch('api/search?q='+encodeURIComponent(q))
    .then(r => {{ if (!r.ok) throw new Error(); return r.json(); }})
    .then(results => {{
      if (billSearch !== q) return;
      billApiResults = Array.isArray(results) ? results : [];
      billApiLoading = false;
      status.textContent = billApiResults.length ? 'Full-text search found '+billApiResults.length+' results' : 'No additional full-text results';
      status.className = 'search-status';
      renderBills();
    }})
    .catch(() => {{
      if (billSearch !== q) return;
      billApiLoading = false; billApiResults = [];
      status.textContent = 'Full-text search unavailable (local matches only)';
      status.className = 'search-status error';
      renderBills();
    }});
}}

document.getElementById('billSearchBox').addEventListener('input', e => {{
  billSearch = e.target.value.trim();
  billApiResults = null; billApiLoading = false;
  clearTimeout(billSearchTimer);
  if (billSearch.length >= 2) {{
    billApiLoading = true;
    billSearchTimer = setTimeout(() => doBillApiSearch(billSearch), 400);
  }} else {{
    document.getElementById('billSearchStatus').textContent = '';
  }}
  renderBills();
}});
document.querySelectorAll('#tab-bills .toggle-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('#tab-bills .toggle-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active'); billChamber = btn.dataset.chamber; renderBills();
  }});
}});
document.getElementById('subjectFilter').addEventListener('change', e => {{
  billSubject = e.target.value; renderBills();
}});
document.querySelectorAll('#tab-bills thead th[data-sort]').forEach(th => {{
  th.addEventListener('click', () => {{
    const col = th.dataset.sort;
    if (billSort===col) billSortAsc=!billSortAsc;
    else {{ billSort=col; billSortAsc=true; }}
    document.querySelectorAll('#tab-bills thead th').forEach(h => {{
      h.classList.remove('sorted');
      const arr = h.querySelector('.sort-arrow');
      if (arr) arr.textContent='\\u25B2';
    }});
    th.classList.add('sorted');
    th.querySelector('.sort-arrow').textContent = billSortAsc?'\\u25B2':'\\u25BC';
    renderBills();
  }});
}});
renderBills();

// ===== HEARINGS TAB =====
let hearingCommittee = '';

function renderHearings() {{
  const tbody = document.getElementById('hearingsBody');
  const count = document.getElementById('hearingResultsCount');
  const noRes = document.getElementById('hearingNoResults');

  let list = RECORDINGS;
  if (hearingCommittee) {{
    list = list.filter(r => r.committee_name === hearingCommittee);
  }}

  count.textContent = 'Showing '+list.length+' of '+RECORDINGS.length+' recordings';
  if (!list.length) {{ tbody.innerHTML=''; noRes.style.display='block'; return; }}
  noRes.style.display='none';

  tbody.innerHTML = list.map((r, i) => {{
    const dateStr = r.date || '';
    const vidUrl = r.video_url ? esc(r.video_url) : '#';
    const hasTr = r.has_transcript;
    const expandId = 'utt-'+i;
    const row = '<tr' + (hasTr ? ' class="expandable" data-expand="'+expandId+'" style="cursor:pointer"' : '') + '>'+
      '<td class="clip-date"><a href="'+vidUrl+'" target="_blank">'+esc(dateStr)+'</a></td>'+
      '<td>'+esc(r.committee_name||r.committee||'')+'</td>'+
      '<td>'+esc(r.duration||'')+'</td>'+
      '<td>'+(hasTr?'<span class="badge badge-yes">Yes</span>':'<span class="badge badge-no">No</span>')+'</td>'+
      '<td>'+(hasTr?r.speaker_count:'')+'</td>'+
      '<td>'+(hasTr?r.utterance_count:'')+'</td>'+
      '</tr>';
    return row;
  }}).join('');

  // Click to expand transcript preview
  tbody.querySelectorAll('tr.expandable').forEach(tr => {{
    tr.addEventListener('click', e => {{
      if (e.target.tagName === 'A') return;
      const idx = parseInt(tr.dataset.expand.replace('utt-',''));
      const rec = list[idx];
      let preview = tr.nextElementSibling;
      if (preview && preview.classList.contains('utterance-preview')) {{
        preview.classList.toggle('open');
        return;
      }}
      // Load from transcripts.json
      loadTranscriptIndex().then(index => {{
        const t = index.find(t => t.clip_id === rec.clip_id);
        if (!t || !t.utterances.length) return;
        const previewRow = document.createElement('tr');
        previewRow.className = 'utterance-preview open';
        const td = document.createElement('td');
        td.colSpan = 6;
        const utts = t.utterances.slice(0, 15);
        td.innerHTML = '<ul class="utterance-list">' +
          utts.map(u =>
            '<li><span class="utt-time">'+fmtMs(u.start)+'</span>' +
            '<span class="utt-speaker">Speaker '+esc(u.speaker)+'</span>' +
            esc(u.text.substring(0,200)) + (u.text.length>200?'...':'') + '</li>'
          ).join('') +
          '</ul>' +
          (t.utterances.length > 15 ? '<div style="font-size:0.8rem;color:#6b7280;margin-top:8px">...and '+(t.utterances.length-15)+' more utterances</div>' : '');
        previewRow.appendChild(td);
        tr.after(previewRow);
      }});
    }});
  }});
}}

document.getElementById('committeeFilter').addEventListener('change', e => {{
  hearingCommittee = e.target.value; renderHearings();
}});
renderHearings();

// ===== SEARCH TAB =====
let transcriptLoading = false;
let billTextIndex = null;
let billTextLoading = false;

function loadTranscriptIndex() {{
  if (transcriptIndex) return Promise.resolve(transcriptIndex);
  if (transcriptLoading) return new Promise(resolve => {{
    const check = setInterval(() => {{
      if (transcriptIndex) {{ clearInterval(check); resolve(transcriptIndex); }}
    }}, 100);
  }});
  transcriptLoading = true;
  return fetch('transcripts.json')
    .then(r => r.json())
    .then(data => {{ transcriptIndex = data; transcriptLoading = false; return data; }})
    .catch(() => {{ transcriptIndex = []; transcriptLoading = false; return []; }});
}}

function loadBillTextIndex() {{
  if (billTextIndex) return Promise.resolve(billTextIndex);
  if (billTextLoading) return new Promise(resolve => {{
    const check = setInterval(() => {{
      if (billTextIndex) {{ clearInterval(check); resolve(billTextIndex); }}
    }}, 100);
  }});
  billTextLoading = true;
  return fetch('bills_text.json')
    .then(r => r.json())
    .then(data => {{ billTextIndex = data; billTextLoading = false; return data; }})
    .catch(() => {{ billTextIndex = []; billTextLoading = false; return []; }});
}}

function highlightSnippet(text, query, contextChars) {{
  const q = query.toLowerCase();
  const idx = text.toLowerCase().indexOf(q);
  if (idx < 0) return null;
  const start = Math.max(0, idx - contextChars);
  const end = Math.min(text.length, idx + q.length + contextChars);
  let snippet = (start > 0 ? '...' : '') + text.substring(start, end) + (end < text.length ? '...' : '');
  const escaped = query.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&');
  snippet = snippet.replace(new RegExp('(' + escaped + ')', 'gi'), '<mark>$1</mark>');
  return snippet;
}}

let globalSearchTimer = null;

function doGlobalSearch(query) {{
  if (!query || query.length < 2) {{
    document.getElementById('searchResults').innerHTML =
      '<div class="no-results">Type a keyword to search across bills and hearing transcripts.</div>';
    document.getElementById('globalSearchStatus').textContent = '';
    return;
  }}

  const status = document.getElementById('globalSearchStatus');
  status.innerHTML = '<span class="spinner"></span>Searching...';
  status.className = 'search-status loading';

  const q = query.toLowerCase();

  // Load both indexes in parallel, then render
  Promise.all([loadBillTextIndex(), loadTranscriptIndex()]).then(([billIdx, transcriptIdx]) => {{
    let html = '';

    // --- Search bills: title + long_title + summary ---
    const billMatches = [];
    const seenBills = new Set();

    // First search the bill text index (has summaries)
    for (const b of billIdx) {{
      const hay = [b.bill_number, b.title||'', b.long_title||'', b.summary||'',
                   (b.sponsors||[]).join(' '), (b.subjects||[]).join(' ')].join(' ').toLowerCase();
      if (hay.includes(q)) {{
        seenBills.add(b.bill_number);
        billMatches.push(b);
      }}
      if (billMatches.length >= 30) break;
    }}

    // Also search BILLS array for any not in bill text index
    if (billMatches.length < 30) {{
      for (const b of BILLS) {{
        if (seenBills.has(b.bill_number)) continue;
        const hay = [b.bill_number, b.title||'', (b.sponsors||[]).join(' '), (b.subjects||[]).join(' ')].join(' ').toLowerCase();
        if (hay.includes(q)) {{
          billMatches.push({{
            bill_number: b.bill_number,
            title: b.title||'',
            long_title: '',
            summary: '',
            sponsors: b.sponsors||[],
            subjects: b.subjects||[],
            url: b.url||'',
          }});
        }}
        if (billMatches.length >= 30) break;
      }}
    }}

    if (billMatches.length) {{
      html += '<div class="search-section"><h3><span class="badge badge-bill">Bills</span> ' + billMatches.length + ' matches</h3>';
      billMatches.forEach(b => {{
        const url = b.url || 'https://leg.colorado.gov/bills/' + b.bill_number.toLowerCase();
        const title = b.title || '';

        html += '<div class="search-result type-bill">' +
          '<div class="sr-title"><a href="' + esc(url) + '" target="_blank">' + esc(b.bill_number) + '</a> &mdash; ' + esc(title) + '</div>' +
          '<div class="sr-meta">' + esc((b.sponsors || []).join(', ')) + '</div>';

        // Show context snippet from summary or long_title
        let snippet = null;
        if (b.summary) snippet = highlightSnippet(b.summary, query, 120);
        if (!snippet && b.long_title) snippet = highlightSnippet(b.long_title, query, 120);
        if (snippet) {{
          html += '<div class="sr-context">' + snippet + '</div>';
        }} else if (b.summary) {{
          // No match in summary text but matched on title/sponsor/etc — show first 200 chars
          html += '<div class="sr-context">' + esc(b.summary.substring(0, 200)) + (b.summary.length > 200 ? '...' : '') + '</div>';
        }}

        html += '</div>';
      }});
      html += '</div>';
    }}

    // --- Search transcripts ---
    const hearingMatches = [];
    for (const t of transcriptIdx) {{
      const matches = [];
      for (const u of t.utterances) {{
        if (u.text.toLowerCase().includes(q)) {{
          matches.push(u);
          if (matches.length >= 3) break;
        }}
      }}
      if (matches.length) {{
        hearingMatches.push({{ ...t, matches }});
      }}
      if (hearingMatches.length >= 20) break;
    }}

    if (hearingMatches.length) {{
      html += '<div class="search-section"><h3><span class="badge badge-hearing">Hearings</span> ' + hearingMatches.length + ' recordings with matches</h3>';
      hearingMatches.forEach(h => {{
        const vidUrl = h.video_url || '#';
        html += '<div class="search-result type-hearing">' +
          '<div class="sr-title"><a href="' + esc(vidUrl) + '" target="_blank">' + esc(h.title || h.clip_id) + '</a></div>' +
          '<div class="sr-meta">' + esc(h.committee_name || '') + ' &middot; ' + esc(h.date || '') + '</div>' +
          '<div class="sr-context">';
        h.matches.forEach(u => {{
          const snippet = highlightSnippet(u.text, query, 80) || esc(u.text.substring(0, 160));
          html += '<div style="margin-bottom:4px"><span class="utt-time">' + fmtMs(u.start) + '</span> <span class="utt-speaker">Speaker ' + esc(u.speaker) + '</span> ' + snippet + '</div>';
        }});
        html += '</div></div>';
      }});
      html += '</div>';
    }}

    if (!html) html = '<div class="no-results">No results found for "' + esc(query) + '".</div>';
    document.getElementById('searchResults').innerHTML = html;
    status.textContent = '';
    status.className = 'search-status';
  }});
}}

document.getElementById('globalSearchBox').addEventListener('input', e => {{
  clearTimeout(globalSearchTimer);
  const val = e.target.value.trim();
  globalSearchTimer = setTimeout(() => doGlobalSearch(val), 400);
}});

</script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='Build Colorado Legislature dashboard')
    parser.add_argument('--output', '-o', default='public/index.html',
                        help='Output HTML file path (default: public/index.html)')
    parser.add_argument('--session', '-s', default=None,
                        help='Session code (default: current session)')
    parser.add_argument('--open', action='store_true',
                        help='Open dashboard in browser after building')
    args = parser.parse_args()

    path = build_dashboard(args.output, args.session)

    if args.open:
        subprocess.run(['open', path])


if __name__ == '__main__':
    main()
