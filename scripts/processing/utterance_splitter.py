"""
Post-processor that splits merged utterances in poorly-diarized transcripts.

When AssemblyAI collapses multiple speakers into 1-3 labels, long utterances
contain multiple speakers' dialogue merged together. This module detects and
splits those utterances using Roberts Rules patterns.
"""
import re
from copy import deepcopy


# Minimum average utterance length to consider a transcript for splitting
_AVG_LENGTH_THRESHOLD = 200

# Maximum speaker count for a transcript to be a splitting candidate
_MAX_SPEAKER_COUNT = 3

# --- Split patterns (ordered by confidence) ---

# Pattern 1: Chair recognition — ". Representative/Senator LastName." mid-utterance
_CHAIR_RECOGNITION_RE = re.compile(
    r'(?<=\.)\s+'
    r'((?:Representative|Senator|Rep\.|Sen\.)\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)'
    r'\.\s*'
)

# Pattern 2: Roll call — "LastName. Here." sequences
_ROLL_CALL_RE = re.compile(
    r'([A-Z][a-z]+(?:-[A-Z][a-z]+)?)\.'
    r'\s+'
    r'((?:[Hh]ere|[Pp]resent|[Aa]ye|[Nn]o|[Nn]ay|[Yy]ea|[Ee]xcused|[Aa]bsent)'
    r'(?:\s*,?\s*(?:Madam|Mr\.|Mister)\s+Chair)?)\.'
)

# Pattern 3: "Thank you, Madam/Mr. Chair" mid-utterance
_THANK_CHAIR_RE = re.compile(
    r'(?<=\.)\s+'
    r'(Thank\s+you,?\s+(?:Madam|Mr\.|Mister)\s+Chair(?:man|woman|person)?)'
    r'[.,]?\s*'
)

# Pattern 4: Self-identification mid-utterance
_SELF_ID_RE = re.compile(
    r'(?<=[.?])\s+'
    r'((?:My\s+name\s+is|I\'?m|I\s+am)\s+[A-Z][a-z]+\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?)'
)


def is_splitting_candidate(transcript_data):
    """Check if a transcript needs utterance splitting.

    A transcript is a candidate when speaker_count <= 3 AND average
    utterance length > 200 chars.

    Args:
        transcript_data: Transcript dict with 'utterances' and 'speaker_count'

    Returns:
        bool: True if the transcript should be processed
    """
    utterances = transcript_data.get('utterances', [])
    if not utterances:
        return False

    speaker_count = transcript_data.get('speaker_count', 0)
    if speaker_count > _MAX_SPEAKER_COUNT:
        return False

    total_len = sum(len(u.get('text', '')) for u in utterances)
    avg_len = total_len / len(utterances)
    return avg_len > _AVG_LENGTH_THRESHOLD


def _split_roll_call(text, original_speaker, start_ms, end_ms):
    """Split a roll call sequence into individual name/response pairs.

    Returns list of utterance dicts, or empty list if no roll call found.
    """
    matches = list(_ROLL_CALL_RE.finditer(text))
    if len(matches) < 2:
        return []

    result = []
    # Text before first match
    pre = text[:matches[0].start()].strip()
    if pre:
        result.append({
            'speaker': original_speaker,
            'text': pre,
            'start': start_ms,
            'end': start_ms,
        })

    # Alternate between caller (name) and responder (response)
    caller_label = original_speaker
    # Use a different label for responders — we'll use the next letter
    responder_label = chr(ord(original_speaker[-1]) + 1) if original_speaker else 'B'

    for m in matches:
        name_text = m.group(1) + '.'
        response_text = m.group(2) + '.'

        result.append({
            'speaker': caller_label,
            'text': name_text,
            'start': start_ms,
            'end': start_ms,
        })
        result.append({
            'speaker': responder_label,
            'text': response_text,
            'start': start_ms,
            'end': start_ms,
            '_roll_call_name': m.group(1),
        })

    # Text after last match
    post = text[matches[-1].end():].strip()
    if post:
        result.append({
            'speaker': original_speaker,
            'text': post,
            'start': start_ms,
            'end': end_ms,
        })

    return result


def _split_by_pattern(text, pattern, original_speaker, start_ms, end_ms):
    """Split text at pattern match points.

    The matched group becomes the start of a new utterance assigned to a
    different speaker label (since the pattern indicates a speaker change).

    Returns list of utterance dicts, or empty list if no splits made.
    """
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    result = []
    prev_end = 0
    # Alternate speaker labels at each split point
    current_speaker = original_speaker

    for m in matches:
        # Text before this split point
        before = text[prev_end:m.start()].strip()
        if before:
            result.append({
                'speaker': current_speaker,
                'text': before,
                'start': start_ms,
                'end': start_ms,
            })

        # Switch speaker for the new segment
        if current_speaker == original_speaker:
            current_speaker = chr(ord(original_speaker[-1]) + 1) if original_speaker else 'B'
        else:
            current_speaker = original_speaker

        prev_end = m.start()
        # The matched text starts the new segment, which continues
        # until the next match or end of text

    # Final segment
    remaining = text[prev_end:].strip()
    if remaining:
        result.append({
            'speaker': current_speaker,
            'text': remaining,
            'start': start_ms,
            'end': end_ms,
        })

    return result if len(result) > 1 else []


def split_utterances(transcript_data):
    """Split merged utterances in a poorly-diarized transcript.

    Operates on the transcript dict in-place. Stores original utterances
    in 'utterances_original' for auditability.

    Args:
        transcript_data: Transcript dict with 'utterances' list

    Returns:
        dict: Stats about the splitting operation:
            - utterances_before: int
            - utterances_after: int
            - splits_made: int
    """
    utterances = transcript_data.get('utterances', [])
    if not utterances:
        return {'utterances_before': 0, 'utterances_after': 0, 'splits_made': 0}

    # Save originals
    transcript_data['utterances_original'] = deepcopy(utterances)

    new_utterances = []
    splits_made = 0

    for utt in utterances:
        text = utt.get('text', '')
        speaker = utt.get('speaker', 'A')
        start_ms = utt.get('start', 0)
        end_ms = utt.get('end', 0)

        # Only try splitting long utterances
        if len(text) < 150:
            new_utterances.append(utt)
            continue

        # Try patterns in order of confidence
        # 1. Roll call
        split_result = _split_roll_call(text, speaker, start_ms, end_ms)
        if split_result:
            new_utterances.extend(split_result)
            splits_made += 1
            continue

        # 2. "Thank you, Madam Chair" pattern
        split_result = _split_by_pattern(
            text, _THANK_CHAIR_RE, speaker, start_ms, end_ms)
        if split_result:
            new_utterances.extend(split_result)
            splits_made += 1
            continue

        # 3. Chair recognition pattern
        split_result = _split_by_pattern(
            text, _CHAIR_RECOGNITION_RE, speaker, start_ms, end_ms)
        if split_result:
            new_utterances.extend(split_result)
            splits_made += 1
            continue

        # 4. Self-identification pattern
        split_result = _split_by_pattern(
            text, _SELF_ID_RE, speaker, start_ms, end_ms)
        if split_result:
            new_utterances.extend(split_result)
            splits_made += 1
            continue

        # No pattern matched — keep original
        new_utterances.append(utt)

    transcript_data['utterances'] = new_utterances

    # Update speaker count
    speakers = set(u.get('speaker', '') for u in new_utterances)
    transcript_data['speaker_count'] = len(speakers)

    return {
        'utterances_before': len(utterances),
        'utterances_after': len(new_utterances),
        'splits_made': splits_made,
    }
