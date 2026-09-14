
# %% tags=["parameters"]
batch_id = "manual-dev-run"

rules_json = "[]"

# %%
# %run 00_silver_common

# %%
import json

# %%
rules = json.loads(rules_json, strict=False)

# %%
if not rules:
    try:
        # spark.read.text() on a single small file in Files/ was unreliable here -
        # it silently returned zero rows even once notebookutils.fs.ls() confirmed
        # the file existed with the right byte count. notebookutils.fs.head() reads
        # the bytes directly and is what actually works for a small one-off file.
        rules = json.loads(utils.fs.head("Files/_dq_rules.json", 1_000_000))
        print("rules loaded from Files/_dq_rules.json (manual run)")
    except Exception as exc:
        raise SystemExit(
            "No rules supplied. The pipeline passes them as rules_json; for a "
            "manual run, export ctl.dq_rule to Files/_dq_rules.json first."
        ) from exc

# %%
print(f"{len(rules)} rules to evaluate")

# %%
results = []
# %%
violations_frames = []

# %%
for rule in rules:
    started = datetime.now(timezone.utc)
    outcome, error, evaluated, violated = "PASSED", None, 0, 0

    try:
        evaluated = spark.table(rule["target_table"]).count()
        found = spark.sql(rule["violation_sql"])
        found = (
            found.select(
                F.col("business_key").cast("string").alias("business_key"),
                F.col("detail").cast("string").alias("detail"),
            )
            .withColumn("batch_id", F.lit(batch_id))
            .withColumn("rule_id", F.lit(rule["rule_id"]).cast("int"))
            .withColumn("rule_code", F.lit(rule["rule_code"]))
            .withColumn("target_table", F.lit(rule["target_table"]))
            .withColumn("severity", F.lit(rule["severity"]))
            .withColumn("detected_ts", F.current_timestamp())
        )
        found.cache()
        violated = found.count()
        if violated:
            violations_frames.append(found)
            outcome = "FAILED"

        max_rate = rule.get("max_violation_rate")
        if max_rate and evaluated and (violated / evaluated) > float(max_rate):
            outcome = "SUSPECT"

    except Exception as exc:
        outcome, error = "ERROR", str(exc)[:4000]

    results.append(
        {
            "batch_id": batch_id,
            "rule_id": int(rule["rule_id"]),
            "rule_code": rule["rule_code"],
            "target_table": rule["target_table"],
            "rows_evaluated": int(evaluated),
            "rows_violated": int(violated),
            "violation_rate": float(violated / evaluated) if evaluated else 0.0,
            "severity": rule["severity"],
            "outcome": outcome,
            "error_message": error,
            "executed_ts": started,
            "duration_seconds": int(
                (datetime.now(timezone.utc) - started).total_seconds()
            ),
        }
    )
    marker = {"PASSED": "  ", "FAILED": " !", "ERROR": "XX", "SUSPECT": " ?"}[outcome]
    print(
        f"{marker} {rule['rule_code']:<28} {rule['target_table']:<28} "
        f"{violated:>7,} / {evaluated:>9,}  {outcome}"
    )

# %%
# an explicit schema, not inference - error_message is None on every row
# whenever every rule passes, and spark can't infer a type from an all-null
# column. a healthy run breaking createDataFrame() is a good bug to have found.
RESULT_SCHEMA = "batch_id STRING, rule_id INT, rule_code STRING, target_table STRING, " \
    "rows_evaluated LONG, rows_violated LONG, violation_rate DOUBLE, severity STRING, " \
    "outcome STRING, error_message STRING, executed_ts TIMESTAMP, duration_seconds INT"
result_df = spark.createDataFrame(results, schema=RESULT_SCHEMA)

# %%
# unionByName only takes one other frame at a time - not the variadic
# UNION ALL a SQL person expects - so multiple violation frames fold in one by one.
violation_df = None
for frame in violations_frames:
    violation_df = frame if violation_df is None else violation_df.unionByName(frame)

# %%
for table, df in [
    ("silver.dq_result", result_df),
    ("silver.dq_violation", violation_df),
]:
    if df is None:
        continue
    if spark.catalog.tableExists(table):
        spark.sql(f"DELETE FROM {table} WHERE batch_id = '{batch_id}'")
        df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(table)
    else:
        df.write.format("delta").mode("overwrite").saveAsTable(table)

# %%
total_violations = sum(r["rows_violated"] for r in results)
# %%
critical = sum(r["rows_violated"] for r in results if r["severity"] == "critical")
# %%
print(f"\n{total_violations:,} violations, {critical:,} of them critical")

# %%
QUARANTINE_KEYS = {
    "silver.sales_contract": "contract_no",
    "silver.repair_order": "repair_order_no",
    "silver.repair_order_line": None,
    "silver.purchase_order_line": None,
}
# %%
COMPOSITE_KEYS = {
    "silver.repair_order_line": ["repair_order_no", "line_no"],
    "silver.purchase_order_line": ["po_no", "po_line_no"],
}

# %%
quarantined_counts = {}

# %%
if spark.catalog.tableExists("silver.dq_violation"):
    critical_violations = spark.sql(
        f"""
        SELECT target_table, business_key,
               CONCAT_WS('; ', COLLECT_SET(CONCAT(rule_code, ': ', detail))) AS reason
        FROM silver.dq_violation
        WHERE batch_id = '{batch_id}' AND severity = 'critical'
        GROUP BY target_table, business_key
        """
    ).cache()

    for table in critical_violations.select("target_table").distinct().toPandas()["target_table"]:
        keys = COMPOSITE_KEYS.get(table)
        offenders = critical_violations.filter(F.col("target_table") == table)

        source = spark.table(table)
        if keys:

            offenders = (
                offenders
                .withColumn(keys[0], F.split(F.col("business_key"), "#").getItem(0))
                .withColumn(keys[1], F.split(F.col("business_key"), "#").getItem(1).cast("int"))
            )
            join_on = keys
        else:
            key = QUARANTINE_KEYS[table]
            offenders = offenders.withColumnRenamed("business_key", key)
            join_on = [key]

        bad_rows = source.join(
            offenders.select(*join_on, "reason"), on=join_on, how="inner"
        )
        entity = table.split(".")[-1]
        count = quarantine(
            bad_rows.withColumn("_qkey", F.col(join_on[0])),
            f"silver.quarantine_{entity}",
            "_qkey", "reason", batch_id,
        )
        quarantined_counts[table] = count

        good = source.join(offenders.select(*join_on), on=join_on, how="left_anti")
        good.write.format("delta").mode("overwrite").option(
            "overwriteSchema", "true"
        ).saveAsTable(table)

        print(f"  {table:<30} quarantined {count:>6,} rows")

# %%
summary = {
    "status": "SUCCEEDED",
    "rules_run": len(results),
    "passed": sum(1 for r in results if r["outcome"] == "PASSED"),
    "failed": sum(1 for r in results if r["outcome"] == "FAILED"),
    "errored": sum(1 for r in results if r["outcome"] == "ERROR"),
    "suspect": sum(1 for r in results if r["outcome"] == "SUSPECT"),
    "total_violations": total_violations,
    "critical_violations": critical,
    "rows_quarantined": sum(quarantined_counts.values()),
    "finished_ts": now_string(),
}
# %%
print(summary)
# %%
utils.notebook.exit(str(summary).replace("'", '"'))
