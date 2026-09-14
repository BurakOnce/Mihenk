"""writing the six source systems out as files - and describing them.

her dosyayı yazarken aynı zamanda _manifest.json'a da yazıyorum (format,
encoding, watermark kolonu). tools/generate_ctl_seed.py bu dosyayı okuyup
ctl.source_config'i üretiyor, yani ingestion config elle yazılmıyor.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .config import Settings
from .customers import CustomerUniverse
from .finance import FinanceResult
from .master import MasterData
from .parts_supply import PartsSupplyResult
from .portal import PortalResult
from .sales import SalesResult
from .vehicles import VehicleFleet
from .versioning import full_snapshots, incremental_extracts, month_starts
from .workshop import WorkshopResult
from .writers import SourceSpec, SourceWriter

_DMS_DIALECT = {"delimiter": ";", "decimal": ",", "encoding": "windows-1254"}

def _by_month(rows: Iterable[dict], date_key: str) -> dict[str, list[dict]]:
    """group transaction rows into monthly files by one of their date columns"""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        value = str(row.get(date_key, ""))
        if len(value) >= 7 and value[4] == "-":
            grouped[value[:7].replace("-", "")].append(row)
        elif len(value) >= 10 and value[2] == ".":

            grouped[f"{value[6:10]}{value[3:5]}"].append(row)
        else:
            grouped["unknown"].append(row)
    return grouped

def _by_day(rows: Iterable[dict], ts_key: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        value = str(row.get(ts_key, ""))
        grouped[value[:10] if len(value) >= 10 else "unknown"].append(row)
    return grouped

def write_all(
    settings: Settings,
    writer: SourceWriter,
    *,
    master: MasterData,
    customers: CustomerUniverse,
    fleet: VehicleFleet,
    sales: SalesResult,
    workshop: WorkshopResult,
    parts: PartsSupplyResult,
    portal: PortalResult,
    finance: FinanceResult,
    injection_log: list[dict],
) -> None:
    snapshots = month_starts(settings.timeline.start, settings.timeline.end)

    _write_dms(settings, writer, master, customers, fleet, sales, snapshots)
    _write_crm(writer, customers, snapshots)
    _write_workshop(writer, workshop)
    _write_parts(writer, master, parts, snapshots)
    _write_portal(writer, portal)
    _write_finance(writer, finance)
    _write_answer_keys(writer.output_path, customers, injection_log)

    writer.write_manifest()

def _write_dms(
    settings: Settings,
    writer: SourceWriter,
    master: MasterData,
    customers: CustomerUniverse,
    fleet: VehicleFleet,
    sales: SalesResult,
    snapshots: list[date],
) -> None:

    for entity, entities, keys in (
        ("dealer", master.dealers, ("dealer_code",)),
        ("employee", master.employees, ("employee_id",)),
        ("model_trim", master.model_trims, ("model_trim_code",)),
    ):
        spec = writer.register(
            SourceSpec("dms", entity, "csv", "full", keys, **_DMS_DIALECT)
        )
        for snapshot, rows in full_snapshots(entities, snapshots):
            writer.write(spec, rows, suffix=snapshot.strftime("%Y%m%d"))

    spec = writer.register(
        SourceSpec(
            "dms", "customer", "csv", "incremental", ("customer_id",),
            watermark_column="last_modified_ts", **_DMS_DIALECT,
        )
    )
    for snapshot, rows in incremental_extracts(customers.dms, snapshots):
        writer.write(spec, rows, suffix=snapshot.strftime("%Y%m%d"))

    spec = writer.register(
        SourceSpec(
            "dms", "vehicle_stock", "csv", "incremental", ("vin",),
            watermark_column="last_modified_ts", **_DMS_DIALECT,
        )
    )
    vehicle_records = [v.record for v in fleet.own if v.record is not None]
    for snapshot, rows in incremental_extracts(vehicle_records, snapshots):
        writer.write(spec, rows, suffix=snapshot.strftime("%Y%m%d"))

    spec = writer.register(
        SourceSpec(
            "dms", "sales_contract", "csv", "incremental", ("contract_no",),
            watermark_column="contract_date", **_DMS_DIALECT,
        )
    )
    for suffix, rows in sorted(_by_month(sales.contracts, "contract_date").items()):
        writer.write(spec, rows, suffix=suffix)

def _write_crm(
    writer: SourceWriter, customers: CustomerUniverse, snapshots: list[date]
) -> None:
    spec = writer.register(
        SourceSpec(
            "crm", "customer", "json", "incremental", ("crm_id",),
            watermark_column="last_modified_ts",
        )
    )
    for snapshot, rows in incremental_extracts(customers.crm, snapshots):
        writer.write(spec, rows, suffix=snapshot.strftime("%Y%m%d"))

def _write_workshop(writer: SourceWriter, workshop: WorkshopResult) -> None:
    """daily drops into date-stamped folders"""
    order_spec = writer.register(
        SourceSpec(
            "workshop", "repair_order", "csv", "incremental", ("repair_order_no",),
            watermark_column="checkin_ts", date_partitioned=True,
        )
    )
    line_spec = writer.register(
        SourceSpec(
            "workshop", "repair_order_line", "csv", "incremental",
            ("repair_order_no", "line_no"),
            watermark_column="checkin_ts", date_partitioned=True,
        )
    )

    orders_by_day = _by_day(workshop.repair_orders, "checkin_ts")
    day_of_order = {
        order["repair_order_no"]: str(order["checkin_ts"])[:10]
        for order in workshop.repair_orders
    }
    lines_by_day: dict[str, list[dict]] = defaultdict(list)
    for line in workshop.lines:
        lines_by_day[day_of_order.get(line["repair_order_no"], "unknown")].append(line)

    for day in sorted(orders_by_day):
        writer.write(order_spec, orders_by_day[day], suffix=day)
        if lines_by_day.get(day):
            writer.write(line_spec, lines_by_day[day], suffix=day)

def _write_parts(
    writer: SourceWriter,
    master: MasterData,
    parts: PartsSupplyResult,
    snapshots: list[date],
) -> None:
    spec = writer.register(
        SourceSpec("parts", "supplier", "csv", "full", ("supplier_id",))
    )
    for snapshot, rows in full_snapshots(master.suppliers, snapshots):
        writer.write(spec, rows, suffix=snapshot.strftime("%Y%m%d"))

    spec = writer.register(
        SourceSpec(
            "parts", "part", "csv", "incremental", ("part_no",),
            watermark_column="last_modified_ts",
        )
    )
    for snapshot, rows in incremental_extracts(master.parts, snapshots):
        writer.write(spec, rows, suffix=snapshot.strftime("%Y%m%d"))

    spec = writer.register(
        SourceSpec(
            "parts", "purchase_order_line", "csv", "incremental",
            ("po_no", "po_line_no"), watermark_column="order_date",
        )
    )
    for suffix, rows in sorted(_by_month(parts.purchase_lines, "order_date").items()):
        writer.write(spec, rows, suffix=suffix)

def _write_portal(writer: SourceWriter, portal: PortalResult) -> None:
    spec = writer.register(
        SourceSpec(
            "portal", "warranty_claim", "jsonl", "incremental", ("claim_no",),
            watermark_column="claim_date",
        )
    )
    for suffix, rows in sorted(_by_month(portal.warranty_claims, "claim_date").items()):
        writer.write(spec, rows, suffix=suffix)

    spec = writer.register(
        SourceSpec("portal", "recall_campaign", "json", "full", ("campaign_code",))
    )
    writer.write(spec, portal.recall_campaigns, suffix="full")

    spec = writer.register(
        SourceSpec(
            "portal", "recall_coverage", "jsonl", "full", ("campaign_code", "vin")
        )
    )
    writer.write(spec, portal.recall_coverage, suffix="full")

def _write_finance(writer: SourceWriter, finance: FinanceResult) -> None:
    """one workbook, two sheets"""
    workbook = "finance_plan"
    budget_spec = writer.register(
        SourceSpec(
            "finance", "budget", "xlsx", "full",
            ("dealer_code", "budget_year", "budget_month", "metric_code"),
            file_stem=workbook, sheet_name="budget",
        )
    )
    fx_spec = writer.register(
        SourceSpec(
            "finance", "fx_rate", "xlsx", "full", ("rate_date", "currency_code"),
            file_stem=workbook, sheet_name="fx_rate",
        )
    )
    writer.write(budget_spec, finance.budget, suffix="full")
    writer.write(fx_spec, finance.fx_rates, suffix="full")

def _write_answer_keys(
    output_path: Path, customers: CustomerUniverse, injection_log: list[dict]
) -> None:
    """the two files the platform must never read"""
    _write_plain_csv(output_path / "_injection_log.csv", injection_log)
    _write_plain_csv(output_path / "_mdm_truth.csv", customers.truth)

def _write_plain_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        out = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        out.writeheader()
        out.writerows(rows)
