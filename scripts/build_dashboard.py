#!/usr/bin/env python3
"""
Build a static HTML dashboard of Colorado Legislature bills.

Fetches all bills via the scraper and generates a self-contained HTML file
at public/index.html suitable for Vercel static deployment.

Usage:
    python3 scripts/build_dashboard.py
    python3 scripts/build_dashboard.py --output public/index.html --open
"""
import argparse
import json
import html
import sys
import subprocess
import warnings
from datetime import datetime
from pathlib import Path

# Suppress SSL warnings
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cache.manager import CacheManager
from scrapers.bills import list_bills
from scrapers.sessions import get_current_session


def build_dashboard(output_path: str, session: str = None):
    """Fetch all bills and generate a static HTML dashboard."""
    if not session:
        session = get_current_session()

    print(f"Fetching bills for session {session}...")
    cache = CacheManager()
    bills = list_bills(session=session, limit=9999, cache_manager=cache)
    print(f"Found {len(bills)} bills.")

    if not bills:
        print("No bills found. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Count by chamber
    house_count = sum(1 for b in bills if b['bill_number'].startswith('H'))
    senate_count = sum(1 for b in bills if b['bill_number'].startswith('S'))

    # Collect unique subjects
    all_subjects = set()
    for b in bills:
        for s in b.get('subjects', []):
            all_subjects.add(s)
    subjects_sorted = sorted(all_subjects)

    # Serialize bills as JSON for embedding
    bills_json = json.dumps(bills, ensure_ascii=False)

    now = datetime.now().strftime('%B %d, %Y at %I:%M %p')
    year = session[:4] if len(session) >= 4 else str(datetime.now().year)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Colorado Legislature Bill Tracker &mdash; {year} Regular Session</title>
<style>
*,*::before,*::after{{box-sizing:border-box}}
body{{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
  margin:0;padding:0;
  background:#f0f2f5;
  color:#1a1a2e;
  line-height:1.5;
}}
.container{{
  max-width:1280px;
  margin:0 auto;
  padding:24px 20px;
}}
header{{
  background:linear-gradient(135deg,#1a365d 0%,#2563eb 100%);
  color:#fff;
  padding:32px 20px;
  text-align:center;
}}
header h1{{
  margin:0 0 4px;
  font-size:1.75rem;
  font-weight:700;
  letter-spacing:-0.02em;
}}
header p{{
  margin:0;
  opacity:0.85;
  font-size:0.95rem;
}}
.stats-bar{{
  display:flex;
  gap:16px;
  justify-content:center;
  flex-wrap:wrap;
  margin:20px auto 0;
}}
.stat{{
  background:rgba(255,255,255,0.15);
  border-radius:8px;
  padding:10px 24px;
  text-align:center;
  min-width:120px;
}}
.stat .num{{
  font-size:1.5rem;
  font-weight:700;
  display:block;
}}
.stat .label{{
  font-size:0.8rem;
  text-transform:uppercase;
  letter-spacing:0.05em;
  opacity:0.85;
}}
.controls{{
  display:flex;
  gap:12px;
  flex-wrap:wrap;
  align-items:center;
  margin-bottom:20px;
}}
.search-box{{
  flex:1;
  min-width:200px;
  padding:10px 14px;
  font-size:0.95rem;
  border:1px solid #d1d5db;
  border-radius:6px;
  outline:none;
  transition:border-color 0.15s;
}}
.search-box:focus{{
  border-color:#2563eb;
  box-shadow:0 0 0 3px rgba(37,99,235,0.1);
}}
.filter-select{{
  padding:10px 14px;
  font-size:0.95rem;
  border:1px solid #d1d5db;
  border-radius:6px;
  background:#fff;
  cursor:pointer;
  min-width:140px;
}}
.toggle-group{{
  display:flex;
  border:1px solid #d1d5db;
  border-radius:6px;
  overflow:hidden;
}}
.toggle-btn{{
  padding:10px 16px;
  border:none;
  background:#fff;
  cursor:pointer;
  font-size:0.9rem;
  font-weight:500;
  color:#4b5563;
  transition:all 0.15s;
}}
.toggle-btn:not(:last-child){{
  border-right:1px solid #d1d5db;
}}
.toggle-btn.active{{
  background:#2563eb;
  color:#fff;
}}
.toggle-btn:hover:not(.active){{
  background:#f3f4f6;
}}
.results-count{{
  font-size:0.85rem;
  color:#6b7280;
  margin-bottom:8px;
}}
table{{
  width:100%;
  border-collapse:collapse;
  background:#fff;
  border-radius:8px;
  overflow:hidden;
  box-shadow:0 1px 3px rgba(0,0,0,0.08);
}}
thead th{{
  background:#1e293b;
  color:#fff;
  padding:12px 14px;
  text-align:left;
  font-weight:600;
  font-size:0.85rem;
  text-transform:uppercase;
  letter-spacing:0.03em;
  cursor:pointer;
  user-select:none;
  white-space:nowrap;
  position:relative;
}}
thead th:hover{{
  background:#334155;
}}
thead th .sort-arrow{{
  margin-left:4px;
  opacity:0.4;
  font-size:0.75rem;
}}
thead th.sorted .sort-arrow{{
  opacity:1;
}}
tbody td{{
  padding:10px 14px;
  border-bottom:1px solid #f1f5f9;
  font-size:0.9rem;
  vertical-align:top;
}}
tbody tr:hover{{
  background:#f8fafc;
}}
tbody tr:last-child td{{
  border-bottom:none;
}}
a{{
  color:#2563eb;
  text-decoration:none;
}}
a:hover{{
  text-decoration:underline;
}}
.bill-num{{
  font-weight:600;
  white-space:nowrap;
}}
.subjects-cell{{
  font-size:0.8rem;
  color:#6b7280;
}}
.sponsors-cell{{
  font-size:0.85rem;
  color:#4b5563;
}}
.last-action-cell{{
  font-size:0.85rem;
  color:#4b5563;
}}
footer{{
  text-align:center;
  padding:32px 20px;
  font-size:0.8rem;
  color:#9ca3af;
}}
footer a{{
  color:#6b7280;
}}
.no-results{{
  text-align:center;
  padding:48px 20px;
  color:#6b7280;
  font-size:1rem;
}}
.search-wrapper{{
  flex:1;
  min-width:200px;
  position:relative;
}}
.search-status{{
  font-size:0.8rem;
  color:#6b7280;
  margin-top:4px;
  min-height:1.2em;
}}
.search-status.loading{{
  color:#2563eb;
}}
.search-status.error{{
  color:#dc2626;
}}
.search-hint{{
  font-size:0.8rem;
  color:#9ca3af;
  margin-bottom:16px;
}}
@keyframes spin{{
  to{{transform:rotate(360deg)}}
}}
.spinner{{
  display:inline-block;
  width:14px;height:14px;
  border:2px solid #d1d5db;
  border-top-color:#2563eb;
  border-radius:50%;
  animation:spin 0.6s linear infinite;
  vertical-align:middle;
  margin-right:6px;
}}
@media(max-width:768px){{
  header h1{{font-size:1.3rem}}
  .controls{{flex-direction:column}}
  .search-box,.filter-select{{width:100%}}
  thead th,tbody td{{padding:8px 10px;font-size:0.8rem}}
  .subjects-cell,.sponsors-cell{{display:none}}
}}
</style>
</head>
<body>

<header>
  <h1>Colorado Legislature Bill Tracker</h1>
  <p>{year} Regular Session</p>
  <div class="stats-bar">
    <div class="stat"><span class="num">{len(bills)}</span><span class="label">Total Bills</span></div>
    <div class="stat"><span class="num">{house_count}</span><span class="label">House</span></div>
    <div class="stat"><span class="num">{senate_count}</span><span class="label">Senate</span></div>
  </div>
</header>

<div class="container">
  <div class="controls">
    <div class="search-wrapper">
      <input type="text" class="search-box" id="searchBox"
             placeholder="Search by keyword, bill number, sponsor, subject...">
      <div class="search-status" id="searchStatus"></div>
    </div>
    <div class="toggle-group">
      <button class="toggle-btn active" data-chamber="all">All</button>
      <button class="toggle-btn" data-chamber="House">House</button>
      <button class="toggle-btn" data-chamber="Senate">Senate</button>
    </div>
    <select class="filter-select" id="subjectFilter">
      <option value="">All Subjects</option>
      {"".join(f'<option value="{html.escape(s)}">{html.escape(s)}</option>' for s in subjects_sorted)}
    </select>
  </div>

  <div class="results-count" id="resultsCount"></div>

  <table>
    <thead>
      <tr>
        <th data-sort="bill_number" class="sorted">Bill # <span class="sort-arrow">&#9650;</span></th>
        <th data-sort="title">Title <span class="sort-arrow">&#9650;</span></th>
        <th data-sort="sponsors">Sponsors <span class="sort-arrow">&#9650;</span></th>
        <th data-sort="subjects">Subjects <span class="sort-arrow">&#9650;</span></th>
        <th data-sort="last_action">Last Action <span class="sort-arrow">&#9650;</span></th>
      </tr>
    </thead>
    <tbody id="billsBody"></tbody>
  </table>
  <div class="no-results" id="noResults" style="display:none">No bills match your filters.</div>
</div>

<footer>
  Data from <a href="https://leg.colorado.gov" target="_blank" rel="noopener">leg.colorado.gov</a> &middot;
  Last updated {now} &middot;
  Built with <a href="https://github.com/joelmcclurg/colorado-legislature-monitor" target="_blank" rel="noopener">Colorado Legislature Monitor</a>
</footer>

<script>
const BILLS = {bills_json};
const BILLS_MAP = {{}};
BILLS.forEach(b => BILLS_MAP[b.bill_number] = b);

let currentChamber = 'all';
let currentSubject = '';
let currentSearch = '';
let sortCol = 'bill_number';
let sortAsc = true;
let apiResults = null;  // null = not searching, [] = no results, [...] = results
let apiLoading = false;
let searchTimer = null;

const tbody = document.getElementById('billsBody');
const resultsCount = document.getElementById('resultsCount');
const noResults = document.getElementById('noResults');
const searchStatus = document.getElementById('searchStatus');

function escapeHtml(s) {{
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}}

function billSortKey(b) {{
  const m = b.bill_number.match(/^([HS])([A-Z]+)(\\d+)-(\\d+)$/);
  if (!m) return b.bill_number;
  return m[1] + m[2] + m[3].padStart(4,'0') + m[4].padStart(5,'0');
}}

function getVal(b, col) {{
  if (col === 'bill_number') return billSortKey(b);
  if (col === 'sponsors') return (b.sponsors || []).join(', ').toLowerCase();
  if (col === 'subjects') return (b.subjects || []).join(', ').toLowerCase();
  return (b[col] || '').toLowerCase();
}}

function clientFilter(bills) {{
  return bills.filter(b => {{
    if (currentChamber === 'House' && !b.bill_number.startsWith('H')) return false;
    if (currentChamber === 'Senate' && !b.bill_number.startsWith('S')) return false;
    if (currentSubject && !(b.subjects || []).some(s => s === currentSubject)) return false;
    return true;
  }});
}}

function clientTextFilter(bills, q) {{
  if (!q) return bills;
  const lower = q.toLowerCase();
  return bills.filter(b => {{
    const haystack = [
      b.bill_number, b.title || '',
      (b.sponsors || []).join(' '),
      (b.subjects || []).join(' '),
      b.last_action || ''
    ].join(' ').toLowerCase();
    return haystack.includes(lower);
  }});
}}

function renderBills(bills, totalLabel) {{
  bills.sort((a, b) => {{
    const va = getVal(a, sortCol);
    const vb = getVal(b, sortCol);
    if (va < vb) return sortAsc ? -1 : 1;
    if (va > vb) return sortAsc ? 1 : -1;
    return 0;
  }});

  resultsCount.textContent = totalLabel;

  if (bills.length === 0) {{
    tbody.innerHTML = '';
    noResults.style.display = 'block';
    return;
  }}
  noResults.style.display = 'none';

  const rows = bills.map(b => {{
    const num = escapeHtml(b.bill_number);
    const url = b.url ? escapeHtml(b.url) : 'https://leg.colorado.gov/bills/' + b.bill_number.toLowerCase();
    const title = escapeHtml(b.title || '');
    const sponsors = escapeHtml((b.sponsors || []).join(', '));
    const subjects = escapeHtml((b.subjects || []).join(', '));
    const lastAction = escapeHtml(b.last_action || '');
    return '<tr>' +
      '<td class="bill-num"><a href="' + url + '" target="_blank" rel="noopener">' + num + '</a></td>' +
      '<td>' + title + '</td>' +
      '<td class="sponsors-cell">' + sponsors + '</td>' +
      '<td class="subjects-cell">' + subjects + '</td>' +
      '<td class="last-action-cell">' + lastAction + '</td>' +
      '</tr>';
  }});
  tbody.innerHTML = rows.join('');
}}

function render() {{
  if (!currentSearch) {{
    // No search query: show all bills with chamber/subject filters
    apiResults = null;
    searchStatus.textContent = '';
    searchStatus.className = 'search-status';
    const filtered = clientFilter(BILLS);
    renderBills(filtered, 'Showing ' + filtered.length + ' of ' + BILLS.length + ' bills');
    return;
  }}

  // Have a search query: first show instant client-side matches
  const localMatches = clientFilter(clientTextFilter(BILLS, currentSearch));

  if (apiResults !== null) {{
    // API results are in — merge with local matches, dedup
    const merged = [...localMatches];
    const seen = new Set(merged.map(b => b.bill_number));
    for (const b of apiResults) {{
      if (!seen.has(b.bill_number)) {{
        // Apply chamber/subject filters to API results too
        if (currentChamber === 'House' && !b.bill_number.startsWith('H')) continue;
        if (currentChamber === 'Senate' && !b.bill_number.startsWith('S')) continue;
        if (currentSubject && !(b.subjects || []).some(s => s === currentSubject)) continue;
        seen.add(b.bill_number);
        merged.push(b);
      }}
    }}
    renderBills(merged, 'Showing ' + merged.length + ' results for "' + escapeHtml(currentSearch) + '"');
  }} else {{
    // Show local matches while API loads
    renderBills(localMatches, 'Showing ' + localMatches.length + ' local matches' +
      (apiLoading ? ' (searching full text...)' : ''));
  }}
}}

function doApiSearch(query) {{
  if (!query) return;
  apiLoading = true;
  apiResults = null;
  searchStatus.innerHTML = '<span class="spinner"></span>Searching full bill text...';
  searchStatus.className = 'search-status loading';

  fetch('/api/search?q=' + encodeURIComponent(query))
    .then(r => {{
      if (!r.ok) throw new Error('Search failed');
      return r.json();
    }})
    .then(results => {{
      // Only apply if query still matches
      if (currentSearch === query) {{
        apiResults = Array.isArray(results) ? results : [];
        apiLoading = false;
        if (apiResults.length > 0) {{
          searchStatus.textContent = 'Full-text search found ' + apiResults.length + ' results';
        }} else {{
          searchStatus.textContent = 'No additional results from full-text search';
        }}
        searchStatus.className = 'search-status';
        render();
      }}
    }})
    .catch(err => {{
      if (currentSearch === query) {{
        apiLoading = false;
        apiResults = [];
        searchStatus.textContent = 'Full-text search unavailable (showing local matches only)';
        searchStatus.className = 'search-status error';
        render();
      }}
    }});
}}

// Search input: instant local filter + debounced API search
document.getElementById('searchBox').addEventListener('input', e => {{
  currentSearch = e.target.value.trim();
  apiResults = null;
  apiLoading = false;
  clearTimeout(searchTimer);

  if (currentSearch.length >= 2) {{
    apiLoading = true;
    searchTimer = setTimeout(() => doApiSearch(currentSearch), 400);
  }} else {{
    searchStatus.textContent = '';
    searchStatus.className = 'search-status';
  }}
  render();
}});

// Chamber toggle
document.querySelectorAll('.toggle-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentChamber = btn.dataset.chamber;
    render();
  }});
}});

// Subject filter
document.getElementById('subjectFilter').addEventListener('change', e => {{
  currentSubject = e.target.value;
  render();
}});

// Sort
document.querySelectorAll('thead th[data-sort]').forEach(th => {{
  th.addEventListener('click', () => {{
    const col = th.dataset.sort;
    if (sortCol === col) {{
      sortAsc = !sortAsc;
    }} else {{
      sortCol = col;
      sortAsc = true;
    }}
    document.querySelectorAll('thead th').forEach(h => {{
      h.classList.remove('sorted');
      h.querySelector('.sort-arrow').textContent = '\\u25B2';
    }});
    th.classList.add('sorted');
    th.querySelector('.sort-arrow').textContent = sortAsc ? '\\u25B2' : '\\u25BC';
    render();
  }});
}});

render();
</script>
</body>
</html>"""

    # Write output
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_content, encoding='utf-8')
    print(f"Dashboard written to {out} ({len(html_content):,} bytes, {len(bills)} bills)")
    return str(out)


def main():
    parser = argparse.ArgumentParser(description='Build Colorado Legislature bill tracker dashboard')
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
