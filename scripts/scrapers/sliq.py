"""SLIQ API client for Colorado legislative committee recordings."""
import json
import re
from datetime import datetime

import requests


SLIQ_BASE = "https://sg001-harmony.sliq.net/00327/Harmony"
SLIQ_API = f"{SLIQ_BASE}/en/api/Data/GetListViewData"

PRIORITY_COMMITTEES = {
    'JointBudgetCommittee': {
        'category_id': 54,
        'name': 'Joint Budget Committee',
    },
    'HealthHumanServices_House': {
        'category_id': 28,
        'name': 'House Health & Human Services',
    },
    'HealthHumanServices_Senate': {
        'category_id': 40,
        'name': 'Senate Health & Human Services',
    },
    'JointTechnologyCommittee': {
        'category_id': 65,
        'name': 'Joint Technology Committee',
    },
    'AgricultureWaterNaturalResources': {
        'category_id': 32,
        'name': 'House Agriculture, Water & Natural Resources',
    },
    'AgricultureNaturalResources': {
        'category_id': 36,
        'name': 'Senate Agriculture & Natural Resources',
    },
}


def _parse_sliq_datetime(dt_str):
    """
    Parse a SLIQ datetime string like '2026-02-04T13:30:00'.

    Returns:
        datetime or None
    """
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00').split('+')[0])
    except (ValueError, AttributeError):
        return None


def _format_duration(seconds):
    """Format duration in seconds to 'Xh Ym' string."""
    if not seconds or seconds <= 0:
        return None
    hours = int(seconds) // 3600
    minutes = (int(seconds) % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _parse_api_response(data, committee_code, committee_name, category_id):
    """
    Convert SLIQ API response into recording dicts.

    Args:
        data: Parsed JSON from GetListViewData API
        committee_code: Committee key like 'JointBudgetCommittee'
        committee_name: Human-readable name
        category_id: SLIQ category ID

    Returns:
        list: List of recording dicts
    """
    recordings = []
    weeks = data.get('Weeks', [])

    for week in weeks:
        entities = week.get('ContentEntityDatas', [])
        for entity in entities:
            clip_id_raw = entity.get('Id')
            if not clip_id_raw:
                continue

            clip_id = f"sliq_{clip_id_raw}"
            title = entity.get('Title', committee_name)

            # Parse dates
            scheduled_start = _parse_sliq_datetime(entity.get('ScheduledStart'))
            actual_start = _parse_sliq_datetime(entity.get('ActualStart'))
            actual_end = _parse_sliq_datetime(entity.get('ActualEnd'))

            # Use actual times for duration, fall back to scheduled
            start_dt = actual_start or scheduled_start
            date_str = start_dt.strftime('%Y-%m-%d') if start_dt else None
            if not date_str:
                continue

            # Calculate duration from actual times
            duration_seconds = None
            if actual_start and actual_end:
                duration_seconds = (actual_end - actual_start).total_seconds()

            # Build PowerBrowser URL for video
            video_url = f"{SLIQ_BASE}/en/PowerBrowser/PowerBrowserV2/{date_str}/-1/{clip_id_raw}"

            recordings.append({
                'clip_id': clip_id,
                'title': title,
                'date': date_str,
                'committee': committee_code,
                'committee_name': committee_name,
                'duration_seconds': duration_seconds,
                'duration': _format_duration(duration_seconds),
                'video_url': video_url,
                'source': 'sliq',
                'category_id': category_id,
                'location': entity.get('Location', ''),
                'status': entity.get('EntityStatusDesc', ''),
            })

    return recordings


def fetch_committee_recordings(committee_code, cache_manager=None, since_date=None):
    """
    Fetch recordings for a specific committee from the SLIQ API.

    Args:
        committee_code: Key from PRIORITY_COMMITTEES dict
        cache_manager: Optional CacheManager for caching
        since_date: Optional start date string 'YYYY-MM-DD' (default: 2025-08-01)

    Returns:
        list: List of recording dicts sorted by date descending
    """
    if committee_code not in PRIORITY_COMMITTEES:
        return []

    committee = PRIORITY_COMMITTEES[committee_code]
    category_id = committee['category_id']
    committee_name = committee['name']

    cache_key = f"sliq_recordings_{category_id}"

    # Check cache (1 hour TTL)
    if cache_manager:
        cached = cache_manager.get(cache_key, max_age_hours=1)
        if cached:
            # Apply since_date filter on cached data
            if since_date:
                cached = [r for r in cached if r.get('date', '') >= since_date]
            return cached

    # Build API request
    from_date = since_date or '2025-08-01'
    from_date_compact = from_date.replace('-', '')
    end_date = datetime.now().strftime('%Y%m%d')

    params = {
        'categoryId': category_id,
        'fromDate': from_date_compact,
        'endDate': end_date,
        'searchTime': '',
        'searchForward': 'true',
        'order': '0',
    }

    try:
        response = requests.get(SLIQ_API, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"Warning: Could not fetch SLIQ recordings for {committee_name}: {e}")
        return []
    except (json.JSONDecodeError, ValueError):
        print(f"Warning: Invalid JSON response for {committee_name}")
        return []

    recordings = _parse_api_response(data, committee_code, committee_name, category_id)

    # Sort by date descending
    recordings.sort(key=lambda x: x.get('date', ''), reverse=True)

    # Cache the full result (before since_date filter)
    if cache_manager and recordings:
        cache_manager.set(cache_key, recordings, subdirectory='recordings')

    # Apply since_date filter
    if since_date:
        recordings = [r for r in recordings if r.get('date', '') >= since_date]

    return recordings


def fetch_all_priority_recordings(cache_manager=None, since_date=None):
    """
    Fetch recordings from all priority committees.

    Args:
        cache_manager: Optional CacheManager for caching
        since_date: Optional start date string 'YYYY-MM-DD' (default: 2025-08-01)

    Returns:
        list: Unified list of recording dicts sorted by date descending
    """
    all_recordings = []

    for committee_code in PRIORITY_COMMITTEES:
        recordings = fetch_committee_recordings(
            committee_code,
            cache_manager=cache_manager,
            since_date=since_date,
        )
        all_recordings.extend(recordings)

    # Sort by date descending
    all_recordings.sort(key=lambda x: x.get('date', ''), reverse=True)
    return all_recordings


def _m3u8_to_mp4(m3u8_url):
    """
    Convert a SLIQ HLS .m3u8 URL to a direct .mp4 download URL.

    SLIQ streams are on sg004-live.sliq.net as HLS, but the same MP4 files
    are available for direct download on sg001-harmony01.sliq.net.

    m3u8: https://sg004-live.sliq.net/00327-vod/_definst_/.../file.mp4/playlist.m3u8
    mp4:  https://sg001-harmony01.sliq.net/00327-Media/.../file.mp4
    """
    if not m3u8_url or '.m3u8' not in m3u8_url:
        return None
    mp4 = m3u8_url.replace(
        'sg004-live.sliq.net/00327-vod/_definst_',
        'sg001-harmony01.sliq.net/00327-Media',
    )
    mp4 = mp4.replace('/playlist.m3u8', '')
    return mp4


def resolve_sliq_media_url(clip_id_raw, cache_manager=None):
    """
    Resolve a SLIQ clip ID to a direct MP4 media URL.

    Fetches the PowerBrowser page, extracts the availableStreams JavaScript
    variable, and converts the HLS URL to a direct MP4 download URL that
    AssemblyAI can access.

    Args:
        clip_id_raw: Raw SLIQ clip ID (without 'sliq_' prefix)
        cache_manager: Optional CacheManager for permanent caching

    Returns:
        str: Direct MP4 URL, or None if not resolved
    """
    cache_key = f"sliq_media_url_{clip_id_raw}"

    # Check permanent cache
    if cache_manager:
        cached = cache_manager.get(cache_key, max_age_hours=None)
        if cached:
            return cached.get('url')

    # Fetch the PowerBrowser page
    today = datetime.now().strftime('%Y-%m-%d')
    page_url = f"{SLIQ_BASE}/en/PowerBrowser/PowerBrowserV2/{today}/-1/{clip_id_raw}"

    try:
        response = requests.get(page_url, timeout=15)
        response.raise_for_status()
        html = response.text
    except requests.RequestException:
        try:
            embed_url = f"{SLIQ_BASE}/en/PowerBrowser/PowerBrowserV2/20250101/-1/{clip_id_raw}"
            response = requests.get(embed_url, timeout=15)
            response.raise_for_status()
            html = response.text
        except requests.RequestException:
            return None

    # Extract availableStreams from JavaScript
    stream_match = re.search(
        r'var\s+availableStreams\s*=\s*(\[.*?\]);',
        html,
        re.DOTALL,
    )
    if stream_match:
        try:
            streams = json.loads(stream_match.group(1))
            for stream in streams:
                url = stream.get('Url', '') or stream.get('url', '')
                if '.m3u8' in url:
                    # Convert HLS to direct MP4
                    mp4_url = _m3u8_to_mp4(url)
                    if mp4_url:
                        if cache_manager:
                            cache_manager.set(cache_key, {'url': mp4_url}, subdirectory='recordings')
                        return mp4_url
            # Fallback: return first stream URL as-is (may be direct MP4)
            if streams:
                url = streams[0].get('Url', '') or streams[0].get('url', '')
                if url and '.mp4' in url and '.m3u8' not in url:
                    if cache_manager:
                        cache_manager.set(cache_key, {'url': url}, subdirectory='recordings')
                    return url
        except (json.JSONDecodeError, IndexError, KeyError):
            pass

    # Try alternate pattern for direct video URLs in page HTML
    video_match = re.search(
        r'(https?://[^"\'<>\s]+\.mp4)(?=["\'\s<])',
        html,
    )
    if video_match:
        url = video_match.group(1)
        if 'pixel' not in url.lower() and 'tracking' not in url.lower():
            if cache_manager:
                cache_manager.set(cache_key, {'url': url}, subdirectory='recordings')
            return url

    return None
