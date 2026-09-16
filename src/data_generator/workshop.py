"""iş emirleri: satış sonrası yaşam döngüsü ve onu birbirine bağlayan kilometre sayacı"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from . import reference as ref
from .config import Settings
from .customers import CustomerUniverse
from .master import ROLE_SERVICE, ROLE_TECH, MasterData, inflate
from .rng import DateSampler, clamp, jitter, stream
from .vehicles import STATUS_SOLD, Vehicle, VehicleFleet
from .versioning import month_starts

LINE_LABOUR, LINE_PART = "LABOUR", "PART"

STATUS_CLOSED = "CLOSED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_WAITING_PARTS = "WAITING_PARTS"
STATUS_AWAITING_COLLECTION = "AWAITING_COLLECTION"

SERVICE_INTERVAL_KM = 15_000
SERVICE_INTERVAL_MONTHS = 12

BASE_LABOUR_RATE_TRY = 780.0

PARTS_WAIT_RATE = 0.24

_PART_GROUPS_BY_SERVICE: dict[str, tuple[str, ...]] = {
    "MAINT": ("FILTER", "FLUID", "IGNIT", "BRAKE"),
    "REPAIR": ("ENGINE", "ELEC", "COOL", "SUSP", "BRAKE", "EXHAUST", "TRANS"),
    "WARRANTY": ("ELEC", "ENGINE", "INTER", "COOL", "SUSP"),
    "BODY": ("BODY", "GLASS", "INTER"),
    "TYRE": ("TYRE",),
    "RECALL": ("ELEC", "ENGINE", "SUSP"),
    "INSPECT": (),
}

_LINE_PROFILE: dict[str, tuple[int, int, int, int]] = {
    "MAINT": (1, 1, 1, 4),
    "REPAIR": (1, 2, 1, 3),
    "WARRANTY": (1, 1, 1, 2),
    "BODY": (1, 3, 2, 5),
    "TYRE": (1, 1, 0, 4),
    "RECALL": (1, 1, 0, 2),
    "INSPECT": (1, 1, 0, 0),
}

_OPERATION_CODES: dict[str, tuple[str, ...]] = {
    "MAINT": ("OP-1010", "OP-1020", "OP-1030", "OP-1040"),
    "REPAIR": ("OP-2010", "OP-2050", "OP-2120", "OP-2200", "OP-2310"),
    "WARRANTY": ("OP-3010", "OP-3040", "OP-3110"),
    "BODY": ("OP-4010", "OP-4020", "OP-4050", "OP-4090"),
    "TYRE": ("OP-5010", "OP-5020"),
    "RECALL": ("OP-6010", "OP-6020"),
    "INSPECT": ("OP-7010",),
}

@dataclass
class WorkshopResult:
    repair_orders: list[dict] = field(default_factory=list)
    lines: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    odometer_readings: dict[str, list[tuple[date, int]]] = field(default_factory=dict)

def _monthly_part_prices(
    master: MasterData, snapshots: list[date]
) -> dict[tuple[str, int, int], float]:
    """ay başına parça liste fiyatı"""
    prices: dict[tuple[str, int, int], float] = {}
    for snapshot in snapshots:
        for part in master.parts:
            state = part.state_at(snapshot)
            if state is None:
                continue
            prices[(part.key, snapshot.year, snapshot.month)] = float(
                state["list_price_try"]
            )
    return prices

def _staff_index(
    master: MasterData, snapshots: list[date], role: str
) -> dict[tuple[str, int, int], list[str]]:
    index: dict[tuple[str, int, int], list[str]] = defaultdict(list)
    for snapshot in snapshots:
        for employee in master.employees:
            state = employee.state_at(snapshot)
            if state is None or not state.get("is_active"):
                continue
            if state["role_code"] != role:
                continue
            index[(state["dealer_code"], snapshot.year, snapshot.month)].append(
                state["employee_id"]
            )
    return index

def _pick_staff(rng, index, dealer_code, when) -> str:
    pool = index.get((dealer_code, when.year, when.month))

    return rng.choice(pool) if pool else ""

def _is_working_day(when: date, holidays: dict[date, float]) -> bool:
    return when.weekday() < 5 and holidays.get(when, 1.0) >= 0.2

def _next_working_day(when: date, holidays: dict[date, float]) -> date:
    for _ in range(12):
        if _is_working_day(when, holidays):
            return when
        when += timedelta(days=1)
    return when

def _advance(moment: datetime, hours: float, holidays: dict[date, float]) -> datetime:
    """`hours` kadar *atölye* zamanı ilerle, duvar saati değil"""
    day_start, day_end = time(8, 0), time(18, 0)
    remaining = hours

    while remaining > 0:
        if not _is_working_day(moment.date(), holidays):
            moment = datetime.combine(
                _next_working_day(moment.date() + timedelta(days=1), holidays), day_start
            )
            continue
        if moment.time() < day_start:
            moment = datetime.combine(moment.date(), day_start)
        if moment.time() >= day_end:
            moment = datetime.combine(
                _next_working_day(moment.date() + timedelta(days=1), holidays), day_start
            )
            continue

        end_of_day = datetime.combine(moment.date(), day_end)
        available = (end_of_day - moment).total_seconds() / 3600.0
        if remaining <= available:
            return moment + timedelta(hours=remaining)
        remaining -= available
        moment = datetime.combine(
            _next_working_day(moment.date() + timedelta(days=1), holidays), day_start
        )

    return moment

def _fmt(moment: datetime | None) -> str:
    """zaman damgaları metin olarak yazılır; boş aşama boş metindir"""
    return moment.strftime("%Y-%m-%d %H:%M:%S") if moment else ""

def _scheduled_maintenance_dates(
    vehicle: Vehicle, window_start: date, window_end: date
) -> list[date]:
    """bu aracın periyodik bakımlarının ne zaman geldiği"""
    if vehicle.daily_km <= 0:
        return []

    days_per_interval = min(
        SERVICE_INTERVAL_KM / vehicle.daily_km,
        SERVICE_INTERVAL_MONTHS * 30.44,
    )
    dates: list[date] = []
    cursor = window_start + timedelta(days=round(days_per_interval))
    while cursor <= window_end:
        dates.append(cursor)
        cursor += timedelta(days=round(days_per_interval))
    return dates

def _pick_service_type(
    rng: random.Random, when: date, under_warranty: bool
) -> ref.ServiceType:
    """mevsime ve garanti durumuna göre plansız bir iş tipi seç"""
    candidates: list[ref.ServiceType] = []
    weights: list[float] = []

    for service in ref.SERVICE_TYPES:
        if service.code == "MAINT":
            continue
        weight = service.share
        if service.code == "WARRANTY":
            if not under_warranty:
                continue

            weight *= 1.25
        if service.code == "TYRE":

            weight *= 4.2 if when.month in (11, 12) else 3.1 if when.month in (3, 4) else 0.25
        if service.code == "RECALL":
            weight *= 0.4
        candidates.append(service)
        weights.append(weight)

    return rng.choices(candidates, weights=weights, k=1)[0]

def generate_workshop(
    settings: Settings,
    master: MasterData,
    customers: CustomerUniverse,
    fleet: VehicleFleet,
) -> WorkshopResult:
    rng = stream(settings.seed, "workshop")
    holidays = ref.build_holiday_calendar(settings.timeline.start, settings.timeline.end)
    snapshots = month_starts(settings.timeline.start, settings.timeline.end)

    part_prices = _monthly_part_prices(master, snapshots)
    advisors = _staff_index(master, snapshots, ROLE_SERVICE)
    technicians = _staff_index(master, snapshots, ROLE_TECH)

    parts_by_group: dict[str, list[str]] = defaultdict(list)
    for part in master.parts:
        parts_by_group[part.base["part_group_code"]].append(part.key)

    service_dealers = master.dealer_codes(servicing=True)
    dealer_weights = [master.dealer_performance[c] for c in service_dealers]

    seasonality = DateSampler(
        rng,
        settings.timeline.start,
        settings.timeline.end,
        settings.seasonality.service,
        profile="service",
        annual_growth=0.12,
        holidays=holidays,
    )

    servicing: list[tuple[Vehicle, date, date]] = []
    for vehicle in fleet.own:
        if vehicle.status != STATUS_SOLD or vehicle.first_sale_date is None:
            continue
        servicing.append((vehicle, vehicle.first_sale_date, settings.timeline.end))

    loyal = [v for v in fleet.external if v.status == STATUS_SOLD and rng.random() < 0.45]
    for vehicle in loyal:
        servicing.append((vehicle, settings.timeline.start, settings.timeline.end))

    result = WorkshopResult()
    readings: dict[str, list[tuple[date, int]]] = defaultdict(list)
    events: list[tuple[date, Vehicle, ref.ServiceType | None]] = []

    for vehicle, start, end in servicing:
        for due in _scheduled_maintenance_dates(vehicle, start, end):

            if vehicle.is_external and rng.random() < 0.50:
                continue
            events.append((due, vehicle, ref.SERVICE_TYPES_BY_CODE["MAINT"]))

    scheduled_count = len(events)

    remaining = max(settings.volumes.repair_orders - scheduled_count, 0)
    exposure = [
        max((end - start).days, 0) * jitter(rng, 1.0, 0.55)
        for _, start, end in servicing
    ]
    total_exposure = sum(exposure) or 1.0

    for (vehicle, start, end), weight in zip(servicing, exposure):
        count = remaining * weight / total_exposure

        whole = int(count)
        if rng.random() < count - whole:
            whole += 1
        for _ in range(whole):

            when = None
            for _ in range(5):
                candidate = seasonality.sample()
                if start <= candidate <= end:
                    when = candidate
                    break
            if when is None:
                span = max((end - start).days, 0)
                when = start + timedelta(days=rng.randint(0, span)) if span else start
            events.append((when, vehicle, None))

    events.sort(key=lambda e: e[0])

    order_seq = 0
    open_orders = 0
    warranty_orders = 0
    parts_waits = 0

    last_visit: dict[str, date] = {}

    for when, vehicle, forced_type in events:
        when = _next_working_day(when, holidays)

        previous = last_visit.get(vehicle.vin)
        if previous is not None and when <= previous:
            when = _next_working_day(previous + timedelta(days=2), holidays)

        if when > settings.timeline.end:
            continue
        last_visit[vehicle.vin] = when

        odometer = _next_odometer(rng, vehicle, when, readings)
        under_warranty = vehicle.is_under_warranty(when, odometer)
        service = forced_type or _pick_service_type(rng, when, under_warranty)

        if vehicle.stock_dealer_code in service_dealers and rng.random() < 0.72:
            dealer_code = vehicle.stock_dealer_code
        else:
            dealer_code = rng.choices(service_dealers, weights=dealer_weights, k=1)[0]

        order_seq += 1
        order_no = f"IE{when.year}{order_seq:07d}"

        order, order_lines, flags = _build_order(
            rng, settings, master, customers, holidays,
            part_prices, parts_by_group, advisors, technicians,
            vehicle, when, odometer, service, under_warranty,
            dealer_code, order_no,
        )
        result.repair_orders.append(order)
        result.lines.extend(order_lines)

        readings[vehicle.vin].append((when, odometer))
        vehicle.last_service_date = when
        open_orders += flags["is_open"]
        warranty_orders += flags["is_warranty"]
        parts_waits += flags["waited_for_parts"]

    result.odometer_readings = dict(readings)
    result.stats = {
        "repair_orders": len(result.repair_orders),
        "lines": len(result.lines),
        "scheduled": scheduled_count,
        "unscheduled": len(result.repair_orders) - scheduled_count,
        "open_at_cutoff": open_orders,
        "warranty_orders": warranty_orders,
        "parts_waits": parts_waits,
        "vehicles_serviced": len(readings),
    }
    return result

def _next_odometer(
    rng: random.Random,
    vehicle: Vehicle,
    when: date,
    readings: dict[str, list[tuple[date, int]]],
) -> int:
    """bu vin'in öncekinden asla düşük olmayan bir kilometre değeri"""
    projected = vehicle.odometer_at(when)
    if vehicle.is_external:

        projected += vehicle.odometer_km

    projected = max(0, round(jitter(rng, max(projected, 1), 0.06)))

    history = readings.get(vehicle.vin)
    if history:
        previous_date, previous_km = history[-1]
        elapsed = max((when - previous_date).days, 0)

        floor = previous_km + max(round(elapsed * vehicle.daily_km * 0.25), 15)
        projected = max(projected, floor)

    return projected

def _build_order(
    rng, settings, master, customers, holidays,
    part_prices, parts_by_group, advisors, technicians,
    vehicle, when, odometer, service, under_warranty,
    dealer_code, order_no,
) -> tuple[dict, list[dict], dict]:
    """tek iş emri ve satırları, her yaşam döngüsü aşamasından geçirilmiş"""

    has_appointment = rng.random() < 0.62
    appointment_date = (
        _next_working_day(when - timedelta(days=rng.randint(1, 14)), holidays)
        if has_appointment else None
    )
    if appointment_date and appointment_date > when:
        appointment_date = None

    checkin = datetime.combine(when, time(rng.randint(8, 11), rng.choice((0, 15, 30, 45))))
    inspection = _advance(checkin, rng.uniform(0.3, 3.0), holidays)

    labour_hours_total = max(
        0.4, jitter(rng, service.typical_labour_hours, 0.55)
    )

    waited = rng.random() < PARTS_WAIT_RATE and service.code != "INSPECT"
    if waited:
        parts_wait_start = _advance(inspection, rng.uniform(0.2, 1.5), holidays)

        parts_ready = _advance(parts_wait_start, rng.randint(1, 6) * 10.0, holidays)
        repair_start = _advance(parts_ready, rng.uniform(0.1, 2.0), holidays)
    else:
        parts_wait_start = parts_ready = None
        repair_start = _advance(inspection, rng.uniform(0.2, 4.0), holidays)

    repair_end = _advance(repair_start, labour_hours_total, holidays)
    qc = _advance(repair_end, rng.uniform(0.2, 1.5), holidays)

    delivery = _advance(qc, rng.uniform(0.5, 26.0), holidays)

    cutoff = datetime.combine(settings.timeline.end, time(23, 59, 59))
    status = STATUS_CLOSED
    if delivery > cutoff:
        if qc > cutoff:
            if repair_start > cutoff:
                status = STATUS_WAITING_PARTS if waited else STATUS_IN_PROGRESS
                repair_start = repair_end = qc = delivery = None
            else:
                status = STATUS_IN_PROGRESS
                repair_end = qc = delivery = None
        else:
            status = STATUS_AWAITING_COLLECTION
            delivery = None

    lines, totals = _build_lines(
        rng, settings, master, part_prices, parts_by_group,
        vehicle, when, service, under_warranty, labour_hours_total,
        dealer_code, order_no,
    )

    order = {
        "repair_order_no": order_no,
        "dealer_code": dealer_code,
        "vin": vehicle.vin,
        "plate_number": vehicle.plate_number or "",
        "customer_id": vehicle.owner_customer_id or "",
        "service_advisor_id": _pick_staff(rng, advisors, dealer_code, when),
        "technician_id": _pick_staff(rng, technicians, dealer_code, when),
        "service_type_code": service.code,
        "odometer_km": odometer,
        "is_warranty": int(under_warranty and service.is_warranty_eligible),
        "status": status,
        "currency_code": ref.BASE_CURRENCY,

        "appointment_date": appointment_date.isoformat() if appointment_date else "",
        "checkin_ts": _fmt(checkin),
        "inspection_ts": _fmt(inspection),
        "parts_wait_start_ts": _fmt(parts_wait_start),
        "parts_ready_ts": _fmt(parts_ready),
        "repair_start_ts": _fmt(repair_start),
        "repair_end_ts": _fmt(repair_end),
        "qc_ts": _fmt(qc),
        "delivery_ts": _fmt(delivery),

        "total_labour_amount": round(totals["labour"], 2),
        "total_part_amount": round(totals["part"], 2),
        "total_warranty_amount": round(totals["warranty"], 2),
        "customer_payable_amount": round(totals["customer"], 2),
    }

    return order, lines, {
        "is_open": int(status != STATUS_CLOSED),
        "is_warranty": int(under_warranty and service.is_warranty_eligible),
        "waited_for_parts": int(waited),
    }

def _build_lines(
    rng, settings, master, part_prices, parts_by_group,
    vehicle, when, service, under_warranty, labour_hours_total,
    dealer_code, order_no,
) -> tuple[list[dict], dict[str, float]]:
    labour_min, labour_max, part_min, part_max = _LINE_PROFILE[service.code]
    covered = under_warranty and service.is_warranty_eligible

    labour_rate = inflate(
        BASE_LABOUR_RATE_TRY,
        settings.timeline.start,
        when,
        settings.economics.annual_inflation,
    )

    labour_rate *= 0.85 + 0.35 * master.dealer_performance.get(dealer_code, 1.0)

    lines: list[dict] = []
    totals = {"labour": 0.0, "part": 0.0, "warranty": 0.0, "customer": 0.0}
    line_no = 0

    labour_line_count = rng.randint(labour_min, labour_max)
    split = _split_hours(rng, labour_hours_total, labour_line_count)
    for hours in split:
        line_no += 1
        amount = round(hours * labour_rate, 2)
        warranty_amount = round(amount, 2) if covered else 0.0
        lines.append(
            {
                "repair_order_no": order_no,
                "line_no": line_no,
                "line_type": LINE_LABOUR,
                "part_no": "",
                "operation_code": rng.choice(_OPERATION_CODES[service.code]),
                "description": service.name_tr,
                "quantity": 1,
                "labour_hours": round(hours, 2),
                "unit_price": round(labour_rate, 2),
                "discount_amount": 0,
                "line_amount": amount,
                "warranty_amount": warranty_amount,
                "customer_amount": round(amount - warranty_amount, 2),
            }
        )
        totals["labour"] += amount
        totals["warranty"] += warranty_amount
        totals["customer"] += amount - warranty_amount

    groups = _PART_GROUPS_BY_SERVICE[service.code]
    part_line_count = rng.randint(part_min, part_max) if groups else 0

    for _ in range(part_line_count):
        group = rng.choice(groups)
        pool = parts_by_group.get(group)
        if not pool:
            continue
        part_no = rng.choice(pool)
        unit_price = part_prices.get((part_no, when.year, when.month))
        if unit_price is None:
            continue

        quantity = _part_quantity(rng, group)
        gross = unit_price * quantity

        discount = 0.0 if covered else round(gross * rng.choice((0.0, 0.0, 0.0, 0.05, 0.10)), 2)
        amount = round(gross - discount, 2)
        warranty_amount = amount if covered else 0.0

        line_no += 1
        lines.append(
            {
                "repair_order_no": order_no,
                "line_no": line_no,
                "line_type": LINE_PART,
                "part_no": part_no,
                "operation_code": "",
                "description": master.parts_by_key[part_no].base["part_name"],
                "quantity": quantity,
                "labour_hours": 0,
                "unit_price": round(unit_price, 2),
                "discount_amount": discount,
                "line_amount": amount,
                "warranty_amount": round(warranty_amount, 2),
                "customer_amount": round(amount - warranty_amount, 2),
            }
        )
        totals["part"] += amount
        totals["warranty"] += warranty_amount
        totals["customer"] += amount - warranty_amount

    return lines, totals

def _split_hours(rng: random.Random, total: float, parts: int) -> list[float]:
    """toplam işçilik süresini işlem satırlarına böl"""
    if parts <= 1:
        return [total]
    cuts = sorted(rng.uniform(0.15, 0.85) for _ in range(parts - 1))
    shares, previous = [], 0.0
    for cut in cuts + [1.0]:
        shares.append(max(total * (cut - previous), 0.1))
        previous = cut
    return shares

def _part_quantity(rng: random.Random, group: str) -> float:
    """miktar parçaya göre: dört lastik, bir şanzıman, litre litre yağ"""
    if group == "TYRE":
        return rng.choice((1, 2, 4, 4))
    if group == "FLUID":
        return round(rng.uniform(1.0, 6.5), 1)
    if group in ("BRAKE", "IGNIT"):
        return rng.choice((1, 2, 2, 4))
    return 1
