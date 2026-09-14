"""deliberate data defects, and the answer key that makes them measurable.

bu modül en son çalışıyor, tüm türetilmiş dosyalar (satın alma, garanti, hedef)
temiz veriden üretildikten sonra. daha erken bozarsam kirlilik türetilmiş
dosyalara da sızar ve cevap anahtarı yanlış olur.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime

from . import vin as vinmod
from .config import Settings
from .master import MasterData
from .rng import stream
from .vehicles import VehicleFleet

RULE_VIN_FORMAT = "VIN_FORMAT"
RULE_VIN_CHECK_DIGIT = "VIN_CHECK_DIGIT"
RULE_VIN_DUPLICATE_NEW_SALE = "VIN_DUPLICATE_NEW_SALE"
RULE_PLATE_FORMAT = "PLATE_FORMAT"
RULE_PLATE_PROVINCE = "PLATE_PROVINCE"
RULE_ODOMETER_ROLLBACK = "ODOMETER_ROLLBACK"
RULE_RO_DATE_SEQUENCE = "RO_DATE_SEQUENCE"
RULE_LABOUR_HOURS_NEGATIVE = "LABOUR_HOURS_NEGATIVE"
RULE_LABOUR_HOURS_EXCESSIVE = "LABOUR_HOURS_EXCESSIVE"
RULE_WARRANTY_AMOUNT_OVERFLOW = "WARRANTY_AMOUNT_OVERFLOW"
RULE_PART_NO_ORPHAN = "PART_NO_ORPHAN"
RULE_VIN_ORPHAN = "VIN_ORPHAN"
RULE_BUSINESS_KEY_NULL = "BUSINESS_KEY_NULL"
RULE_DATE_FORMAT = "DATE_FORMAT_INCONSISTENT"
RULE_HEADER_LINE_MISMATCH = "HEADER_LINE_MISMATCH"

@dataclass
class InjectionResult:
    log: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

class _Injector:
    """applies defects and records each one"""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.log: list[dict] = []
        self._seq = 0

    def record(
        self,
        *,
        rule: str,
        entity: str,
        business_key: str,
        column: str,
        before,
        after,
        cascades: str = "",
    ) -> None:
        self._seq += 1
        self.log.append(
            {
                "injection_id": self._seq,
                "rule_code": rule,
                "target_entity": entity,
                "business_key": business_key,
                "column_name": column,
                "value_before": "" if before is None else str(before),
                "value_after": "" if after is None else str(after),

                "cascade_rules": cascades,
            }
        )

    def sample(self, rows: list, rate: float) -> list:
        """pick a share of rows to corrupt, without replacement"""
        count = min(len(rows), round(len(rows) * rate))
        return self.rng.sample(rows, count) if count else []

def _corrupt_vins(inj: _Injector, settings: Settings, contracts: list[dict],
                  repair_orders: list[dict]) -> None:
    """malformed vins and vins that fail their check digit"""
    for rows, entity, key_col in (
        (contracts, "dms.sales_contract", "contract_no"),
        (repair_orders, "workshop.repair_order", "repair_order_no"),
    ):
        for row in inj.sample(rows, settings.dirty.invalid_vin_format):
            before = row["vin"]
            after, _ = vinmod.corrupt_format(inj.rng, before)
            row["vin"] = after
            inj.record(rule=RULE_VIN_FORMAT, entity=entity,
                       business_key=row[key_col], column="vin",
                       before=before, after=after)

        for row in inj.sample(rows, settings.dirty.invalid_vin_check_digit):
            before = row["vin"]
            if not vinmod.is_well_formed(before):
                continue
            after, _ = vinmod.corrupt_check_digit(inj.rng, before)
            row["vin"] = after
            inj.record(rule=RULE_VIN_CHECK_DIGIT, entity=entity,
                       business_key=row[key_col], column="vin",
                       before=before, after=after)

def _duplicate_new_sales(inj: _Injector, settings: Settings,
                         contracts: list[dict]) -> None:
    """the same vin sold as new twice - physically impossible, genuinely common"""
    new_sales = [c for c in contracts if c["sale_type"] == "NEW"]
    for row in inj.sample(new_sales, settings.dirty.duplicate_new_vehicle_sale):
        clone = dict(row)

        clone["contract_no"] = row["contract_no"] + "D"
        contracts.append(clone)
        inj.record(rule=RULE_VIN_DUPLICATE_NEW_SALE, entity="dms.sales_contract",
                   business_key=clone["contract_no"], column="vin",
                   before=row["contract_no"], after=clone["vin"])

def _corrupt_plates(inj: _Injector, settings: Settings, contracts: list[dict],
                    repair_orders: list[dict]) -> None:
    for rows, entity, key_col in (
        (contracts, "dms.sales_contract", "contract_no"),
        (repair_orders, "workshop.repair_order", "repair_order_no"),
    ):
        for row in inj.sample(rows, settings.dirty.invalid_plate_format):
            before = row.get("plate_number", "")
            if not before:
                continue
            style = inj.rng.choice(("no_space", "lowercase", "too_many_digits", "letters_only"))
            if style == "no_space":
                after = before.replace(" ", "")
            elif style == "lowercase":
                after = before.lower()
            elif style == "too_many_digits":
                after = before + str(inj.rng.randint(0, 9))
            else:
                after = "".join(c for c in before if not c.isdigit()).strip()
            row["plate_number"] = after
            inj.record(rule=RULE_PLATE_FORMAT, entity=entity,
                       business_key=row[key_col], column="plate_number",
                       before=before, after=after)

        for row in inj.sample(rows, settings.dirty.invalid_plate_province):
            before = row.get("plate_number", "")
            if not before or " " not in before:
                continue

            bad_code = f"{inj.rng.randint(82, 99)}"
            after = bad_code + before[2:]
            row["plate_number"] = after
            inj.record(rule=RULE_PLATE_PROVINCE, entity=entity,
                       business_key=row[key_col], column="plate_number",
                       before=before, after=after)

def _rollback_odometers(inj: _Injector, settings: Settings,
                        repair_orders: list[dict]) -> None:
    """make a reading lower than the same vin's previous one"""
    by_vin: dict[str, list[dict]] = {}
    for order in repair_orders:
        by_vin.setdefault(order["vin"], []).append(order)

    candidates = [
        orders[i]
        for orders in by_vin.values()
        if len(orders) > 1
        for i in range(1, len(orders))
    ]
    for row in inj.sample(candidates, settings.dirty.odometer_rollback):
        before = row["odometer_km"]
        after = max(0, int(before * inj.rng.uniform(0.55, 0.93)))
        if after >= before:
            continue
        row["odometer_km"] = after
        inj.record(rule=RULE_ODOMETER_ROLLBACK, entity="workshop.repair_order",
                   business_key=row["repair_order_no"], column="odometer_km",
                   before=before, after=after)

def _break_date_sequences(inj: _Injector, settings: Settings,
                          repair_orders: list[dict]) -> None:
    """put a lifecycle stage out of order"""
    closed = [o for o in repair_orders if o["delivery_ts"] and o["repair_start_ts"]]
    for row in inj.sample(closed, settings.dirty.repair_order_date_out_of_order):
        style = inj.rng.choice(("delivery_before_checkin", "repair_before_inspection"))
        if style == "delivery_before_checkin":
            column, before = "delivery_ts", row["delivery_ts"]
            checkin = datetime.fromisoformat(row["checkin_ts"])
            after = (checkin.replace(hour=7)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            column, before = "repair_start_ts", row["repair_start_ts"]
            checkin = datetime.fromisoformat(row["checkin_ts"])
            after = (checkin.replace(hour=6)).strftime("%Y-%m-%d %H:%M:%S")
        row[column] = after
        inj.record(rule=RULE_RO_DATE_SEQUENCE, entity="workshop.repair_order",
                   business_key=row["repair_order_no"], column=column,
                   before=before, after=after)

def _corrupt_labour(inj: _Injector, settings: Settings, lines: list[dict]) -> None:
    labour = [l for l in lines if l["line_type"] == "LABOUR"]

    for row in inj.sample(labour, settings.dirty.negative_labour_hours):
        before = row["labour_hours"]
        after = -abs(before) if before else -1.5
        row["labour_hours"] = after
        inj.record(rule=RULE_LABOUR_HOURS_NEGATIVE, entity="workshop.repair_order_line",
                   business_key=f"{row['repair_order_no']}#{row['line_no']}",
                   column="labour_hours", before=before, after=after)

    for row in inj.sample(labour, settings.dirty.excessive_labour_hours):
        before = row["labour_hours"]

        after = round(inj.rng.uniform(120.0, 400.0), 2)
        row["labour_hours"] = after
        inj.record(rule=RULE_LABOUR_HOURS_EXCESSIVE, entity="workshop.repair_order_line",
                   business_key=f"{row['repair_order_no']}#{row['line_no']}",
                   column="labour_hours", before=before, after=after)

def _overflow_warranty(inj: _Injector, settings: Settings, lines: list[dict]) -> None:
    """claim more under warranty than the line is worth"""
    for row in inj.sample(lines, settings.dirty.warranty_amount_overflow):
        before = row["warranty_amount"]
        after = round(float(row["line_amount"]) * inj.rng.uniform(1.15, 2.10), 2)
        row["warranty_amount"] = after
        inj.record(
            rule=RULE_WARRANTY_AMOUNT_OVERFLOW, entity="workshop.repair_order_line",
            business_key=f"{row['repair_order_no']}#{row['line_no']}",
            column="warranty_amount", before=before, after=after,

            cascades=RULE_HEADER_LINE_MISMATCH,
        )

def _orphan_references(inj: _Injector, settings: Settings, master: MasterData,
                       fleet: VehicleFleet, lines: list[dict],
                       repair_orders: list[dict], purchase_lines: list[dict]) -> None:
    """foreign keys pointing at things that do not exist"""
    known_parts = {p.key for p in master.parts}

    def unknown_part() -> str:
        for _ in range(20):
            candidate = f"{inj.rng.choice('ABCDEFGH')}{inj.rng.choice('ABCDEFGH')}-" \
                        f"{inj.rng.randint(10_000, 99_999)}-{inj.rng.choice('XYZ')}"
            if candidate not in known_parts:
                return candidate
        return "ZZ-00000-X"

    part_lines = [l for l in lines if l["line_type"] == "PART" and l["part_no"]]
    for row in inj.sample(part_lines, settings.dirty.orphan_part_no):
        before, after = row["part_no"], unknown_part()
        row["part_no"] = after
        inj.record(rule=RULE_PART_NO_ORPHAN, entity="workshop.repair_order_line",
                   business_key=f"{row['repair_order_no']}#{row['line_no']}",
                   column="part_no", before=before, after=after)

    for row in inj.sample(purchase_lines, settings.dirty.orphan_part_no):
        before, after = row["part_no"], unknown_part()
        row["part_no"] = after
        inj.record(rule=RULE_PART_NO_ORPHAN, entity="parts.purchase_order_line",
                   business_key=f"{row['po_no']}#{row['po_line_no']}",
                   column="part_no", before=before, after=after)

    known_vins = set(fleet.by_vin)
    for row in inj.sample(repair_orders, settings.dirty.orphan_vin):
        before = row["vin"]
        for _ in range(20):
            candidate = vinmod.build_vin(
                "ZZZ", vinmod.random_vds(inj.rng),
                inj.rng.randint(2015, 2026), "B",
                inj.rng.randint(1, 999_999),
            )
            if candidate not in known_vins:
                row["vin"] = candidate
                inj.record(rule=RULE_VIN_ORPHAN, entity="workshop.repair_order",
                           business_key=row["repair_order_no"], column="vin",
                           before=before, after=candidate)
                break

def _null_business_keys(inj: _Injector, settings: Settings, contracts: list[dict],
                        repair_orders: list[dict]) -> None:
    """blank out a key column. cheap to inject, expensive to miss"""
    for rows, entity, key_col, blank_col in (
        (contracts, "dms.sales_contract", "contract_no", "customer_id"),
        (repair_orders, "workshop.repair_order", "repair_order_no", "vin"),
    ):
        for row in inj.sample(rows, settings.dirty.null_business_key):
            before = row[blank_col]
            if not before:
                continue
            row[blank_col] = ""
            inj.record(rule=RULE_BUSINESS_KEY_NULL, entity=entity,
                       business_key=row[key_col], column=blank_col,
                       before=before, after="")

def _inconsistent_dates(inj: _Injector, settings: Settings,
                        contracts: list[dict]) -> None:
    """write some dates the turkish way in a column that is otherwise iso"""
    for row in inj.sample(contracts, settings.dirty.inconsistent_date_format):
        column = inj.rng.choice(("contract_date", "delivery_date", "registration_date"))
        before = row[column]
        if not before or "." in before:
            continue
        parsed = date.fromisoformat(before)
        after = parsed.strftime("%d.%m.%Y")
        row[column] = after
        inj.record(rule=RULE_DATE_FORMAT, entity="dms.sales_contract",
                   business_key=row["contract_no"], column=column,
                   before=before, after=after)

def inject_defects(
    settings: Settings,
    master: MasterData,
    fleet: VehicleFleet,
    *,
    contracts: list[dict],
    repair_orders: list[dict],
    repair_order_lines: list[dict],
    purchase_lines: list[dict],
) -> InjectionResult:
    """corrupt the generated rows in place and return the answer key"""
    rng = stream(settings.seed, "dirty")
    inj = _Injector(rng)

    _corrupt_vins(inj, settings, contracts, repair_orders)
    _duplicate_new_sales(inj, settings, contracts)
    _corrupt_plates(inj, settings, contracts, repair_orders)
    _rollback_odometers(inj, settings, repair_orders)
    _break_date_sequences(inj, settings, repair_orders)
    _corrupt_labour(inj, settings, repair_order_lines)
    _overflow_warranty(inj, settings, repair_order_lines)
    _orphan_references(inj, settings, master, fleet,
                       repair_order_lines, repair_orders, purchase_lines)
    _null_business_keys(inj, settings, contracts, repair_orders)
    _inconsistent_dates(inj, settings, contracts)

    by_rule: dict[str, int] = {}
    for entry in inj.log:
        by_rule[entry["rule_code"]] = by_rule.get(entry["rule_code"], 0) + 1

    return InjectionResult(
        log=inj.log,
        stats={"injected_total": len(inj.log), "by_rule": by_rule},
    )
