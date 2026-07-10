import datetime

import pytest

from app.core.time import load_timezone
from app.domains.reservations.rules import (
    ReservationRuleError,
    build_period,
    daily_slots,
)

SEOUL = load_timezone("Asia/Seoul")
NOW = datetime.datetime(2026, 7, 8, 0, 0, tzinfo=datetime.UTC)


def build(start_at: datetime.datetime, duration_hours: int = 1):
    return build_period(
        start_at=start_at,
        duration_hours=duration_hours,
        opens_at=datetime.time(9),
        closes_at=datetime.time(0),
        timezone=SEOUL,
        now=NOW,
    )


def test_build_period_creates_hourly_utc_slots() -> None:
    period = build(datetime.datetime(2026, 7, 9, 10, 0, tzinfo=SEOUL), 3)

    assert period.start_at == datetime.datetime(2026, 7, 9, 1, 0, tzinfo=datetime.UTC)
    assert period.end_at == datetime.datetime(2026, 7, 9, 4, 0, tzinfo=datetime.UTC)
    assert len(period.slot_starts) == 3


@pytest.mark.parametrize(
    ("start_at", "duration", "code"),
    [
        (datetime.datetime(2026, 7, 9, 10), 1, "timezone_required"),
        (
            datetime.datetime(2026, 7, 9, 10, 30, tzinfo=SEOUL),
            1,
            "reservation_start_not_aligned",
        ),
        (
            datetime.datetime(2026, 7, 9, 10, tzinfo=SEOUL),
            5,
            "invalid_reservation_duration",
        ),
        (
            datetime.datetime(2026, 7, 8, 9, tzinfo=SEOUL),
            1,
            "reservation_too_soon",
        ),
        (
            datetime.datetime(2026, 7, 9, 23, tzinfo=SEOUL),
            2,
            "outside_business_hours",
        ),
        (
            datetime.datetime(2026, 8, 8, 10, tzinfo=SEOUL),
            1,
            "reservation_date_too_far",
        ),
    ],
)
def test_build_period_rejects_invalid_periods(
    start_at: datetime.datetime,
    duration: int,
    code: str,
) -> None:
    with pytest.raises(ReservationRuleError) as captured:
        build(start_at, duration)

    assert captured.value.code == code


def test_daily_slots_cover_branch_business_hours() -> None:
    slots = daily_slots(
        target_date=datetime.date(2026, 7, 9),
        opens_at=datetime.time(9),
        closes_at=datetime.time(0),
        timezone=SEOUL,
        now=NOW,
    )

    assert len(slots) == 15
    assert slots[0] == datetime.datetime(2026, 7, 9, 0, tzinfo=datetime.UTC)
    assert slots[-1] == datetime.datetime(2026, 7, 9, 14, tzinfo=datetime.UTC)
