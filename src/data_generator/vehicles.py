"""the vehicle population: 35,000 vins and the state each one carries forward"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from .config import Settings
from .master import MasterData
from .rng import DateSampler, clamp, stream
from .reference import build_holiday_calendar
from .versioning import Versioned
from .vin import build_vin

STATUS_IN_STOCK = "IN_STOCK"
STATUS_SOLD = "SOLD"
STATUS_USED_STOCK = "USED_STOCK"

WMI_BY_BRAND = {"Atlas": "NM7", "Verda": "VF9", "Nova": "WNV"}

PLANT_CODES = ("B", "G", "K", "T")

_COLOURS: tuple[tuple[str, float], ...] = (
    ("Beyaz", 0.34), ("Gri", 0.17), ("Siyah", 0.15), ("Gümüş", 0.11),
    ("Mavi", 0.07), ("Kırmızı", 0.05), ("Lacivert", 0.05), ("Bej", 0.03),
    ("Yeşil", 0.02), ("Kahverengi", 0.01),
)

_DEALER_MARGIN = (0.070, 0.135)

@dataclass
class Vehicle:
    """one vehicle: its identity, and the state it carries through the timeline"""

    vin: str
    model_trim_code: str
    brand: str
    model_year: int
    production_date: date
    arrival_date: date
    stock_dealer_code: str
    colour: str
    dealer_cost_try: float
    list_price_at_arrival_try: float
    warranty_months: int
    warranty_km: int

    is_external: bool = False
    odometer_km: int = 0
    plate_number: str | None = None
    owner_customer_id: str | None = None
    status: str = STATUS_IN_STOCK
    first_sale_date: date | None = None
    last_service_date: date | None = None

    ownership_history: list[tuple[date, str]] = field(default_factory=list)

    daily_km: float = 40.0

    record: Versioned | None = None

    def warranty_expiry_date(self) -> date | None:
        """calendar end of the warranty, measured from first registration"""
        if self.first_sale_date is None:
            return None
        return self.first_sale_date + timedelta(days=round(self.warranty_months * 30.44))

    def is_under_warranty(self, when: date, odometer_km: int) -> bool:
        """warranty is the earlier of the time limit and the distance limit"""
        expiry = self.warranty_expiry_date()
        if expiry is None:
            return False
        return when <= expiry and odometer_km <= self.warranty_km

    def odometer_at(self, when: date) -> int:
        """projected reading on a given date, from first registration"""
        if self.first_sale_date is None or when <= self.first_sale_date:
            return 0
        return max(0, round((when - self.first_sale_date).days * self.daily_km))

@dataclass
class VehicleFleet:
    own: list[Vehicle] = field(default_factory=list)
    external: list[Vehicle] = field(default_factory=list)

    by_vin: dict[str, Vehicle] = field(default_factory=dict)

    def all(self) -> list[Vehicle]:
        return self.own + self.external

    def available_stock(self, when: date) -> list[Vehicle]:
        """vehicles that have arrived and are still unsold on `when`"""
        return [
            v for v in self.own
            if v.status == STATUS_IN_STOCK and v.arrival_date <= when
        ]

def _daily_km_for(rng: random.Random, segment: str) -> float:
    """annual mileage, expressed per day and varying by segment"""
    annual = {
        "A": 9_000, "B": 12_000, "C": 16_000, "D": 21_000,
        "E": 23_000, "LCV": 34_000,
    }.get(segment, 15_000)
    return clamp(rng.gauss(annual, annual * 0.30), annual * 0.30, annual * 2.2) / 365.0

def generate_fleet(settings: Settings, master: MasterData) -> VehicleFleet:
    """produce the vehicle population and place it into dealer stock"""
    rng = stream(settings.seed, "vehicles")
    holidays = build_holiday_calendar(
        settings.timeline.start - timedelta(days=200), settings.timeline.end
    )

    arrivals = DateSampler(
        rng,
        settings.timeline.start,
        settings.timeline.end,
        settings.seasonality.vehicle_sales,
        profile="sales",
        annual_growth=0.10,
        holidays=holidays,
        tax_change_dates=settings.seasonality.tax_change_dates,
    )

    trims = [t for t in master.model_trims]
    trim_weights = _trim_popularity(rng, trims)
    colours, colour_weights = zip(*_COLOURS)

    stock_dealers = master.dealer_codes(selling=True)
    stock_weights = [master.dealer_performance[c] for c in stock_dealers]

    fleet = VehicleFleet()
    serial = 100_000

    expected_new_sales = settings.volumes.vehicle_sales * 0.82
    aimed_at_demand = min(settings.volumes.vehicles, round(expected_new_sales))
    closing_stock_window = 270

    for index in range(settings.volumes.vehicles):
        trim = rng.choices(trims, weights=trim_weights, k=1)[0]

        if index < aimed_at_demand:
            target_sale_date = arrivals.sample()

            arrival = target_sale_date - timedelta(days=rng.randint(10, 75))
        else:
            arrival = settings.timeline.end - timedelta(
                days=rng.randint(0, closing_stock_window)
            )
        production = arrival - timedelta(days=rng.randint(20, 75))

        serial += 1
        vehicle = _build_vehicle(
            rng, settings, master, trim, production, arrival,
            rng.choices(stock_dealers, weights=stock_weights, k=1)[0],
            rng.choices(colours, weights=colour_weights, k=1)[0],
            serial,
        )
        fleet.own.append(vehicle)
        fleet.by_vin[vehicle.vin] = vehicle

    _build_external_pool(rng, settings, master, fleet, serial)
    _attach_source_records(fleet, settings)
    return fleet

def _trim_popularity(rng: random.Random, trims: list[Versioned]) -> list[float]:
    """sales weight per trim"""
    weights = []
    for trim in trims:
        base = rng.lognormvariate(0.0, 0.75)

        if trim.base["trim_name"] in ("Comfort", "Elegance"):
            base *= 1.9
        elif trim.base["trim_name"] == "Premium":
            base *= 0.45

        if trim.base["fuel_type"] == "ELECTRIC":
            base *= 0.25
        elif trim.base["fuel_type"] == "HYBRID":
            base *= 0.55
        weights.append(base)
    return weights

def _build_vehicle(
    rng: random.Random,
    settings: Settings,
    master: MasterData,
    trim: Versioned,
    production: date,
    arrival: date,
    dealer_code: str,
    colour: str,
    serial: int,
    *,
    is_external: bool = False,
) -> Vehicle:
    brand = trim.base["brand"]

    if production.month >= 10 and rng.random() < 0.65:
        model_year = production.year + 1
    else:
        model_year = max(int(trim.base["model_year"]), production.year)
    model_year = int(clamp(model_year, 2010, 2030))

    vin = build_vin(
        wmi=WMI_BY_BRAND[brand],
        vds=master.trim_vds[trim.key],
        model_year=model_year,
        plant_code=rng.choice(PLANT_CODES),
        serial=serial,
    )

    state_at_arrival = trim.state_at(max(arrival, settings.timeline.start)) or trim.base
    list_price = float(state_at_arrival["list_price_try"])
    dealer_cost = round(list_price * (1.0 - rng.uniform(*_DEALER_MARGIN)), 2)

    return Vehicle(
        vin=vin,
        model_trim_code=trim.key,
        brand=brand,
        model_year=model_year,
        production_date=production,
        arrival_date=arrival,
        stock_dealer_code=dealer_code,
        colour=colour,
        dealer_cost_try=dealer_cost,
        list_price_at_arrival_try=list_price,
        warranty_months=int(state_at_arrival["warranty_months"]),
        warranty_km=int(state_at_arrival["warranty_km"]),
        is_external=is_external,
        daily_km=_daily_km_for(rng, state_at_arrival["segment"]),
    )

def _build_external_pool(
    rng: random.Random,
    settings: Settings,
    master: MasterData,
    fleet: VehicleFleet,
    serial_start: int,
) -> None:
    """vehicles this distributor never sold, sized at 8% of the own fleet"""

    count = round(len(fleet.own) * 0.20)
    trims = list(master.model_trims)
    colours, colour_weights = zip(*_COLOURS)
    serial = serial_start

    for _ in range(count):
        trim = rng.choice(trims)

        production = settings.timeline.start - timedelta(days=rng.randint(400, 3_000))
        serial += 1
        vehicle = _build_vehicle(
            rng, settings, master, trim, production,
            production + timedelta(days=rng.randint(20, 75)),
            rng.choice(master.dealer_codes(selling=True)),
            rng.choices(colours, weights=colour_weights, k=1)[0],
            serial,
            is_external=True,
        )

        vehicle.status = STATUS_SOLD
        vehicle.first_sale_date = production + timedelta(days=rng.randint(30, 180))
        vehicle.odometer_km = vehicle.odometer_at(settings.timeline.start)
        fleet.external.append(vehicle)
        fleet.by_vin[vehicle.vin] = vehicle

def _engine_no(brand: str, vin: str) -> str:
    """a stable engine number derived from the vin"""
    digest = hashlib.blake2b(vin.encode("ascii"), digest_size=4).digest()
    return f"{brand[:2].upper()}{int.from_bytes(digest, 'big') % 10**8:08d}"

def _attach_source_records(fleet: VehicleFleet, settings: Settings) -> None:
    """create the dms vehicle-stock view for own vehicles only"""
    for vehicle in fleet.own:
        created = max(vehicle.arrival_date, settings.timeline.start)
        vehicle.record = Versioned(
            key=vehicle.vin,
            created_on=created,
            base={
                "vin": vehicle.vin,
                "model_trim_code": vehicle.model_trim_code,
                "model_year": vehicle.model_year,
                "colour": vehicle.colour,
                "production_date": vehicle.production_date.isoformat(),
                "arrival_date": vehicle.arrival_date.isoformat(),
                "stock_dealer_code": vehicle.stock_dealer_code,
                "dealer_cost_try": vehicle.dealer_cost_try,

                "engine_no": _engine_no(vehicle.brand, vehicle.vin),
                "status": STATUS_IN_STOCK,

                "plate_number": "",
                "owner_customer_id": "",
                "is_active": 1,
            },
        )
