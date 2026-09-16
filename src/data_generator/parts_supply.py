"""yedek parça tedariki: atölyelerin kullandığına göre oluşan satın alma siparişleri"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import reference as ref
from .config import Settings
from .master import MasterData
from .rng import stream
from .workshop import LINE_PART, WorkshopResult
from .versioning import month_starts

_COST_RATIO = (0.52, 0.74)

_SAFETY_FACTOR = (1.05, 1.45)

_LINES_PER_ORDER = (4, 16)

STATUS_RECEIVED, STATUS_PARTIAL, STATUS_OPEN = "RECEIVED", "PARTIAL", "OPEN"

@dataclass
class PartsSupplyResult:
    purchase_lines: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

def generate_part_purchases(
    settings: Settings,
    master: MasterData,
    workshop: WorkshopResult,
    fx: ref.FxLookup,
) -> PartsSupplyResult:
    rng = stream(settings.seed, "parts_supply")
    snapshots = month_starts(settings.timeline.start, settings.timeline.end)

    supplier_of = {p.key: p.base["supplier_id"] for p in master.parts}
    lead_time_of = {s.key: s.base["lead_time_days"] for s in master.suppliers}
    country_of = {s.key: s.base["country_code"] for s in master.suppliers}

    monthly: dict[tuple[str, int, int], dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    order_month = {
        order["repair_order_no"]: (
            int(order["checkin_ts"][0:4]), int(order["checkin_ts"][5:7])
        )
        for order in workshop.repair_orders
    }
    for line in workshop.lines:
        if line["line_type"] != LINE_PART or not line["part_no"]:
            continue
        supplier = supplier_of.get(line["part_no"])
        if supplier is None:
            continue
        year, month = order_month[line["repair_order_no"]]
        monthly[(supplier, year, month)][line["part_no"]] += float(line["quantity"])

    part_price: dict[tuple[str, int, int], float] = {}
    for snapshot in snapshots:
        for part in master.parts:
            state = part.state_at(snapshot)
            if state is not None:
                part_price[(part.key, snapshot.year, snapshot.month)] = float(
                    state["list_price_try"]
                )

    result = PartsSupplyResult()
    order_seq = 0
    late_lines = 0
    short_lines = 0
    open_lines = 0

    target_lines = settings.volumes.part_purchase_lines
    keys = sorted(monthly.keys(), key=lambda k: (k[1], k[2], k[0]))

    all_demand: list[tuple[str, int, int, str, float]] = [
        (supplier, year, month, part_no, quantity)
        for (supplier, year, month) in keys
        for part_no, quantity in monthly[(supplier, year, month)].items()
    ]
    if len(all_demand) > target_lines:
        keep = target_lines / len(all_demand)
        all_demand = [d for d in all_demand if rng.random() < keep]

    grouped: dict[tuple[str, int, int], list[tuple[str, float]]] = defaultdict(list)
    for supplier, year, month, part_no, quantity in all_demand:
        grouped[(supplier, year, month)].append((part_no, quantity))

    for (supplier, year, month), demand in sorted(
        grouped.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])
    ):
        reliability = master.supplier_reliability[supplier]
        lead_time = lead_time_of[supplier]
        is_import = country_of[supplier] != "TR"

        need_by = date(year, month, 1)
        order_date = need_by - timedelta(days=lead_time + rng.randint(0, 10))
        if order_date < settings.timeline.start:
            order_date = settings.timeline.start
        if order_date > settings.timeline.end:
            continue

        rows = list(demand)
        rng.shuffle(rows)
        while rows:
            order_seq += 1
            chunk = [rows.pop() for _ in range(min(rng.randint(*_LINES_PER_ORDER), len(rows)))]
            po_no = f"SAS{order_date.year}{order_seq:06d}"

            promised = order_date + timedelta(days=lead_time)

            if rng.random() < reliability:
                delay = rng.randint(-2, 2)
            else:
                delay = rng.randint(3, 45 if is_import else 18)
            actual = promised + timedelta(days=delay)

            currency = _order_currency(rng, is_import)

            for line_no, (part_no, quantity) in enumerate(chunk, start=1):
                list_price = part_price.get(
                    (part_no, year, month)
                ) or part_price.get((part_no, settings.timeline.start.year, 1))
                if list_price is None:
                    continue

                ordered = max(1.0, round(quantity * rng.uniform(*_SAFETY_FACTOR), 1))
                unit_cost_try = round(list_price * rng.uniform(*_COST_RATIO), 2)

                rate = fx.rate(currency, order_date)

                if actual > settings.timeline.end:
                    status, received, delivery = STATUS_OPEN, 0.0, None
                    open_lines += 1
                elif rng.random() < 0.06:
                    status = STATUS_PARTIAL
                    received = round(ordered * rng.uniform(0.35, 0.92), 1)
                    delivery = actual
                    short_lines += 1
                else:
                    status, received, delivery = STATUS_RECEIVED, ordered, actual

                if delay > 2 and status != STATUS_OPEN:
                    late_lines += 1

                result.purchase_lines.append(
                    {
                        "po_no": po_no,
                        "po_line_no": line_no,
                        "order_date": order_date.isoformat(),
                        "supplier_id": supplier,
                        "part_no": part_no,
                        "ordered_quantity": ordered,
                        "received_quantity": received,
                        "promised_date": promised.isoformat(),
                        "delivery_date": delivery.isoformat() if delivery else "",
                        "delay_days": delay if status != STATUS_OPEN else "",
                        "status": status,
                        "currency_code": currency,
                        "unit_cost": round(unit_cost_try / rate, 2),
                        "line_amount": round(ordered * unit_cost_try / rate, 2),
                    }
                )

    result.stats = {
        "purchase_lines": len(result.purchase_lines),
        "purchase_orders": len({r["po_no"] for r in result.purchase_lines}),
        "late_lines": late_lines,
        "short_deliveries": short_lines,
        "open_at_cutoff": open_lines,
        "suppliers_used": len({r["supplier_id"] for r in result.purchase_lines}),
    }
    return result

def _order_currency(rng: random.Random, is_import: bool) -> str:
    """ithal parçalar eur veya usd ile faturalanır; yerli olanlar try ile"""
    if not is_import:
        return ref.BASE_CURRENCY
    return rng.choices(("EUR", "USD", ref.BASE_CURRENCY), weights=(0.55, 0.30, 0.15), k=1)[0]
