"""进程内短期 Trace 存储：有上限、有 TTL、可并发访问。"""
from __future__ import annotations

import time
from collections import OrderedDict
from threading import RLock
from typing import Any


class TraceStore:
    def __init__(
        self,
        *,
        max_entries: int = 100,
        ttl_seconds: float = 3600,
        max_item_chars: int = 4000,
    ) -> None:
        self.max_entries = max(1, int(max_entries))
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self.max_item_chars = max(1, int(max_item_chars))
        self._items: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = RLock()

    def put(self, trace_id: str | dict[str, Any], record: dict[str, Any] | None = None) -> None:
        if record is None:
            if not isinstance(trace_id, dict):
                raise TypeError("record is required when trace_id is not a mapping")
            record = trace_id
            trace_id = str(record.get("trace_id", ""))
        if not trace_id:
            raise ValueError("trace_id must not be empty")
        payload = self._truncate(record)
        with self._lock:
            self._cleanup_locked()
            self._items.pop(str(trace_id), None)
            self._items[str(trace_id)] = (time.time(), payload)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def get(self, trace_id: str) -> dict[str, Any] | None:
        if not trace_id:
            return None
        with self._lock:
            self._cleanup_locked()
            item = self._items.get(trace_id)
            if item is None:
                return None
            return self._copy_record(item[1])

    def cleanup(self) -> None:
        with self._lock:
            self._cleanup_locked()

    def __len__(self) -> int:
        self.cleanup()
        with self._lock:
            return len(self._items)

    def _cleanup_locked(self) -> None:
        if self.ttl_seconds <= 0:
            self._items.clear()
            return
        now = time.time()
        expired = [
            trace_id
            for trace_id, (created_at, _) in self._items.items()
            if now - created_at >= self.ttl_seconds
        ]
        for trace_id in expired:
            self._items.pop(trace_id, None)

    def _truncate(self, value: Any) -> Any:
        if isinstance(value, str):
            if len(value) <= self.max_item_chars:
                return value
            return value[: self.max_item_chars]
        if isinstance(value, dict):
            return {str(key): self._truncate(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._truncate(item) for item in value]
        if isinstance(value, tuple):
            return [self._truncate(item) for item in value]
        return value

    @staticmethod
    def _copy_record(record: dict[str, Any]) -> dict[str, Any]:
        if isinstance(record, dict):
            return {key: TraceStore._copy_record(value) if isinstance(value, dict)
                    else [TraceStore._copy_record(item) if isinstance(item, dict) else item for item in value]
                    if isinstance(value, list) else value for key, value in record.items()}
        return record
