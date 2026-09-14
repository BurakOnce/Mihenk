
# %% tags=["parameters"]
batch_id = "manual-dev-run"
evaluation_path = "Files/_evaluation"

# %%
# %run 00_silver_common

# %%
truth = (
    spark.read.option("header", "true")
    .csv(f"{evaluation_path}/_mdm_truth.csv")
    .filter((F.col("dms_customer_id") != "") & (F.col("crm_id") != ""))
    .select(
        F.col("dms_customer_id").alias("truth_dms"),
        F.col("crm_id").alias("truth_crm"),
        F.col("match_difficulty"),
        F.col("customer_type"),
    )
)

# %%
predicted = (
    spark.table("silver.customer_xref")
    .filter(F.col("dms_customer_id").isNotNull() & F.col("crm_id").isNotNull())
    .select(
        F.col("dms_customer_id").alias("pred_dms"),
        F.col("crm_id").alias("pred_crm"),
        F.col("match_score"),
    )
)

# %%
truth.cache()
# %%
predicted.cache()
# %%
truth_pairs = truth.count()
# %%
predicted_pairs = predicted.count()

# %%
scored = (
    truth.join(
        predicted,
        (F.col("truth_dms") == F.col("pred_dms")) & (F.col("truth_crm") == F.col("pred_crm")),
        how="full_outer",
    )
    .withColumn(
        "classification",
        F.when(F.col("truth_dms").isNotNull() & F.col("pred_dms").isNotNull(), "TP")
        .when(F.col("pred_dms").isNotNull(), "FP")
        .otherwise("FN"),
    )
)

# %%
counts = {
    row["classification"]: row["n"]
    for row in scored.groupBy("classification").agg(F.count("*").alias("n")).collect()
}
# %%
tp, fp, fn = counts.get("TP", 0), counts.get("FP", 0), counts.get("FN", 0)
# %%
precision = tp / (tp + fp) if tp + fp else 0.0
# %%
recall = tp / (tp + fn) if tp + fn else 0.0
# %%
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

# %%
print("MDM MATCHING")
# %%
print(f"  matchable pairs in truth : {truth_pairs:,}")
# %%
print(f"  pairs the platform made  : {predicted_pairs:,}")
# %%
print(f"  true positives           : {tp:,}")
# %%
print(f"  false positives          : {fp:,}   <- wrong merges, the expensive kind")
# %%
print(f"  false negatives          : {fn:,}   <- missed merges, the visible kind")
# %%
print(f"  precision                : {precision:.2%}")
# %%
print(f"  recall                   : {recall:.2%}")
# %%
print(f"  F1                       : {f1:.2%}")

# %%
by_difficulty = (
    truth.join(
        predicted,
        (F.col("truth_dms") == F.col("pred_dms")) & (F.col("truth_crm") == F.col("pred_crm")),
        how="left",
    )
    .groupBy("match_difficulty")
    .agg(
        F.count("*").alias("pairs_in_truth"),
        F.sum(F.when(F.col("pred_dms").isNotNull(), 1).otherwise(0)).alias("found"),
    )
    .withColumn("recall", F.round(F.col("found") / F.col("pairs_in_truth"), 4))
    .orderBy("match_difficulty")
)
# %%
by_difficulty.show(truncate=False)

# %%
by_type = (
    truth.join(
        predicted,
        (F.col("truth_dms") == F.col("pred_dms")) & (F.col("truth_crm") == F.col("pred_crm")),
        how="left",
    )
    .groupBy("customer_type")
    .agg(
        F.count("*").alias("pairs_in_truth"),
        F.sum(F.when(F.col("pred_dms").isNotNull(), 1).otherwise(0)).alias("found"),
    )
    .withColumn("recall", F.round(F.col("found") / F.col("pairs_in_truth"), 4))
)
# %%
by_type.show(truncate=False)

# %%
missed = (
    truth.join(
        predicted,
        (F.col("truth_dms") == F.col("pred_dms")) & (F.col("truth_crm") == F.col("pred_crm")),
        how="left_anti",
    )
    .limit(25)
)

# %%
dms_names = spark.table("bronze.dms_customer").select(
    F.col("customer_id").alias("truth_dms"),
    F.col("full_name").alias("dms_name"),
    F.col("identity_no").alias("dms_identity"),
)
# %%
crm_names = spark.table("bronze.crm_customer").select(
    F.col("crm_id").alias("truth_crm"),
    F.col("full_name").alias("crm_name"),
    F.col("identity_no").alias("crm_identity"),
)

# %%
print("a sample of pairs the matcher did not find:")
# %%
(
    missed.join(dms_names, on="truth_dms", how="left")
    .join(crm_names, on="truth_crm", how="left")
    .select("match_difficulty", "dms_name", "crm_name", "dms_identity", "crm_identity")
    .show(25, truncate=False)
)

# %%
injected = (
    spark.read.option("header", "true")
    .csv(f"{evaluation_path}/_injection_log.csv")
    .select("rule_code", "business_key", "target_entity", "column_name", "cascade_rules")
)

# %%
detected = spark.table("silver.dq_violation").filter(
    F.col("batch_id") == batch_id
).select("rule_code", "business_key")

# %%
dq = (
    injected.alias("i")
    .join(
        detected.alias("d"),
        (F.col("i.rule_code") == F.col("d.rule_code"))
        & (F.col("i.business_key") == F.col("d.business_key")),
        how="left",
    )
    .groupBy(F.col("i.rule_code").alias("rule_code"))
    .agg(
        F.count("*").alias("injected"),
        F.sum(F.when(F.col("d.business_key").isNotNull(), 1).otherwise(0)).alias("detected"),
    )
    .withColumn("recall", F.round(F.col("detected") / F.col("injected"), 4))
    .orderBy(F.col("recall").asc())
)

# %%
print("DQ RECALL BY RULE  (lowest first - the interesting end)")
# %%
dq.show(30, truncate=False)

# %%
totals = dq.agg(
    F.sum("injected").alias("injected"), F.sum("detected").alias("detected")
).collect()[0]
# %%
print(
    f"overall DQ recall: {totals['detected']:,} / {totals['injected']:,} = "
    f"{totals['detected'] / totals['injected']:.2%}"
)

# %%
unexplained = (
    detected.alias("d")
    .join(
        injected.alias("i"),
        (F.col("i.rule_code") == F.col("d.rule_code"))
        & (F.col("i.business_key") == F.col("d.business_key")),
        how="left_anti",
    )
    .groupBy("rule_code")
    .agg(F.count("*").alias("detected_without_injection"))
    .orderBy(F.col("detected_without_injection").desc())
)
# %%
unexplained.show(30, truncate=False)

# %%
print(
    "\nRecord these figures in docs/interview_defense_notes.md. "
    "A measured number with its failure modes explained is worth more than a "
    "round number with none."
)
