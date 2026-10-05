import time
import uuid

from traininglogs.db.ids import new_id


def test_is_a_version_7_uuid() -> None:
    u = uuid.UUID(new_id())
    assert u.version == 7
    assert u.variant == uuid.RFC_4122


def test_starts_with_the_time() -> None:
    before = time.time_ns() // 1_000_000
    ms = uuid.UUID(new_id()).int >> 80
    assert before <= ms <= time.time_ns() // 1_000_000


def test_later_ids_sort_after_earlier_ones() -> None:
    first = new_id()
    time.sleep(0.002)
    assert new_id() > first


def test_unique() -> None:
    assert len({new_id() for _ in range(10_000)}) == 10_000


def test_ids_made_in_the_same_millisecond_keep_their_order() -> None:
    ids = [new_id() for _ in range(5_000)]
    assert ids == sorted(ids)
