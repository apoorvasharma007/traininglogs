"""Ids for new rows: UUID version 7 (RFC 9562). The first 48 bits are the time in milliseconds,
so rows made together sit together in an index instead of scattering, which keeps inserts fast on
big tables; the rest is random, so ids are unique without asking the database. Postgres 17 can't
make these, so the code does."""
from __future__ import annotations

import os
import time
import uuid


def new_id() -> str:
    ms = time.time_ns() // 1_000_000
    value = (ms & ((1 << 48) - 1)) << 80 | int.from_bytes(os.urandom(10), "big") & ((1 << 80) - 1)
    value = value & ~(0xF << 76) | (0x7 << 76)  # version 7
    value = value & ~(0x3 << 62) | (0x2 << 62)  # RFC 4122 variant
    return str(uuid.UUID(int=value))
