"""Search engine for Colorado Legislature data."""
import re
from datetime import datetime


def build_search_pattern(keywords, match_mode="word_boundary"):
    """
    Build a regex pattern for searching.

    Supports quoted phrases for exact matching:
    - "food assistance" -> matches only the exact phrase
    - food assistance -> matches "food" OR "assistance" separately
    - "SNAP" -> same as SNAP (single word)

    Args:
        keywords: String (space-separated, with optional quotes) or list
        match_mode: "word_boundary" (default) or "substring"

    Returns:
        re.Pattern: Compiled regex pattern for matching
    """
    # Parse keywords with quote tracking
    if isinstance(keywords, str):
        keyword_list = []
        current = ""
        in_quotes = False

        for char in keywords:
            if char == '"':
                if in_quotes:
                    # End quote: save as quoted phrase
                    if current:
                        keyword_list.append((current, True))
                        current = ""
                    in_quotes = False
                else:
                    # Start quote
                    in_quotes = True
            elif char == ' ' and not in_quotes:
                # Space outside quotes: save as unquoted word
                if current:
                    keyword_list.append((current, False))
                    current = ""
            else:
                current += char

        # Save last keyword
        if current:
            keyword_list.append((current, in_quotes))
    else:
        # List input: all unquoted (backward compatibility)
        keyword_list = [(kw, False) for kw in keywords]

    if not keyword_list:
        return None

    # Build patterns based on quote status
    patterns = []
    for keyword, is_quoted in keyword_list:
        escaped = re.escape(keyword)

        # Check if multi-word phrase
        has_spaces = ' ' in keyword

        if has_spaces and is_quoted:
            # Multi-word quoted phrase: word boundaries at edges only
            if match_mode == "word_boundary":
                # Use lookahead/lookbehind for phrase matching
                patterns.append(rf'(?<!\w){escaped}(?!\w)')
            else:
                patterns.append(escaped)
        else:
            # Single word or unquoted: standard word boundary
            if match_mode == "word_boundary":
                patterns.append(rf'\b{escaped}\b')
            else:
                patterns.append(escaped)

    # Combine with OR
    combined = '|'.join(patterns)
    return re.compile(combined, re.IGNORECASE)


def highlight_matches(text, pattern):
    """
    Highlight matching text with bold markdown.

    Args:
        text: Text to search in
        pattern: Compiled regex pattern

    Returns:
        str: Text with matches wrapped in **bold**
    """
    if not text or not pattern:
        return text

    def replacer(match):
        return f"**{match.group(0)}**"

    return pattern.sub(replacer, text)


def extract_content_context(text, pattern, context_chars=200, max_matches=3):
    """
    Extract text snippets around pattern matches in content.

    Args:
        text: Full text to search
        pattern: Compiled regex pattern
        context_chars: Number of characters to show before/after match
        max_matches: Maximum number of match contexts to return

    Returns:
        list: List of context strings with highlighted matches
    """
    if not text or not pattern:
        return []

    contexts = []
    matches = list(pattern.finditer(text))[:max_matches]

    for match in matches:
        start_pos = max(0, match.start() - context_chars)
        end_pos = min(len(text), match.end() + context_chars)

        # Extract context
        context = text[start_pos:end_pos]

        # Add ellipsis if truncated
        if start_pos > 0:
            context = "..." + context
        if end_pos < len(text):
            context = context + "..."

        # Highlight the match in the context
        context = highlight_matches(context, pattern)

        # Clean up whitespace
        context = ' '.join(context.split())

        contexts.append(context)

    return contexts


def search_schedules(query, cache_manager=None, department=None):
    """
    Search across cached schedule data.

    Args:
        query: Search query string
        cache_manager: CacheManager instance for accessing cached data
        department: Optional department filter

    Returns:
        list: List of matching schedule entries with structure:
            - date: str
            - time: str
            - topic: str (with highlights)
            - topic_raw: str (original)
            - week_number: int
            - match_context: str
    """
    if not cache_manager:
        return []

    pattern = build_search_pattern(query)
    if not pattern:
        return []

    results = []

    # Search through cached schedules
    # Check metadata for all schedule cache keys
    for key, info in cache_manager.metadata.items():
        if not key.startswith('jbc_schedule_week_'):
            continue

        schedule = cache_manager.get(key, max_age_hours=None)  # Never expire for search
        if not schedule or not schedule.get('meetings'):
            continue

        week_number = schedule.get('week_number')

        for meeting in schedule['meetings']:
            if meeting.get('is_cancelled'):
                continue

            topic = meeting.get('topic', '')
            topic_dept = meeting.get('department', '')
            raw_text = meeting.get('raw_text', '')

            # Check department filter
            if department:
                if not topic_dept or department.lower() not in topic_dept.lower():
                    continue

            # Search in topic and raw text
            searchable = f"{topic} {raw_text}"
            if pattern.search(searchable):
                results.append({
                    'date': meeting.get('date'),
                    'time': meeting.get('time'),
                    'topic': highlight_matches(topic, pattern),
                    'topic_raw': topic,
                    'department': topic_dept,
                    'week_number': week_number,
                    'match_context': 'schedule'
                })

    # Sort by date descending
    results.sort(key=lambda x: x.get('date', ''), reverse=True)
    return results


def _extract_transcript_context(transcript, pattern, max_matches=3):
    """
    Extract speaker-labeled context snippets from transcript utterances.

    Uses stored speaker_map to replace generic labels with real names.

    Args:
        transcript: Transcript data dict with 'utterances' list
        pattern: Compiled regex pattern
        max_matches: Maximum number of matches to return

    Returns:
        list: Context strings like "[Chair Morrow, 01:23:45] ...discussing **food assistance** programs..."
    """
    from scrapers.transcripts import format_timestamp

    utterances = transcript.get('utterances', [])
    if not utterances:
        return []

    # Load stored speaker_map if available
    speaker_map = transcript.get('speaker_map', {})

    contexts = []
    for utt in utterances:
        if len(contexts) >= max_matches:
            break

        text = utt.get('text', '')
        if not pattern.search(text):
            continue

        raw_speaker = utt.get('speaker', '?')
        start_ms = utt.get('start', 0)
        timestamp = format_timestamp(start_ms)

        # Resolve speaker label to real name
        if raw_speaker in speaker_map:
            display_name = speaker_map[raw_speaker].get('display', f'Speaker {raw_speaker}')
        else:
            display_name = f'Speaker {raw_speaker}'

        # Truncate long utterances around the match
        match = pattern.search(text)
        if len(text) > 300 and match:
            start_pos = max(0, match.start() - 100)
            end_pos = min(len(text), match.end() + 100)
            snippet = text[start_pos:end_pos]
            if start_pos > 0:
                snippet = "..." + snippet
            if end_pos < len(text):
                snippet = snippet + "..."
        else:
            snippet = text

        # Highlight matches
        snippet = highlight_matches(snippet, pattern)
        # Clean up whitespace
        snippet = ' '.join(snippet.split())

        contexts.append(f"[{display_name}, {timestamp}] {snippet}")

    return contexts


def count_transcript_mentions(transcript, pattern):
    """
    Count total keyword matches in transcript text.

    Args:
        transcript: Transcript data dict with 'text' field
        pattern: Compiled regex pattern

    Returns:
        int: Number of matches found
    """
    if not transcript or not pattern:
        return 0
    text = transcript.get('text', '')
    if not text:
        return 0
    return len(pattern.findall(text))


def search_recordings(query, cache_manager=None):
    """
    Search across all recording data (Granicus JBC + SLIQ priority committees),
    including transcript content.

    Args:
        query: Search query string
        cache_manager: CacheManager instance

    Returns:
        list: List of matching recordings with structure:
            - date: str
            - title: str (with highlights)
            - title_raw: str
            - video_url: str
            - clip_id: str
            - committee: str (committee code, if from SLIQ)
            - committee_name: str (human-readable, if from SLIQ)
            - match_location: str ('title' or 'transcript')
            - match_context: list of context snippets (for transcript matches)
    """
    if not cache_manager:
        return []

    pattern = build_search_pattern(query)
    if not pattern:
        return []

    # Collect all recordings from both sources
    all_recordings = []
    seen_clip_ids = set()

    # 1. Granicus JBC recordings
    granicus_data = cache_manager.get('jbc_recordings', max_age_hours=None)
    if granicus_data:
        for rec in granicus_data:
            clip_id = rec.get('clip_id', '')
            if clip_id not in seen_clip_ids:
                seen_clip_ids.add(clip_id)
                all_recordings.append(rec)

    # 2. SLIQ priority committee recordings
    try:
        from scrapers.sliq import PRIORITY_COMMITTEES
        for committee_code in PRIORITY_COMMITTEES:
            category_id = PRIORITY_COMMITTEES[committee_code]['category_id']
            cache_key = f"sliq_recordings_{category_id}"
            sliq_data = cache_manager.get(cache_key, max_age_hours=None)
            if sliq_data:
                for rec in sliq_data:
                    clip_id = rec.get('clip_id', '')
                    if clip_id not in seen_clip_ids:
                        seen_clip_ids.add(clip_id)
                        all_recordings.append(rec)
    except ImportError:
        pass

    results = []

    for recording in all_recordings:
        title = recording.get('title', '')
        clip_id = recording.get('clip_id', '')
        committee_name = recording.get('committee_name', '')
        # Search title and committee name
        searchable = f"{title} {committee_name}"
        title_match = pattern.search(searchable)

        # Check transcript content if available
        transcript_contexts = []
        transcript_match = False
        if clip_id:
            from scrapers.transcripts import get_transcript
            transcript = get_transcript(clip_id, cache_manager)
            if transcript and not transcript.get('error'):
                full_text = transcript.get('text', '')
                if pattern.search(full_text):
                    transcript_match = True
                    transcript_contexts = _extract_transcript_context(transcript, pattern)

        if title_match or transcript_match:
            result = {
                'date': recording.get('date'),
                'title': highlight_matches(title, pattern) if title_match else title,
                'title_raw': title,
                'video_url': recording.get('video_url'),
                'clip_id': clip_id,
                'duration': recording.get('duration'),
                'committee': recording.get('committee', ''),
                'committee_name': committee_name,
            }

            if transcript_match:
                result['match_location'] = 'transcript'
                result['match_context'] = transcript_contexts
                result['mention_count'] = count_transcript_mentions(transcript, pattern)
            else:
                result['match_location'] = 'title'
                result['match_context'] = None
                result['mention_count'] = 0

            results.append(result)

    # Sort by date descending
    results.sort(key=lambda x: x.get('date', ''), reverse=True)
    return results


def search_documents(query, cache_manager=None, department=None, doc_type=None):
    """
    Search across cached document data, including PDF content if available.

    Args:
        query: Search query string
        cache_manager: CacheManager instance
        department: Optional department filter
        doc_type: Optional document type filter

    Returns:
        list: List of matching documents with structure:
            - title: str (with highlights)
            - title_raw: str
            - department: str
            - doc_type: str
            - url: str
            - year: str
            - match_location: str ('title', 'pdf_content')
            - match_context: str or list of context snippets
            - pdf_pages: int (if content searched)
    """
    if not cache_manager:
        return []

    pattern = build_search_pattern(query)
    if not pattern:
        return []

    results = []

    # Try to get documents with content first, fallback to without
    documents_data = cache_manager.get('budget_documents_with_content', max_age_hours=None)
    if not documents_data:
        documents_data = cache_manager.get('budget_documents', max_age_hours=None)
    if not documents_data:
        return []

    for doc in documents_data:
        title = doc.get('title', '')
        doc_dept = doc.get('department', '')
        dtype = doc.get('doc_type', '')
        pdf_content = doc.get('pdf_content', '')

        # Apply filters
        if department:
            if not doc_dept or department.lower() not in doc_dept.lower():
                continue

        if doc_type:
            if dtype != doc_type:
                continue

        # Search in title and department (metadata)
        searchable_metadata = f"{title} {doc_dept}"
        metadata_match = pattern.search(searchable_metadata)

        # Search in PDF content if available
        content_match = pattern.search(pdf_content) if pdf_content else False

        if metadata_match or content_match:
            result = {
                'title': highlight_matches(title, pattern) if metadata_match else title,
                'title_raw': title,
                'department': highlight_matches(doc_dept, pattern) if doc_dept and metadata_match else doc_dept,
                'department_raw': doc_dept,
                'doc_type': dtype,
                'url': doc.get('url'),
                'year': doc.get('year'),
            }

            # Determine match location and context
            if content_match:
                result['match_location'] = 'pdf_content'
                result['match_context'] = extract_content_context(pdf_content, pattern)
                result['pdf_pages'] = doc.get('pdf_pages', 0)
            else:
                result['match_location'] = 'title'
                result['match_context'] = None

            results.append(result)

    # Sort by department then title
    results.sort(key=lambda x: (x.get('department_raw', '') or '', x.get('title_raw', '')))
    return results


def search_bills(query, cache_manager=None, chamber=None):
    """
    Search across cached bill data, including PDF content if available.

    Args:
        query: Search query string
        cache_manager: CacheManager instance
        chamber: Optional chamber filter ('House' or 'Senate')

    Returns:
        list: List of matching bills with structure:
            - bill_number: str
            - title: str (with highlights)
            - title_raw: str
            - status: str
            - sponsors: list
            - url: str
            - match_location: str ('title', 'bill_text', 'amendment', 'fiscal_note')
            - match_context: str or list of context snippets
            - match_version: str (version name if matched in bill text)
    """
    if not cache_manager:
        return []

    pattern = build_search_pattern(query)
    if not pattern:
        return []

    results = []

    # Search through cached bills
    for key, info in cache_manager.metadata.items():
        if not key.startswith('bill_') and not key.startswith('bills_list_'):
            continue

        # Skip list caches, focus on individual bills
        if key.startswith('bills_list_'):
            continue

        bill = cache_manager.get(key, max_age_hours=None)
        if not bill:
            continue

        bill_number = bill.get('bill_number', '')
        title = bill.get('title', '')
        long_title = bill.get('long_title', '')
        sponsors_list = bill.get('sponsors', [])
        sponsors_text = ' '.join([s.get('name', '') for s in sponsors_list])
        subjects = ' '.join(bill.get('subjects', []))

        # Apply chamber filter
        if chamber:
            if chamber == 'House' and not bill_number.startswith('H'):
                continue
            elif chamber == 'Senate' and not bill_number.startswith('S'):
                continue

        # Search in bill metadata
        searchable_metadata = f"{bill_number} {title} {long_title} {sponsors_text} {subjects}"
        metadata_match = pattern.search(searchable_metadata)

        # Search in bill text content if available
        bill_text_match = None
        bill_text_contexts = []
        matched_version = None

        for version in bill.get('bill_text', []):
            content = version.get('content', '')
            if content and pattern.search(content):
                bill_text_match = True
                matched_version = version.get('version', 'Unknown')
                bill_text_contexts.extend(extract_content_context(content, pattern, max_matches=2))
                break  # Only show first matching version

        # Search in amendments if no bill text match
        amendment_match = False
        amendment_contexts = []
        matched_amendment = None

        if not bill_text_match:
            for amendment in bill.get('amendments', []):
                content = amendment.get('content', '')
                if content and pattern.search(content):
                    amendment_match = True
                    matched_amendment = amendment.get('number', 'Unknown')
                    amendment_contexts.extend(extract_content_context(content, pattern, max_matches=2))
                    break  # Only show first matching amendment

        # Search in fiscal notes if no other content match
        fiscal_note_match = False
        fiscal_note_contexts = []

        if not bill_text_match and not amendment_match:
            for note in bill.get('fiscal_notes', []):
                content = note.get('content', '')
                if content and pattern.search(content):
                    fiscal_note_match = True
                    fiscal_note_contexts.extend(extract_content_context(content, pattern, max_matches=2))
                    break  # Only show first matching fiscal note

        # Add to results if any match found
        if metadata_match or bill_text_match or amendment_match or fiscal_note_match:
            title_match = title if pattern.search(title) else long_title

            result = {
                'bill_number': bill_number,
                'title': highlight_matches(title_match, pattern) if metadata_match and title_match else title,
                'title_raw': title,
                'long_title': long_title,
                'status': bill.get('status'),
                'last_action': bill.get('last_action'),
                'sponsors': [s.get('name') for s in sponsors_list[:2]],  # First 2 sponsors
                'subjects': bill.get('subjects', []),
                'url': bill.get('url'),
            }

            # Determine match location and context
            if bill_text_match:
                result['match_location'] = 'bill_text'
                result['match_context'] = bill_text_contexts
                result['match_version'] = matched_version
            elif amendment_match:
                result['match_location'] = 'amendment'
                result['match_context'] = amendment_contexts
                result['match_amendment'] = matched_amendment
            elif fiscal_note_match:
                result['match_location'] = 'fiscal_note'
                result['match_context'] = fiscal_note_contexts
            else:
                result['match_location'] = 'title'
                result['match_context'] = None

            results.append(result)

    # Sort by bill number
    results.sort(key=lambda x: x.get('bill_number', ''))
    return results


def search_all(query, data_types=None, cache_manager=None, department=None, chamber=None):
    """
    Search across all data types.

    Args:
        query: Search query string
        data_types: List of types to search ('schedules', 'recordings', 'documents', 'bills')
                   If None, searches all types
        cache_manager: CacheManager instance
        department: Optional department filter (applies to schedules and documents)
        chamber: Optional chamber filter (applies to bills)

    Returns:
        dict: Results grouped by type:
            {
                'query': str,
                'schedules': list,
                'recordings': list,
                'documents': list,
                'bills': list,
                'total_count': int
            }
    """
    if data_types is None:
        data_types = ['schedules', 'recordings', 'documents', 'bills']

    results = {
        'query': query,
        'schedules': [],
        'recordings': [],
        'documents': [],
        'bills': [],
        'total_count': 0
    }

    if 'schedules' in data_types:
        results['schedules'] = search_schedules(query, cache_manager, department=department)

    if 'recordings' in data_types:
        results['recordings'] = search_recordings(query, cache_manager)

    if 'documents' in data_types:
        results['documents'] = search_documents(query, cache_manager, department=department)

    if 'bills' in data_types:
        results['bills'] = search_bills(query, cache_manager, chamber=chamber)

    results['total_count'] = (
        len(results['schedules']) +
        len(results['recordings']) +
        len(results['documents']) +
        len(results['bills'])
    )

    return results


def filter_results_since(results, since_date):
    """
    Filter results to only include items after a certain date.

    Args:
        results: Results dict from search_all
        since_date: ISO date string (YYYY-MM-DD) or datetime

    Returns:
        dict: Filtered results with updated counts
    """
    if isinstance(since_date, str):
        since_dt = datetime.fromisoformat(since_date)
    else:
        since_dt = since_date

    filtered = {
        'query': results.get('query'),
        'schedules': [],
        'recordings': [],
        'documents': [],
        'bills': [],
        'total_count': 0
    }

    # Filter schedules by date
    for item in results.get('schedules', []):
        try:
            item_date = datetime.strptime(item.get('date', ''), '%Y-%m-%d')
            if item_date > since_dt:
                item['is_new'] = True
                filtered['schedules'].append(item)
        except ValueError:
            continue

    # Filter recordings by date
    for item in results.get('recordings', []):
        try:
            item_date = datetime.strptime(item.get('date', ''), '%Y-%m-%d')
            if item_date > since_dt:
                item['is_new'] = True
                filtered['recordings'].append(item)
        except ValueError:
            continue

    # Documents don't have dates typically, so include all but mark as new
    for item in results.get('documents', []):
        item['is_new'] = True
        filtered['documents'].append(item)

    # Bills don't have simple dates in cache, so include all but mark as new
    for item in results.get('bills', []):
        item['is_new'] = True
        filtered['bills'].append(item)

    filtered['total_count'] = (
        len(filtered['schedules']) +
        len(filtered['recordings']) +
        len(filtered['documents']) +
        len(filtered['bills'])
    )

    return filtered
