"""Pure five-box SRS and Bangkok calendar oracle (ADR-0005 C013-02)."""

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

Rating = Literal["AGAIN", "HARD", "GOOD", "EASY"]
PRODUCT_TIMEZONE = "Asia/Bangkok"
_INTERVALS = (1, 3, 7, 14, 30)


def validate_box(box: int) -> None:
    if type(box) is not int or not 0 <= box <= 5:
        raise ValueError("Invalid box: expected an integer in 0..5")


def validate_rating(rating: str) -> Rating:
    match rating:
        case "AGAIN" | "HARD" | "GOOD" | "EASY":
            return rating
        case _:
            raise ValueError("Invalid rating: expected AGAIN, HARD, GOOD or EASY")


def require_aware(instant: datetime) -> None:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Expected a timezone-aware instant")


@dataclass(frozen=True)
class Schedule:
    box: int = 0
    due_at: datetime | None = None

    def __post_init__(self) -> None:
        validate_box(self.box)
        if self.box == 0 and self.due_at is not None:
            raise ValueError("NEW must have due_at=None")
        if self.box != 0 and self.due_at is None:
            raise ValueError("Learned cards require due_at")
        if self.due_at is not None:
            require_aware(self.due_at)


def destination_box(current_box: int, rating: str) -> int:
    validate_box(current_box)
    match validate_rating(rating):
        case "AGAIN":
            return 1
        case "HARD":
            return max(1, current_box)
        case "GOOD":
            return min(5, current_box + 1)
        case "EASY":
            return min(5, current_box + 2)


def interval_days(box: int) -> int:
    validate_box(box)
    if box == 0:
        raise ValueError("NEW has no interval")
    return _INTERVALS[box - 1]


def next_due_at(box: int, reviewed_at: datetime) -> datetime | None:
    validate_box(box)
    require_aware(reviewed_at)
    if box == 0:
        return None
    zone = ZoneInfo(PRODUCT_TIMEZONE)
    due_date = reviewed_at.astimezone(zone).date() + timedelta(days=interval_days(box))
    return datetime.combine(due_date, time.min, tzinfo=zone).astimezone(UTC)


def transition(current_box: int, rating: str, reviewed_at: datetime) -> Schedule:
    box = destination_box(current_box, rating)
    return Schedule(box, next_due_at(box, reviewed_at))
