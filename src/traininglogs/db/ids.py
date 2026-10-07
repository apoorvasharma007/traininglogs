"""Ids for new rows: UUID version 7 (RFC 9562). The first 48 bits are the time in milliseconds,
so rows made together sit together in an index instead of scattering, which keeps inserts fast on
big tables; the rest is random, so ids are unique without asking the database. Within one
millisecond the next 12 bits count up (the RFC's counter method), so ids made by this process
always sort in the order they were made. Postgres 17 can't make these, so the code does."""
from __future__ import annotations

import os
import threading
import time
import uuid

_lock = threading.Lock()
_last_ms = 0
_counter = 0


def new_id() -> str:
    """Generate a unique UUID v7 ID with timestamp and counter for sequential inserts."""
    global _last_ms, _counter
    with _lock:
        ms = max(time.time_ns() // 1_000_000, _last_ms)
        if ms == _last_ms:
            _counter += 1
            if _counter > 0xFFF:  # 4,096 ids in one millisecond: borrow the next one
                ms, _counter = ms + 1, 0
        else:
            _counter = 0
        _last_ms = ms
        counter = _counter
    random = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    value = (ms << 80) | (0x7 << 76) | (counter << 64) | (0x2 << 62) | random
    return str(uuid.UUID(int=value))
