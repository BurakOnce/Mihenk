"""turkish reference data: provinces, plates, public holidays, fx rates"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

@dataclass(frozen=True)
class Province:
    plate_code: str
    name: str
    region: str
    population_m: float

MARMARA = "Marmara"
EGE = "Ege"
AKDENIZ = "Akdeniz"
IC_ANADOLU = "İç Anadolu"
KARADENIZ = "Karadeniz"
DOGU = "Doğu Anadolu"
GUNEYDOGU = "Güneydoğu Anadolu"

_PROVINCE_DATA: tuple[tuple[str, str, str, float], ...] = (
    ("01", "Adana", AKDENIZ, 2.27), ("02", "Adıyaman", GUNEYDOGU, 0.64),
    ("03", "Afyonkarahisar", EGE, 0.75), ("04", "Ağrı", DOGU, 0.51),
    ("05", "Amasya", KARADENIZ, 0.34), ("06", "Ankara", IC_ANADOLU, 5.80),
    ("07", "Antalya", AKDENIZ, 2.69), ("08", "Artvin", KARADENIZ, 0.17),
    ("09", "Aydın", EGE, 1.15), ("10", "Balıkesir", MARMARA, 1.26),
    ("11", "Bilecik", MARMARA, 0.23), ("12", "Bingöl", DOGU, 0.28),
    ("13", "Bitlis", DOGU, 0.35), ("14", "Bolu", KARADENIZ, 0.32),
    ("15", "Burdur", AKDENIZ, 0.27), ("16", "Bursa", MARMARA, 3.24),
    ("17", "Çanakkale", MARMARA, 0.56), ("18", "Çankırı", IC_ANADOLU, 0.20),
    ("19", "Çorum", KARADENIZ, 0.53), ("20", "Denizli", EGE, 1.06),
    ("21", "Diyarbakır", GUNEYDOGU, 1.80), ("22", "Edirne", MARMARA, 0.41),
    ("23", "Elazığ", DOGU, 0.60), ("24", "Erzincan", DOGU, 0.24),
    ("25", "Erzurum", DOGU, 0.75), ("26", "Eskişehir", IC_ANADOLU, 0.92),
    ("27", "Gaziantep", GUNEYDOGU, 2.16), ("28", "Giresun", KARADENIZ, 0.45),
    ("29", "Gümüşhane", KARADENIZ, 0.15), ("30", "Hakkari", DOGU, 0.28),
    ("31", "Hatay", AKDENIZ, 1.69), ("32", "Isparta", AKDENIZ, 0.45),
    ("33", "Mersin", AKDENIZ, 1.94), ("34", "İstanbul", MARMARA, 15.65),
    ("35", "İzmir", EGE, 4.46), ("36", "Kars", DOGU, 0.28),
    ("37", "Kastamonu", KARADENIZ, 0.39), ("38", "Kayseri", IC_ANADOLU, 1.45),
    ("39", "Kırklareli", MARMARA, 0.37), ("40", "Kırşehir", IC_ANADOLU, 0.24),
    ("41", "Kocaeli", MARMARA, 2.08), ("42", "Konya", IC_ANADOLU, 2.31),
    ("43", "Kütahya", EGE, 0.58), ("44", "Malatya", DOGU, 0.81),
    ("45", "Manisa", EGE, 1.47), ("46", "Kahramanmaraş", AKDENIZ, 1.18),
    ("47", "Mardin", GUNEYDOGU, 0.87), ("48", "Muğla", EGE, 1.05),
    ("49", "Muş", DOGU, 0.40), ("50", "Nevşehir", IC_ANADOLU, 0.31),
    ("51", "Niğde", IC_ANADOLU, 0.37), ("52", "Ordu", KARADENIZ, 0.76),
    ("53", "Rize", KARADENIZ, 0.35), ("54", "Sakarya", MARMARA, 1.09),
    ("55", "Samsun", KARADENIZ, 1.37), ("56", "Siirt", GUNEYDOGU, 0.33),
    ("57", "Sinop", KARADENIZ, 0.22), ("58", "Sivas", IC_ANADOLU, 0.64),
    ("59", "Tekirdağ", MARMARA, 1.14), ("60", "Tokat", KARADENIZ, 0.60),
    ("61", "Trabzon", KARADENIZ, 0.82), ("62", "Tunceli", DOGU, 0.09),
    ("63", "Şanlıurfa", GUNEYDOGU, 2.21), ("64", "Uşak", EGE, 0.38),
    ("65", "Van", DOGU, 1.13), ("66", "Yozgat", IC_ANADOLU, 0.42),
    ("67", "Zonguldak", KARADENIZ, 0.58), ("68", "Aksaray", IC_ANADOLU, 0.44),
    ("69", "Bayburt", KARADENIZ, 0.08), ("70", "Karaman", IC_ANADOLU, 0.26),
    ("71", "Kırıkkale", IC_ANADOLU, 0.28), ("72", "Batman", GUNEYDOGU, 0.63),
    ("73", "Şırnak", GUNEYDOGU, 0.57), ("74", "Bartın", KARADENIZ, 0.20),
    ("75", "Ardahan", DOGU, 0.08), ("76", "Iğdır", DOGU, 0.20),
    ("77", "Yalova", MARMARA, 0.30), ("78", "Karabük", KARADENIZ, 0.25),
    ("79", "Kilis", GUNEYDOGU, 0.15), ("80", "Osmaniye", AKDENIZ, 0.56),
    ("81", "Düzce", KARADENIZ, 0.40),
)

PROVINCES: tuple[Province, ...] = tuple(Province(*row) for row in _PROVINCE_DATA)
PROVINCES_BY_CODE: dict[str, Province] = {p.plate_code: p for p in PROVINCES}
VALID_PLATE_CODES: frozenset[str] = frozenset(PROVINCES_BY_CODE)

PLATE_LETTERS = "ABCDEFGHIJKLMNOPRSTUVYZ"

_PLATE_SHAPES: tuple[tuple[int, int], ...] = (
    (1, 4), (1, 5), (2, 3), (2, 4), (3, 2),
)

def generate_plate(rng: random.Random, plate_code: str) -> str:
    """a syntactically valid turkish plate for the given province"""
    letters_n, digits_n = rng.choice(_PLATE_SHAPES)
    letters = "".join(rng.choice(PLATE_LETTERS) for _ in range(letters_n))

    digits = "".join(rng.choice("0123456789") for _ in range(digits_n))
    return f"{plate_code} {letters} {digits}"

_FULL_HOLIDAY = 0.05
_HALF_DAY = 0.45

_FIXED_HOLIDAYS: tuple[tuple[int, int], ...] = (
    (1, 1),
    (4, 23),
    (5, 1),
    (5, 19),
    (7, 15),
    (8, 30),
    (10, 29),
)

_RELIGIOUS_HOLIDAYS: tuple[tuple[date, int], ...] = (
    (date(2023, 4, 21), 3),
    (date(2023, 6, 28), 4),
    (date(2024, 4, 10), 3),
    (date(2024, 6, 16), 4),
    (date(2025, 3, 30), 3),
    (date(2025, 6, 6), 4),
    (date(2026, 3, 20), 3),
    (date(2026, 5, 27), 4),
)

def build_holiday_calendar(start: date, end: date) -> dict[date, float]:
    """map every holiday in the range to a business-activity multiplier"""
    calendar: dict[date, float] = {}

    for year in range(start.year, end.year + 1):
        for month, day in _FIXED_HOLIDAYS:
            calendar[date(year, month, day)] = _FULL_HOLIDAY

        calendar[date(year, 10, 28)] = _HALF_DAY

    for first_day, length in _RELIGIOUS_HOLIDAYS:

        calendar[first_day - timedelta(days=1)] = _HALF_DAY
        for offset in range(length):
            calendar[first_day + timedelta(days=offset)] = _FULL_HOLIDAY

    return {d: v for d, v in calendar.items() if start <= d <= end}

BASE_CURRENCY = "TRY"
FOREIGN_CURRENCIES: tuple[str, ...] = ("USD", "EUR")

@dataclass(frozen=True)
class FxRate:
    rate_date: date
    currency_code: str
    rate_to_try: float

def _interpolate(anchors: dict[date, float], day: date) -> float:
    """linear interpolation between the two anchors surrounding `day`"""
    points = sorted(anchors.items())
    if day <= points[0][0]:
        return points[0][1]
    if day >= points[-1][0]:
        return points[-1][1]

    for (d0, v0), (d1, v1) in zip(points, points[1:]):
        if d0 <= day <= d1:
            span = (d1 - d0).days
            progress = (day - d0).days / span if span else 0.0
            return v0 + (v1 - v0) * progress
    return points[-1][1]

def build_fx_series(
    rng: random.Random,
    start: date,
    end: date,
    usd_anchors: dict[date, float],
    eur_anchors: dict[date, float],
) -> list[FxRate]:
    """daily fx rates, business days only"""
    holidays = build_holiday_calendar(start, end)
    rates: list[FxRate] = []

    current = start
    while current <= end:
        is_weekend = current.weekday() >= 5
        is_holiday = holidays.get(current, 1.0) < 0.2
        if not (is_weekend or is_holiday):
            for code, anchors in (("USD", usd_anchors), ("EUR", eur_anchors)):
                base = _interpolate(anchors, current)

                noisy = base * (1.0 + rng.gauss(0.0, 0.007))
                rates.append(FxRate(current, code, round(noisy, 4)))
        current += timedelta(days=1)

    return rates

@dataclass(frozen=True)
class ServiceType:
    code: str
    name_tr: str
    name_en: str
    is_warranty_eligible: bool
    typical_labour_hours: float
    share: float

SERVICE_TYPES: tuple[ServiceType, ...] = (
    ServiceType("MAINT", "Periyodik Bakım", "Scheduled maintenance", False, 2.0, 0.42),
    ServiceType("REPAIR", "Arıza Onarımı", "Fault repair", False, 3.5, 0.22),
    ServiceType("WARRANTY", "Garanti Onarımı", "Warranty repair", True, 4.0, 0.13),
    ServiceType("BODY", "Kaporta-Boya", "Body and paint", False, 12.0, 0.09),
    ServiceType("TYRE", "Lastik / Mevsimsel", "Tyre and seasonal", False, 1.0, 0.10),
    ServiceType("RECALL", "Geri Çağırma", "Recall campaign", True, 1.5, 0.03),
    ServiceType("INSPECT", "Ekspertiz", "Inspection", False, 1.0, 0.01),
)

SERVICE_TYPES_BY_CODE: dict[str, ServiceType] = {s.code: s for s in SERVICE_TYPES}

class FxLookup:
    """rate lookup with forward fill, because rates are not published daily"""

    def __init__(self, rates: list[FxRate]) -> None:
        self._by_currency: dict[str, list[tuple[date, float]]] = {}
        for rate in rates:
            self._by_currency.setdefault(rate.currency_code, []).append(
                (rate.rate_date, rate.rate_to_try)
            )
        for series in self._by_currency.values():
            series.sort()

    def rate(self, currency_code: str, when: date) -> float:
        """rate to try on `when`, or the most recent published rate before it"""
        if currency_code == BASE_CURRENCY:
            return 1.0

        series = self._by_currency.get(currency_code)
        if not series:
            raise KeyError(f"no FX series for {currency_code!r}")

        import bisect

        index = bisect.bisect_right(series, (when, float("inf"))) - 1

        return series[max(index, 0)][1]

    def to_try(self, amount: float, currency_code: str, when: date) -> float:
        return amount * self.rate(currency_code, when)

    def from_try(self, amount_try: float, currency_code: str, when: date) -> float:
        return amount_try / self.rate(currency_code, when)
