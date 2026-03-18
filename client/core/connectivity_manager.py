"""
Connectivity Manager - Server Reachability Check

Lightweight HEAD-request ping to detect whether the API server is reachable.
Result is cached per session so the same check isn't repeated on every job.
"""

import threading
from typing import Optional


class ConnectivityManager:
    """
    Singleton that checks and caches server reachability.

    Design:
    - Uses a HEAD request (fastest possible, no body) to the API base URL.
    - Caches the result for the session lifetime (re-checked only on demand).
    - Non-blocking: check() runs on a background thread if async=True.
    - Emits no Qt signals — purely a data utility.
    """

    _instance: Optional["ConnectivityManager"] = None

    # Cache
    _is_online: Optional[bool] = None   # None = unknown, True/False = checked
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "ConnectivityManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if ConnectivityManager._instance is not None:
            raise Exception("ConnectivityManager is a singleton. Use instance().")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, timeout: float = 4.0) -> bool:
        """
        Synchronously check if the API server is reachable.

        Uses cached result if already checked this session.
        Cache can be busted by calling reset().

        Args:
            timeout: Request timeout in seconds (default 4s)

        Returns:
            True  — server reachable
            False — server unreachable (no internet OR server down)
        """
        with self._lock:
            if self._is_online is not None:
                return self._is_online
            result = self._ping(timeout)
            self._is_online = result
            return result

    def check_async(self, callback, timeout: float = 4.0):
        """
        Non-blocking version. Calls callback(is_online: bool) on a daemon thread.

        Args:
            callback: callable(bool) — receives True/False
            timeout: ping timeout in seconds
        """
        def _worker():
            result = self.check(timeout)
            callback(result)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def reset(self):
        """Bust the cache so the next check() performs a fresh ping."""
        with self._lock:
            self._is_online = None

    @property
    def is_online(self) -> Optional[bool]:
        """Return the cached result (None if not checked yet)."""
        return self._is_online

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _ping(self, timeout: float) -> bool:
        """
        HEAD request to the API server root.

        HEAD is used because:
        - No response body → minimal bandwidth
        - Server still processes the route → confirms real connectivity
        - Faster than GET for the same purpose
        """
        try:
            import requests
            from client.config.config import API_BASE_URL
            resp = requests.head(API_BASE_URL, timeout=timeout, allow_redirects=True)
            # Any HTTP response (even 404/500) means the server/internet is there
            online = resp.status_code < 600
            print(f"[ConnectivityManager] Ping {API_BASE_URL} → HTTP {resp.status_code} ({'online' if online else 'offline'})")
            return online
        except Exception as e:
            print(f"[ConnectivityManager] Ping failed ({type(e).__name__}) → offline")
            return False
