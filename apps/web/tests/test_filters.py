from datetime import UTC, datetime, timedelta

import pytest

from posts_web.filters import avatar_hue, full_datetime, timeago

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (timedelta(seconds=10), "agora"),
        (timedelta(minutes=5), "há 5 min"),
        (timedelta(hours=3), "há 3 h"),
        (timedelta(days=1, hours=2), "ontem"),
        (timedelta(days=4), "há 4 dias"),
        (timedelta(days=30), "15/10/2026"),
    ],
)
def test_timeago(delta, expected):
    assert timeago(NOW - delta, now=NOW) == expected


def test_naive_datetimes_are_treated_as_utc():
    # O SQLite devolve datas sem fuso horário.
    naive = datetime(2026, 11, 14, 11, 55)

    assert timeago(naive, now=NOW) == "há 5 min"
    assert full_datetime(naive) == "14/11/2026 11:55"


def test_avatar_hue_is_stable_and_case_insensitive():
    assert avatar_hue("Alice") == avatar_hue("alice")
    assert 0 <= avatar_hue("bob") < 360
