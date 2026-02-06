"""AssemblyAI transcript integration for legislative recordings."""
import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests

# Granicus URLs for resolving media
GRANICUS_PLAYER_URL = "https://coloradoga.granicus.com/MediaPlayer.php?view_id=26&clip_id="

# AssemblyAI pricing per hour
ASSEMBLYAI_COST_PER_HOUR = 0.37


def _get_api_key():
    """
    Get AssemblyAI API key from environment or .env file.

    Returns:
        str: API key, or None if not found
    """
    key = os.environ.get('ASSEMBLYAI_API_KEY')
    if key:
        return key

    # Try .env file in project root
    env_paths = [
        Path.home() / '.claude' / 'skills' / 'colorado-legislature' / '.env',
        Path.home() / '.env',
    ]
    for env_path in env_paths:
        if env_path.exists():
            try:
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('ASSEMBLYAI_API_KEY='):
                            return line.split('=', 1)[1].strip().strip('"').strip("'")
            except IOError:
                continue

    return None


def format_timestamp(ms):
    """
    Convert milliseconds to HH:MM:SS format.

    Args:
        ms: Milliseconds (int)

    Returns:
        str: Formatted timestamp like "01:23:45"
    """
    if ms is None:
        return "00:00:00"
    total_seconds = int(ms / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def resolve_media_url(clip_id, cache_manager=None):
    """
    Resolve a clip ID to a direct media URL.

    Supports both Granicus clip IDs and SLIQ clip IDs (prefixed with 'sliq_').

    Args:
        clip_id: Clip ID (str or int). SLIQ IDs start with 'sliq_'.
        cache_manager: Optional CacheManager for SLIQ URL caching

    Returns:
        str: Direct media URL, or None if not resolved
    """
    # Route SLIQ clips to the SLIQ resolver
    clip_str = str(clip_id)
    if clip_str.startswith('sliq_'):
        from scrapers.sliq import resolve_sliq_media_url
        raw_id = clip_str[5:]  # Strip 'sliq_' prefix
        return resolve_sliq_media_url(raw_id, cache_manager=cache_manager)

    from bs4 import BeautifulSoup

    # Strategy 1: Scrape ViewPublisher page for MP4 download link
    # The listing page has direct archive-video.granicus.com MP4 links
    publisher_url = "https://coloradoga.granicus.com/ViewPublisher.php?view_id=26"
    try:
        response = requests.get(publisher_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')

        # Find the row containing this clip_id
        clip_pattern = re.compile(rf'clip_id={clip_id}\b')
        for row in soup.find_all('tr'):
            if row.find('a', href=clip_pattern):
                # Found the row - look for MP4 download link
                for link in row.find_all('a', href=re.compile(r'\.mp4', re.I)):
                    href = link.get('href', '')
                    if href.startswith('//'):
                        href = 'https:' + href
                    if href.startswith('http'):
                        return href
    except requests.RequestException:
        pass

    # Strategy 2: Scrape MediaPlayer page for stream URL in JavaScript
    player_url = f"{GRANICUS_PLAYER_URL}{clip_id}"
    try:
        response = requests.get(player_url, timeout=15)
        response.raise_for_status()
        html = response.text

        patterns = [
            r'''["']?(?:clipUrl|file|src|url)["']?\s*[:=]\s*["'](https?://[^"']+\.(?:mp4|mp3|m4a|webm)[^"']*)["']''',
            r'<source[^>]+src=["\'](https?://[^"\']+)["\']',
            r'(https?://archive-video\.granicus\.com/[^"\'<>\s]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                url = match.group(1)
                if 'pixel' not in url.lower() and 'tracking' not in url.lower():
                    return url
    except requests.RequestException:
        pass

    # Strategy 3: Try common Granicus download URL patterns
    download_patterns = [
        f"https://coloradoga.granicus.com/videos/{clip_id}/original",
        f"https://coloradoga.granicus.com/clips/{clip_id}.mp4",
    ]

    for url in download_patterns:
        try:
            head = requests.head(url, timeout=10, allow_redirects=True)
            content_type = head.headers.get('Content-Type', '')
            if head.status_code == 200 and ('video' in content_type or 'audio' in content_type):
                return url
        except requests.RequestException:
            continue

    return None


def transcribe_recording(clip_id, cache_manager=None, progress_callback=None):
    """
    Transcribe a recording using AssemblyAI with speaker diarization.

    Args:
        clip_id: Granicus clip ID
        cache_manager: CacheManager instance for caching
        progress_callback: Optional callback(status_message) for progress updates

    Returns:
        dict: Transcript data with keys:
            - clip_id: str
            - media_url: str
            - transcript_id: str
            - text: str (full transcript)
            - utterances: list of {speaker, text, start, end}
            - speaker_count: int
            - duration_seconds: float
            - transcribed_at: str (ISO timestamp)
            - error: str or None
    """
    cache_key = f"transcript_{clip_id}"

    # Check cache first
    if cache_manager:
        cached = cache_manager.get(cache_key, max_age_hours=None)  # Permanent cache
        if cached:
            if progress_callback:
                progress_callback("Loaded transcript from cache")
            return cached

    # Check for API key
    api_key = _get_api_key()
    if not api_key:
        return {
            'clip_id': str(clip_id),
            'error': 'ASSEMBLYAI_API_KEY not set. Set it as an environment variable or in .env file.'
        }

    # Resolve media URL
    if progress_callback:
        progress_callback("Resolving media URL...")

    media_url = resolve_media_url(clip_id, cache_manager=cache_manager)
    if not media_url:
        return {
            'clip_id': str(clip_id),
            'error': f'Could not resolve media URL for clip {clip_id}. '
                     'The Granicus player page may not contain a direct media link.'
        }

    if progress_callback:
        progress_callback(f"Media URL resolved. Submitting to AssemblyAI...")

    # Use AssemblyAI SDK
    try:
        import assemblyai as aai
    except ImportError:
        return {
            'clip_id': str(clip_id),
            'error': 'assemblyai package not installed. Run: pip install assemblyai'
        }

    aai.settings.api_key = api_key

    config = aai.TranscriptionConfig(
        speaker_labels=True,
        speech_models=["universal-3-pro"],
    )

    transcriber = aai.Transcriber()

    if progress_callback:
        progress_callback("Transcription submitted. This may take 5-15 minutes for long recordings...")

    try:
        transcript = transcriber.transcribe(media_url, config=config)
    except Exception as e:
        return {
            'clip_id': str(clip_id),
            'media_url': media_url,
            'error': f'AssemblyAI transcription failed: {str(e)}'
        }

    if transcript.status == aai.TranscriptStatus.error:
        return {
            'clip_id': str(clip_id),
            'media_url': media_url,
            'transcript_id': transcript.id,
            'error': f'Transcription error: {transcript.error}'
        }

    # Build utterances list
    utterances = []
    if transcript.utterances:
        for utt in transcript.utterances:
            utterances.append({
                'speaker': utt.speaker,
                'text': utt.text,
                'start': utt.start,
                'end': utt.end,
            })

    # Count unique speakers
    speakers = set(u['speaker'] for u in utterances) if utterances else set()

    # Calculate duration
    duration_ms = transcript.audio_duration
    duration_seconds = (duration_ms / 1000.0) if duration_ms else 0.0

    result = {
        'clip_id': str(clip_id),
        'media_url': media_url,
        'transcript_id': transcript.id,
        'text': transcript.text or '',
        'utterances': utterances,
        'speaker_count': len(speakers),
        'duration_seconds': duration_seconds,
        'transcribed_at': datetime.now().isoformat(),
        'error': None,
    }

    # Cache the result permanently
    if cache_manager:
        cache_manager.set(cache_key, result, subdirectory='transcripts')

    if progress_callback:
        progress_callback(
            f"Transcription complete! {len(utterances)} utterances, "
            f"{len(speakers)} speakers, {format_timestamp(int(duration_seconds * 1000))} duration"
        )

    return result


def get_transcript(clip_id, cache_manager):
    """
    Retrieve a cached transcript without making API calls.

    Args:
        clip_id: Granicus clip ID
        cache_manager: CacheManager instance

    Returns:
        dict: Transcript data, or None if not cached
    """
    if not cache_manager:
        return None
    cache_key = f"transcript_{clip_id}"
    return cache_manager.get(cache_key, max_age_hours=None)


def list_transcribed_recordings(cache_manager):
    """
    List all recordings that have cached transcripts.

    Args:
        cache_manager: CacheManager instance

    Returns:
        list: List of transcript summary dicts with keys:
            - clip_id: str
            - transcript_id: str
            - speaker_count: int
            - duration_seconds: float
            - transcribed_at: str
            - error: str or None
    """
    if not cache_manager:
        return []

    results = []
    for key in cache_manager.metadata.keys():
        if not key.startswith('transcript_'):
            continue

        transcript = cache_manager.get(key, max_age_hours=None)
        if not transcript:
            continue

        results.append({
            'clip_id': transcript.get('clip_id'),
            'transcript_id': transcript.get('transcript_id'),
            'speaker_count': transcript.get('speaker_count', 0),
            'duration_seconds': transcript.get('duration_seconds', 0),
            'transcribed_at': transcript.get('transcribed_at'),
            'utterance_count': len(transcript.get('utterances', [])),
            'error': transcript.get('error'),
        })

    # Sort by transcribed_at descending
    results.sort(key=lambda x: x.get('transcribed_at', ''), reverse=True)
    return results


def estimate_cost(recordings, cache_manager=None):
    """
    Estimate transcription cost for a list of recordings.

    Args:
        recordings: List of recording dicts (with clip_id and duration_seconds)
        cache_manager: CacheManager to check for already-transcribed recordings

    Returns:
        dict: Cost estimate with keys:
            - total: int (total recordings)
            - already_done: int (already transcribed)
            - to_do: int (need transcription)
            - hours: float (total hours to transcribe)
            - cost: float (estimated cost in USD)
    """
    already_done = 0
    to_do = 0
    total_seconds = 0

    for rec in recordings:
        clip_id = rec.get('clip_id', '')
        if cache_manager:
            transcript = get_transcript(clip_id, cache_manager)
            if transcript and not transcript.get('error'):
                already_done += 1
                continue

        to_do += 1
        total_seconds += rec.get('duration_seconds') or 0

    hours = total_seconds / 3600.0
    cost = hours * ASSEMBLYAI_COST_PER_HOUR

    return {
        'total': len(recordings),
        'already_done': already_done,
        'to_do': to_do,
        'hours': round(hours, 1),
        'cost': round(cost, 2),
    }


def batch_transcribe(recordings, cache_manager=None, progress_callback=None):
    """
    Batch transcribe a list of recordings, skipping already-transcribed ones.

    Args:
        recordings: List of recording dicts (with clip_id, title, duration)
        cache_manager: CacheManager instance for caching
        progress_callback: Optional callback(message) for progress updates

    Returns:
        dict: Results with keys:
            - transcribed: int (successfully transcribed)
            - skipped: int (already in cache)
            - errors: list of {clip_id, title, error} dicts
    """
    transcribed = 0
    skipped = 0
    errors = []
    total = len(recordings)

    for i, rec in enumerate(recordings, 1):
        clip_id = rec.get('clip_id', '')
        title = rec.get('title', 'Unknown')
        duration = rec.get('duration', '')

        # Check if already transcribed
        if cache_manager:
            existing = get_transcript(clip_id, cache_manager)
            if existing and not existing.get('error'):
                skipped += 1
                if progress_callback:
                    progress_callback(f"[{i}/{total}] Skipping (cached): {title}")
                continue

        if progress_callback:
            progress_callback(f"[{i}/{total}] Transcribing: {title} ({duration})...")

        result = transcribe_recording(clip_id, cache_manager=cache_manager)

        if result.get('error'):
            errors.append({
                'clip_id': clip_id,
                'title': title,
                'error': result['error'],
            })
            if progress_callback:
                progress_callback(f"  Error: {result['error']}")
        else:
            transcribed += 1
            if progress_callback:
                dur = format_timestamp(int(result.get('duration_seconds', 0) * 1000))
                speakers = result.get('speaker_count', 0)
                progress_callback(f"  Done: {dur} duration, {speakers} speakers")

    return {
        'transcribed': transcribed,
        'skipped': skipped,
        'errors': errors,
    }
