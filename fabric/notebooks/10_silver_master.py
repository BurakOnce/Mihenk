
# %% tags=["parameters"]
batch_id = "manual-dev-run"
pii_salt = "REPLACE_WITH_KEY_VAULT_SECRET"

# %%
# %run 00_silver_common

# %%
SPECS = [
    {
        "name": "dealer",
        "source": "bronze.dms_dealer",
        "target": "silver.dealer",
        "keys": ["dealer_code"],
        "order_by": "last_modified_ts",
        "turkish_decimal": True,
        "strings": ["dealer_code", "dealer_name", "dealer_type", "province_code",
                    "city", "region", "address_line", "phone"],
        "integers": ["workshop_bay_count", "monthly_capacity_hours", "is_active"],
        "dates": ["opening_date"],
        "timestamps": ["last_modified_ts"],
        "decimals": [],
    },
    {
        "name": "employee",
        "source": "bronze.dms_employee",
        "target": "silver.employee",
        "keys": ["employee_id"],
        "order_by": "last_modified_ts",
        "turkish_decimal": True,
        "strings": ["employee_id", "first_name", "last_name", "full_name",
                    "dealer_code", "role_code", "email"],
        "integers": ["is_active"],
        "dates": ["hire_date"],
        "timestamps": ["last_modified_ts"],
        "decimals": [],
    },
    {
        "name": "model_trim",
        "source": "bronze.dms_model_trim",
        "target": "silver.model_trim",
        "keys": ["model_trim_code"],
        "order_by": "last_modified_ts",
        "turkish_decimal": True,
        "strings": ["model_trim_code", "brand", "model_name", "trim_name",
                    "body_type", "segment", "fuel_type", "transmission"],
        "integers": ["model_year", "engine_cc", "warranty_months", "warranty_km",
                     "is_active"],
        "dates": [],
        "timestamps": ["last_modified_ts"],
        "decimals": ["list_price_try"],
    },
    {
        "name": "part",
        "source": "bronze.parts_part",
        "target": "silver.part",
        "keys": ["part_no"],
        "order_by": "last_modified_ts",
        "turkish_decimal": False,
        "strings": ["part_no", "part_name", "part_group_code", "part_group_name",
                    "supplier_id", "unit_of_measure"],
        "integers": ["is_genuine", "is_active"],
        "dates": [],
        "timestamps": ["last_modified_ts"],
        "decimals": ["list_price_try"],
    },
    {
        "name": "supplier",
        "source": "bronze.parts_supplier",
        "target": "silver.supplier",
        "keys": ["supplier_id"],
        "order_by": "last_modified_ts",
        "turkish_decimal": False,
        "strings": ["supplier_id", "supplier_name", "country_code", "contact_email"],
        "integers": ["lead_time_days", "is_active"],
        "dates": [],
        "timestamps": ["last_modified_ts"],
        "decimals": [],
    },
    {
        "name": "vehicle",
        "source": "bronze.dms_vehicle_stock",
        "target": "silver.vehicle",
        "keys": ["vin"],
        "order_by": "last_modified_ts",
        "turkish_decimal": True,
        "strings": ["vin", "model_trim_code", "colour", "stock_dealer_code",
                    "engine_no", "status", "plate_number", "owner_customer_id"],
        "integers": ["model_year", "is_active"],
        "dates": ["production_date", "arrival_date"],
        "timestamps": ["last_modified_ts"],
        "decimals": ["dealer_cost_try"],
    },
    {
        "name": "fx_rate",
        "source": "bronze.finance_fx_rate",
        "target": "silver.ref_fx_rate",
        "keys": ["rate_date", "currency_code"],

        "order_by": "_ingest_ts",
        "turkish_decimal": False,
        "strings": ["currency_code"],
        "integers": [],
        "dates": ["rate_date"],
        "timestamps": [],
        "decimals": [],
        "decimals_6dp": ["rate_to_try"],
    },
]

# %%
def load_entity(spec: dict) -> dict:
    source = spark.table(spec["source"])

    df = latest_by_key(source, spec["keys"], spec["order_by"])

    for column in spec.get("strings", []):
        if column in df.columns:
            df = df.withColumn(column, clean_string(column))

    for column in spec.get("integers", []):
        if column in df.columns:
            df = df.withColumn(column, F.col(column).cast("int"))

    for column in spec.get("dates", []):
        if column in df.columns:
            df = df.withColumn(f"{column}_raw", F.col(column))
            df = df.withColumn(column, parse_date(f"{column}_raw"))

    for column in spec.get("timestamps", []):
        if column in df.columns:
            df = df.withColumn(column, parse_timestamp(column))

    for column in spec.get("decimals", []):
        if column in df.columns:
            df = df.withColumn(
                column, parse_decimal(column, turkish=spec["turkish_decimal"])
            )

    for column in spec.get("decimals_6dp", []):
        if column in df.columns:
            df = df.withColumn(
                column,
                parse_decimal(column, turkish=spec["turkish_decimal"], scale=6),
            )

    if spec["name"] == "vehicle":

        df = df.withColumn("vin", F.upper(F.col("vin")))
        df = df.withColumn("vin_well_formed", vin_is_well_formed("vin").cast("int"))
        df = df.withColumn("vin_check_digit_valid", vin_check_digit_valid("vin"))
        df = df.withColumn("plate_number_masked", mask_plate("plate_number"))
        df = df.withColumn("plate_hash", hash_pii("plate_number", pii_salt))
        df = df.drop("plate_number")

    business_columns = [
        c for c in df.columns
        if not c.startswith("_") and not c.endswith("_raw")
    ]
    df = add_silver_audit(df, batch_id, spec["source"].split(".")[0].split("_")[0],
                          business_columns)

    df = df.drop("_ingest_ts", "_source_file")

    return merge_into_silver(df, spec["target"], spec["keys"])

# %%
results = {}
# %%
for spec in SPECS:
    if not spark.catalog.tableExists(spec["source"]):
        print(f"  SKIP {spec['name']:<12} {spec['source']} does not exist yet")
        continue
    outcome = load_entity(spec)
    results[spec["name"]] = outcome
    print(
        f"  {spec['name']:<12} {spec['target']:<24} "
        f"rows={outcome['rows']:>7,}  inserted={outcome['inserted']:>7,}  "
        f"updated={outcome['updated']:>6,}"
    )

# %%
print("second pass - every count below must be zero\n")
# %%
for spec in SPECS:
    if spec["name"] not in results:
        continue
    outcome = load_entity(spec)
    status = "OK" if outcome["inserted"] == 0 and outcome["updated"] == 0 else "NOT IDEMPOTENT"
    print(
        f"  {spec['name']:<12} inserted={outcome['inserted']:>4}  "
        f"updated={outcome['updated']:>4}   {status}"
    )

# %%
# her tablo gerçekten arandığı sütuna göre z-order alıyor - başlıkta vin var,
# satırlarda sadece ait oldukları iş emri numarası var.
OPTIMIZE_KEYS = {
    "bronze.workshop_repair_order": "vin",
    "bronze.workshop_repair_order_line": "repair_order_no",
}
for table, zorder_column in OPTIMIZE_KEYS.items():
    if spark.catalog.tableExists(table):
        before = spark.sql(f"DESCRIBE DETAIL {table}").collect()[0]["numFiles"]
        spark.sql(f"OPTIMIZE {table} ZORDER BY ({zorder_column})")
        after = spark.sql(f"DESCRIBE DETAIL {table}").collect()[0]["numFiles"]
        print(f"  {table:<38} {before:>5} files -> {after:>4}")

# %%
summary = {
    "status": "SUCCEEDED",
    "entities": len(results),
    "rows_written": sum(r["inserted"] + r["updated"] for r in results.values()),
    "finished_ts": now_string(),
}
# %%
print(summary)
# %%
utils.notebook.exit(str(summary).replace("'", '"'))
