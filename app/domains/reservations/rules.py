import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class ReservationRuleError(Exception):
    code: str
    message: str


@dataclass(frozen=True)
class ReservationPeriod:
    start_at: datetime.datetime
    end_at: datetime.datetime
    slot_starts: tuple[datetime.datetime, ...]


def require_aware(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ReservationRuleError(
            code="timezone_required",
            message="예약 시각에는 시간대 정보가 필요합니다.",
        )
    return value


def operating_period(
    target_date: datetime.date,
    opens_at: datetime.time,
    closes_at: datetime.time,
    timezone: datetime.tzinfo,
) -> tuple[datetime.datetime, datetime.datetime]:
    opens = datetime.datetime.combine(target_date, opens_at, timezone)
    closes = datetime.datetime.combine(target_date, closes_at, timezone)
    if closes <= opens:
        closes += datetime.timedelta(days=1)
    return opens, closes


def validate_target_date(
    target_date: datetime.date,
    timezone: datetime.tzinfo,
    *,
    now: datetime.datetime | None = None,
) -> None:
    local_now = (now or datetime.datetime.now(datetime.UTC)).astimezone(timezone)
    if target_date < local_now.date():
        raise ReservationRuleError(
            code="reservation_date_in_past",
            message="지난 날짜는 조회하거나 예약할 수 없습니다.",
        )
    if target_date > local_now.date() + datetime.timedelta(days=30):
        raise ReservationRuleError(
            code="reservation_date_too_far",
            message="예약은 오늘부터 30일 이내에서만 가능합니다.",
        )


def build_period(
    *,
    start_at: datetime.datetime,
    duration_hours: int,
    opens_at: datetime.time,
    closes_at: datetime.time,
    timezone: datetime.tzinfo,
    now: datetime.datetime | None = None,
) -> ReservationPeriod:
    aware_start = require_aware(start_at)
    local_start = aware_start.astimezone(timezone)
    utc_now = now or datetime.datetime.now(datetime.UTC)
    require_aware(utc_now)

    if local_start.minute != 0 or local_start.second != 0 or local_start.microsecond != 0:
        raise ReservationRuleError(
            code="reservation_start_not_aligned",
            message="예약은 정각에 시작해야 합니다.",
        )
    if duration_hours < 1 or duration_hours > 4:
        raise ReservationRuleError(
            code="invalid_reservation_duration",
            message="예약 시간은 1시간 이상 4시간 이하여야 합니다.",
        )

    validate_target_date(local_start.date(), timezone, now=utc_now)
    if aware_start.astimezone(datetime.UTC) < utc_now.astimezone(datetime.UTC) + datetime.timedelta(
        hours=1
    ):
        raise ReservationRuleError(
            code="reservation_too_soon",
            message="현재 시각으로부터 최소 1시간 이후를 예약해야 합니다.",
        )

    business_start, business_end = operating_period(
        local_start.date(),
        opens_at,
        closes_at,
        timezone,
    )
    local_end = local_start + datetime.timedelta(hours=duration_hours)
    if local_start < business_start or local_end > business_end:
        raise ReservationRuleError(
            code="outside_business_hours",
            message="지점 영업시간을 벗어난 예약입니다.",
        )

    start_utc = local_start.astimezone(datetime.UTC)
    end_utc = local_end.astimezone(datetime.UTC)
    slots = tuple(start_utc + datetime.timedelta(hours=offset) for offset in range(duration_hours))
    return ReservationPeriod(start_at=start_utc, end_at=end_utc, slot_starts=slots)


def daily_slots(
    *,
    target_date: datetime.date,
    opens_at: datetime.time,
    closes_at: datetime.time,
    timezone: datetime.tzinfo,
    now: datetime.datetime | None = None,
) -> tuple[datetime.datetime, ...]:
    validate_target_date(target_date, timezone, now=now)
    business_start, business_end = operating_period(
        target_date,
        opens_at,
        closes_at,
        timezone,
    )
    slot_count = int((business_end - business_start).total_seconds() // 3600)
    return tuple(
        (business_start + datetime.timedelta(hours=offset)).astimezone(datetime.UTC)
        for offset in range(slot_count)
    )
