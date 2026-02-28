# Bills Scraper — Website Redesign Issue

**Date Discovered**: February 9, 2026
**Status**: UNFIXED — workaround used ad-hoc, permanent fix not yet applied
**Priority**: High — bills list command only returns 3 "Most Accessed" bills

---

## Problem

The Colorado Legislature website (`leg.colorado.gov`) was redesigned to use **Turbo Streams** (Hotwire/Stimulus.js framework). The existing bills scraper in `scripts/scrapers/bills.py` fetches from `https://leg.colorado.gov/bills`, which is now a **landing page** showing only 3 "Most Accessed Bills" — not a comprehensive listing.

### Current Behavior
```bash
$ python3 scripts/legislature.py bills list
# Returns only 3 bills (the "Most Accessed" on the landing page)
```

### Expected Behavior
```bash
$ python3 scripts/legislature.py bills list
# Should return all 302 bills for the 2026 Regular Session
```

---

## Root Cause

The redesigned site uses:
1. **Turbo Streams** — Content is loaded dynamically via Hotwire/Stimulus.js
2. **POST-based form submission** — Bill search requires POST to `/bills/bill-search`
3. **CSRF tokens** — Each request needs an `authenticity_token` from the search page
4. **Session cookies** — Must maintain cookies between GET and POST
5. **Template tags** — Actual HTML content is inside `<template>` tags within turbo-stream responses
6. **Checkbox-based filters** — Session filter uses `sessions[]=2026 Regular Session`

### Old URL (landing page only)
```
GET https://leg.colorado.gov/bills
→ Returns landing page with "Most Accessed Bills" (3 bills)
```

### New URL (actual search)
```
GET https://leg.colorado.gov/bill-search
→ Returns search form with CSRF token

POST https://leg.colorado.gov/bills/bill-search
→ With: authenticity_token, sessions[], sort, page
→ Returns turbo-stream response with <template> tags containing bill results
```

---

## Workaround Used (Ad-Hoc, Feb 9, 2026)

A Python script was run inline to fetch all 302 bills. This was NOT integrated into `bills.py`:

```python
import requests
from bs4 import BeautifulSoup
import re
import json

# Step 1: GET the search page for CSRF token + cookies
resp = requests.get('https://leg.colorado.gov/bill-search', verify=False, timeout=30)
soup = BeautifulSoup(resp.text, 'html.parser')
token_input = soup.find('input', {'name': 'authenticity_token'})
token = token_input['value']
cookies = resp.cookies

# Step 2: POST with session filter
all_bills = []
for page in range(1, 14):  # 13 pages, ~25 bills/page
    resp2 = requests.post(
        'https://leg.colorado.gov/bills/bill-search',
        data={
            'authenticity_token': token,
            'sessions[]': '2026 Regular Session',
            'sort': 'field_bill_number DESC',
            'page': str(page),
        },
        headers={'Accept': 'text/vnd.turbo-stream.html, text/html'},
        cookies=cookies,
        verify=False,
        timeout=30
    )

    # Step 3: Parse <template> tags (NOT normal DOM)
    templates = re.findall(r'<template>(.*?)</template>', resp2.text, re.DOTALL)
    for tmpl in templates:
        if 'bill-result' not in tmpl:
            continue
        inner_soup = BeautifulSoup(tmpl, 'html.parser')
        results = inner_soup.find_all('div', class_='bill-result')
        for div in results:
            bill_num = div.find('h2').get_text(strip=True)
            title_el = div.find('h3')
            title = title_el.get_text(strip=True) if title_el else ''
            # ... extract last_action, sponsors, subjects from spans
            all_bills.append({...})

# Result: 302 bills for 2026 Regular Session
```

### Key Technical Details

1. **CSRF token**: Found in `<input name="authenticity_token" value="...">` on the search page
2. **Accept header**: Must include `text/vnd.turbo-stream.html` to get turbo-stream response
3. **Template extraction**: Use `re.findall(r'<template>(.*?)</template>', resp.text, re.DOTALL)` — BeautifulSoup's normal parsing doesn't traverse into template tags
4. **Bill structure**: `div.bill-result` > `h2` (bill number), `h3 > a` (title), spans for metadata
5. **Pagination**: ~25 bills per page, 13 pages total for 302 bills
6. **Sort order**: `field_bill_number DESC` gives newest first

### Response Format

The POST response is a turbo-stream:
```html
<turbo-stream action="replace" target="bill-results">
  <template>
    <div id="bill-results">
      <div class="bill-result">
        <h2>HB26-1190</h2>
        <h3><a href="/bills/hb26-1190">Concerning Agricultural Producers...</a></h3>
        <span class="last-action">Introduced 02/07/2026</span>
        <span class="sponsors">Rep. Smith, Sen. Jones</span>
        <span class="subjects">Agriculture</span>
      </div>
      <!-- ... more bills ... -->
    </div>
  </template>
</turbo-stream>
```

---

## Fix Plan

To permanently fix `scripts/scrapers/bills.py`:

1. **Add `fetch_all_bills()` function** that implements the POST-based search
2. **Update `fetch_bills()` to use the new function** instead of scraping the landing page
3. **Handle pagination** — iterate pages until no more results
4. **Cache results** with appropriate TTL (6 hours, matching existing bills cache)
5. **Maintain backward compatibility** — `bill info HB26-####` still works (individual bill pages unchanged)

### Files to Modify
- `scripts/scrapers/bills.py` — Main fix: replace landing page scrape with POST-based search
- `scripts/legislature.py` — May need to update `bills list` command if arguments change

### Testing
- Clear cache: `rm -rf ~/.claude/skills/colorado-legislature/data/bills/`
- Verify: `python3 scripts/legislature.py bills list --limit 10` returns 10 bills
- Verify: `python3 scripts/legislature.py bills list` returns all 302 bills
- Verify: Individual bill info still works: `python3 scripts/legislature.py bill info HB26-1001`

---

## Errors Encountered During Investigation

1. **curl without `-k` flag**: SSL cert issues with leg.colorado.gov → use `verify=False`
2. **BeautifulSoup finding empty bill-result divs**: Content is inside `<template>` tags that BS4 doesn't traverse → extract with regex first
3. **Python f-string with `!=`**: SyntaxError in `-c` flag → use heredoc (`<< 'PYEOF'`) for inline scripts
4. **grep -P not available on macOS**: Use Python regex or `grep -E` instead
