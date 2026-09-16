"""araç satışları: sözleşmeler, takaslar ve el değiştiren vin'ler"""

from __future__ import annotations

import bisect
import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import reference as ref
from .config import Settings
from .customers import CustomerUniverse, TYPE_CORPORATE
from .master import MasterData, ROLE_SALES
from .rng import DateSampler, clamp, stream
from .vehicles import STATUS_IN_STOCK, STATUS_SOLD, STATUS_USED_STOCK, Vehicle, VehicleFleet
from .versioning import month_starts

SALE_NEW, SALE_USED = "NEW", "USED"

PAYMENT_CASH, PAYMENT_LOAN, PAYMENT_LEASE = "CASH", "LOAN", "LEASE"
CHANNEL_SHOWROOM, CHANNEL_FLEET, CHANNEL_ONLINE = "SHOWROOM", "FLEET", "ONLINE"

_TRADE_IN_RATE = 0.26

_FOREIGN_CURRENCY_RATE_INDIVIDUAL = 0.04
_FOREIGN_CURRENCY_RATE_CORPORATE = 0.18

_MAX_DISCOUNT_RATE = 0.28

@dataclass
class SalesResult:
    contracts: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

def _build_salesperson_index(
    master: MasterData, snapshot_dates: list[date]
) -> dict[tuple[str, int, int], list[str]]:
    """bayi ve ay başına satış danışmanları"""
    index: dict[tuple[str, int, int], list[str]] = defaultdict(list)
    for snapshot in snapshot_dates:
        for employee in master.employees:
            state = employee.state_at(snapshot)
            if state is None or not state.get("is_active"):
                continue
            if state["role_code"] != ROLE_SALES:
                continue
            index[(state["dealer_code"], snapshot.year, snapshot.month)].append(
                state["employee_id"]
            )
    return index

def _build_customer_index(
    customers: CustomerUniverse,
) -> tuple[dict[str, list[tuple[date, str]]], list[tuple[date, str]]]:
    """ikamet iline göre müşteriler, kazanıldıkları tarihe göre sıralı"""
    by_province: dict[str, list[tuple[date, str]]] = defaultdict(list)
    everyone: list[tuple[date, str]] = []

    for dms_id in customers.dms_ids:
        entry = (customers.customer_since[dms_id], dms_id)
        by_province[customers.customer_home[dms_id]].append(entry)
        everyone.append(entry)

    for series in by_province.values():
        series.sort()
    everyone.sort()
    return by_province, everyone

def _pick_customer(
    rng: random.Random,
    by_province: dict[str, list[tuple[date, str]]],
    everyone: list[tuple[date, str]],
    province_code: str,
    when: date,
) -> str | None:
    """mevcut bir müşteri, bayiye yakın olan tercih edilir"""
    pools = [by_province.get(province_code, []), everyone]
    if rng.random() > 0.70:
        pools.reverse()

    for pool in pools:
        cutoff = bisect.bisect_right(pool, (when, "￿"))
        if cutoff:
            return pool[rng.randrange(cutoff)][1]
    return None

def _discount_rate(
    rng: random.Random,
    *,
    is_campaign: bool,
    is_fleet: bool,
    days_in_stock: int,
) -> float:
    """liste fiyatından ne kadar düşülüyor ve neden"""
    rate = rng.uniform(0.020, 0.090)
    if is_campaign:
        rate += rng.uniform(0.030, 0.080)
    if is_fleet:
        rate += rng.uniform(0.020, 0.060)
    if days_in_stock > 90:
        rate += min((days_in_stock - 90) / 1_000.0, 0.060)
    return min(rate, _MAX_DISCOUNT_RATE)

def _trade_in_value(
    rng: random.Random,
    vehicle: Vehicle,
    master: MasterData,
    when: date,
    settings: Settings,
) -> float:
    """bayinin takasa alınan araca ödediği tutar, try cinsinden"""
    trim = master.trims_by_key.get(vehicle.model_trim_code)
    state = trim.state_at(when) if trim else None
    current_list = float(state["list_price_try"]) if state else vehicle.list_price_at_arrival_try

    age_years = max((when - vehicle.production_date).days / 365.25, 0.0)

    age_factor = 0.82 ** age_years
    km_factor = clamp(1.0 - (vehicle.odometer_km / 400_000.0), 0.35, 1.0)

    market_value = current_list * age_factor * km_factor
    return round(market_value * rng.uniform(0.86, 0.97), 2)

def _next_working_day(when: date, holidays: dict[date, float]) -> date:
    """hafta sonu ya da tatile denk gelen tarihi sonraki iş gününe it"""
    for _ in range(10):
        if when.weekday() < 5 and holidays.get(when, 1.0) >= 0.2:
            return when
        when += timedelta(days=1)
    return when

def generate_sales(
    settings: Settings,
    master: MasterData,
    customers: CustomerUniverse,
    fleet: VehicleFleet,
    fx: ref.FxLookup,
) -> SalesResult:
    rng = stream(settings.seed, "sales")
    holidays = ref.build_holiday_calendar(settings.timeline.start, settings.timeline.end)
    snapshots = month_starts(settings.timeline.start, settings.timeline.end)

    salespeople = _build_salesperson_index(master, snapshots)
    by_province, everyone = _build_customer_index(customers)

    sampler = DateSampler(
        rng,
        settings.timeline.start,
        settings.timeline.end,
        settings.seasonality.vehicle_sales,
        profile="sales",
        annual_growth=0.10,
        holidays=holidays,
        tax_change_dates=settings.seasonality.tax_change_dates,
    )

    incoming: dict[str, deque[Vehicle]] = defaultdict(deque)
    for vehicle in sorted(fleet.own, key=lambda v: v.arrival_date):
        incoming[vehicle.stock_dealer_code].append(vehicle)
    on_forecourt: dict[str, list[Vehicle]] = defaultdict(list)

    used_stock: dict[str, list[tuple[date, Vehicle, float]]] = defaultdict(list)

    owned: dict[str, list[Vehicle]] = defaultdict(list)

    tradeable = round(len(fleet.external) * 0.60)
    external_pool: list[Vehicle] = list(fleet.external[:tradeable])
    rng.shuffle(external_pool)

    dealers = master.dealer_codes(selling=True)
    dealer_weights = [master.dealer_performance[c] for c in dealers]
    dealer_province = {
        d.key: d.base["province_code"] for d in master.dealers
    }

    result = SalesResult()
    sale_dates = sorted(sampler.sample_many(settings.volumes.vehicle_sales))
    contract_seq = 0
    skipped_no_stock = 0
    used_sold = 0
    trade_ins = 0

    for contract_date in sale_dates:
        dealer_code = rng.choices(dealers, weights=dealer_weights, k=1)[0]

        queue = incoming[dealer_code]
        while queue and queue[0].arrival_date <= contract_date:
            on_forecourt[dealer_code].append(queue.popleft())

        customer_id = _pick_customer(
            rng, by_province, everyone, dealer_province[dealer_code], contract_date
        )
        if customer_id is None:
            continue

        is_corporate = customers.customer_type.get(customer_id) == TYPE_CORPORATE

        waiting = [
            entry for entry in used_stock[dealer_code]
            if (contract_date - entry[0]).days >= 10
        ]

        sell_used = bool(waiting) and rng.random() < 0.21

        if sell_used:
            contract_seq += 1
            used_sold += 1
            result.contracts.append(
                _used_contract(
                    rng, settings, master, customers, fx, holidays, salespeople,
                    dealer_code, customer_id, is_corporate, contract_date,
                    waiting, used_stock[dealer_code], owned, contract_seq,
                )
            )
            continue

        available = on_forecourt[dealer_code]
        if not available:
            skipped_no_stock += 1
            continue

        contract_seq += 1
        contract, traded = _new_contract(
            rng, settings, master, customers, external_pool, fx, holidays, salespeople,
            dealer_code, customer_id, is_corporate, contract_date,
            available, owned, used_stock, contract_seq,
        )
        result.contracts.append(contract)
        if traded:
            trade_ins += 1

    result.stats = {
        "contracts": len(result.contracts),
        "new_sales": len(result.contracts) - used_sold,
        "used_sales": used_sold,
        "trade_ins": trade_ins,
        "skipped_no_stock": skipped_no_stock,
        "unsold_at_end": sum(1 for v in fleet.own if v.status == STATUS_IN_STOCK),
        "used_unsold_at_end": sum(len(v) for v in used_stock.values()),
    }
    return result

def _pick_from_forecourt(rng: random.Random, available: list[Vehicle]) -> Vehicle:
    """stoktan bir araç al, en eskiye doğru ağırlıklı"""
    if rng.random() < 0.60:
        return available.pop(0)
    return available.pop(rng.randrange(min(len(available), 40)))

def _contract_currency(rng: random.Random, is_corporate: bool) -> str:
    rate = _FOREIGN_CURRENCY_RATE_CORPORATE if is_corporate else _FOREIGN_CURRENCY_RATE_INDIVIDUAL
    if rng.random() >= rate:
        return ref.BASE_CURRENCY
    return rng.choice(ref.FOREIGN_CURRENCIES)

def _salesperson(
    rng: random.Random,
    salespeople: dict[tuple[str, int, int], list[str]],
    dealer_code: str,
    when: date,
) -> str:
    pool = salespeople.get((dealer_code, when.year, when.month))
    if pool:
        return rng.choice(pool)

    return ""

def _new_contract(
    rng, settings, master, customers, external_pool, fx, holidays, salespeople,
    dealer_code, customer_id, is_corporate, contract_date,
    available, owned, used_stock, contract_seq,
) -> tuple[dict, bool]:
    vehicle = _pick_from_forecourt(rng, available)

    delivery_date = _next_working_day(
        contract_date + timedelta(days=rng.randint(2, 38)), holidays
    )
    registration_date = _next_working_day(
        delivery_date + timedelta(days=rng.randint(0, 12)), holidays
    )
    days_in_stock = (delivery_date - vehicle.arrival_date).days

    trim = master.trims_by_key[vehicle.model_trim_code]
    list_price_try = float(
        (trim.state_at(contract_date) or trim.base)["list_price_try"]
    )

    is_campaign = rng.random() < 0.22
    channel = (
        CHANNEL_FLEET if is_corporate and rng.random() < 0.55
        else CHANNEL_ONLINE if rng.random() < 0.07
        else CHANNEL_SHOWROOM
    )
    discount_rate = _discount_rate(
        rng,
        is_campaign=is_campaign,
        is_fleet=channel == CHANNEL_FLEET,
        days_in_stock=days_in_stock,
    )
    discount_try = round(list_price_try * discount_rate, 2)
    net_try = round(list_price_try - discount_try, 2)

    trade_in_vin = ""
    trade_in_try = 0.0
    traded = False
    candidates = owned.get(customer_id, [])

    if rng.random() < _TRADE_IN_RATE:
        traded_vehicle: Vehicle | None = None
        if candidates:
            traded_vehicle = candidates.pop(rng.randrange(len(candidates)))
        else:

            if external_pool:
                traded_vehicle = external_pool.pop()

        if traded_vehicle is not None:
            traded = True
            trade_in_vin = traded_vehicle.vin
            trade_in_try = _trade_in_value(rng, traded_vehicle, master, contract_date, settings)
            traded_vehicle.status = STATUS_USED_STOCK
            if traded_vehicle.record is not None:
                traded_vehicle.record.add_change(
                    delivery_date, status=STATUS_USED_STOCK, owner_customer_id=""
                )
            used_stock[dealer_code].append((delivery_date, traded_vehicle, trade_in_try))

    province_code = customers.customer_home[customer_id]
    plate = ref.generate_plate(rng, province_code)

    vehicle.status = STATUS_SOLD
    vehicle.first_sale_date = delivery_date
    vehicle.owner_customer_id = customer_id
    vehicle.plate_number = plate
    vehicle.ownership_history.append((delivery_date, customer_id))
    owned[customer_id].append(vehicle)
    if vehicle.record is not None:
        vehicle.record.add_change(
            delivery_date,
            status=STATUS_SOLD,
            plate_number=plate,
            owner_customer_id=customer_id,
        )

    currency = _contract_currency(rng, is_corporate)
    rate = fx.rate(currency, contract_date)

    return (
        {
            "contract_no": f"SZL{contract_date.year}{contract_seq:06d}",
            "contract_date": contract_date.isoformat(),
            "delivery_date": delivery_date.isoformat(),
            "invoice_date": delivery_date.isoformat(),
            "registration_date": registration_date.isoformat(),
            "vin": vehicle.vin,
            "dealer_code": dealer_code,
            "salesperson_id": _salesperson(rng, salespeople, dealer_code, contract_date),
            "customer_id": customer_id,
            "sale_type": SALE_NEW,
            "model_trim_code": vehicle.model_trim_code,
            "plate_number": plate,
            "currency_code": currency,

            "list_price": round(list_price_try / rate, 2),
            "discount_amount": round(discount_try / rate, 2),
            "net_sale_amount": round(net_try / rate, 2),
            "trade_in_vin": trade_in_vin,
            "trade_in_amount": round(trade_in_try / rate, 2) if traded else 0,
            "payment_type": _payment_type(rng, is_corporate),
            "channel": channel,
            "is_campaign": int(is_campaign),
            "days_in_stock": days_in_stock,
        },
        traded,
    )

def _used_contract(
    rng, settings, master, customers, fx, holidays, salespeople,
    dealer_code, customer_id, is_corporate, contract_date,
    waiting, dealer_used_stock, owned, contract_seq,
) -> dict:
    """takasa alınan aracı yeniden sat. bu, o vin'in ikinci sahibi"""

    entry = waiting[0]
    dealer_used_stock.remove(entry)
    taken_on, vehicle, cost_try = entry

    delivery_date = _next_working_day(
        contract_date + timedelta(days=rng.randint(1, 15)), holidays
    )
    registration_date = _next_working_day(
        delivery_date + timedelta(days=rng.randint(0, 12)), holidays
    )

    asking_try = round(cost_try * rng.uniform(1.08, 1.30), 2)
    discount_try = round(asking_try * rng.uniform(0.0, 0.06), 2)
    net_try = round(asking_try - discount_try, 2)

    province_code = customers.customer_home[customer_id]
    plate = ref.generate_plate(rng, province_code)

    vehicle.status = STATUS_SOLD
    vehicle.owner_customer_id = customer_id
    vehicle.plate_number = plate
    vehicle.ownership_history.append((delivery_date, customer_id))
    owned[customer_id].append(vehicle)
    if vehicle.record is not None:
        vehicle.record.add_change(
            delivery_date,
            status=STATUS_SOLD,
            plate_number=plate,
            owner_customer_id=customer_id,
        )

    currency = _contract_currency(rng, is_corporate)
    rate = fx.rate(currency, contract_date)

    return {
        "contract_no": f"SZL{contract_date.year}{contract_seq:06d}",
        "contract_date": contract_date.isoformat(),
        "delivery_date": delivery_date.isoformat(),
        "invoice_date": delivery_date.isoformat(),
        "registration_date": registration_date.isoformat(),
        "vin": vehicle.vin,
        "dealer_code": dealer_code,
        "salesperson_id": _salesperson(rng, salespeople, dealer_code, contract_date),
        "customer_id": customer_id,
        "sale_type": SALE_USED,
        "model_trim_code": vehicle.model_trim_code,
        "plate_number": plate,
        "currency_code": currency,
        "list_price": round(asking_try / rate, 2),
        "discount_amount": round(discount_try / rate, 2),
        "net_sale_amount": round(net_try / rate, 2),
        "trade_in_vin": "",
        "trade_in_amount": 0,
        "payment_type": _payment_type(rng, is_corporate),
        "channel": CHANNEL_SHOWROOM,
        "is_campaign": 0,
        "days_in_stock": (delivery_date - taken_on).days,
    }

def _payment_type(rng: random.Random, is_corporate: bool) -> str:
    if is_corporate:
        return rng.choices(
            (PAYMENT_LEASE, PAYMENT_LOAN, PAYMENT_CASH), weights=(0.42, 0.36, 0.22), k=1
        )[0]
    return rng.choices(
        (PAYMENT_LOAN, PAYMENT_CASH, PAYMENT_LEASE), weights=(0.58, 0.38, 0.04), k=1
    )[0]
