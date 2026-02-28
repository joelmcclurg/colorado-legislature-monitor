#!/usr/bin/env python3
"""
Bills scraper for Colorado Legislature.

Fetches and parses bill information from colorado.leg.gov including:
- Bill listings with filtering by session, chamber, type
- Detailed bill information (sponsors, committees, status)
- Bill text versions, amendments, fiscal notes
- Vote history

Updated Feb 2026: Uses POST-based Turbo Stream search (site redesigned from
static pages to Hotwire/Turbo Streams).
"""
import re
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from datetime import datetime
from .sessions import get_current_session
from .pdf_extractor import extract_pdf_text, batch_extract_pdfs

# Suppress SSL warnings for leg.colorado.gov
urllib3.disable_warnings(InsecureRequestWarning)

BASE_URL = "https://leg.colorado.gov"
BILLS_SEARCH_URL = f"{BASE_URL}/bills/bill-search"
SEARCH_FORM_URL = f"{BASE_URL}/bill-search"


def _session_code_to_name(session_code: str) -> str:
    """
    Convert session code to the display name used by the search form.

    Args:
        session_code: e.g. '2026A'

    Returns:
        Display name e.g. '2026 Regular Session'
    """
    if not session_code or len(session_code) < 4:
        return f"{datetime.now().year} Regular Session"
    year = session_code[:4]
    suffix = session_code[4:] if len(session_code) > 4 else 'A'
    if suffix == 'B':
        return f"{year} Second Session"
    return f"{year} Regular Session"


def _fetch_turbo_search_results(
    session_name: str,
    query: Optional[str] = None,
    sort: str = 'Bill # Ascending',
    max_pages: int = 20
) -> List[Dict[str, Any]]:
    """
    Fetch bill results via the Turbo Stream POST-based search.

    The redesigned leg.colorado.gov uses Hotwire Turbo Streams. Bill search
    requires: GET /bill-search (CSRF + cookies) → POST /bills/bill-search.

    Args:
        session_name: Session display name (e.g. '2026 Regular Session')
        query: Optional search query string
        sort: Sort order (e.g. 'Bill # Ascending', 'Most Relevant')
        max_pages: Safety limit on pagination

    Returns:
        List of bill dicts
    """
    # Step 1: GET the search form for CSRF token + session cookies
    try:
        form_resp = requests.get(SEARCH_FORM_URL, verify=False, timeout=30)
        form_resp.raise_for_status()
    except requests.RequestException as e:
        raise Exception(f"Failed to load bill search form: {e}")

    form_soup = BeautifulSoup(form_resp.text, 'html.parser')
    token_input = form_soup.find('input', {'name': 'authenticity_token'})
    if not token_input:
        raise Exception("Could not find CSRF token on bill search page")
    csrf_token = token_input['value']
    cookies = form_resp.cookies

    # Step 2: Paginate through POST results
    all_bills = []
    seen_numbers = set()

    for page in range(1, max_pages + 1):
        post_data = {
            'authenticity_token': csrf_token,
            'sessions[]': session_name,
            'sort': sort,
            'page': str(page),
        }
        if query:
            post_data['q'] = query

        try:
            resp = requests.post(
                BILLS_SEARCH_URL,
                data=post_data,
                headers={'Accept': 'text/vnd.turbo-stream.html, text/html'},
                cookies=cookies,
                verify=False,
                timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch bill search results (page {page}): {e}")

        # Step 3: Extract content from <template> tags (BS4 doesn't traverse these)
        templates = re.findall(r'<template>(.*?)</template>', resp.text, re.DOTALL)
        page_bills = []

        for tmpl in templates:
            if 'bill-result' not in tmpl:
                continue
            inner_soup = BeautifulSoup(tmpl, 'html.parser')
            results = inner_soup.find_all('div', class_='bill-result')
            for div in results:
                bill = _parse_bill_result_div(div)
                if bill and bill['bill_number'] not in seen_numbers:
                    seen_numbers.add(bill['bill_number'])
                    page_bills.append(bill)

        if not page_bills:
            break

        all_bills.extend(page_bills)

        # If we got fewer than ~20 results, we're on the last page
        if len(page_bills) < 20:
            break

    return all_bills


def _parse_bill_result_div(div) -> Optional[Dict[str, Any]]:
    """
    Parse a single div.bill-result into a bill dict.

    Expected structure:
        <div class="bill-result">
            <h2>HB26-1190</h2>
            <h3><a href="/bills/hb26-1190">Title...</a></h3>
            <span class="last-action">...</span>
            <span class="sponsors">...</span>
            <span class="subjects">...</span>
        </div>
    """
    bill = {
        'bill_number': None,
        'title': None,
        'url': None,
        'last_action': None,
        'subjects': [],
        'sponsors': []
    }

    # Bill number from h2
    h2 = div.find('h2')
    if not h2:
        return None
    bill['bill_number'] = h2.get_text(strip=True).upper()

    # Title + URL from h3 > a
    h3 = div.find('h3')
    if h3:
        link = h3.find('a')
        if link:
            bill['title'] = link.get_text(strip=True)
            href = link.get('href', '')
            bill['url'] = f"{BASE_URL}{href}" if href.startswith('/') else href

    # Last action
    last_action_el = div.find('span', class_=re.compile(r'last.?action', re.I))
    if last_action_el:
        bill['last_action'] = last_action_el.get_text(strip=True)

    # Sponsors
    sponsors_el = div.find('span', class_=re.compile(r'sponsor', re.I))
    if sponsors_el:
        text = sponsors_el.get_text(strip=True)
        if text:
            bill['sponsors'] = [s.strip() for s in text.split(',') if s.strip()]

    # Subjects
    subjects_el = div.find('span', class_=re.compile(r'subject', re.I))
    if subjects_el:
        text = subjects_el.get_text(strip=True)
        if text:
            bill['subjects'] = [s.strip() for s in text.split(',') if s.strip()]

    return bill


def list_bills(
    session: Optional[str] = None,
    chamber: Optional[str] = None,
    bill_type: Optional[str] = None,
    sponsor: Optional[str] = None,
    subject: Optional[str] = None,
    limit: int = 100,
    cache_manager=None
) -> List[Dict[str, Any]]:
    """
    List bills with optional filtering.

    Uses POST-based Turbo Stream search to get full bill listings from the
    redesigned leg.colorado.gov (Feb 2026+).

    Args:
        session: Session code (e.g., '2026A'). Defaults to current session.
        chamber: Filter by chamber ('House', 'Senate', or None for all)
        bill_type: Filter by type ('Bill', 'Resolution', 'Memorial', or None)
        sponsor: Filter by sponsor name
        subject: Filter by subject/topic
        limit: Maximum number of bills to return (default 100)
        cache_manager: Optional cache manager instance

    Returns:
        List of bill dicts with basic information
    """
    if not session:
        session = get_current_session()

    # Check cache — cache the full unfiltered result so filters are instant
    cache_key = f"bills_turbo_{session}"
    all_bills = None
    if cache_manager:
        all_bills = cache_manager.get(cache_key, max_age_hours=6)

    if not all_bills:
        session_name = _session_code_to_name(session)
        all_bills = _fetch_turbo_search_results(session_name)

        # Cache full result
        if cache_manager and all_bills:
            cache_manager.set(cache_key, all_bills, subdirectory='bills')

    # Apply client-side filters
    bills = all_bills
    if chamber:
        bills = [b for b in bills if (
            (chamber == 'House' and b['bill_number'].startswith('H')) or
            (chamber == 'Senate' and b['bill_number'].startswith('S'))
        )]
    if bill_type:
        type_prefix_map = {
            'Bill': ['HB', 'SB'],
            'Resolution': ['HR', 'SR', 'HJR', 'SJR'],
            'Memorial': ['HM', 'SM', 'HJM', 'SJM'],
            'Concurrent Resolution': ['HCR', 'SCR'],
        }
        prefixes = type_prefix_map.get(bill_type, [])
        if prefixes:
            bills = [b for b in bills if any(b['bill_number'].startswith(p) for p in prefixes)]
    if sponsor:
        sponsor_lower = sponsor.lower()
        bills = [b for b in bills if any(sponsor_lower in s.lower() for s in b.get('sponsors', []))]
    if subject:
        subject_lower = subject.lower()
        bills = [b for b in bills if any(subject_lower in s.lower() for s in b.get('subjects', []))]

    return bills[:limit]


def get_bill_info(
    bill_number: str,
    session: Optional[str] = None,
    cache_manager=None,
    extract_content=False,
    progress_callback=None
) -> Optional[Dict[str, Any]]:
    """
    Fetch detailed information for a specific bill.

    Args:
        bill_number: Bill number (e.g., 'HB26-1001', 'SB26-004')
        session: Session code (e.g., '2026A'). Used for cache key.
        cache_manager: Optional cache manager instance
        extract_content: If True, extract PDF content for bill text/amendments
        progress_callback: Optional callback(completed, total, url, from_cache) for progress

    Returns:
        Dict with bill details including sponsors, status, amendments, votes
    """
    if not session:
        session = get_current_session()

    # Normalize bill number to lowercase for URL
    bill_slug = bill_number.lower()

    # Check cache
    cache_key = f"bill_{bill_slug}_{session}"
    if cache_manager:
        cached = cache_manager.get(cache_key, max_age_hours=6)
        if cached:
            return cached

    # Fetch bill page
    url = f"{BASE_URL}/bills/{bill_slug}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch bill page: {e}")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract bill information
    bill_info = {
        'bill_number': bill_number.upper(),
        'session': session,
        'url': url,
        'title': None,
        'long_title': None,
        'status': None,
        'sponsors': [],
        'committee': None,
        'subjects': [],
        'last_action': None,
        'bill_text': [],
        'fiscal_notes': [],
        'amendments': [],
        'votes': [],
        'history': [],
        'fetched_at': datetime.now().isoformat()
    }

    # Extract title
    title_elem = soup.find('h1')
    if title_elem:
        # Remove bill number from title
        title_text = title_elem.text.strip()
        title_text = re.sub(r'^[HS][BCJM][JR]*\d+-\d+\s*', '', title_text)
        bill_info['title'] = title_text

    # Extract long title
    long_title_elem = soup.find('div', class_=re.compile(r'long.*title'))
    if long_title_elem:
        bill_info['long_title'] = long_title_elem.text.strip()

    # Extract status from the status badge (most reliable)
    status_badge = soup.find('div', class_=re.compile(r'final-status-badge'))
    if status_badge:
        bill_info['status'] = status_badge.get_text(strip=True)
    else:
        # Fallback: try to find status in other ways
        status_elem = soup.find('div', class_=re.compile(r'status'))
        if status_elem:
            # Get text and clean up duplicates/extra whitespace
            status_text = status_elem.get_text(separator=' ', strip=True)
            # Remove extra whitespace and take the most specific status (last one)
            status_parts = [s.strip() for s in status_text.split('\n') if s.strip()]
            # Remove 'Status' heading and duplicates
            status_parts = [p for p in status_parts if p.lower() != 'status']
            # Remove duplicates while preserving order
            seen = set()
            unique_parts = []
            for part in status_parts:
                if part not in seen:
                    seen.add(part)
                    unique_parts.append(part)
            # Use the first unique status (typically the main one)
            bill_info['status'] = unique_parts[0] if unique_parts else status_text

    # Extract sponsors
    bill_info['sponsors'] = _extract_sponsors(soup)

    # Extract committee assignment
    committee_link = soup.find('a', href=re.compile(r'/committees/\d+[A-Z]/'))
    if committee_link:
        committee_name = committee_link.text.strip()
        committee_url = f"{BASE_URL}{committee_link.get('href')}"
        bill_info['committee'] = {
            'name': committee_name,
            'url': committee_url
        }

    # Extract subjects
    subject_links = soup.find_all('a', href=re.compile(r'field_subjects='))
    for link in subject_links:
        subject = link.text.strip()
        if subject:
            bill_info['subjects'].append(subject)

    # Extract last action
    last_action_elem = soup.find(text=re.compile(r'LAST ACTION:'))
    if last_action_elem:
        parent = last_action_elem.find_parent()
        if parent:
            action_text = parent.text.replace('LAST ACTION:', '').strip()
            bill_info['last_action'] = action_text

    # Extract bill text versions
    bill_info['bill_text'] = _extract_bill_text(soup)

    # Extract fiscal notes
    bill_info['fiscal_notes'] = _extract_fiscal_notes(soup)

    # Extract amendments
    bill_info['amendments'] = _extract_amendments(soup)

    # Extract votes
    bill_info['votes'] = _extract_votes(soup)

    # Extract history
    bill_info['history'] = _extract_history(soup)

    # Extract PDF content if requested
    if extract_content and cache_manager:
        # Collect all PDF URLs from bill text, amendments, and fiscal notes
        pdf_urls = []

        # Bill text versions
        for version in bill_info['bill_text']:
            if version.get('url', '').lower().endswith('.pdf'):
                pdf_urls.append(version['url'])

        # Amendments
        for amendment in bill_info['amendments']:
            if amendment.get('url', '').lower().endswith('.pdf'):
                pdf_urls.append(amendment['url'])

        # Fiscal notes
        for note in bill_info['fiscal_notes']:
            if note.get('url', '').lower().endswith('.pdf'):
                pdf_urls.append(note['url'])

        # Extract all PDFs in parallel
        if pdf_urls:
            extraction_results = batch_extract_pdfs(
                pdf_urls,
                cache_manager=cache_manager,
                progress_callback=progress_callback
            )

            # Add extracted content to bill text versions
            for version in bill_info['bill_text']:
                url = version.get('url')
                if url in extraction_results:
                    result = extraction_results[url]
                    version['content'] = result.get('text', '')
                    version['pages'] = result.get('pages', 0)
                    if result.get('error'):
                        version['extraction_error'] = result['error']

            # Add extracted content to amendments
            for amendment in bill_info['amendments']:
                url = amendment.get('url')
                if url in extraction_results:
                    result = extraction_results[url]
                    amendment['content'] = result.get('text', '')
                    amendment['pages'] = result.get('pages', 0)
                    if result.get('error'):
                        amendment['extraction_error'] = result['error']

            # Add extracted content to fiscal notes
            for note in bill_info['fiscal_notes']:
                url = note.get('url')
                if url in extraction_results:
                    result = extraction_results[url]
                    note['content'] = result.get('text', '')
                    note['pages'] = result.get('pages', 0)
                    if result.get('error'):
                        note['extraction_error'] = result['error']

    # Cache result
    if cache_manager:
        cache_manager.set(cache_key, bill_info, subdirectory='bills')

    return bill_info


def search_bills(
    query: str,
    session: Optional[str] = None,
    chamber: Optional[str] = None,
    limit: int = 50,
    cache_manager=None
) -> List[Dict[str, Any]]:
    """
    Search bills by keyword using Turbo Stream POST search.

    Args:
        query: Search query string
        session: Session code to filter by
        chamber: Chamber to filter by
        limit: Maximum number of results
        cache_manager: Optional cache manager

    Returns:
        List of matching bill dicts
    """
    if not session:
        session = get_current_session()

    session_name = _session_code_to_name(session)

    # Use relevance sort for keyword searches
    bills = _fetch_turbo_search_results(
        session_name,
        query=query,
        sort='Most Relevant'
    )

    # Apply chamber filter client-side
    if chamber:
        bills = [b for b in bills if (
            (chamber == 'House' and b['bill_number'].startswith('H')) or
            (chamber == 'Senate' and b['bill_number'].startswith('S'))
        )]

    return bills[:limit]


def _extract_sponsors(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Extract bill sponsors."""
    sponsors = []

    # Find sponsor section
    sponsor_section = soup.find('div', class_=re.compile(r'sponsor'))
    if not sponsor_section:
        sponsor_heading = soup.find(text=re.compile(r'Sponsors?', re.I))
        if sponsor_heading:
            sponsor_section = sponsor_heading.find_parent('div') or sponsor_heading.find_parent('section')

    if sponsor_section:
        # Find all legislator links
        sponsor_links = sponsor_section.find_all('a', href=re.compile(r'/legislators/'))

        for link in sponsor_links:
            # Collapse all whitespace to single spaces
            sponsor_name = ' '.join(link.text.split())
            sponsor_url = f"{BASE_URL}{link.get('href')}"

            # Try to determine if prime or co-sponsor
            role = 'Prime Sponsor'
            parent_text = link.find_parent().text if link.find_parent() else ''
            if 'co-sponsor' in parent_text.lower():
                role = 'Co-Sponsor'

            sponsors.append({
                'name': sponsor_name,
                'role': role,
                'url': sponsor_url
            })

    return sponsors


def _extract_bill_text(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Extract bill text versions."""
    versions = []

    # Find bill text section
    bill_text_section = soup.find('div', id=re.compile(r'bill.*text'))
    if bill_text_section:
        # Find all download links
        links = bill_text_section.find_all('a', href=re.compile(r'/bill_files/'))

        for link in links:
            version = {
                'version': None,
                'date': None,
                'url': None
            }

            # Extract version name from aria-label (most reliable)
            aria_label = link.get('aria-label', '')
            if aria_label:
                # Pattern: "PDF Bill File for HB26-1001 Introduced"
                # Extract the last word(s) after the bill number
                parts = aria_label.split()
                if len(parts) > 0:
                    # Find bill number pattern (e.g., HB26-1001, SB26-004)
                    for i, part in enumerate(parts):
                        if re.match(r'[HS][BJ]R?\d{2}-\d+', part):
                            # Everything after the bill number is the version
                            if i + 1 < len(parts):
                                version['version'] = ' '.join(parts[i+1:])
                            break
                    # If no bill number found, try last word
                    if not version['version'] and parts:
                        version['version'] = parts[-1]

            # Fallback: Extract version name from link text
            if not version['version']:
                link_text = link.text.strip()
                if link_text and link_text.lower() not in ['download', 'pdf', 'view']:
                    version['version'] = link_text

            # Extract version name and date from surrounding text
            parent = link.find_parent()
            if parent:
                text = parent.text.strip()
                # Common patterns: "Introduced (01/15/2026)", "Engrossed (02/03/2026)"
                version_match = re.search(r'([A-Za-z\s]+)\s*\((\d{2}/\d{2}/\d{4})\)', text)
                if version_match:
                    # Only override if we didn't get it from aria-label
                    if not version['version']:
                        version['version'] = version_match.group(1).strip()
                    version['date'] = version_match.group(2)

            # URL
            href = link.get('href', '')
            version['url'] = f"{BASE_URL}{href}" if href.startswith('/') else href

            if version['url']:
                versions.append(version)

    return versions


def _extract_fiscal_notes(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Extract fiscal notes."""
    fiscal_notes = []

    # Find fiscal section
    fiscal_section = soup.find('div', id=re.compile(r'fiscal'))
    if fiscal_section:
        # Find all fiscal note links
        links = fiscal_section.find_all('a', href=re.compile(r'fiscal'))

        for link in links:
            note = {
                'version': None,
                'date': None,
                'url': None
            }

            # Extract info from text
            text = link.text.strip()
            # Common pattern: "FN1 (01/20/2026)"
            note_match = re.search(r'(FN\d+)\s*\((\d{2}/\d{2}/\d{4})\)', text)
            if note_match:
                note['version'] = note_match.group(1)
                note['date'] = note_match.group(2)

            href = link.get('href', '')
            note['url'] = f"{BASE_URL}{href}" if href.startswith('/') else href

            if note['url']:
                fiscal_notes.append(note)

    return fiscal_notes


def _extract_amendments(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Extract amendments."""
    amendments = []

    # Find amendments section
    amendments_section = soup.find('div', id=re.compile(r'amendment'))
    if amendments_section:
        # Find amendment table
        table = amendments_section.find('table')
        if table:
            rows = table.find_all('tr')[1:]  # Skip header

            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    amendment = {
                        'date': cells[0].text.strip(),
                        'number': cells[1].text.strip(),
                        'location': cells[2].text.strip(),
                        'status': cells[3].text.strip(),
                        'url': None
                    }

                    # Find download link
                    link = row.find('a', href=re.compile(r'/bill_amendments/'))
                    if link:
                        href = link.get('href', '')
                        amendment['url'] = f"{BASE_URL}{href}" if href.startswith('/') else href

                    amendments.append(amendment)

    return amendments


def _extract_votes(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """Extract vote records."""
    votes = []

    # Find votes section or table
    vote_table = soup.find('table', class_=re.compile(r'vote'))
    if not vote_table:
        # Try finding by heading
        vote_heading = soup.find(text=re.compile(r'Vote.*History', re.I))
        if vote_heading:
            parent = vote_heading.find_parent()
            if parent:
                vote_table = parent.find_next('table')

    if vote_table:
        rows = vote_table.find_all('tr')[1:]  # Skip header

        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 3:
                vote = {
                    'date': cells[0].text.strip(),
                    'calendar': cells[1].text.strip() if len(cells) > 1 else None,
                    'motion': cells[2].text.strip() if len(cells) > 2 else None,
                    'result': cells[3].text.strip() if len(cells) > 3 else None,
                    'url': None
                }

                # Find vote document link
                link = row.find('a', href=re.compile(r'/bill_votes/'))
                if link:
                    href = link.get('href', '')
                    vote['url'] = f"{BASE_URL}{href}" if href.startswith('/') else href

                votes.append(vote)

    return votes


def _extract_history(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Extract bill history timeline."""
    history = []

    # Find history section
    history_section = soup.find('div', id=re.compile(r'history'))
    if history_section:
        # Find all history items (could be list items or divs)
        items = history_section.find_all(['li', 'div'], class_=re.compile(r'history.*item'))

        for item in items:
            entry = {
                'date': None,
                'action': None,
                'location': None
            }

            text = item.text.strip()

            # Try to parse date and action
            # Common format: "01/15/2026 - Introduced in House"
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})\s*[-:]\s*(.+)', text)
            if date_match:
                entry['date'] = date_match.group(1)
                entry['action'] = date_match.group(2).strip()
            else:
                entry['action'] = text

            if entry['action']:
                history.append(entry)

    return history


def extract_bill_content(bill_info: Dict[str, Any], cache_manager=None, progress_callback=None) -> Dict[str, Any]:
    """
    Extract PDF content from an existing bill info dict.

    Useful for extracting content from bills retrieved from cache without
    needing to re-fetch the bill page.

    Args:
        bill_info: Bill info dict from get_bill_info()
        cache_manager: Optional cache manager for caching extraction results
        progress_callback: Optional callback(completed, total, url, from_cache) for progress

    Returns:
        Updated bill_info dict with 'content' fields added to bill_text, amendments, fiscal_notes
    """
    if not cache_manager:
        return bill_info

    # Collect all PDF URLs
    pdf_urls = []

    for version in bill_info.get('bill_text', []):
        if version.get('url', '').lower().endswith('.pdf'):
            pdf_urls.append(version['url'])

    for amendment in bill_info.get('amendments', []):
        if amendment.get('url', '').lower().endswith('.pdf'):
            pdf_urls.append(amendment['url'])

    for note in bill_info.get('fiscal_notes', []):
        if note.get('url', '').lower().endswith('.pdf'):
            pdf_urls.append(note['url'])

    # Extract all PDFs
    if pdf_urls:
        extraction_results = batch_extract_pdfs(
            pdf_urls,
            cache_manager=cache_manager,
            progress_callback=progress_callback
        )

        # Add to bill text versions
        for version in bill_info.get('bill_text', []):
            url = version.get('url')
            if url in extraction_results:
                result = extraction_results[url]
                version['content'] = result.get('text', '')
                version['pages'] = result.get('pages', 0)
                if result.get('error'):
                    version['extraction_error'] = result['error']

        # Add to amendments
        for amendment in bill_info.get('amendments', []):
            url = amendment.get('url')
            if url in extraction_results:
                result = extraction_results[url]
                amendment['content'] = result.get('text', '')
                amendment['pages'] = result.get('pages', 0)
                if result.get('error'):
                    amendment['extraction_error'] = result['error']

        # Add to fiscal notes
        for note in bill_info.get('fiscal_notes', []):
            url = note.get('url')
            if url in extraction_results:
                result = extraction_results[url]
                note['content'] = result.get('text', '')
                note['pages'] = result.get('pages', 0)
                if result.get('error'):
                    note['extraction_error'] = result['error']

    return bill_info
