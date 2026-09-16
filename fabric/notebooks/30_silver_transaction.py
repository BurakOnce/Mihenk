
# %% tags=["parameters"]
batch_id = "manual-dev-run"
pii_salt = "REPLACE_WITH_KEY_VAULT_SECRET"

# %%
# %run 00_silver_common

# %%
fx_rates = build_fx_lookup(spark.table("silver.ref_fx_rate"))

# %%
xref = (
    spark.table("silver.customer_xref")
    .filter(F.col("dms_customer_id").isNotNull())
    .select(
        F.col("dms_customer_id").alias("customer_id"),
        F.col("master_customer_id"),
    )
    .dropDuplicates(["customer_id"])
)

# %%
print(f"fx rate rows       : {fx_rates.count():,}")
# %%
print(f"customer xref rows : {xref.count():,}")

# %%
contracts_raw = spark.table("bronze.dms_sales_contract")

# %%
contracts = (
    latest_by_key(contracts_raw, ["contract_no"], "contract_date")

    .withColumn("contract_date_raw", F.col("contract_date"))
    .withColumn("delivery_date_raw", F.col("delivery_date"))
    .withColumn("registration_date_raw", F.col("registration_date"))
    .withColumn("contract_date", parse_date("contract_date_raw"))
    .withColumn("delivery_date", parse_date("delivery_date_raw"))
    .withColumn("invoice_date", parse_date("invoice_date"))
    .withColumn("registration_date", parse_date("registration_date_raw"))
    .withColumn("vin", F.upper(clean_string("vin")))
    .withColumn("trade_in_vin", F.upper(clean_string("trade_in_vin")))

    .withColumn("vin_well_formed", vin_is_well_formed("vin").cast("int"))
    .withColumn("vin_check_digit_valid", vin_check_digit_valid("vin"))
    .withColumn("dealer_code", clean_string("dealer_code"))
    .withColumn("salesperson_id", clean_string("salesperson_id"))
    .withColumn("customer_id", clean_string("customer_id"))
    .withColumn("sale_type", F.upper(clean_string("sale_type")))
    .withColumn("payment_type", F.upper(clean_string("payment_type")))
    .withColumn("channel", F.upper(clean_string("channel")))
    .withColumn("currency_code", F.upper(clean_string("currency_code")))
    .withColumn("is_campaign", F.col("is_campaign").cast("int"))
    .withColumn("list_price", parse_decimal("list_price", turkish=True))
    .withColumn("discount_amount", parse_decimal("discount_amount", turkish=True))
    .withColumn("net_sale_amount", parse_decimal("net_sale_amount", turkish=True))
    .withColumn("trade_in_amount", parse_decimal("trade_in_amount", turkish=True))

    .withColumn("plate_number", F.upper(clean_string("plate_number")))
    .withColumn("plate_hash", hash_pii("plate_number", pii_salt))
    .withColumn("plate_masked", mask_plate("plate_number"))
)

# %%
contracts = convert_to_try(
    contracts,
    fx_rates,
    amount_columns=["list_price", "discount_amount", "net_sale_amount", "trade_in_amount"],
    currency_column="currency_code",
    date_column="contract_date",
)

# %%
vehicle_arrival = spark.table("silver.vehicle").select(
    F.col("vin"), F.col("arrival_date").alias("vehicle_arrival_date")
)

# %%
contracts = (
    contracts
    .join(vehicle_arrival, on="vin", how="left")
    .withColumn(
        "days_in_stock",
        F.when(
            F.col("vehicle_arrival_date").isNotNull() & F.col("delivery_date").isNotNull(),
            F.datediff(F.col("delivery_date"), F.col("vehicle_arrival_date")),
        ),
    )
    .join(xref, on="customer_id", how="left")
    .withColumn(
        "discount_rate",
        F.when(
            F.col("list_price") > 0,
            (F.col("discount_amount") / F.col("list_price")).cast("decimal(9,6)"),
        ),
    )
    .withColumn(
        "gross_margin_amount",
        (F.col("net_sale_amount") - F.coalesce(F.col("trade_in_amount"), F.lit(0)))
        .cast("decimal(18,2)"),
    )
    .drop("plate_number")
)

# %%
contract_columns = [
    "contract_no", "contract_date", "delivery_date", "invoice_date",
    "registration_date", "vin", "vin_well_formed", "vin_check_digit_valid",
    "dealer_code", "salesperson_id", "customer_id",
    "master_customer_id", "sale_type", "model_trim_code", "plate_hash",
    "plate_masked", "currency_code", "fx_rate_to_try", "list_price",
    "discount_amount", "discount_rate", "net_sale_amount", "trade_in_vin",
    "trade_in_amount", "gross_margin_amount", "payment_type", "channel",
    "is_campaign", "days_in_stock",
]

# %%
contracts = add_silver_audit(contracts, batch_id, "dms", contract_columns).select(
    *contract_columns,
    "contract_date_raw", "delivery_date_raw", "registration_date_raw",
    *SILVER_AUDIT_COLUMNS,
)

# %%
result_contracts = merge_into_silver(contracts, "silver.sales_contract", ["contract_no"])
# %%
print(f"silver.sales_contract : {result_contracts}")

# %%
orders_raw = spark.table("bronze.workshop_repair_order")

# %%
orders = (
    latest_by_key(orders_raw, ["repair_order_no"], "checkin_ts")
    .withColumn("vin", F.upper(clean_string("vin")))
    .withColumn("vin_well_formed", vin_is_well_formed("vin").cast("int"))
    .withColumn("vin_check_digit_valid", vin_check_digit_valid("vin"))
    .withColumn("dealer_code", clean_string("dealer_code"))
    .withColumn("customer_id", clean_string("customer_id"))
    .withColumn("service_advisor_id", clean_string("service_advisor_id"))
    .withColumn("technician_id", clean_string("technician_id"))
    .withColumn("service_type_code", F.upper(clean_string("service_type_code")))
    .withColumn("status", F.upper(clean_string("status")))
    .withColumn("odometer_km", F.col("odometer_km").cast("bigint"))
    .withColumn("is_warranty", F.col("is_warranty").cast("int"))
    .withColumn("appointment_date", parse_date("appointment_date"))
    .withColumn("checkin_ts", parse_timestamp("checkin_ts"))
    .withColumn("inspection_ts", parse_timestamp("inspection_ts"))
    .withColumn("parts_wait_start_ts", parse_timestamp("parts_wait_start_ts"))
    .withColumn("parts_ready_ts", parse_timestamp("parts_ready_ts"))
    .withColumn("repair_start_ts", parse_timestamp("repair_start_ts"))
    .withColumn("repair_end_ts", parse_timestamp("repair_end_ts"))
    .withColumn("qc_ts", parse_timestamp("qc_ts"))
    .withColumn("delivery_ts", parse_timestamp("delivery_ts"))
    .withColumn("total_labour_amount", parse_decimal("total_labour_amount"))
    .withColumn("total_part_amount", parse_decimal("total_part_amount"))
    .withColumn("total_warranty_amount", parse_decimal("total_warranty_amount"))
    .withColumn("customer_payable_amount", parse_decimal("customer_payable_amount"))
    .withColumn("plate_number", F.upper(clean_string("plate_number")))
    .withColumn("plate_hash", hash_pii("plate_number", pii_salt))
    .withColumn("plate_masked", mask_plate("plate_number"))
    .drop("plate_number")
)

# %%
def hours_between(start: str, end: str) -> "F.Column":
    """geçen saat, iki uçtan biri eksikse null"""
    return F.when(
        F.col(start).isNotNull() & F.col(end).isNotNull(),
        ((F.unix_timestamp(F.col(end)) - F.unix_timestamp(F.col(start))) / 3600.0)
        .cast("decimal(12,2)"),
    )

# %%
orders = (
    orders
    .withColumn("inspection_wait_hours", hours_between("checkin_ts", "inspection_ts"))
    .withColumn("parts_wait_hours", hours_between("parts_wait_start_ts", "parts_ready_ts"))
    .withColumn("repair_duration_hours", hours_between("repair_start_ts", "repair_end_ts"))
    .withColumn("qc_wait_hours", hours_between("repair_end_ts", "qc_ts"))
    .withColumn("collection_wait_hours", hours_between("qc_ts", "delivery_ts"))
    .withColumn("total_cycle_hours", hours_between("checkin_ts", "delivery_ts"))

    .withColumn(
        "touch_time_hours",
        F.coalesce(F.col("repair_duration_hours"), F.lit(0))
        + F.coalesce(F.col("inspection_wait_hours"), F.lit(0)),
    )
    .withColumn("is_open", F.when(F.col("delivery_ts").isNull(), 1).otherwise(0))
    .join(xref, on="customer_id", how="left")
)

# %%
order_columns = [
    "repair_order_no", "dealer_code", "vin", "vin_well_formed",
    "vin_check_digit_valid", "plate_hash", "plate_masked",
    "customer_id", "master_customer_id", "service_advisor_id", "technician_id",
    "service_type_code", "odometer_km", "is_warranty", "status", "is_open",
    "appointment_date", "checkin_ts", "inspection_ts", "parts_wait_start_ts",
    "parts_ready_ts", "repair_start_ts", "repair_end_ts", "qc_ts", "delivery_ts",
    "inspection_wait_hours", "parts_wait_hours", "repair_duration_hours",
    "qc_wait_hours", "collection_wait_hours", "total_cycle_hours",
    "touch_time_hours",
    "total_labour_amount", "total_part_amount", "total_warranty_amount",
    "customer_payable_amount",
]

# %%
orders = add_silver_audit(orders, batch_id, "workshop", order_columns).select(
    *order_columns, *SILVER_AUDIT_COLUMNS
)

# %%
result_orders = merge_into_silver(
    orders, "silver.repair_order", ["repair_order_no"]
)
# %%
print(f"silver.repair_order : {result_orders}")

# %%
lines_raw = spark.table("bronze.workshop_repair_order_line")

# %%
lines = (
    latest_by_key(lines_raw, ["repair_order_no", "line_no"], "_ingest_ts")
    .withColumn("repair_order_no", clean_string("repair_order_no"))
    .withColumn("line_no", F.col("line_no").cast("int"))
    .withColumn("line_type", F.upper(clean_string("line_type")))
    .withColumn("part_no", clean_string("part_no"))
    .withColumn("operation_code", clean_string("operation_code"))
    .withColumn("description", clean_string("description"))
    .withColumn("quantity", parse_decimal("quantity", scale=3))
    .withColumn("labour_hours", parse_decimal("labour_hours"))
    .withColumn("unit_price", parse_decimal("unit_price"))
    .withColumn("discount_amount", parse_decimal("discount_amount"))
    .withColumn("line_amount", parse_decimal("line_amount"))
    .withColumn("warranty_amount", parse_decimal("warranty_amount"))
    .withColumn("customer_amount", parse_decimal("customer_amount"))
)

# %%
line_columns = [
    "repair_order_no", "line_no", "line_type", "part_no", "operation_code",
    "description", "quantity", "labour_hours", "unit_price", "discount_amount",
    "line_amount", "warranty_amount", "customer_amount",
]
# %%
lines = add_silver_audit(lines, batch_id, "workshop", line_columns).select(
    *line_columns, *SILVER_AUDIT_COLUMNS
)

# %%
result_lines = merge_into_silver(
    lines, "silver.repair_order_line", ["repair_order_no", "line_no"]
)
# %%
print(f"silver.repair_order_line : {result_lines}")

# %%
po_raw = spark.table("bronze.parts_purchase_order_line")

# %%
purchases = (
    latest_by_key(po_raw, ["po_no", "po_line_no"], "order_date")
    .withColumn("po_no", clean_string("po_no"))
    .withColumn("po_line_no", F.col("po_line_no").cast("int"))
    .withColumn("supplier_id", clean_string("supplier_id"))
    .withColumn("part_no", clean_string("part_no"))
    .withColumn("status", F.upper(clean_string("status")))
    .withColumn("currency_code", F.upper(clean_string("currency_code")))
    .withColumn("order_date", parse_date("order_date"))
    .withColumn("promised_date", parse_date("promised_date"))
    .withColumn("delivery_date", parse_date("delivery_date"))
    .withColumn("ordered_quantity", parse_decimal("ordered_quantity", scale=3))
    .withColumn("received_quantity", parse_decimal("received_quantity", scale=3))
    .withColumn("unit_cost", parse_decimal("unit_cost"))
    .withColumn("line_amount", parse_decimal("line_amount"))
)

# %%
purchases = convert_to_try(
    purchases, fx_rates,
    amount_columns=["unit_cost", "line_amount"],
    currency_column="currency_code",
    date_column="order_date",
)

# %%
purchases = (
    purchases

    .withColumn(
        "delay_days",
        F.when(
            F.col("delivery_date").isNotNull() & F.col("promised_date").isNotNull(),
            F.datediff(F.col("delivery_date"), F.col("promised_date")),
        ),
    )
    .withColumn(
        "is_late",
        F.when(F.col("delay_days").isNull(), None)
        .when(F.col("delay_days") > 2, 1).otherwise(0),
    )
    .withColumn(
        "shortfall_quantity",
        (F.coalesce(F.col("ordered_quantity"), F.lit(0))
         - F.coalesce(F.col("received_quantity"), F.lit(0))).cast("decimal(18,3)"),
    )
)

# %%
po_columns = [
    "po_no", "po_line_no", "order_date", "supplier_id", "part_no",
    "ordered_quantity", "received_quantity", "shortfall_quantity",
    "promised_date", "delivery_date", "delay_days", "is_late", "status",
    "currency_code", "fx_rate_to_try", "unit_cost", "line_amount",
]
# %%
purchases = add_silver_audit(purchases, batch_id, "parts", po_columns).select(
    *po_columns, *SILVER_AUDIT_COLUMNS
)

# %%
result_po = merge_into_silver(
    purchases, "silver.purchase_order_line", ["po_no", "po_line_no"]
)
# %%
print(f"silver.purchase_order_line : {result_po}")

# %%
claims = (
    latest_by_key(spark.table("bronze.portal_warranty_claim"), ["claim_no"], "claim_date")
    .withColumn("claim_no", clean_string("claim_no"))
    .withColumn("repair_order_no", clean_string("repair_order_no"))
    .withColumn("vin", F.upper(clean_string("vin")))
    .withColumn("dealer_code", clean_string("dealer_code"))
    .withColumn("status", F.upper(clean_string("status")))
    .withColumn("rejection_reason", clean_string("rejection_reason"))
    .withColumn("claim_date", parse_date("claim_date"))
    .withColumn("decision_date", parse_date("decision_date"))
    .withColumn("claimed_amount", parse_decimal("claimed_amount"))
    .withColumn("approved_amount", parse_decimal("approved_amount"))
    .withColumn(
        "unreimbursed_amount",
        (F.col("claimed_amount") - F.coalesce(F.col("approved_amount"), F.lit(0)))
        .cast("decimal(18,2)"),
    )
    .withColumn(
        "decision_days",
        F.when(
            F.col("decision_date").isNotNull(),
            F.datediff(F.col("decision_date"), F.col("claim_date")),
        ),
    )
)
# %%
claim_columns = [
    "claim_no", "repair_order_no", "vin", "dealer_code", "service_type_code",
    "claim_date", "decision_date", "decision_days", "status",
    "claimed_amount", "approved_amount", "unreimbursed_amount", "rejection_reason",
]
# %%
claims = add_silver_audit(claims, batch_id, "portal", claim_columns).select(
    *claim_columns, *SILVER_AUDIT_COLUMNS
)
# %%
result_claims = merge_into_silver(claims, "silver.warranty_claim", ["claim_no"])
# %%
print(f"silver.warranty_claim : {result_claims}")

# %%
campaigns = (
    latest_by_key(spark.table("bronze.portal_recall_campaign"), ["campaign_code"], "_ingest_ts")
    .withColumn("campaign_code", clean_string("campaign_code"))
    .withColumn("campaign_name", clean_string("campaign_name"))
    .withColumn("category", F.upper(clean_string("category")))
    .withColumn("launch_date", parse_date("launch_date"))
    .withColumn("production_from", parse_date("production_from"))
    .withColumn("production_to", parse_date("production_to"))
    .withColumn("affected_vehicle_count", F.col("affected_vehicle_count").cast("int"))
)
# %%
campaign_columns = [
    "campaign_code", "campaign_name", "category", "launch_date",
    "production_from", "production_to", "affected_vehicle_count",
    "affected_models", "affected_model_trim_codes",
]
# %%
campaigns = add_silver_audit(campaigns, batch_id, "portal", campaign_columns).select(
    *campaign_columns, *SILVER_AUDIT_COLUMNS
)
# %%
result_campaigns = merge_into_silver(
    campaigns, "silver.recall_campaign", ["campaign_code"]
)
# %%
print(f"silver.recall_campaign : {result_campaigns}")

# %%
coverage = (
    latest_by_key(
        spark.table("bronze.portal_recall_coverage"), ["campaign_code", "vin"], "_ingest_ts"
    )
    .withColumn("campaign_code", clean_string("campaign_code"))
    .withColumn("vin", F.upper(clean_string("vin")))
    .withColumn("notified_date", parse_date("notified_date"))
    .withColumn("completed_date", parse_date("completed_date"))
    .withColumn("is_completed", F.col("is_completed").cast("int"))
    .withColumn(
        "days_to_complete",
        F.when(
            F.col("completed_date").isNotNull() & F.col("notified_date").isNotNull(),
            F.datediff(F.col("completed_date"), F.col("notified_date")),
        ),
    )
)
# %%
coverage_columns = [
    "campaign_code", "vin", "notified_date", "completed_date",
    "is_completed", "days_to_complete",
]
# %%
coverage = add_silver_audit(coverage, batch_id, "portal", coverage_columns).select(
    *coverage_columns, *SILVER_AUDIT_COLUMNS
)
# %%
result_coverage = merge_into_silver(
    coverage, "silver.recall_coverage", ["campaign_code", "vin"]
)
# %%
print(f"silver.recall_coverage : {result_coverage}")

# %%
budget = (
    latest_by_key(
        spark.table("bronze.finance_budget"),
        ["dealer_code", "budget_year", "budget_month", "metric_code"],
        "_ingest_ts",
    )
    .withColumn("dealer_code", clean_string("dealer_code"))
    .withColumn("budget_year", F.col("budget_year").cast("int"))
    .withColumn("budget_month", F.col("budget_month").cast("int"))
    .withColumn("metric_code", F.upper(clean_string("metric_code")))
    .withColumn("target_value", parse_decimal("target_value"))
    .withColumn("currency_code", F.upper(clean_string("currency_code")))
)
# %%
budget_columns = [
    "dealer_code", "budget_year", "budget_month", "metric_code",
    "target_value", "currency_code",
]
# %%
budget = add_silver_audit(budget, batch_id, "finance", budget_columns).select(
    *budget_columns, *SILVER_AUDIT_COLUMNS
)
# %%
result_budget = merge_into_silver(
    budget, "silver.budget",
    ["dealer_code", "budget_year", "budget_month", "metric_code"],
)
# %%
print(f"silver.budget : {result_budget}")

# %%
summary = {
    "status": "SUCCEEDED",
    "sales_contract": result_contracts["rows"],
    "repair_order": result_orders["rows"],
    "repair_order_line": result_lines["rows"],
    "purchase_order_line": result_po["rows"],
    "warranty_claim": result_claims["rows"],
    "recall_coverage": result_coverage["rows"],
    "budget": result_budget["rows"],
    "rows_written": sum(
        r["inserted"] + r["updated"]
        for r in [result_contracts, result_orders, result_lines, result_po,
                  result_claims, result_campaigns, result_coverage, result_budget]
    ),
    "finished_ts": now_string(),
}
# %%
print(summary)
# %%
utils.notebook.exit(str(summary).replace("'", '"'))
