"""ana veri: bayiler, personel, model/donanım kataloğu, parçalar, tedarikçiler"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from faker import Faker

from . import reference as ref
from .config import Settings
from .identity import ascii_fold
from .rng import clamp, jitter, performance_index, stream, weighted_sample
from .versioning import Versioned, spread_changes
from .vin import random_vds

BRANDS = ("Atlas", "Verda", "Nova")

BODY_SEDAN, BODY_HATCH, BODY_SUV = "SEDAN", "HATCHBACK", "SUV"
BODY_WAGON, BODY_VAN, BODY_PICKUP = "STATION_WAGON", "VAN", "PICKUP"

FUEL_PETROL, FUEL_DIESEL = "PETROL", "DIESEL"
FUEL_HYBRID, FUEL_ELECTRIC, FUEL_LPG = "HYBRID", "ELECTRIC", "LPG"

TRANS_MANUAL, TRANS_AUTO = "MANUAL", "AUTOMATIC"

_MODEL_CATALOGUE: tuple[tuple, ...] = (
    ("Atlas", "Efe",     BODY_HATCH,  "A",   1000, FUEL_PETROL,   TRANS_MANUAL,  620_000),
    ("Atlas", "Ceyra",   BODY_HATCH,  "B",   1332, FUEL_PETROL,   TRANS_MANUAL,  780_000),
    ("Atlas", "Ceyra S", BODY_SEDAN,  "B",   1332, FUEL_PETROL,   TRANS_AUTO,    865_000),
    ("Atlas", "Vira",    BODY_SEDAN,  "C",   1598, FUEL_DIESEL,   TRANS_AUTO,  1_150_000),
    ("Atlas", "Vira SW", BODY_WAGON,  "C",   1598, FUEL_DIESEL,   TRANS_AUTO,  1_240_000),
    ("Atlas", "Toros",   BODY_SUV,    "C",   1499, FUEL_PETROL,   TRANS_AUTO,  1_420_000),
    ("Atlas", "Kartal",  BODY_SUV,    "D",   1997, FUEL_DIESEL,   TRANS_AUTO,  2_050_000),
    ("Atlas", "Ruzgar",  BODY_SEDAN,  "D",   1997, FUEL_DIESEL,   TRANS_AUTO,  1_980_000),

    ("Verda", "Mira",    BODY_HATCH,  "B",   1197, FUEL_PETROL,   TRANS_MANUAL,  735_000),
    ("Verda", "Sena",    BODY_SEDAN,  "C",   1461, FUEL_DIESEL,   TRANS_MANUAL, 1_080_000),
    ("Verda", "Duru",    BODY_SUV,    "B",   1332, FUEL_PETROL,   TRANS_AUTO,  1_180_000),
    ("Verda", "Bora",    BODY_SUV,    "C",   1598, FUEL_DIESEL,   TRANS_AUTO,  1_490_000),
    ("Verda", "Alp",     BODY_SUV,    "D",   1995, FUEL_DIESEL,   TRANS_AUTO,  2_310_000),
    ("Verda", "Ege",     BODY_HATCH,  "C",   1332, FUEL_LPG,      TRANS_MANUAL,  915_000),

    ("Nova",  "Deniz",   BODY_SEDAN,  "B",   1197, FUEL_PETROL,   TRANS_MANUAL,  795_000),
    ("Nova",  "Tempo",   BODY_SEDAN,  "C",   1498, FUEL_PETROL,   TRANS_AUTO,  1_105_000),
    ("Nova",  "Meltem",  BODY_SUV,    "C",   1498, FUEL_HYBRID,   TRANS_AUTO,  1_685_000),
    ("Nova",  "Poyraz",  BODY_WAGON,  "D",   1995, FUEL_DIESEL,   TRANS_AUTO,  2_120_000),
    ("Nova",  "Zirve",   BODY_SUV,    "E",   2487, FUEL_HYBRID,   TRANS_AUTO,  3_450_000),
    ("Nova",  "Simsek",  BODY_HATCH,  "C",      0, FUEL_ELECTRIC, TRANS_AUTO,  1_760_000),
    ("Nova",  "Isik",    BODY_SEDAN,  "C",      0, FUEL_ELECTRIC, TRANS_AUTO,  1_920_000),
    ("Nova",  "Kobra",   BODY_VAN,    "LCV",  1598, FUEL_DIESEL,  TRANS_MANUAL,  980_000),
    ("Nova",  "Panel",   BODY_VAN,    "LCV",  1995, FUEL_DIESEL,  TRANS_MANUAL, 1_140_000),
    ("Nova",  "Yuk",     BODY_PICKUP, "LCV",  1995, FUEL_DIESEL,  TRANS_AUTO,  1_575_000),
)

_TRIMS: tuple[tuple[str, float, int, int], ...] = (
    ("Base",     1.00, 24, 100_000),
    ("Comfort",  1.09, 24, 100_000),
    ("Elegance", 1.18, 36, 150_000),
    ("Sport",    1.26, 36, 150_000),
    ("Premium",  1.38, 60, 200_000),
)

PART_GROUPS: tuple[tuple[str, str, float], ...] = (

    ("FILTER",  "Filtre",              420.0),
    ("BRAKE",   "Fren Sistemi",       1_850.0),
    ("ENGINE",  "Motor",              6_400.0),
    ("TRANS",   "Şanzıman",           9_800.0),
    ("SUSP",    "Süspansiyon",        2_950.0),
    ("ELEC",    "Elektrik",           1_620.0),
    ("BODY",    "Kaporta",            4_300.0),
    ("GLASS",   "Cam",                2_100.0),
    ("TYRE",    "Lastik",             2_650.0),
    ("FLUID",   "Yağ ve Sıvılar",       780.0),
    ("INTER",   "İç Donanım",         1_450.0),
    ("EXHAUST", "Egzoz",              3_200.0),
    ("COOL",    "Soğutma",            1_980.0),
    ("IGNIT",   "Ateşleme",             920.0),
)

ROLE_SALES, ROLE_SERVICE = "SALES_ADVISOR", "SERVICE_ADVISOR"
ROLE_TECH, ROLE_MANAGER = "TECHNICIAN", "MANAGER"
_ROLE_MIX = ((ROLE_SALES, 0.40), (ROLE_TECH, 0.35), (ROLE_SERVICE, 0.18), (ROLE_MANAGER, 0.07))

DEALER_SALES, DEALER_SERVICE, DEALER_BOTH = "SALES", "SERVICE", "BOTH"

_DEALER_STEMS = (
    "Yıldız", "Şahin", "Öztürk", "Aslan", "Demir", "Kaya", "Çelik", "Doğan",
    "Ekinci", "Güneş", "Özkan", "Tunç", "Bozkurt", "Yücel", "Korkmaz", "Erdem",
    "Tekin", "Aydın", "Polat", "Sarı", "Gürsoy", "Uçar", "Balcı", "Kılıç",
    "Ateş", "Turan", "Coşkun", "Duman", "Keskin", "Akgün", "Baran", "Sezer",
    "Toprak", "Ünal", "Yalçın", "Zengin", "Bulut", "Çetin", "Kurt", "Aksoy",
)
_DEALER_SUFFIXES = ("Otomotiv", "Motorlu Araçlar", "Oto", "Otomotiv Tic. A.Ş.")

_SUPPLIER_COUNTRIES = (
    ("TR", 0.46), ("DE", 0.18), ("IT", 0.09), ("FR", 0.07),
    ("ES", 0.05), ("PL", 0.05), ("CZ", 0.04), ("CN", 0.06),
)

@dataclass
class MasterData:
    """üretilen ana veri varlıkları, artı sadece simülasyonda kullanılan yan tablolar"""

    dealers: list[Versioned] = field(default_factory=list)
    employees: list[Versioned] = field(default_factory=list)
    model_trims: list[Versioned] = field(default_factory=list)
    parts: list[Versioned] = field(default_factory=list)
    suppliers: list[Versioned] = field(default_factory=list)

    dealer_performance: dict[str, float] = field(default_factory=dict)

    supplier_reliability: dict[str, float] = field(default_factory=dict)

    trim_vds: dict[str, str] = field(default_factory=dict)

    trim_base_price: dict[str, float] = field(default_factory=dict)

    trims_by_key: dict[str, Versioned] = field(default_factory=dict)
    parts_by_key: dict[str, Versioned] = field(default_factory=dict)

    def dealer_codes(self, *, selling: bool = False, servicing: bool = False) -> list[str]:
        """bayinin yetkili olduğu işe göre süzülmüş bayi kodları"""
        codes: list[str] = []
        for dealer in self.dealers:
            dealer_type = dealer.base["dealer_type"]
            if selling and dealer_type not in (DEALER_SALES, DEALER_BOTH):
                continue
            if servicing and dealer_type not in (DEALER_SERVICE, DEALER_BOTH):
                continue
            codes.append(dealer.key)
        return codes

def inflate(base_price: float, from_date: date, to_date: date, annual: dict[int, float]) -> float:
    """bir fiyatı yapılandırılmış yıllık enflasyonla ileri taşı"""
    if to_date <= from_date:
        return base_price

    price = base_price
    cursor = from_date
    while cursor < to_date:
        year_end = min(date(cursor.year, 12, 31), to_date)
        fraction = ((year_end - cursor).days + 1) / 365.25
        rate = annual.get(cursor.year, 0.20)
        price *= (1.0 + rate) ** fraction
        cursor = year_end + timedelta(days=1)
    return price

def generate_suppliers(settings: Settings, faker: Faker) -> tuple[list[Versioned], dict[str, float]]:
    """parça tedarikçileri. gold'da type 1 - bunlar için geçmiş tutulmuyor"""
    rng = stream(settings.seed, "suppliers")
    faker.seed_instance(rng.randint(0, 2**31))

    countries, weights = zip(*_SUPPLIER_COUNTRIES)
    suppliers: list[Versioned] = []
    reliability: dict[str, float] = {}

    for index in range(1, settings.volumes.suppliers + 1):
        code = f"SUP{index:04d}"
        country = rng.choices(countries, weights=weights, k=1)[0]

        lead_time = rng.randint(3, 12) if country == "TR" else rng.randint(14, 55)

        suppliers.append(
            Versioned(
                key=code,
                created_on=settings.timeline.start,
                base={
                    "supplier_id": code,
                    "supplier_name": faker.company(),
                    "country_code": country,
                    "lead_time_days": lead_time,
                    "contact_email": f"siparis@sup{index:04d}.example",
                    "is_active": 1,
                },
            )
        )

        base_reliability = 0.90 if country == "TR" else 0.78
        reliability[code] = clamp(rng.gauss(base_reliability, 0.09), 0.45, 0.99)

    return suppliers, reliability

def generate_dealers(settings: Settings) -> tuple[list[Versioned], dict[str, float]]:
    """yetkili bayi ağı"""
    rng = stream(settings.seed, "dealers")
    count = settings.volumes.dealers

    anchors: tuple[tuple[str, int], ...] = (("34", 3), ("06", 2), ("35", 2))
    placements = [
        ref.PROVINCES_BY_CODE[code] for code, seats in anchors for _ in range(seats)
    ]

    anchor_codes = {code for code, _ in anchors}
    remaining = [p for p in ref.PROVINCES if p.plate_code not in anchor_codes]
    weights = [p.population_m for p in remaining]
    placements += weighted_sample(rng, remaining, weights, count - len(placements))
    placements = placements[:count]
    rng.shuffle(placements)

    dealers: list[Versioned] = []
    performance: dict[str, float] = {}
    stems = list(_DEALER_STEMS)
    rng.shuffle(stems)

    for index, province in enumerate(placements, start=1):
        code = f"BYI{index:03d}"
        dealer_type = rng.choices(
            (DEALER_BOTH, DEALER_SALES, DEALER_SERVICE), weights=(0.60, 0.20, 0.20), k=1
        )[0]

        if rng.random() < 0.12:
            opening = settings.timeline.start + timedelta(days=rng.randint(60, 900))
        else:
            opening = settings.timeline.start - timedelta(days=rng.randint(400, 5_000))

        bays = 0
        capacity_hours = 0
        if dealer_type in (DEALER_SERVICE, DEALER_BOTH):

            bays = max(3, round(clamp(province.population_m * 1.6, 3, 22)))
            capacity_hours = round(bays * 8 * 22 * rng.uniform(0.85, 1.05))

        dealers.append(
            Versioned(
                key=code,
                created_on=max(opening, settings.timeline.start),
                base={
                    "dealer_code": code,
                    "dealer_name": f"{stems[index % len(stems)]} {rng.choice(_DEALER_SUFFIXES)}",
                    "dealer_type": dealer_type,
                    "province_code": province.plate_code,
                    "city": province.name,
                    "region": province.region,
                    "address_line": f"{rng.randint(1, 250)}. Sokak No:{rng.randint(1, 90)}",
                    "phone": f"0{province.plate_code[-2:]}{rng.randint(2000000, 8999999)}",
                    "workshop_bay_count": bays,
                    "monthly_capacity_hours": capacity_hours,
                    "opening_date": opening.isoformat(),
                    "is_active": 1,
                },
            )
        )
        performance[code] = performance_index(rng)

    _apply_dealer_changes(rng, dealers, settings)
    return dealers, performance

def _apply_dealer_changes(rng: random.Random, dealers: list[Versioned], settings: Settings) -> None:
    """scd type 2'nin dimension versiyonlarına çevireceği öznitelik değişiklikleri"""
    regions = sorted({p.region for p in ref.PROVINCES})

    for dealer in dealers:
        earliest = max(dealer.created_on, settings.timeline.start) + timedelta(days=45)

        if rng.random() < 0.20:
            for when in spread_changes(rng, earliest, settings.timeline.end, 1, min_gap_days=60):
                new_region = rng.choice([r for r in regions if r != dealer.base["region"]])
                dealer.add_change(when, region=new_region)

        if dealer.base["dealer_type"] == DEALER_SERVICE and rng.random() < 0.25:
            for when in spread_changes(rng, earliest, settings.timeline.end, 1, min_gap_days=60):
                dealer.add_change(when, dealer_type=DEALER_BOTH)

        if rng.random() < 0.15:
            for when in spread_changes(rng, earliest, settings.timeline.end, 1, min_gap_days=60):
                dealer.add_change(
                    when,
                    dealer_name=f"{rng.choice(_DEALER_STEMS)} {rng.choice(_DEALER_SUFFIXES)}",
                )

        if rng.random() < 0.05:
            closing = settings.timeline.end - timedelta(days=rng.randint(30, 500))
            if closing > earliest:
                dealer.retired_on = closing

def generate_employees(
    settings: Settings, faker: Faker, dealers: list[Versioned]
) -> list[Versioned]:
    """satış danışmanları, servis danışmanları, teknisyenler ve müdürler"""
    rng = stream(settings.seed, "employees")
    faker.seed_instance(rng.randint(0, 2**31))

    roles, role_weights = zip(*_ROLE_MIX)
    dealer_keys = [d.key for d in dealers]
    employees: list[Versioned] = []

    for index in range(1, settings.volumes.employees + 1):
        code = f"PRS{index:05d}"
        home = rng.choice(dealers)
        role = rng.choices(roles, weights=role_weights, k=1)[0]

        if role == ROLE_TECH and home.base["dealer_type"] == DEALER_SALES:
            role = ROLE_SALES
        if role == ROLE_SALES and home.base["dealer_type"] == DEALER_SERVICE:
            role = ROLE_SERVICE

        hire_date = max(
            home.created_on,
            settings.timeline.start - timedelta(days=rng.randint(0, 3_600)),
        )
        created = max(hire_date, settings.timeline.start)

        first_name = faker.first_name()
        last_name = faker.last_name()

        employee = Versioned(
            key=code,
            created_on=created,
            base={
                "employee_id": code,
                "first_name": first_name,
                "last_name": last_name,
                "full_name": f"{first_name} {last_name}",
                "dealer_code": home.key,
                "role_code": role,
                "hire_date": hire_date.isoformat(),
                "email": f"{ascii_fold(first_name).lower()}.{ascii_fold(last_name).lower()}"
                         f"@{home.key.lower()}.example",
                "is_active": 1,
            },
        )

        _apply_employee_changes(rng, employee, dealer_keys, settings)
        employees.append(employee)

    return employees

def _apply_employee_changes(
    rng: random.Random, employee: Versioned, dealer_keys: list[str], settings: Settings
) -> None:
    earliest = employee.created_on + timedelta(days=90)
    if earliest >= settings.timeline.end:
        return

    if rng.random() < 0.10:
        for when in spread_changes(rng, earliest, settings.timeline.end, 1, min_gap_days=90):
            new_dealer = rng.choice([k for k in dealer_keys if k != employee.base["dealer_code"]])
            employee.add_change(when, dealer_code=new_dealer)

    if rng.random() < 0.08 and employee.base["role_code"] != ROLE_MANAGER:
        for when in spread_changes(rng, earliest, settings.timeline.end, 1, min_gap_days=90):
            employee.add_change(when, role_code=ROLE_MANAGER)

    if rng.random() < 0.12:
        leaving = settings.timeline.end - timedelta(days=rng.randint(20, 800))
        if leaving > earliest:
            employee.retired_on = leaving

def generate_model_trims(settings: Settings) -> tuple[list[Versioned], dict[str, str], dict[str, float]]:
    """ürün kataloğu: her model her donanım seviyesiyle çaprazlanmış"""
    rng = stream(settings.seed, "model_trims")
    trims: list[Versioned] = []
    vds_by_trim: dict[str, str] = {}
    base_price_by_trim: dict[str, float] = {}

    combinations = [
        (model, trim) for model in _MODEL_CATALOGUE for trim in _TRIMS
    ][: settings.volumes.model_trims]

    for index, (model, trim) in enumerate(combinations, start=1):
        brand, model_name, body, segment, engine_cc, fuel, transmission, base_price = model
        trim_name, multiplier, warranty_months, warranty_km = trim

        code = f"{brand[:2].upper()}{index:04d}"
        list_price = round(jitter(rng, base_price * multiplier, 0.02), -2)

        trims.append(
            Versioned(
                key=code,
                created_on=settings.timeline.start,
                base={
                    "model_trim_code": code,
                    "brand": brand,
                    "model_name": model_name,
                    "trim_name": trim_name,
                    "model_year": 2023,
                    "body_type": body,
                    "segment": segment,
                    "engine_cc": engine_cc,
                    "fuel_type": fuel,
                    "transmission": transmission,
                    "warranty_months": warranty_months,
                    "warranty_km": warranty_km,
                    "list_price_try": list_price,
                    "is_active": 1,
                },
            )
        )
        vds_by_trim[code] = random_vds(rng)
        base_price_by_trim[code] = list_price

    _apply_price_changes(rng, trims, settings)
    return trims, vds_by_trim, base_price_by_trim

def _apply_price_changes(rng: random.Random, trims: list[Versioned], settings: Settings) -> None:
    """donanım başına iki ila beş liste fiyatı güncellemesi, artı ara sıra makyaj"""
    annual = settings.economics.annual_inflation

    for trim in trims:
        revisions = spread_changes(
            rng,
            settings.timeline.start,
            settings.timeline.end,
            rng.randint(2, 5),
            min_gap_days=90,
        )
        base = trim.base["list_price_try"]
        for when in revisions:
            price = inflate(base, settings.timeline.start, when, annual)
            trim.add_change(when, list_price_try=round(jitter(rng, price, 0.015), -2))

        if rng.random() < 0.30:
            for when in spread_changes(
                rng, settings.timeline.start + timedelta(days=400), settings.timeline.end, 1
            ):
                trim.add_change(when, model_year=when.year + 1)

        if rng.random() < 0.08:
            retiring = settings.timeline.end - timedelta(days=rng.randint(60, 600))
            trim.retired_on = retiring

def generate_parts(
    settings: Settings, suppliers: list[Versioned]
) -> list[Versioned]:
    """yedek parça kataloğu"""
    rng = stream(settings.seed, "parts")
    supplier_keys = [s.key for s in suppliers]
    group_codes = [g[0] for g in PART_GROUPS]
    group_prices = {g[0]: g[2] for g in PART_GROUPS}
    group_names = {g[0]: g[1] for g in PART_GROUPS}

    group_weights = {
        "FILTER": 0.14, "BRAKE": 0.12, "ELEC": 0.11, "BODY": 0.11, "SUSP": 0.09,
        "ENGINE": 0.08, "INTER": 0.07, "FLUID": 0.06, "COOL": 0.05, "IGNIT": 0.05,
        "GLASS": 0.04, "EXHAUST": 0.04, "TYRE": 0.03, "TRANS": 0.01,
    }
    weights = [group_weights[c] for c in group_codes]

    parts: list[Versioned] = []
    for index in range(1, settings.volumes.parts + 1):
        group = rng.choices(group_codes, weights=weights, k=1)[0]

        part_no = f"{group[:2]}-{rng.randint(10_000, 99_999)}-{rng.choice('ABCDE')}"

        is_genuine = 1 if rng.random() < 0.68 else 0

        price = group_prices[group] * rng.uniform(0.35, 2.4) * (1.0 if is_genuine else 0.62)

        parts.append(
            Versioned(
                key=part_no,
                created_on=settings.timeline.start,
                base={
                    "part_no": part_no,
                    "part_name": f"{group_names[group]} {rng.randint(100, 999)}",
                    "part_group_code": group,
                    "part_group_name": group_names[group],
                    "is_genuine": is_genuine,
                    "supplier_id": rng.choice(supplier_keys),
                    "unit_of_measure": "AD" if group != "FLUID" else "LT",
                    "list_price_try": round(price, 2),
                    "is_active": 1,
                },
            )
        )

    _apply_part_changes(rng, parts, settings, supplier_keys)
    return parts

def _apply_part_changes(
    rng: random.Random,
    parts: list[Versioned],
    settings: Settings,
    supplier_keys: list[str],
) -> None:
    annual = settings.economics.annual_inflation

    for part in parts:

        for when in spread_changes(
            rng, settings.timeline.start, settings.timeline.end, rng.randint(1, 4), min_gap_days=120
        ):
            price = inflate(
                part.base["list_price_try"], settings.timeline.start, when, annual
            )
            part.add_change(when, list_price_try=round(jitter(rng, price, 0.03), 2))

        if rng.random() < 0.07 and len(supplier_keys) > 1:
            alternatives = [k for k in supplier_keys if k != part.base["supplier_id"]]
            for when in spread_changes(rng, settings.timeline.start, settings.timeline.end, 1):
                part.add_change(when, supplier_id=rng.choice(alternatives))

def generate_master_data(settings: Settings) -> MasterData:
    """her ana veri varlığını bağımlılık sırasıyla üret"""
    faker = Faker("tr_TR")

    suppliers, reliability = generate_suppliers(settings, faker)
    dealers, performance = generate_dealers(settings)
    employees = generate_employees(settings, faker, dealers)
    model_trims, trim_vds, trim_base_price = generate_model_trims(settings)
    parts = generate_parts(settings, suppliers)

    return MasterData(
        dealers=dealers,
        employees=employees,
        model_trims=model_trims,
        parts=parts,
        suppliers=suppliers,
        dealer_performance=performance,
        supplier_reliability=reliability,
        trim_vds=trim_vds,
        trim_base_price=trim_base_price,
        trims_by_key={t.key: t for t in model_trims},
        parts_by_key={p.key: p for p in parts},
    )
