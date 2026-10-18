"""Shared meter-reading logic: consumption, rolling average and anomaly flags.

Readings are cumulative, so a value below the previous one usually means a
transcription error. Suspicious readings are always stored — they are flagged
for the administrator to review rather than rejected.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.meter import Meter, MeterReading

HIGH_CONSUMPTION_RATIO = 1.25
AVERAGE_WINDOW = 6


def recent_average(db: Session, meter_id, window: int = AVERAGE_WINDOW) -> float:
    """Mean consumption over the most recent readings with usage."""
    rows = (
        db.query(MeterReading.consumption_m3)
        .filter(MeterReading.meter_id == meter_id)
        .order_by(MeterReading.reading_date.desc())
        .limit(window)
        .all()
    )
    values = [r[0] for r in rows if r[0] and r[0] > 0]
    if not values:
        return 0.0
    return sum(values) / len(values)


def flag_reading(reading_value: float, previous_value: float, average: float) -> str | None:
    """Return a human-readable reason the reading looks wrong, or None."""
    if reading_value < previous_value:
        return (
            f"Reading {reading_value:g} is below the previous reading "
            f"{previous_value:g} — meters only count up."
        )
    consumption = reading_value - previous_value
    if consumption == 0:
        return "No consumption since the last reading — check the meter was read correctly."
    if average > 0 and consumption > average * HIGH_CONSUMPTION_RATIO:
        pct = round((consumption / average - 1) * 100)
        return (
            f"Consumption {consumption:g} m³ is {pct}% above this household's "
            f"average of {average:.1f} m³ — possible leak or misread."
        )
    return None


def record_reading(
    db: Session,
    meter: Meter,
    *,
    reading_value: float,
    reading_date: datetime,
    notes: str | None = None,
    is_estimated: bool = False,
    recorded_by: str | None = None,
    photo_url: str | None = None,
    client_id: str | None = None,
) -> MeterReading:
    """Persist a reading, flagging anomalies and refreshing meter aggregates."""
    previous_value = meter.last_reading_value
    average = recent_average(db, meter.id)
    consumption = max(0.0, reading_value - previous_value)

    reading = MeterReading(
        reading_value=reading_value,
        previous_value=previous_value,
        consumption_m3=consumption,
        reading_date=reading_date,
        photo_url=photo_url,
        notes=notes,
        is_estimated=is_estimated,
        recorded_by=recorded_by,
        flag_reason=flag_reading(reading_value, previous_value, average),
        client_id=client_id,
        meter_id=meter.id,
    )
    db.add(reading)
    db.flush()

    # A backwards reading is kept for the record but must not rewind the meter.
    if reading_value >= meter.last_reading_value:
        meter.last_reading_value = reading_value
        meter.last_reading_date = reading_date
    meter.avg_consumption_m3 = recent_average(db, meter.id)
    return reading


def expected_consumption(
    db: Session, meter: Meter, now: datetime
) -> tuple[float | None, int | None, float | None]:
    """(average m³ per day, days since last reading, expected m³ now) from recent history."""
    readings = (
        db.query(MeterReading)
        .filter(MeterReading.meter_id == meter.id)
        .order_by(MeterReading.reading_date.desc())
        .limit(6)
        .all()
    )
    last_date = meter.last_reading_date
    if last_date is None and readings:
        last_date = readings[0].reading_date
    days = None
    if last_date is not None:
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)
        days = max(0, (now - last_date).days)
    if len(readings) < 2:
        return None, days, None
    newest, oldest = readings[0].reading_date, readings[-1].reading_date
    span_days = (newest - oldest).total_seconds() / 86400
    if span_days <= 0:
        return None, days, None
    used = sum(r.consumption_m3 for r in readings[:-1])
    daily = round(used / span_days, 3)
    expected = round(daily * days, 1) if days is not None else None
    return daily, days, expected
