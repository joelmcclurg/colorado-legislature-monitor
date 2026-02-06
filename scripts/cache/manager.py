"""Cache manager for Colorado Legislature data."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path


# TTL constants (in hours)
class CacheTTL:
    """Cache time-to-live constants."""
    # Schedules
    SCHEDULE_CURRENT = 0  # Always fresh for current week
    SCHEDULE_HISTORICAL = None  # Never expire

    # Recordings
    RECORDINGS_CURRENT = 1  # 1 hour for current recordings
    RECORDINGS_HISTORICAL = None  # Permanent for historical

    # Documents
    DOCUMENTS = 6  # 6 hours for budget documents


class CacheManager:
    """Manages caching of fetched data with TTL support."""

    def __init__(self, base_dir=None):
        """
        Initialize cache manager.

        Args:
            base_dir: Base directory for cache storage.
                     Defaults to ~/.claude/skills/colorado-legislature/data
        """
        if base_dir is None:
            base_dir = Path.home() / ".claude" / "skills" / "colorado-legislature" / "data"

        self.base_dir = Path(base_dir)
        self.metadata_file = self.base_dir / "metadata.json"

        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Load or initialize metadata
        self.metadata = self._load_metadata()

    def get_watchlists_dir(self):
        """
        Get the directory path for watchlist storage.

        Returns:
            Path: Path to watchlists directory
        """
        watchlists_dir = self.base_dir / "watchlists"
        watchlists_dir.mkdir(parents=True, exist_ok=True)
        return watchlists_dir

    def _load_metadata(self):
        """Load cache metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_metadata(self):
        """Save cache metadata to disk, merging with any concurrent changes."""
        try:
            # Reload from disk to pick up writes from parallel processes
            if self.metadata_file.exists():
                try:
                    with open(self.metadata_file, 'r') as f:
                        disk_metadata = json.load(f)
                    # Merge: our in-memory entries take precedence, but keep
                    # entries written by other processes that we don't have
                    disk_metadata.update(self.metadata)
                    self.metadata = disk_metadata
                except (json.JSONDecodeError, IOError):
                    pass
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save cache metadata: {e}")

    def get(self, key, max_age_hours=24):
        """
        Retrieve cached data if it exists and is fresh.

        Args:
            key: Cache key (e.g., "jbc_schedule_week_5")
            max_age_hours: Maximum age in hours. None = never expire

        Returns:
            Cached data if fresh, None if stale or missing
        """
        # Check metadata for timestamp
        if key not in self.metadata:
            return None

        cache_info = self.metadata[key]
        timestamp = datetime.fromisoformat(cache_info['timestamp'])

        # Check if expired
        if max_age_hours is not None:
            age = datetime.now() - timestamp
            if age > timedelta(hours=max_age_hours):
                return None

        # Load data file
        data_file = self.base_dir / cache_info['file']
        if not data_file.exists():
            return None

        try:
            with open(data_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def set(self, key, data, subdirectory=None):
        """
        Store data in cache with timestamp.

        Args:
            key: Cache key
            data: Data to cache (must be JSON-serializable)
            subdirectory: Optional subdirectory (e.g., "schedules")
        """
        # Determine file path
        if subdirectory:
            subdir = self.base_dir / subdirectory
            subdir.mkdir(parents=True, exist_ok=True)
            relative_path = f"{subdirectory}/{key}.json"
        else:
            relative_path = f"{key}.json"

        data_file = self.base_dir / relative_path

        # Save data
        try:
            with open(data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save cache data: {e}")
            return

        # Update metadata
        self.metadata[key] = {
            'timestamp': datetime.now().isoformat(),
            'file': relative_path
        }
        self._save_metadata()

    def is_current_week(self, week_number):
        """
        Check if a week number is the current week.

        Args:
            week_number: ISO week number

        Returns:
            bool: True if current week
        """
        current_week = datetime.now().isocalendar()[1]
        return week_number == current_week

    def clear(self, key=None):
        """
        Clear cache entries.

        Args:
            key: Specific key to clear. If None, clears all cache.
        """
        if key is None:
            # Clear all
            self.metadata = {}
            self._save_metadata()
        elif key in self.metadata:
            # Clear specific key
            cache_info = self.metadata[key]
            data_file = self.base_dir / cache_info['file']
            if data_file.exists():
                data_file.unlink()
            del self.metadata[key]
            self._save_metadata()

    def get_recording_cache_ttl(self, week_number=None):
        """
        Get appropriate TTL for recording cache.

        Args:
            week_number: Week number to check. If None, uses current week behavior.

        Returns:
            int or None: TTL in hours (None for permanent cache)
        """
        if week_number is None or self.is_current_week(week_number):
            return CacheTTL.RECORDINGS_CURRENT
        return CacheTTL.RECORDINGS_HISTORICAL

    def get_document_cache_ttl(self):
        """
        Get appropriate TTL for document cache.

        Returns:
            int: TTL in hours
        """
        return CacheTTL.DOCUMENTS

    def get_schedule_cache_ttl(self, week_number):
        """
        Get appropriate TTL for schedule cache.

        Args:
            week_number: Week number to check

        Returns:
            int or None: TTL in hours (None for permanent cache)
        """
        if self.is_current_week(week_number):
            return CacheTTL.SCHEDULE_CURRENT
        return CacheTTL.SCHEDULE_HISTORICAL
