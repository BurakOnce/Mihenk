"""generate the ctl seed sql from metadata rather than typing it twice"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from data_generator import dirty, reference

MANIFEST = REPO_ROOT / "data" / "_manifest.json"
OUT_SOURCE_CONFIG = REPO_ROOT / "sql" / "00_control" / "60_seed_source_config.sql"
OUT_DQ_RULES = REPO_ROOT / "sql" / "00_control" / "70_seed_dq_rules.sql"
OUT_PROVINCE = REPO_ROOT / "sql" / "03_gold" / "05_ref_province.sql"

LOAD_ORDER = {
    "dms.dealer": 10,
    "dms.employee": 20,
    "dms.model_trim": 30,
    "parts.supplier": 40,
    "parts.part": 50,
    "dms.customer": 60,
    "crm.customer": 70,
    "dms.vehicle_stock": 80,
    "finance.fx_rate": 90,
    "finance.budget": 100,
    "dms.sales_contract": 110,
    "workshop.repair_order": 120,
    "workshop.repair_order_line": 130,
    "parts.purchase_order_line": 140,
    "portal.warranty_claim": 150,
    "portal.recall_campaign": 160,
    "portal.recall_coverage": 170,
}

def q(value) -> str:
    """t-sql string literal, with embedded quotes doubled"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"

def generate_source_config() -> str:
    if not MANIFEST.exists():
        raise SystemExit(
            f"{MANIFEST} not found. Run `python -m data_generator --clean` first - "
            "the ingestion config is generated from what the generator actually wrote."
        )

    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "-- generated file, do not edit by hand - see tools/generate_ctl_seed.py",
        f"-- generated {now} from data/_manifest.json ({len(entries)} entities)",
        "",
        "DELETE FROM ctl.source_config;",
        "GO",
        "",
        "INSERT INTO ctl.source_config",
        "    (source_id, source_system, entity, target_table,",
        "     file_pattern, is_date_partitioned,",
        "     file_format, delimiter, decimal_mark, encoding, has_header, sheet_name,",
        "     load_type, watermark_column, watermark_value, key_columns,",
        "     is_active, load_order, retry_limit, description, created_ts, updated_ts)",
        "SELECT * FROM (VALUES",
    ]

    rows = []
    for index, entry in enumerate(sorted(entries, key=lambda e: LOAD_ORDER.get(
        f"{e['source_system']}.{e['entity']}", 999)), start=1):
        key = f"{entry['source_system']}.{entry['entity']}"
        is_csv = entry["file_format"] == "csv"
        description = (
            f"{entry['source_system'].upper()} {entry['entity'].replace('_', ' ')} "
            f"({entry['load_type']}, {entry['file_count']} file(s) at generation time)"
        )
        rows.append(
            "    ("
            + ", ".join(
                [
                    q(index),
                    q(entry["source_system"]),
                    q(entry["entity"]),
                    q(entry["target_table"]),
                    q(entry["file_pattern"]),
                    q(bool(entry["date_partitioned"])),
                    q(entry["file_format"]),
                    q(entry["delimiter"] if is_csv else None),
                    q(entry["decimal"] if is_csv else None),
                    q(entry["encoding"]),
                    q(bool(entry["has_header"])),
                    q(entry.get("sheet_name")),
                    q(entry["load_type"]),
                    q(entry["watermark_column"]),

                    "NULL",
                    q(",".join(entry["key_columns"])),
                    "1",
                    q(LOAD_ORDER.get(key, 999)),
                    "2",
                    q(description),
                    f"'{now}'",
                    f"'{now}'",
                ]
            )
            + ")"
        )

    lines.append(",\n".join(rows))
    lines.extend([
        ") AS v (source_id, source_system, entity, target_table,",
        "        file_pattern, is_date_partitioned,",
        "        file_format, delimiter, decimal_mark, encoding, has_header, sheet_name,",
        "        load_type, watermark_column, watermark_value, key_columns,",
        "        is_active, load_order, retry_limit, description, created_ts, updated_ts);",
        "GO",
        "",
    ])
    return "\n".join(lines)

@dataclass
class Rule:
    rule_code: str
    rule_name: str
    target_table: str
    rule_type: str
    violation_sql: str
    severity: str = "warning"
    quarantine: bool = False
    target_column: str | None = None
    max_violation_rate: float | None = 0.15
    description: str = ""

def _rules() -> list[Rule]:
    """every rule, with the sql that finds its violations"""
    return [

        Rule(
            dirty.RULE_VIN_FORMAT, "VIN is 17 characters and contains no I, O or Q",
            "silver.repair_order", "regex", target_column="vin",
            severity="critical", quarantine=True,
            description=(
                "ISO 3779 forbids I, O and Q anywhere in a VIN because they are "
                "confused with 1, 0 and 0 when read off a stamped plate. Null VINs "
                "are deliberately excluded here - they are a different defect and "
                "BUSINESS_KEY_NULL reports them, so the two rules stay separable."
            ),
            violation_sql="""
                SELECT repair_order_no AS business_key,
                       CONCAT('vin=', vin, ' len=', CAST(LEN(vin) AS VARCHAR(4))) AS detail
                FROM silver.repair_order
                WHERE vin IS NOT NULL AND vin <> '' AND vin_well_formed = 0
            """,
        ),
        Rule(
            dirty.RULE_VIN_FORMAT, "VIN is 17 characters and contains no I, O or Q (sales)",
            "silver.sales_contract", "regex", target_column="vin",
            severity="critical", quarantine=True,
            violation_sql="""
                SELECT contract_no AS business_key,
                       CONCAT('vin=', vin, ' len=', CAST(LEN(vin) AS VARCHAR(4))) AS detail
                FROM silver.sales_contract
                WHERE vin IS NOT NULL AND vin <> '' AND vin_well_formed = 0
            """,
        ),
        Rule(
            dirty.RULE_VIN_CHECK_DIGIT, "VIN check digit matches ISO 3779",
            "silver.repair_order", "business", target_column="vin",
            severity="warning",
            description=(
                "The rule that separates 'I wrote a data quality check' from 'I "
                "understood the domain'. A VIN can be exactly 17 legal characters "
                "and still be wrong; only position 9 catches a transposition, "
                "which is what human transcription actually produces. Warning "
                "rather than critical: the vehicle is probably real and the VIN "
                "probably has one digit wrong, so quarantining the repair order "
                "would lose genuine revenue to fix a typo. "
                "The check digit is computed once in Silver and stored, so this "
                "rule is a boolean test that runs identically in the Warehouse "
                "procedure and in the Spark runner. Pointing it at "
                "ctl.vw_vin_check_digit instead would tie every DQ run to the "
                "Warehouse and to ADR-0002 item 4, which is unverified - and "
                "rules as data only pays off if the rules do not secretly depend "
                "on one engine."
            ),
            violation_sql="""
                SELECT repair_order_no AS business_key,
                       CONCAT('vin=', vin, ' fails the ISO 3779 check digit') AS detail
                FROM silver.repair_order
                WHERE vin_check_digit_valid = 0
            """,
        ),
        Rule(
            dirty.RULE_VIN_CHECK_DIGIT, "VIN check digit matches ISO 3779 (sales)",
            "silver.sales_contract", "business", target_column="vin",
            severity="warning",
            violation_sql="""
                SELECT contract_no AS business_key,
                       CONCAT('vin=', vin, ' fails the ISO 3779 check digit') AS detail
                FROM silver.sales_contract
                WHERE vin_check_digit_valid = 0
            """,
        ),
        Rule(
            dirty.RULE_VIN_DUPLICATE_NEW_SALE, "A VIN can be sold as new only once",
            "silver.sales_contract", "unique", target_column="vin",
            severity="critical", quarantine=True,
            description=(
                "Physically impossible and genuinely common. A vehicle leaves the "
                "factory once; a second 'NEW' contract for the same VIN is either "
                "a duplicated record or a used car booked under the wrong type. "
                "Either way it double-counts a unit sale and inflates revenue."
            ),
            violation_sql="""
                SELECT contract_no AS business_key,
                       CONCAT('vin=', vin, ' appears on ',
                              CAST(sale_count AS VARCHAR(6)), ' new-vehicle contracts') AS detail
                FROM (
                    SELECT contract_no, vin,
                           COUNT(*) OVER (PARTITION BY vin) AS sale_count
                    FROM silver.sales_contract
                    WHERE sale_type = 'NEW' AND vin IS NOT NULL AND vin <> ''
                ) AS d
                WHERE sale_count > 1
            """,
        ),
        Rule(
            dirty.RULE_VIN_ORPHAN, "Repair order VIN exists in the vehicle master",
            "silver.repair_order", "referential", target_column="vin",
            severity="warning",
            max_violation_rate=0.30,
            description=(
                "Fabric Warehouse constraints are NOT ENFORCED, so referential "
                "integrity is our job. Deliberately a warning and NOT quarantined: "
                "in automotive this is often legitimate - a car bought from another "
                "dealer in the network arrives for service and the vehicle master "
                "has genuinely never seen it. Gold creates an inferred member for "
                "these rather than dropping the fact. The rule exists to measure "
                "how often it happens, not to reject it."
            ),
            violation_sql="""
                SELECT ro.repair_order_no AS business_key,
                       CONCAT('vin=', ro.vin, ' not present in silver.vehicle') AS detail
                FROM silver.repair_order AS ro
                WHERE ro.vin IS NOT NULL AND ro.vin <> ''
                  AND NOT EXISTS (SELECT 1 FROM silver.vehicle AS v WHERE v.vin = ro.vin)
            """,
        ),

        Rule(
            dirty.RULE_PLATE_FORMAT, "Plate matches the Turkish format",
            "silver.repair_order", "regex", target_column="plate_masked",
            severity="warning",
            description=(
                "Turkish plates are a province code, then one to three letters, "
                "then two to five digits, with the letter and digit counts "
                "constrained together. The letter class excludes Q, W and X, which "
                "do not exist in the Turkish alphabet. T-SQL has no regex, so this "
                "was five LIKE patterns - but Silver only ever exposes the "
                "PII-masked plate (mask_plate collapses every letter run to a "
                "literal '***', regardless of whether it was 1, 2 or 3 letters), "
                "so the letter/digit-count correlation this rule was designed to "
                "check is gone by the time it can run. What's left checkable is "
                "the coarser shape: two digits, '***', two-to-five digits."
            ),
            violation_sql="""
                SELECT repair_order_no AS business_key,
                       CONCAT('plate=', plate_masked) AS detail
                FROM silver.repair_order
                WHERE plate_masked IS NOT NULL AND plate_masked <> ''
                  AND plate_masked NOT LIKE '[0-9][0-9] *** [0-9][0-9]'
                  AND plate_masked NOT LIKE '[0-9][0-9] *** [0-9][0-9][0-9]'
                  AND plate_masked NOT LIKE '[0-9][0-9] *** [0-9][0-9][0-9][0-9]'
                  AND plate_masked NOT LIKE '[0-9][0-9] *** [0-9][0-9][0-9][0-9][0-9]'
            """,
        ),
        Rule(
            dirty.RULE_PLATE_PROVINCE, "Plate province code is between 01 and 81",
            "silver.repair_order", "range", target_column="plate_masked",
            severity="warning",
            description=(
                "Turkey has 81 provinces. A plate beginning 84 is not a formatting "
                "problem, it is a value that cannot exist - which is why this is a "
                "separate rule from the format check and would be actioned "
                "differently. Reads plate_masked rather than the raw plate: "
                "mask_plate only touches the letter run, so the province digits "
                "survive masking untouched and this check loses nothing by running "
                "after PII masking, unlike PLATE_FORMAT."
            ),
            violation_sql="""
                SELECT repair_order_no AS business_key,
                       CONCAT('plate=', plate_masked, ' province=',
                              LEFT(plate_masked, 2)) AS detail
                FROM silver.repair_order
                WHERE plate_masked IS NOT NULL AND LEN(plate_masked) >= 2
                  AND (TRY_CAST(LEFT(plate_masked, 2) AS INT) IS NULL
                       OR TRY_CAST(LEFT(plate_masked, 2) AS INT) < 1
                       OR TRY_CAST(LEFT(plate_masked, 2) AS INT) > 81)
            """,
        ),

        Rule(
            dirty.RULE_ODOMETER_ROLLBACK, "Odometer never decreases for a VIN",
            "silver.repair_order", "business", target_column="odometer_km",
            severity="critical", quarantine=True,
            description=(
                "The best argument in this project for why data quality belongs in "
                "the platform rather than in source-system field validation. Each "
                "individual reading is perfectly plausible; the value is only wrong "
                "in the context of the same VIN's other readings, which no single "
                "form can see. Critical because a rolled-back odometer corrupts "
                "every mileage-based measure downstream - service interval "
                "compliance, average km at repair, warranty distance eligibility."
            ),
            violation_sql="""
                SELECT repair_order_no AS business_key,
                       CONCAT('vin=', vin, ' reading=', CAST(odometer_km AS VARCHAR(12)),
                              ' previous=', CAST(previous_km AS VARCHAR(12)),
                              ' on ', CAST(previous_ts AS VARCHAR(10))) AS detail
                FROM (
                    SELECT repair_order_no, vin, odometer_km, checkin_ts,
                           LAG(odometer_km) OVER (PARTITION BY vin ORDER BY checkin_ts) AS previous_km,
                           LAG(checkin_ts)  OVER (PARTITION BY vin ORDER BY checkin_ts) AS previous_ts
                    FROM silver.repair_order
                    WHERE vin IS NOT NULL AND vin <> '' AND odometer_km IS NOT NULL
                ) AS r
                WHERE previous_km IS NOT NULL AND odometer_km < previous_km
            """,
        ),

        Rule(
            dirty.RULE_RO_DATE_SEQUENCE, "Repair order stages run in order",
            "silver.repair_order", "business",
            severity="critical", quarantine=True,
            description=(
                "The accumulating snapshot's stage columns are the source of every "
                "duration measure in the aftersales report. A delivery timestamp "
                "before check-in does not just look wrong, it produces a negative "
                "cycle time that silently drags the average down. Nulls are allowed "
                "throughout - an unfinished order legitimately has no later stages."
            ),
            violation_sql="""
                SELECT repair_order_no AS business_key,
                       CONCAT('checkin=', LEFT(CAST(checkin_ts AS VARCHAR(30)), 19),
                              ' repair_start=', COALESCE(LEFT(CAST(repair_start_ts AS VARCHAR(30)), 19), '-'),
                              ' delivery=', COALESCE(LEFT(CAST(delivery_ts AS VARCHAR(30)), 19), '-')) AS detail
                FROM silver.repair_order
                WHERE (appointment_date IS NOT NULL AND appointment_date > CAST(checkin_ts AS DATE))
                   OR (inspection_ts   IS NOT NULL AND inspection_ts   < checkin_ts)
                   OR (repair_start_ts IS NOT NULL AND repair_start_ts < checkin_ts)
                   OR (repair_end_ts   IS NOT NULL AND repair_end_ts   < repair_start_ts)
                   OR (qc_ts           IS NOT NULL AND qc_ts           < repair_end_ts)
                   OR (delivery_ts     IS NOT NULL AND delivery_ts     < checkin_ts)
            """,
        ),

        Rule(
            dirty.RULE_LABOUR_HOURS_NEGATIVE, "Labour hours are not negative",
            "silver.repair_order_line", "range", target_column="labour_hours",
            severity="critical", quarantine=True,
            violation_sql="""
                SELECT CONCAT(repair_order_no, '#', CAST(line_no AS VARCHAR(6))) AS business_key,
                       CONCAT('labour_hours=', CAST(labour_hours AS VARCHAR(20))) AS detail
                FROM silver.repair_order_line
                WHERE labour_hours < 0
            """,
        ),
        Rule(
            dirty.RULE_LABOUR_HOURS_EXCESSIVE, "A single labour line stays under 100 hours",
            "silver.repair_order_line", "range", target_column="labour_hours",
            severity="warning",
            description=(
                "One operation line cannot plausibly take two and a half working "
                "weeks. The threshold is set well above the longest real job in "
                "this dataset - body and paint tops out around 30 hours - so it "
                "flags data entry, not busy workshops. A warning rather than "
                "critical because the labour was probably done; the number is what "
                "is wrong."
            ),
            violation_sql="""
                SELECT CONCAT(repair_order_no, '#', CAST(line_no AS VARCHAR(6))) AS business_key,
                       CONCAT('labour_hours=', CAST(labour_hours AS VARCHAR(20))) AS detail
                FROM silver.repair_order_line
                WHERE labour_hours > 100
            """,
        ),
        Rule(
            dirty.RULE_WARRANTY_AMOUNT_OVERFLOW,
            "Warranty amount does not exceed the line total",
            "silver.repair_order_line", "business", target_column="warranty_amount",
            severity="critical", quarantine=True,
            description=(
                "The manufacturer cannot reimburse more than the work is worth. "
                "This one is also a cascade: because the repair order header "
                "carries its own warranty total, a line pushed above its value "
                "also breaks HEADER_LINE_MISMATCH. The injection log records that "
                "cascade so the second detection is scored as expected rather than "
                "as a false positive."
            ),
            violation_sql="""
                SELECT CONCAT(repair_order_no, '#', CAST(line_no AS VARCHAR(6))) AS business_key,
                       CONCAT('warranty=', CAST(warranty_amount AS VARCHAR(24)),
                              ' line=', CAST(line_amount AS VARCHAR(24))) AS detail
                FROM silver.repair_order_line
                WHERE warranty_amount > line_amount + 0.01
            """,
        ),
        Rule(
            dirty.RULE_HEADER_LINE_MISMATCH,
            "Repair order header totals equal the sum of their lines",
            "silver.repair_order", "business",
            severity="warning",
            description=(
                "The header stores totals its lines already add up to. That "
                "redundancy is how real dealer systems work, and it is deliberate "
                "here: it gives the platform a reconciliation with a knowable "
                "answer. The generator proves the totals tie before injection, so "
                "every mismatch found is one that was created on purpose."
            ),
            violation_sql="""
                SELECT h.repair_order_no AS business_key,
                       CONCAT('header_warranty=', CAST(h.total_warranty_amount AS VARCHAR(24)),
                              ' line_sum=', CAST(COALESCE(l.warranty_sum, 0) AS VARCHAR(24))) AS detail
                FROM silver.repair_order AS h
                LEFT JOIN (
                    SELECT repair_order_no,
                           SUM(warranty_amount) AS warranty_sum,
                           SUM(line_amount)     AS line_sum
                    FROM silver.repair_order_line
                    GROUP BY repair_order_no
                ) AS l ON l.repair_order_no = h.repair_order_no
                WHERE ABS(h.total_warranty_amount - COALESCE(l.warranty_sum, 0)) > 0.02
                   OR ABS(h.total_labour_amount + h.total_part_amount
                          - COALESCE(l.line_sum, 0)) > 0.02
            """,
        ),

        Rule(
            dirty.RULE_PART_NO_ORPHAN, "Repair order line part exists in the part master",
            "silver.repair_order_line", "referential", target_column="part_no",
            severity="critical", quarantine=True,
            violation_sql="""
                SELECT CONCAT(l.repair_order_no, '#', CAST(l.line_no AS VARCHAR(6))) AS business_key,
                       CONCAT('part_no=', l.part_no, ' not present in silver.part') AS detail
                FROM silver.repair_order_line AS l
                WHERE l.line_type = 'PART' AND l.part_no IS NOT NULL AND l.part_no <> ''
                  AND NOT EXISTS (SELECT 1 FROM silver.part AS p WHERE p.part_no = l.part_no)
            """,
        ),
        Rule(
            dirty.RULE_PART_NO_ORPHAN, "Purchase order line part exists in the part master",
            "silver.purchase_order_line", "referential", target_column="part_no",
            severity="critical", quarantine=True,
            violation_sql="""
                SELECT CONCAT(l.po_no, '#', CAST(l.po_line_no AS VARCHAR(6))) AS business_key,
                       CONCAT('part_no=', l.part_no, ' not present in silver.part') AS detail
                FROM silver.purchase_order_line AS l
                WHERE l.part_no IS NOT NULL AND l.part_no <> ''
                  AND NOT EXISTS (SELECT 1 FROM silver.part AS p WHERE p.part_no = l.part_no)
            """,
        ),
        Rule(
            "DEALER_ORPHAN", "Repair order dealer exists in the dealer master",
            "silver.repair_order", "referential", target_column="dealer_code",
            severity="critical", quarantine=True,
            description=(
                "Not an injected defect - this rule exists to prove the framework "
                "reports zero when the data is clean. A DQ suite in which every "
                "rule always fires is indistinguishable from a DQ suite that is "
                "broken."
            ),
            violation_sql="""
                SELECT ro.repair_order_no AS business_key,
                       CONCAT('dealer_code=', ro.dealer_code) AS detail
                FROM silver.repair_order AS ro
                WHERE ro.dealer_code IS NOT NULL AND ro.dealer_code <> ''
                  AND NOT EXISTS (SELECT 1 FROM silver.dealer AS d
                                  WHERE d.dealer_code = ro.dealer_code)
            """,
        ),

        Rule(
            dirty.RULE_BUSINESS_KEY_NULL, "Repair order carries a VIN",
            "silver.repair_order", "not_null", target_column="vin",
            severity="critical", quarantine=True,
            violation_sql="""
                SELECT repair_order_no AS business_key,
                       'vin is null or blank' AS detail
                FROM silver.repair_order
                WHERE vin IS NULL OR vin = ''
            """,
        ),
        Rule(
            dirty.RULE_BUSINESS_KEY_NULL, "Sales contract carries a customer",
            "silver.sales_contract", "not_null", target_column="customer_id",
            severity="critical", quarantine=True,
            violation_sql="""
                SELECT contract_no AS business_key,
                       'customer_id is null or blank' AS detail
                FROM silver.sales_contract
                WHERE customer_id IS NULL OR customer_id = ''
            """,
        ),
        Rule(
            dirty.RULE_DATE_FORMAT, "Contract dates parsed to a real date",
            "silver.sales_contract", "business", target_column="contract_date",
            severity="critical", quarantine=True,
            description=(
                "The source file mixes ISO dates with Turkish dd.mm.yyyy in the "
                "same column. Silver parses both; this rule catches whatever it "
                "could not. The danger being guarded against is not a failed load "
                "- it is a silent NULL for the minority format, which nobody "
                "notices until a month is missing from a report."
            ),
            violation_sql="""
                SELECT contract_no AS business_key,
                       CONCAT('raw contract_date=', COALESCE(contract_date_raw, '<null>')) AS detail
                FROM silver.sales_contract
                WHERE contract_date IS NULL
                  AND contract_date_raw IS NOT NULL AND contract_date_raw <> ''
            """,
        ),

        Rule(
            "MODEL_YEAR_RANGE", "Model year is within one year of production",
            "silver.vehicle", "range", target_column="model_year",
            severity="warning",
            description=(
                "A car built in the last quarter is normally registered as next "
                "year's model, so a gap of one is expected and a gap of four is a "
                "defect. The rule encodes the industry practice rather than a "
                "generic 'is it a plausible year' check."
            ),
            violation_sql="""
                SELECT vin AS business_key,
                       CONCAT('model_year=', CAST(model_year AS VARCHAR(6)),
                              ' production=', CAST(production_date AS VARCHAR(10))) AS detail
                FROM silver.vehicle
                WHERE model_year IS NOT NULL AND production_date IS NOT NULL
                  AND (model_year - YEAR(production_date) > 1
                       OR model_year - YEAR(production_date) < 0)
            """,
        ),
        Rule(
            "FX_RATE_MISSING", "Every foreign-currency amount has a rate to convert it",
            "silver.sales_contract", "referential", target_column="currency_code",
            severity="critical", quarantine=True,
            description=(
                "Rates are published on business days only, so a contract signed "
                "at a weekend has no rate of its own and Silver forward-fills the "
                "last published one. This rule proves the forward fill actually "
                "covered every row - a missed conversion does not fail loudly, it "
                "reports a lira amount that is really euros."
            ),
            violation_sql="""
                SELECT c.contract_no AS business_key,
                       CONCAT('currency=', c.currency_code,
                              ' date=', CAST(c.contract_date AS VARCHAR(10))) AS detail
                FROM silver.sales_contract AS c
                WHERE c.currency_code <> 'TRY'
                  AND c.net_sale_amount IS NULL
            """,
        ),
        Rule(
            "SALE_DATE_SEQUENCE", "Contract, delivery and registration run in order",
            "silver.sales_contract", "business",
            severity="warning",
            violation_sql="""
                SELECT contract_no AS business_key,
                       CONCAT('contract=', CAST(contract_date AS VARCHAR(10)),
                              ' delivery=', COALESCE(CAST(delivery_date AS VARCHAR(10)), '-'),
                              ' registration=', COALESCE(CAST(registration_date AS VARCHAR(10)), '-')) AS detail
                FROM silver.sales_contract
                WHERE (delivery_date IS NOT NULL AND delivery_date < contract_date)
                   OR (registration_date IS NOT NULL AND delivery_date IS NOT NULL
                       AND registration_date < delivery_date)
            """,
        ),
        Rule(
            "DISCOUNT_RATE_RANGE", "Discount is between zero and the list price",
            "silver.sales_contract", "range", target_column="discount_amount",
            severity="warning",
            violation_sql="""
                SELECT contract_no AS business_key,
                       CONCAT('list=', CAST(list_price AS VARCHAR(24)),
                              ' discount=', CAST(discount_amount AS VARCHAR(24))) AS detail
                FROM silver.sales_contract
                WHERE discount_amount < 0 OR discount_amount > list_price
            """,
        ),
        Rule(
            "MASTER_CUSTOMER_ASSIGNED", "Every contract resolves to an MDM golden record",
            "silver.sales_contract", "referential", target_column="master_customer_id",
            severity="warning",
            max_violation_rate=0.25,
            description=(
                "Measures MDM coverage, not source data quality. A contract whose "
                "customer could not be resolved to a golden record still loads and "
                "points at the Unknown member - but the rate is the honest "
                "headline number for how well the matching worked, and it belongs "
                "on the data quality page rather than in a slide."
            ),
            violation_sql="""
                SELECT contract_no AS business_key,
                       CONCAT('customer_id=', COALESCE(customer_id, '<null>'),
                              ' has no master_customer_id') AS detail
                FROM silver.sales_contract
                WHERE master_customer_id IS NULL
                  AND customer_id IS NOT NULL AND customer_id <> ''
            """,
        ),
    ]

def generate_province_ref() -> str:
    """turkey's 81 provinces, generated from the same table the data uses"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    provinces = reference.PROVINCES

    lines = [
        "-- generated file, do not edit by hand - see tools/generate_ctl_seed.py",
        f"-- generated {now} from src/data_generator/reference.py ({len(provinces)} provinces)",
        "",
        "CREATE TABLE gold.ref_province",
        "(",
        "    province_code   VARCHAR(2)      NOT NULL,",
        "    province_name   VARCHAR(40)     NOT NULL,",
        "    region          VARCHAR(30)     NOT NULL,",
        "    population_m    DECIMAL(9,2)    NULL",
        ");",
        "GO",
        "",
        "INSERT INTO gold.ref_province (province_code, province_name, region, population_m)",
        "SELECT * FROM (VALUES",
    ]

    rows = [
        f"    ({q(p.plate_code)}, {q(p.name)}, {q(p.region)}, {p.population_m})"
        for p in provinces
    ]
    lines.append(",\n".join(rows))
    lines += [
        ") AS v (province_code, province_name, region, population_m);",
        "GO",
        "",
        "-- The Unknown member, so a customer with an unparseable city code still",
        "-- resolves to a region rather than dropping out of every regional visual.",
        "INSERT INTO gold.ref_province (province_code, province_name, region, population_m)",
        "VALUES ('-1', 'Bilinmiyor', 'Bilinmiyor', NULL);",
        "GO",
        "",
    ]
    return "\n".join(lines)

def _tidy(sql: str) -> str:
    """collapse the indented triple-quoted sql into something readable in a cell"""
    lines = [line.rstrip() for line in sql.strip("\n").split("\n")]
    if not lines:
        return ""
    indent = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    return "\n".join(l[indent:] if len(l) >= indent else l for l in lines).strip()

def generate_dq_rules() -> str:
    rules = _rules()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    injectable = {
        value for name, value in vars(dirty).items()
        if name.startswith("RULE_") and isinstance(value, str)
    }
    covered = {r.rule_code for r in rules}
    uncovered = injectable - covered
    if uncovered:
        raise SystemExit(
            "These defect types can be injected but no DQ rule looks for them:\n  "
            + "\n  ".join(sorted(uncovered))
            + "\nAdd a rule in tools/generate_ctl_seed.py or the measured recall "
              "in Phase 3 will be wrong."
        )

    lines = [
        "-- generated file, do not edit by hand - see tools/generate_ctl_seed.py",
        f"-- generated {now} - {len(rules)} rules, {len(covered)} codes, "
        f"{len(injectable)} injectable defects covered",
        "",
        "DELETE FROM ctl.dq_rule;",
        "GO",
        "",
    ]

    for index, rule in enumerate(rules, start=1):
        lines.append(f"-- {index:>2}. {rule.rule_code} :: {rule.rule_name}")
        lines.append("INSERT INTO ctl.dq_rule")
        lines.append(
            "    (rule_id, rule_code, rule_name, target_layer, target_table, target_column,"
        )
        lines.append(
            "     rule_type, violation_sql, severity, quarantine_on_fail,"
        )
        lines.append(
            "     max_violation_rate, is_active, description, created_ts)"
        )
        lines.append("VALUES")
        lines.append(
            f"    ({index}, {q(rule.rule_code)}, {q(rule.rule_name)}, 'silver',"
        )
        lines.append(
            f"     {q(rule.target_table)}, {q(rule.target_column)}, {q(rule.rule_type)},"
        )
        lines.append(f"     {q(_tidy(rule.violation_sql))},")
        lines.append(
            f"     {q(rule.severity)}, {q(rule.quarantine)}, "
            f"{q(rule.max_violation_rate)}, 1, {q(rule.description or rule.rule_name)}, '{now}');"
        )
        lines.append("GO")
        lines.append("")

    return "\n".join(lines)

def main() -> int:
    OUT_SOURCE_CONFIG.parent.mkdir(parents=True, exist_ok=True)

    source_sql = generate_source_config()
    OUT_SOURCE_CONFIG.write_text(source_sql, encoding="utf-8")
    print(f"wrote {OUT_SOURCE_CONFIG.relative_to(REPO_ROOT)}")

    rules_sql = generate_dq_rules()
    OUT_DQ_RULES.write_text(rules_sql, encoding="utf-8")
    print(f"wrote {OUT_DQ_RULES.relative_to(REPO_ROOT)}")

    OUT_PROVINCE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PROVINCE.write_text(generate_province_ref(), encoding="utf-8")
    print(f"wrote {OUT_PROVINCE.relative_to(REPO_ROOT)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
