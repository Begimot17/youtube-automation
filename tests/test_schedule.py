from datetime import time

import pytest

from src.utils.schedule import in_window, is_within_schedule, parse_window


def test_parse_window():
    assert parse_window("08:00-20:30") == (time(8, 0), time(20, 30))
    assert parse_window(" 8:05 - 9:10 ") == (time(8, 5), time(9, 10))


@pytest.mark.parametrize("bad", ["", "08:00", "25:00-26:00", "a-b", "08:00-09:00-10:00"])
def test_parse_window_invalid(bad):
    with pytest.raises(ValueError):
        parse_window(bad)


def test_in_window_plain_and_edges():
    assert in_window(time(8, 0), time(8, 0), time(20, 0))
    assert in_window(time(20, 0), time(8, 0), time(20, 0))
    assert not in_window(time(7, 59), time(8, 0), time(20, 0))


def test_in_window_wraps_midnight():
    start, end = time(22, 0), time(2, 0)
    assert in_window(time(23, 30), start, end)
    assert in_window(time(1, 0), start, end)
    assert not in_window(time(12, 0), start, end)


def test_empty_schedule_allows_any_time():
    assert is_within_schedule(None, time(3, 0))
    assert is_within_schedule([], time(3, 0))


def test_schedule_multiple_windows():
    sched = ["08:00-10:00", "18:00-20:00"]
    assert is_within_schedule(sched, time(9, 0))
    assert is_within_schedule(sched, time(19, 0))
    assert not is_within_schedule(sched, time(14, 0))


def test_schedule_overnight_window():
    assert is_within_schedule(["22:00-02:00"], time(0, 30))
    assert not is_within_schedule(["22:00-02:00"], time(10, 0))


def test_schedule_json_string_and_bare_string():
    assert is_within_schedule('["08:00-20:00"]', time(9, 0))
    assert not is_within_schedule('["08:00-20:00"]', time(21, 0))
    assert not is_within_schedule("08:00-20:00", time(21, 0))


def test_schedule_all_invalid_does_not_block():
    assert is_within_schedule(["garbage"], time(3, 0))
    assert is_within_schedule("not json", time(3, 0))


def test_schedule_skips_invalid_but_uses_valid():
    assert not is_within_schedule(["garbage", "08:00-09:00"], time(12, 0))
    assert is_within_schedule(["garbage", "08:00-09:00"], time(8, 30))
