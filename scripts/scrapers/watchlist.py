"""Watchlist manager for Colorado Legislature monitoring."""
import json
from datetime import datetime
from pathlib import Path

from .search import search_all, filter_results_since


class WatchlistManager:
    """Manages topic watchlists for monitoring legislature data."""

    def __init__(self, watchlists_dir=None):
        """
        Initialize the watchlist manager.

        Args:
            watchlists_dir: Directory containing watchlist JSON files.
                           Defaults to ~/.claude/skills/colorado-legislature/data/watchlists
        """
        if watchlists_dir is None:
            watchlists_dir = Path.home() / ".claude" / "skills" / "colorado-legislature" / "data" / "watchlists"

        self.watchlists_dir = Path(watchlists_dir)
        self.watchlists_dir.mkdir(parents=True, exist_ok=True)

    def _get_watchlist_path(self, name):
        """Get the file path for a watchlist by name."""
        return self.watchlists_dir / f"watchlist_{name}.json"

    def list_watchlists(self):
        """
        List all available watchlists.

        Returns:
            list: List of watchlist summary dicts with keys:
                - name: str
                - display_name: str
                - keywords: list
                - last_checked: str or None
        """
        watchlists = []

        for path in self.watchlists_dir.glob("watchlist_*.json"):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    watchlists.append({
                        'name': data.get('name'),
                        'display_name': data.get('display_name', data.get('name')),
                        'keywords': data.get('keywords', []),
                        'departments': data.get('departments', []),
                        'last_checked': data.get('last_checked')
                    })
            except (json.JSONDecodeError, IOError):
                continue

        # Sort by name
        watchlists.sort(key=lambda x: x.get('name', ''))
        return watchlists

    def get_watchlist(self, name):
        """
        Get a watchlist by name.

        Args:
            name: Watchlist name (e.g., 'snap')

        Returns:
            dict: Watchlist configuration or None if not found
        """
        path = self._get_watchlist_path(name)

        if not path.exists():
            return None

        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def create_watchlist(self, name, keywords, departments=None, display_name=None, match_mode="word_boundary", exact=False):
        """
        Create a new watchlist.

        Args:
            name: Watchlist identifier (lowercase, no spaces)
            keywords: List of keywords to search for
            departments: Optional list of departments to filter
            display_name: Human-readable name (defaults to name)
            match_mode: "word_boundary" or "substring"

        Returns:
            dict: Created watchlist configuration

        Raises:
            ValueError: If watchlist already exists or invalid name
        """
        # Validate name
        if not name or not name.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f"Invalid watchlist name: {name}. Use only letters, numbers, underscores, and hyphens.")

        name = name.lower()

        path = self._get_watchlist_path(name)
        if path.exists():
            raise ValueError(f"Watchlist '{name}' already exists. Use delete first to replace it.")

        if not keywords:
            raise ValueError("Keywords list cannot be empty.")

        watchlist = {
            'name': name,
            'display_name': display_name or name.replace('_', ' ').replace('-', ' ').title(),
            'keywords': keywords if isinstance(keywords, list) else [keywords],
            'departments': departments or [],
            'match_mode': match_mode,
            'exact': exact,
            'last_checked': None,
            'created_at': datetime.now().isoformat()
        }

        try:
            with open(path, 'w') as f:
                json.dump(watchlist, f, indent=2)
        except IOError as e:
            raise ValueError(f"Could not save watchlist: {e}")

        return watchlist

    def delete_watchlist(self, name):
        """
        Delete a watchlist.

        Args:
            name: Watchlist name

        Returns:
            bool: True if deleted, False if not found
        """
        path = self._get_watchlist_path(name)

        if not path.exists():
            return False

        try:
            path.unlink()
            return True
        except IOError:
            return False

    def run_watchlist(self, name, cache_manager=None, new_only=False):
        """
        Run a watchlist query and return results.

        Args:
            name: Watchlist name
            cache_manager: CacheManager for accessing cached data
            new_only: If True, only return results since last check

        Returns:
            dict: Results with structure:
                {
                    'watchlist': dict (watchlist config),
                    'results': dict (from search_all),
                    'new_only': bool,
                    'run_at': str (ISO timestamp)
                }

        Raises:
            ValueError: If watchlist not found
        """
        watchlist = self.get_watchlist(name)
        if not watchlist:
            raise ValueError(f"Watchlist '{name}' not found.")

        # Build query from keywords
        keywords = watchlist.get('keywords', [])
        departments = watchlist.get('departments', [])

        # Search across all types
        # If departments specified, filter to those departments
        dept_filter = departments[0] if len(departments) == 1 else None

        query = ' '.join(keywords)
        if watchlist.get('exact', False):
            query = f'"{query}"'

        results = search_all(
            query=query,
            cache_manager=cache_manager,
            department=dept_filter
        )

        # Filter to new items if requested
        if new_only and watchlist.get('last_checked'):
            results = filter_results_since(results, watchlist['last_checked'])

        return {
            'watchlist': watchlist,
            'results': results,
            'new_only': new_only,
            'run_at': datetime.now().isoformat()
        }

    def update_last_checked(self, name, timestamp=None):
        """
        Update the last_checked timestamp for a watchlist.

        Args:
            name: Watchlist name
            timestamp: ISO timestamp string. Defaults to now.

        Returns:
            bool: True if updated, False if watchlist not found
        """
        watchlist = self.get_watchlist(name)
        if not watchlist:
            return False

        if timestamp is None:
            timestamp = datetime.now().isoformat()

        watchlist['last_checked'] = timestamp

        path = self._get_watchlist_path(name)
        try:
            with open(path, 'w') as f:
                json.dump(watchlist, f, indent=2)
            return True
        except IOError:
            return False
