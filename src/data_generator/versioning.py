"""attribute change history for master data - so scd type 2 has work to do.

tek snapshot alsaydım scd2'nin takip edecek hiçbir şeyi kalmazdı, o yüzden her
entity için tarihli bir değişim listesi tutuyorum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterator

@dataclass
class Versioned:
    """one master-data entity and its attribute history"""

    key: str
    created_on: date
    base: dict[str, Any]
    changes: list[tuple[date, dict[str, Any]]] = field(default_factory=list)

    retired_on: date | None = None

    def add_change(self, when: date, **attributes: Any) -> None:
        """record an attribute change. changes are kept in date order"""
        if when < self.created_on:
            raise ValueError(f"{self.key}: change dated before creation")
        self.changes.append((when, attributes))
        self.changes.sort(key=lambda c: c[0])

    def exists_at(self, when: date) -> bool:
        return self.created_on <= when

    def state_at(self, when: date) -> dict[str, Any] | None:
        """full attribute state as of `when`, or none if not yet created"""
        if not self.exists_at(when):
            return None

        state = dict(self.base)
        for effective, attributes in self.changes:
            if effective > when:
                break
            state.update(attributes)

        if self.retired_on is not None and when >= self.retired_on:
            state["is_active"] = 0

        return state

    def last_modified_at(self, when: date) -> date | None:
        """date of the most recent change on or before `when`"""
        if not self.exists_at(when):
            return None

        latest = self.created_on
        for effective, _ in self.changes:
            if effective > when:
                break
            latest = effective

        if self.retired_on is not None and self.retired_on <= when:
            latest = max(latest, self.retired_on)

        return latest

def month_starts(start: date, end: date) -> list[date]:
    """first of every month in the range, plus `start` itself if it is not one"""
    dates: list[date] = []
    if start.day != 1:
        dates.append(start)

    year, month = start.year, start.month
    if start.day != 1:
        month += 1
        if month > 12:
            year, month = year + 1, 1

    while date(year, month, 1) <= end:
        dates.append(date(year, month, 1))
        month += 1
        if month > 12:
            year, month = year + 1, 1

    return dates

def full_snapshots(
    entities: list[Versioned],
    snapshot_dates: list[date],
    *,
    last_modified_field: str = "last_modified_ts",
) -> Iterator[tuple[date, list[dict[str, Any]]]]:
    """every entity that exists, at every snapshot date"""
    for snapshot_date in snapshot_dates:
        rows: list[dict[str, Any]] = []
        for entity in entities:
            state = entity.state_at(snapshot_date)
            if state is None:
                continue
            row = dict(state)
            row[last_modified_field] = entity.last_modified_at(snapshot_date).isoformat()
            rows.append(row)
        if rows:
            yield snapshot_date, rows

def incremental_extracts(
    entities: list[Versioned],
    snapshot_dates: list[date],
    *,
    last_modified_field: str = "last_modified_ts",
) -> Iterator[tuple[date, list[dict[str, Any]]]]:
    """only rows created or changed since the previous extract"""
    previous: date | None = None

    for snapshot_date in snapshot_dates:
        rows: list[dict[str, Any]] = []
        for entity in entities:
            state = entity.state_at(snapshot_date)
            if state is None:
                continue

            modified = entity.last_modified_at(snapshot_date)
            if previous is not None and modified <= previous:
                continue

            row = dict(state)
            row[last_modified_field] = modified.isoformat()
            rows.append(row)

        previous = snapshot_date
        if rows:
            yield snapshot_date, rows

def spread_changes(
    rng,
    start: date,
    end: date,
    count: int,
    *,
    min_gap_days: int = 30,
) -> list[date]:
    """`count` change dates in a range, never two closer than `min_gap_days`"""
    if end <= start or count <= 0:
        return []

    span = (end - start).days
    if span < min_gap_days:
        return []

    picked: list[date] = []
    for _ in range(count * 6):
        if len(picked) == count:
            break
        candidate = start + timedelta(days=rng.randint(1, span))
        if all(abs((candidate - existing).days) >= min_gap_days for existing in picked):
            picked.append(candidate)

    return sorted(picked)
