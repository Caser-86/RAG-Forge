"""API 请求级安全控制：有界内存的滑动窗口限流。"""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from math import ceil
from threading import Lock
from time import monotonic


class RateLimiter:
    """进程内限流器；生产多进程部署应改用共享存储实现。"""

    def __init__(
        self,
        window_seconds: float = 60.0,
        max_keys: int = 4096,
        clock: Callable[[], float] = monotonic,
    ):
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if max_keys <= 0:
            raise ValueError("max_keys must be positive")
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str, limit: int) -> int:
        """记录一次请求；允许时返回 0，否则返回建议等待秒数。"""
        if limit <= 0:
            raise ValueError("limit must be positive")
        now = self._clock()
        with self._lock:
            events = self._events.get(key)
            if events is None:
                self._purge_expired(now)
                if len(self._events) >= self._max_keys:
                    self._events.pop(next(iter(self._events)), None)
                events = deque()
                self._events[key] = events
            self._discard_expired(events, now)
            if len(events) >= limit:
                return max(1, ceil(self._window_seconds - (now - events[0])))
            events.append(now)
            return 0

    def _purge_expired(self, now: float) -> None:
        for key, events in list(self._events.items()):
            self._discard_expired(events, now)
            if not events:
                self._events.pop(key, None)

    def _discard_expired(self, events: deque[float], now: float) -> None:
        while events and now - events[0] >= self._window_seconds:
            events.popleft()
