"""Granicus audio/video scraper for JBC recordings."""
import re
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup


# Granicus JBC recordings page
GRANICUS_URL = "https://coloradoga.granicus.com/ViewPublisher.php?view_id=26"
GRANICUS_PLAYER_BASE = "https://coloradoga.granicus.com/MediaPlayer.php?view_id=26&clip_id="


def fetch_jbc_recordings(cache_manager=None, max_age_hours=1):
    """
    Fetch all JBC recordings from Granicus.

    Scrapes the Granicus ViewPublisher page to extract recording metadata
    including dates and clip IDs.

    Args:
        cache_manager: Optional CacheManager for caching
        max_age_hours: Cache TTL in hours (default 1hr for current data)

    Returns:
        list: List of recording dicts with keys:
            - date: str (YYYY-MM-DD)
            - title: str (meeting title)
            - clip_id: str (Granicus clip ID)
            - video_url: str (full player URL)
            - duration: str (if available)
    """
    cache_key = "jbc_recordings"

    # Check cache first
    if cache_manager:
        cached = cache_manager.get(cache_key, max_age_hours=max_age_hours)
        if cached:
            return cached

    try:
        response = requests.get(GRANICUS_URL, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Warning: Could not fetch Granicus recordings: {e}")
        return []

    recordings = _parse_granicus_page(response.text)

    # Cache results
    if cache_manager and recordings:
        cache_manager.set(cache_key, recordings, subdirectory="recordings")

    return recordings


def _parse_granicus_page(html):
    """
    Parse Granicus ViewPublisher HTML to extract recordings.

    The page contains a table or list of recordings with links like:
    MediaPlayer.php?view_id=26&clip_id=15549

    Args:
        html: Raw HTML from Granicus page

    Returns:
        list: List of recording dicts
    """
    soup = BeautifulSoup(html, 'lxml')
    recordings = []

    # Find all links to MediaPlayer with clip_id
    # Pattern: MediaPlayer.php?view_id=26&clip_id=XXXXX
    clip_pattern = re.compile(r'clip_id=(\d+)')

    # Look for table rows or list items containing recording info
    # Granicus pages typically have a table with date, title, and duration

    # Try finding rows in the main content area
    # Granicus uses class="odd" and class="even" for table rows
    for row in soup.find_all(['tr', 'div'], class_=re.compile(r'row|item|entry|odd|even', re.I)):
        link = row.find('a', href=clip_pattern)
        if not link:
            continue

        clip_match = clip_pattern.search(link.get('href', ''))
        if not clip_match:
            continue

        clip_id = clip_match.group(1)

        # Extract date - look for date patterns in the row
        date_str = _extract_date_from_element(row)

        # Extract title from the first table cell (Granicus puts title in td[0])
        cells = row.find_all('td')
        if cells:
            title = cells[0].get_text(strip=True)
        else:
            title = _extract_title_from_element(row)

        # Extract duration if present
        duration = _extract_duration_from_element(row)

        if date_str:
            recordings.append({
                'date': date_str,
                'title': title,
                'clip_id': clip_id,
                'video_url': f"{GRANICUS_PLAYER_BASE}{clip_id}",
                'duration': duration
            })

    # Also try a more generic approach - find all clip links
    if not recordings:
        for link in soup.find_all('a', href=clip_pattern):
            clip_match = clip_pattern.search(link.get('href', ''))
            if not clip_match:
                continue

            clip_id = clip_match.group(1)

            # Try to find date in parent elements
            parent = link.find_parent(['tr', 'div', 'li', 'td'])
            date_str = _extract_date_from_element(parent) if parent else None

            # If still no date, try to extract from link text
            if not date_str:
                date_str = _extract_date_from_text(link.get_text())

            title = link.get_text(strip=True)

            if date_str:
                recordings.append({
                    'date': date_str,
                    'title': title,
                    'clip_id': clip_id,
                    'video_url': f"{GRANICUS_PLAYER_BASE}{clip_id}",
                    'duration': None
                })

    # Sort by date descending (most recent first)
    recordings.sort(key=lambda x: x['date'], reverse=True)

    return recordings


def _extract_date_from_element(element):
    """Extract a date from an HTML element's text content."""
    if element is None:
        return None
    return _extract_date_from_text(element.get_text())


def _extract_date_from_text(text):
    """
    Extract a date from text, trying multiple formats.

    Common formats:
    - January 6, 2026
    - 01/06/2026
    - 2026-01-06
    """
    if not text:
        return None

    # Pattern for "Month Day, Year"
    month_day_pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})'
    match = re.search(month_day_pattern, text, re.IGNORECASE)
    if match:
        try:
            parsed = datetime.strptime(f"{match.group(1)} {match.group(2)} {match.group(3)}", "%B %d %Y")
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            pass

    # Pattern for MM/DD/YYYY
    slash_pattern = r'(\d{1,2})/(\d{1,2})/(\d{4})'
    match = re.search(slash_pattern, text)
    if match:
        try:
            parsed = datetime.strptime(f"{match.group(1)}/{match.group(2)}/{match.group(3)}", "%m/%d/%Y")
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            pass

    # Pattern for YYYY-MM-DD
    iso_pattern = r'(\d{4})-(\d{2})-(\d{2})'
    match = re.search(iso_pattern, text)
    if match:
        return match.group(0)

    return None


def _extract_title_from_element(element):
    """Extract a meeting title from an element."""
    if element is None:
        return "JBC Meeting"

    # Look for text that mentions JBC, Budget, Hearing, etc.
    text = element.get_text(strip=True)

    # Try to find a meaningful title
    title_patterns = [
        r'(Joint Budget Committee.*?)(?:\d|$)',
        r'(JBC.*?(?:Hearing|Meeting|Session))',
        r'(Budget.*?Hearing)',
    ]

    for pattern in title_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Default: first 50 chars of text
    if len(text) > 50:
        return text[:50] + "..."
    return text or "JBC Meeting"


def _extract_duration_from_element(element):
    """Extract duration from an element if present."""
    if element is None:
        return None

    text = element.get_text()

    # Pattern for duration like "2:30:45" or "1h 30m"
    duration_patterns = [
        r'(\d{1,2}:\d{2}:\d{2})',  # HH:MM:SS
        r'(\d{1,2}:\d{2})',  # MM:SS or H:MM
        r'(\d+)\s*h(?:our)?s?\s*(\d+)?\s*m(?:in)?',  # Xh Ym
    ]

    for pattern in duration_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    return None


def get_recording_for_date(date_str, cache_manager=None):
    """
    Find a recording matching a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format
        cache_manager: Optional CacheManager

    Returns:
        dict: Recording dict if found, None otherwise
    """
    recordings = fetch_jbc_recordings(cache_manager)

    for recording in recordings:
        if recording['date'] == date_str:
            return recording

    return None


def get_recordings_for_week(week_number, year=None, cache_manager=None):
    """
    Get all recordings for a specific week.

    Args:
        week_number: ISO week number (1-52)
        year: Year (defaults to current year)
        cache_manager: Optional CacheManager

    Returns:
        list: List of recordings in that week
    """
    if year is None:
        year = datetime.now().year

    # Calculate week date range (Monday to Sunday)
    jan4 = datetime(year, 1, 4)
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())
    week_start = start_of_week1 + timedelta(weeks=week_number - 1)
    week_end = week_start + timedelta(days=6)

    recordings = fetch_jbc_recordings(cache_manager)

    week_recordings = []
    for recording in recordings:
        try:
            rec_date = datetime.strptime(recording['date'], '%Y-%m-%d')
            if week_start <= rec_date <= week_end:
                week_recordings.append(recording)
        except ValueError:
            continue

    return week_recordings


def get_recording_status(date_str, cache_manager=None):
    """
    Determine the status of a recording for a date.

    Args:
        date_str: Date in YYYY-MM-DD format
        cache_manager: Optional CacheManager

    Returns:
        str: 'available', 'pending', or 'unavailable'
    """
    recording = get_recording_for_date(date_str, cache_manager)

    if recording:
        return 'available'

    # Check if the date is in the future
    try:
        meeting_date = datetime.strptime(date_str, '%Y-%m-%d')
        if meeting_date >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            return 'pending'
    except ValueError:
        pass

    return 'unavailable'
