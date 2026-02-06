"""Session year helper for Colorado Legislature."""
from datetime import datetime


def get_current_session():
    """
    Returns the current legislative session code (e.g., "2026A").

    Colorado Legislature operates on year-long sessions with suffixes:
    - A: Regular session (Jan-May typically)
    - B: Second session (rare, for special circumstances)

    Returns:
        str: Session code like "2026A"
    """
    current_year = datetime.now().year
    # For simplicity, we'll use "A" suffix (regular session)
    # In production, you might query the website to detect the active session
    return f"{current_year}A"


def parse_session_code(session_code):
    """
    Parse a session code into year and suffix.

    Args:
        session_code: String like "2026A"

    Returns:
        tuple: (year: int, suffix: str)
    """
    if not session_code:
        return None, None

    year_str = session_code[:-1]
    suffix = session_code[-1]

    try:
        year = int(year_str)
        return year, suffix
    except (ValueError, IndexError):
        return None, None


def is_historical_session(session_code):
    """
    Check if a session code refers to a historical (past) session.

    Args:
        session_code: String like "2026A"

    Returns:
        bool: True if historical, False if current or future
    """
    current = get_current_session()
    year, _ = parse_session_code(session_code)
    current_year, _ = parse_session_code(current)

    if year is None or current_year is None:
        return False

    return year < current_year
