"""Fixed UTC analytical windows; no implied London/New York civil-time or DST calendar."""

from datetime import UTC, datetime

from trading_ecosystem.features.contracts import BuildConfig
from trading_ecosystem.mt5.client import Record


def temporal(at: datetime, config: BuildConfig) -> Record:
    at = at.astimezone(UTC)
    minute = at.hour * 60 + at.minute
    matches = [
        w
        for w in config.session_windows
        if (minute - w.start_minute_utc) % 1440 < (w.end_minute_utc - w.start_minute_utc) % 1440
    ]
    return dict(
        hour_utc=at.hour,
        minute_utc=at.minute,
        day_of_week=at.weekday(),
        session="+".join(sorted(w.name for w in matches)) if matches else None,
        minutes_since_session_open=(minute - matches[0].start_minute_utc) % 1440
        if len(matches) == 1
        else None,
    )
