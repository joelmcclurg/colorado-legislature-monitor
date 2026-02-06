"""JBC PDF schedule parser for Colorado Legislature."""
import re
from datetime import datetime, timedelta
from io import BytesIO

import pdfplumber
import requests


def get_current_week_number():
    """Get the current ISO week number."""
    return datetime.now().isocalendar()[1]


def get_week_date_range(week_number, year=None):
    """
    Get the start (Monday) and end (Sunday) dates for a given ISO week number.

    Args:
        week_number: ISO week number (1-52)
        year: Year (defaults to current year)

    Returns:
        tuple: (start_date, end_date) as datetime objects
    """
    if year is None:
        year = datetime.now().year

    # Find the first day of ISO week 1 (the Monday of the week containing Jan 4)
    jan4 = datetime(year, 1, 4)
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())

    # Calculate the start of the requested week
    week_start = start_of_week1 + timedelta(weeks=week_number - 1)
    week_end = week_start + timedelta(days=6)

    return week_start, week_end


def _fetch_latest_jbc_pdf():
    """
    Fetch the latest JBC schedule PDF by finding the highest revision number.

    The JBC publishes the full-year schedule as revisions:
    JBC Schedule_1.pdf, JBC Schedule_2.pdf, etc.

    Returns:
        tuple: (pdf_content, source_url, revision_number) or (None, None, None)
    """
    base_url = "https://content.leg.colorado.gov/sites/default/files"

    # Search from high to low to find the latest revision
    # Start at 20 and work down (usually won't be more than ~15 revisions)
    for revision in range(20, 0, -1):
        url = f"{base_url}/JBC%20Schedule_{revision}.pdf"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.content, url, revision
        except requests.RequestException:
            continue

    return None, None, None


def fetch_jbc_schedule_pdf(week_number=None):
    """
    Fetch and parse JBC schedule PDF, filtered to a specific week.

    The JBC publishes the full-year schedule as a single PDF with revision numbers.
    This function fetches the latest revision and filters to the requested week.

    Args:
        week_number: Week number (1-52). If None, uses current week.

    Returns:
        dict: Parsed schedule data with structure:
            {
                'week_number': int,
                'meetings': [...],
                'week_start': str (YYYY-MM-DD),
                'week_end': str (YYYY-MM-DD),
                'revision': int,
                'raw_content': str,
                'source_url': str,
                'fetched_at': str (ISO timestamp)
            }

        Returns None if PDF not found or parsing fails.
    """
    if week_number is None:
        week_number = get_current_week_number()

    # Fetch the latest PDF revision
    pdf_content, source_url, revision = _fetch_latest_jbc_pdf()

    if pdf_content is None:
        return None

    # Get the date range for the requested week
    week_start, week_end = get_week_date_range(week_number)

    # Parse PDF with pdfplumber
    try:
        raw_text = ""

        with pdfplumber.open(BytesIO(pdf_content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    raw_text += text + "\n"

        # Parse all meetings from text
        all_meetings = _parse_schedule_text(raw_text)

        # Filter to requested week
        meetings = _filter_meetings_by_week(all_meetings, week_start, week_end)

        return {
            'week_number': week_number,
            'meetings': meetings,
            'week_start': week_start.strftime('%Y-%m-%d'),
            'week_end': week_end.strftime('%Y-%m-%d'),
            'revision': revision,
            'raw_content': raw_text,
            'source_url': source_url,
            'fetched_at': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"Error parsing PDF: {e}")
        return None


def _filter_meetings_by_week(meetings, week_start, week_end):
    """
    Filter meetings to only those within the specified week.

    Args:
        meetings: List of meeting dicts with 'date' field
        week_start: Start of week (Monday) as datetime
        week_end: End of week (Sunday) as datetime

    Returns:
        list: Filtered meetings
    """
    filtered = []
    for meeting in meetings:
        try:
            meeting_date = datetime.strptime(meeting['date'], '%Y-%m-%d')
            if week_start <= meeting_date <= week_end:
                filtered.append(meeting)
        except (ValueError, KeyError):
            continue
    return filtered


# Lines that are boilerplate and should be skipped
BOILERPLATE_PATTERNS = [
    r'^\*\* Tentative',
    r'^Unless Otherwise Noted',
    r'^JBC Hearing Room',
    r'^Legislative Service Building',
    r'^200 East 14th Avenue',
    r'^Denver, CO',
    r'^\(303\) 866',
    r'^https?://',
    r'^Updated \d+/\d+',
    r'^\d{4}/\d{4} JOINT BUDGET COMMITTEE SCHEDULE',
    r'^Page \d+',
]


def _is_boilerplate(line):
    """Check if a line is boilerplate text that should be skipped."""
    for pattern in BOILERPLATE_PATTERNS:
        if re.match(pattern, line, re.IGNORECASE):
            return True
    return False


def _parse_schedule_text(text):
    """
    Parse schedule text into structured meeting data.

    Handles the JBC schedule format:
    - Day headers: "Monday, February 3" or "Tuesday, November 18"
    - Time ranges at start of lines: "9:00 – 12:00 Briefing for..."
    - "Will Not Meet" notices

    Args:
        text: Raw text from PDF

    Returns:
        list: List of meeting dicts
    """
    meetings = []
    lines = text.split('\n')

    current_date = None
    current_year = datetime.now().year

    # Track which months we've seen to handle year transitions
    # JBC schedule typically runs Nov-May, crossing the year boundary
    seen_late_year_month = False  # Nov, Dec

    # Patterns
    # Day header: "Monday, February 3" or "Tuesday November 18" (may have text after)
    day_header_pattern = r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:\s|$)'

    # Time range at start: "9:00 – 12:00" or "1:30 – 5:00" (using en-dash or hyphen)
    time_range_pattern = r'^(\d{1,2}:\d{2})\s*[–\-]\s*(\d{1,2}:\d{2})\s+(.+)$'

    # Single time: "9:00 AM" style (less common in this PDF)
    single_time_pattern = r'^(\d{1,2}:\d{2}\s*(?:AM|PM|a\.m\.|p\.m\.))\s+(.+)$'

    # Special time markers: "Upon Adjournment", "TBA"
    special_time_pattern = r'^(Upon Adjournment|TBA)\s+(.+)$'

    # "Will Not Meet" notice
    not_meeting_pattern = r'The JBC Will Not Meet'

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip boilerplate
        if _is_boilerplate(line):
            continue

        # Check for day header (sets the current date)
        day_match = re.match(day_header_pattern, line, re.IGNORECASE)
        if day_match:
            day_name, month_name, day_num = day_match.groups()

            # Determine the year based on month
            month_num = datetime.strptime(month_name, '%B').month

            if month_num >= 11:  # November or December
                seen_late_year_month = True
                year = current_year if datetime.now().month >= 11 else current_year - 1
            else:  # January through October
                # If we've seen Nov/Dec, this is the next year
                year = current_year if not seen_late_year_month or datetime.now().month <= 10 else current_year

            try:
                parsed_date = datetime(year, month_num, int(day_num))
                current_date = parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
            continue  # Don't add the header itself as a meeting

        # Skip if we don't have a current date yet
        if not current_date:
            continue

        # Check for "Will Not Meet" notice
        if re.search(not_meeting_pattern, line, re.IGNORECASE):
            meetings.append({
                'date': current_date,
                'time': 'N/A',
                'topic': line,
                'department': None,
                'is_cancelled': True,
                'raw_text': line
            })
            continue

        # Check for time range at start of line
        time_match = re.match(time_range_pattern, line)
        if time_match:
            start_time, end_time, topic = time_match.groups()
            meetings.append({
                'date': current_date,
                'time': f"{start_time} – {end_time}",
                'topic': topic.strip(),
                'department': _extract_department(topic),
                'is_cancelled': False,
                'raw_text': line
            })
            continue

        # Check for single time
        single_match = re.match(single_time_pattern, line, re.IGNORECASE)
        if single_match:
            time_str, topic = single_match.groups()
            meetings.append({
                'date': current_date,
                'time': time_str,
                'topic': topic.strip(),
                'department': _extract_department(topic),
                'is_cancelled': False,
                'raw_text': line
            })
            continue

        # Check for special time markers (Upon Adjournment, TBA)
        special_match = re.match(special_time_pattern, line, re.IGNORECASE)
        if special_match:
            time_str, topic = special_match.groups()
            meetings.append({
                'date': current_date,
                'time': time_str,
                'topic': topic.strip(),
                'department': _extract_department(topic),
                'is_cancelled': False,
                'raw_text': line
            })
            continue

        # If line starts with a department keyword and we have meetings,
        # it might be a continuation of the previous meeting's topic
        if meetings and current_date == meetings[-1]['date']:
            # Check if this looks like a continuation (starts with common continuation patterns)
            continuation_patterns = [
                r'^[a-z]',  # Starts with lowercase
                r'^\(',     # Starts with parenthesis
                r'^and\s',  # Starts with "and"
                r'^or\s',   # Starts with "or"
            ]
            is_continuation = any(re.match(p, line) for p in continuation_patterns)

            if is_continuation and len(line) > 5:
                # Append to previous meeting's topic
                meetings[-1]['topic'] += ' ' + line
                meetings[-1]['raw_text'] += ' ' + line
                if not meetings[-1]['department']:
                    meetings[-1]['department'] = _extract_department(line)

    return meetings


def _extract_department(text):
    """Extract department name from topic text if present."""
    dept_pattern = r'(?:Department of|Office of|Division of)\s+([A-Za-z\s&]+?)(?:\s*\(|$|,)'
    match = re.search(dept_pattern, text)
    if match:
        return match.group(1).strip()
    return None


def get_jbc_schedule_for_week(week_number=None, cache_manager=None, include_media=True, include_docs=True):
    """
    Get JBC schedule with caching support.

    Args:
        week_number: Week number (1-52). If None, uses current week.
        cache_manager: CacheManager instance. If None, no caching.
        include_media: Whether to enrich with audio/video links
        include_docs: Whether to enrich with document links

    Returns:
        dict: Schedule data, or None if not available
    """
    if week_number is None:
        week_number = get_current_week_number()

    cache_key = f"jbc_schedule_week_{week_number}"

    # Check cache first
    if cache_manager:
        # Current week: always fetch fresh
        # Historical weeks: cache permanently (max_age_hours=None)
        if cache_manager.is_current_week(week_number):
            max_age = 0  # Always fetch fresh
        else:
            max_age = None  # Never expire

        cached = cache_manager.get(cache_key, max_age_hours=max_age)
        if cached:
            # Still need to enrich if requested (enrichment data may have changed)
            if include_media or include_docs:
                cached = enrich_schedule(cached, cache_manager, include_media, include_docs)
            return cached

    # Fetch fresh data
    schedule = fetch_jbc_schedule_pdf(week_number)

    # Enrich with media and documents if requested
    if schedule and (include_media or include_docs):
        schedule = enrich_schedule(schedule, cache_manager, include_media, include_docs)

    # Cache if available
    if schedule and cache_manager:
        cache_manager.set(cache_key, schedule, subdirectory="schedules")

    return schedule


def enrich_schedule(schedule, cache_manager=None, include_media=True, include_docs=True):
    """
    Enrich a schedule with audio/video links and document links.

    Args:
        schedule: Schedule dict from fetch_jbc_schedule_pdf
        cache_manager: Optional CacheManager for caching scraper results
        include_media: Whether to add audio/video links
        include_docs: Whether to add document links

    Returns:
        dict: Enriched schedule with media and document links added to meetings
    """
    if not schedule or not schedule.get('meetings'):
        return schedule

    # Import here to avoid circular imports
    from scrapers.audio import get_recording_for_date, get_recording_status
    from scrapers.documents import get_briefing_for_department, normalize_department

    for meeting in schedule['meetings']:
        # Add media links
        if include_media:
            meeting_date = meeting.get('date')
            if meeting_date:
                recording = get_recording_for_date(meeting_date, cache_manager)
                if recording:
                    meeting['video_url'] = recording.get('video_url')
                    meeting['media_status'] = 'available'
                else:
                    meeting['video_url'] = None
                    meeting['media_status'] = get_recording_status(meeting_date, cache_manager)
            else:
                meeting['video_url'] = None
                meeting['media_status'] = 'unavailable'

        # Add document links
        if include_docs:
            department = meeting.get('department')
            if department:
                # Try to get briefing document for this department
                briefing = get_briefing_for_department(department, cache_manager)
                if briefing:
                    meeting['document_url'] = briefing.get('url')
                    meeting['document_title'] = briefing.get('title')
                else:
                    meeting['document_url'] = None
                    meeting['document_title'] = None
            else:
                meeting['document_url'] = None
                meeting['document_title'] = None

    return schedule
