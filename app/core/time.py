import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def load_timezone(name: str) -> datetime.tzinfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name == "Asia/Seoul":
            return datetime.timezone(datetime.timedelta(hours=9), name="Asia/Seoul")
        raise
