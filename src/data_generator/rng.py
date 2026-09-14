"""randomness with a spine: reproducible, independent, and shaped like a business"""

from __future__ import annotations

import bisect
import hashlib
import random
from collections.abc import Sequence
from datetime import date, timedelta

# hashlib kullanıyorum, python'ın hash() fonksiyonunu değil - hash() string'lerde
# process başına rastgele (PYTHONHASHSEED), yani her çalıştırmada farklı sonuç
# verir. bunu engine_no üretirken hash() kullanıp bulmuştum, veri hiç
# tekrar üretilemiyordu.
def sub_seed(master_seed: int, name: str) -> int:
    """derive a stable child seed from the master seed and a stream name"""
    digest = hashlib.blake2b(
        f"{master_seed}:{name}".encode("utf-8"), digest_size=8
    ).digest()
    return int.from_bytes(digest, "big")

def stream(master_seed: int, name: str) -> random.Random:
    """an independent random stream for one generator module"""
    return random.Random(sub_seed(master_seed, name))

def weighted_choice(rng: random.Random, items: Sequence, weights: Sequence[float]):
    """pick one item with probability proportional to its weight"""
    return rng.choices(items, weights=weights, k=1)[0]

def weighted_sample(
    rng: random.Random, items: Sequence, weights: Sequence[float], k: int
) -> list:
    """pick `k` distinct items with probability proportional to weight"""
    pool = list(items)
    pool_weights = list(weights)
    picked: list = []
    for _ in range(min(k, len(pool))):
        choice = rng.choices(range(len(pool)), weights=pool_weights, k=1)[0]
        picked.append(pool.pop(choice))
        pool_weights.pop(choice)
    return picked

def performance_index(rng: random.Random) -> float:
    """a multiplier describing how well one dealer or salesperson performs"""
    return clamp(rng.lognormvariate(0.0, 0.38), 0.35, 2.80)

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def jitter(rng: random.Random, value: float, pct: float) -> float:
    """vary a value by +/- `pct`, e.g. jitter(rng, 1000, 0.1) -> 900..1100"""
    return value * (1.0 + rng.uniform(-pct, pct))

_WEEKDAY_SALES = (1.00, 1.00, 1.00, 1.02, 1.10, 1.25, 0.15)
_WEEKDAY_SERVICE = (1.10, 1.08, 1.05, 1.05, 1.05, 0.55, 0.05)

class DateSampler:
    """samples dates across a timeline with a realistic demand shape"""

    def __init__(
        self,
        rng: random.Random,
        start: date,
        end: date,
        monthly_weights: Sequence[float],
        *,
        profile: str = "sales",
        annual_growth: float = 0.10,
        holidays: dict[date, float] | None = None,
        tax_change_dates: Sequence[date] = (),
    ) -> None:
        self._rng = rng
        self._start = start
        self._days: list[date] = []
        self._cumulative: list[float] = []

        weekday_weights = _WEEKDAY_SALES if profile == "sales" else _WEEKDAY_SERVICE
        holidays = holidays or {}
        base_year = start.year
        running = 0.0

        current = start
        while current <= end:
            weight = monthly_weights[current.month - 1]
            weight *= weekday_weights[current.weekday()]

            years_elapsed = (current - start).days / 365.25
            weight *= (1.0 + annual_growth) ** years_elapsed

            weight *= holidays.get(current, 1.0)

            weight *= self._tax_event_factor(current, tax_change_dates)

            running += weight
            self._days.append(current)
            self._cumulative.append(running)
            current += timedelta(days=1)

        self._total = running

    @staticmethod
    def _tax_event_factor(day: date, tax_change_dates: Sequence[date]) -> float:
        """pull-forward spike before a tax change, slump after it"""
        factor = 1.0
        for change in tax_change_dates:
            delta = (day - change).days
            if -30 <= delta < 0:

                factor *= 1.0 + 1.4 * (30 + delta) / 30
            elif 0 <= delta <= 45:

                factor *= 0.45 + 0.55 * (delta / 45)
        return factor

    def sample(self) -> date:
        target = self._rng.random() * self._total
        index = bisect.bisect_left(self._cumulative, target)
        return self._days[min(index, len(self._days) - 1)]

    def sample_many(self, k: int) -> list[date]:
        return [self.sample() for _ in range(k)]

    def weight_on(self, day: date) -> float:
        """relative weight of a single day. used for reporting and testing"""
        index = (day - self._start).days
        if not 0 <= index < len(self._cumulative):
            return 0.0
        previous = self._cumulative[index - 1] if index else 0.0
        return self._cumulative[index] - previous

def random_date_between(rng: random.Random, start: date, end: date) -> date:
    """uniform date in a closed interval. for spans where shape does not matter"""
    if end < start:
        start, end = end, start
    return start + timedelta(days=rng.randint(0, (end - start).days))

def business_days_after(start: date, days: int, holidays: dict[date, float]) -> date:
    """advance `days` working days, skipping weekends and public holidays"""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        is_weekend = current.weekday() >= 5
        is_holiday = holidays.get(current, 1.0) < 0.2
        if not is_weekend and not is_holiday:
            remaining -= 1
    return current
