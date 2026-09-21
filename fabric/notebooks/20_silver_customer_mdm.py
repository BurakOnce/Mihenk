
# %% tags=["parameters"]
batch_id = "manual-dev-run"

pii_salt = "REPLACE_WITH_KEY_VAULT_SECRET"

match_threshold = 55

# %%
# %run 00_silver_common

# %%
dms_raw = spark.table("bronze.dms_customer")
# %%
crm_raw = spark.table("bronze.crm_customer")

# %%
dms = (
    latest_by_key(dms_raw, ["customer_id"], "last_modified_ts")
    .withColumn("full_name_clean", clean_string("full_name"))
    .withColumn("match_name", strip_company_suffix(normalise_for_matching("full_name")))
    .withColumn("match_phone", F.substring(F.regexp_replace(F.col("phone"), r"[^0-9]", ""), -10, 10))
    .withColumn("match_email", F.lower(F.trim(F.col("email"))))
    .withColumn("identity_hash", hash_pii("identity_no", pii_salt))
    .withColumn("city_clean", clean_string("city"))

    .select(
        F.col("customer_id").alias("dms_customer_id"),
        F.col("customer_type").alias("dms_customer_type"),
        F.col("full_name_clean").alias("dms_full_name"),
        F.col("match_name").alias("dms_match_name"),
        F.col("match_phone").alias("dms_match_phone"),
        F.col("match_email").alias("dms_match_email"),
        F.col("identity_hash").alias("dms_identity_hash"),
        F.col("city_clean").alias("dms_city"),
        F.col("city_code").alias("dms_city_code"),
        F.col("identity_no").alias("dms_identity_no"),
        F.col("phone").alias("dms_phone"),
        F.col("email").alias("dms_email"),
        F.col("address_line").alias("dms_address_line"),
        parse_date("created_date").alias("dms_created_date"),
        parse_timestamp("last_modified_ts").alias("dms_modified_ts"),
    )
)

# %%
crm = (
    latest_by_key(crm_raw, ["crm_id"], "last_modified_ts")
    .withColumn(
        "primary_gsm",
        F.element_at(
            F.filter(
                F.col("contacts"),
                lambda c: (c["contact_type"] == "GSM") & (c["is_primary"] == True),
            ),
            1,
        )["value"],
    )
    .withColumn("full_name_clean", clean_string("full_name"))
    .withColumn("match_name", strip_company_suffix(normalise_for_matching("full_name")))
    .withColumn("match_phone", F.substring(F.regexp_replace(F.col("primary_gsm"), r"[^0-9]", ""), -10, 10))
    .withColumn("match_email", F.lower(F.trim(F.col("primary_email"))))
    .withColumn("identity_hash", hash_pii("identity_no", pii_salt))
    .withColumn("city_clean", clean_string("city"))
    .select(
        F.col("crm_id"),
        F.col("customer_type").alias("crm_customer_type"),
        F.col("full_name_clean").alias("crm_full_name"),
        F.col("match_name").alias("crm_match_name"),
        F.col("match_phone").alias("crm_match_phone"),
        F.col("match_email").alias("crm_match_email"),
        F.col("identity_hash").alias("crm_identity_hash"),
        F.col("city_clean").alias("crm_city"),
        F.col("identity_no").alias("crm_identity_no"),
        F.col("primary_gsm").alias("crm_phone"),
        F.col("primary_email").alias("crm_email"),
        F.col("lead_source"),
        F.col("consent_kvkk"),
        parse_timestamp("last_modified_ts").alias("crm_modified_ts"),
    )
)

# %%
dms.cache()
# %%
crm.cache()
# %%
print(f"DMS customers : {dms.count():,}")
# %%
print(f"CRM customers : {crm.count():,}")

# %%
def block(dms_key: "F.Column", crm_key: "F.Column", label: str) -> DataFrame:
    left = dms.withColumn("_bk", dms_key).filter(F.col("_bk").isNotNull() & (F.col("_bk") != ""))
    right = crm.withColumn("_bk", crm_key).filter(F.col("_bk").isNotNull() & (F.col("_bk") != ""))
    return (
        left.select("dms_customer_id", "_bk")
        .join(right.select("crm_id", "_bk"), on="_bk")
        .select("dms_customer_id", "crm_id")
        .withColumn("block", F.lit(label))
    )

# %%
candidates = (
    block(F.col("dms_identity_hash"), F.col("crm_identity_hash"), "identity")
    .unionByName(block(F.col("dms_match_phone"), F.col("crm_match_phone"), "phone"))
    .unionByName(block(F.col("dms_match_email"), F.col("crm_match_email"), "email"))
    .unionByName(
        block(
            F.concat_ws("|", F.substring("dms_match_name", 1, 6), F.col("dms_city")),
            F.concat_ws("|", F.substring("crm_match_name", 1, 6), F.col("crm_city")),
            "name_city",
        )
    )
    .dropDuplicates(["dms_customer_id", "crm_id"])
)

# %%
candidates.cache()
# %%
candidate_count = candidates.count()
# %%
print(f"candidate pairs : {candidate_count:,}")
# %%
print(f"  versus a full cross join of {dms.count() * crm.count():,}")
# %%
print(f"  reduction     : {1 - candidate_count / (dms.count() * crm.count()):.4%}")

# %%
scored = (
    candidates
    .join(dms, on="dms_customer_id")
    .join(crm, on="crm_id")
    .withColumn(
        "score_identity",
        F.when(
            F.col("dms_identity_hash").isNotNull()
            & (F.col("dms_identity_hash") == F.col("crm_identity_hash")),
            F.lit(60),
        ).otherwise(F.lit(0)),
    )
    .withColumn(
        "score_phone",
        F.when(
            F.col("dms_match_phone").isNotNull()
            & (F.length("dms_match_phone") >= 10)
            & (F.col("dms_match_phone") == F.col("crm_match_phone")),
            F.lit(30),
        ).otherwise(F.lit(0)),
    )
    .withColumn(
        "score_email",
        F.when(
            F.col("dms_match_email").isNotNull()
            & (F.col("dms_match_email") == F.col("crm_match_email")),
            F.lit(20),
        ).otherwise(F.lit(0)),
    )
    .withColumn(
        "score_name",
        F.when(F.col("dms_match_name") == F.col("crm_match_name"), F.lit(25))
        .when(
            (F.length("dms_match_name") > 8)
            & (F.levenshtein(F.col("dms_match_name"), F.col("crm_match_name")) <= 3),
            F.lit(12),
        )
        .when(

            (F.element_at(F.split(F.col("dms_match_name"), " "), -1)
             == F.element_at(F.split(F.col("crm_match_name"), " "), -1))
            & (F.length(F.element_at(F.split(F.col("dms_match_name"), " "), -1)) >= 4),
            F.lit(8),
        )
        .otherwise(F.lit(0)),
    )
    .withColumn(
        "score_city",
        F.when(F.col("dms_city") == F.col("crm_city"), F.lit(8)).otherwise(F.lit(0)),
    )
    .withColumn(
        "score_type_penalty",
        F.when(F.col("dms_customer_type") != F.col("crm_customer_type"), F.lit(-40))
        .otherwise(F.lit(0)),
    )
    .withColumn(
        "match_score",
        F.col("score_identity") + F.col("score_phone") + F.col("score_email")
        + F.col("score_name") + F.col("score_city") + F.col("score_type_penalty"),
    )
)

# %%
above_threshold = scored.filter(F.col("match_score") >= match_threshold)
# %%
above_threshold.cache()
# %%
print(f"pairs scoring >= {match_threshold}: {above_threshold.count():,}")

# %%
dms_window = Window.partitionBy("dms_customer_id").orderBy(
    F.col("match_score").desc(), F.col("crm_id").asc()
)
# %%
crm_window = Window.partitionBy("crm_id").orderBy(
    F.col("match_score").desc(), F.col("dms_customer_id").asc()
)

# %%
mutual = (
    above_threshold
    .withColumn("rank_for_dms", F.row_number().over(dms_window))
    .withColumn("rank_for_crm", F.row_number().over(crm_window))
    .filter((F.col("rank_for_dms") == 1) & (F.col("rank_for_crm") == 1))
)

# %%
mutual.cache()
# %%
matched_pairs = mutual.count()
# %%
print(f"mutual best matches : {matched_pairs:,}")
# %%
print(f"  dropped as ambiguous: {above_threshold.count() - matched_pairs:,}")

# %%
golden_matched = mutual.select(
    F.col("dms_customer_id"),
    F.col("crm_id"),
    F.col("match_score"),

    F.col("dms_customer_type").alias("customer_type"),
    F.coalesce(F.col("dms_identity_no"), F.col("crm_identity_no")).alias("identity_no"),

    F.when(
        (F.length("dms_full_name")
         + F.length(F.regexp_replace(F.col("dms_full_name"), r"[A-Za-z0-9 .]", "")) * 3)
        >=
        (F.length("crm_full_name")
         + F.length(F.regexp_replace(F.col("crm_full_name"), r"[A-Za-z0-9 .]", "")) * 3),
        F.col("dms_full_name"),
    ).otherwise(F.col("crm_full_name")).alias("full_name"),

    F.coalesce(F.col("crm_email"), F.col("dms_email")).alias("email"),
    F.when(F.col("crm_modified_ts") >= F.col("dms_modified_ts"), F.col("crm_phone"))
     .otherwise(F.col("dms_phone")).alias("phone"),
    F.when(F.col("crm_modified_ts") >= F.col("dms_modified_ts"), F.col("crm_city"))
     .otherwise(F.col("dms_city")).alias("city"),
    F.col("dms_city_code").alias("city_code"),
    F.col("dms_address_line").alias("address_line"),
    F.col("lead_source"),
    F.col("consent_kvkk"),
    F.col("dms_created_date").alias("customer_since"),
    F.greatest(F.col("dms_modified_ts"), F.col("crm_modified_ts")).alias("last_modified_ts"),
    F.lit("BOTH").alias("source_presence"),
)

# %%
dms_only = (
    dms.join(mutual.select("dms_customer_id"), on="dms_customer_id", how="left_anti")
    .select(
        F.col("dms_customer_id"), F.lit(None).cast("string").alias("crm_id"),
        F.lit(0).alias("match_score"),
        F.col("dms_customer_type").alias("customer_type"),
        F.col("dms_identity_no").alias("identity_no"),
        F.col("dms_full_name").alias("full_name"),
        F.col("dms_email").alias("email"), F.col("dms_phone").alias("phone"),
        F.col("dms_city").alias("city"), F.col("dms_city_code").alias("city_code"),
        F.col("dms_address_line").alias("address_line"),
        F.lit(None).cast("string").alias("lead_source"),
        F.lit(None).cast("boolean").alias("consent_kvkk"),
        F.col("dms_created_date").alias("customer_since"),
        F.col("dms_modified_ts").alias("last_modified_ts"),
        F.lit("DMS_ONLY").alias("source_presence"),
    )
)

# %%
crm_only = (
    crm.join(mutual.select("crm_id"), on="crm_id", how="left_anti")
    .select(
        F.lit(None).cast("string").alias("dms_customer_id"), F.col("crm_id"),
        F.lit(0).alias("match_score"),
        F.col("crm_customer_type").alias("customer_type"),
        F.col("crm_identity_no").alias("identity_no"),
        F.col("crm_full_name").alias("full_name"),
        F.col("crm_email").alias("email"), F.col("crm_phone").alias("phone"),
        F.col("crm_city").alias("city"),
        F.lit(None).cast("string").alias("city_code"),
        F.lit(None).cast("string").alias("address_line"),
        F.col("lead_source"), F.col("consent_kvkk"),
        F.lit(None).cast("date").alias("customer_since"),
        F.col("crm_modified_ts").alias("last_modified_ts"),
        F.lit("CRM_ONLY").alias("source_presence"),
    )
)

# %%
golden = golden_matched.unionByName(dms_only).unionByName(crm_only)
# %%
print(f"golden records : {golden.count():,}")

# %%
if spark.catalog.tableExists("silver.customer_xref"):
    existing = spark.table("silver.customer_xref").select(
        "master_customer_id", "dms_customer_id", "crm_id"
    )
    existing_by_dms = existing.filter(F.col("dms_customer_id").isNotNull()) \
        .select("master_customer_id", "dms_customer_id")
    existing_by_crm = existing.filter(F.col("crm_id").isNotNull()) \
        .select(F.col("master_customer_id").alias("master_from_crm"), "crm_id")

    with_existing = (
        golden
        .join(existing_by_dms, on="dms_customer_id", how="left")
        .join(existing_by_crm, on="crm_id", how="left")

        .withColumn(
            "master_customer_id",
            F.coalesce(F.col("master_customer_id"), F.col("master_from_crm")),
        )
        .drop("master_from_crm")
    )
    next_id = spark.sql(
        "SELECT COALESCE(MAX(CAST(SUBSTRING(master_customer_id, 4, 20) AS BIGINT)), 0) AS m "
        "FROM silver.customer_xref"
    ).collect()[0]["m"]
else:
    with_existing = golden.withColumn(
        "master_customer_id", F.lit(None).cast("string")
    )
    next_id = 0

# %%
assign_window = Window.orderBy(
    F.coalesce(F.col("dms_customer_id"), F.col("crm_id"))
)
# %%
final = with_existing.withColumn(
    "master_customer_id",
    F.coalesce(
        F.col("master_customer_id"),
        F.concat(
            F.lit("MST"),
            F.lpad(
                (F.row_number().over(assign_window) + F.lit(next_id)).cast("string"),
                8, "0",
            ),
        ),
    ),
)

# %%
business_columns = [
    "customer_type", "identity_no", "full_name", "email", "phone",
    "city", "city_code", "address_line", "lead_source", "consent_kvkk",
    "customer_since", "source_presence",
]

# %%
customer = (
    final
    .withColumn("identity_hash", hash_pii("identity_no", pii_salt))
    .withColumn("identity_no_masked", mask_identity_no("identity_no"))
    .withColumn("phone_hash", hash_pii("phone", pii_salt))
    .withColumn("phone_masked", mask_phone("phone"))
    .withColumn("email_hash", hash_pii("email", pii_salt))
    .withColumn("email_masked", mask_email("email"))
    .drop("identity_no", "phone", "email")
)

# %%
customer = add_silver_audit(
    customer, batch_id, "mdm",
    [c for c in business_columns if c not in ("identity_no", "phone", "email")],
).select(
    "master_customer_id", "customer_type", "full_name",
    "identity_hash", "identity_no_masked",
    "phone_hash", "phone_masked", "email_hash", "email_masked",
    "city", "city_code", "address_line", "lead_source", "consent_kvkk",
    "customer_since", "last_modified_ts", "source_presence", "match_score",
    *SILVER_AUDIT_COLUMNS,
)

# %%
xref = add_silver_audit(
    final.select("master_customer_id", "dms_customer_id", "crm_id", "source_presence", "match_score"),
    batch_id, "mdm",
    ["master_customer_id", "dms_customer_id", "crm_id", "source_presence", "match_score"],
).select("master_customer_id", "dms_customer_id", "crm_id", "source_presence", "match_score",
         *SILVER_AUDIT_COLUMNS)

# %%
customer_result = merge_into_silver(customer, "silver.customer", ["master_customer_id"])
# %%
xref_result = merge_into_silver(
    xref, "silver.customer_xref", ["master_customer_id"]
)

# %%
print(f"silver.customer      : {customer_result}")
# %%
print(f"silver.customer_xref : {xref_result}")

# %%
summary = spark.sql(
    """
    SELECT source_presence, COUNT(*) AS records
    FROM silver.customer
    GROUP BY source_presence
    ORDER BY records DESC
    """
)
# %%
summary.show()

# %%
result = {
    "status": "SUCCEEDED",
    "golden_records": customer_result["rows"],
    "matched_pairs": matched_pairs,
    "candidate_pairs": candidate_count,
    "rows_written": customer_result["inserted"] + customer_result["updated"],
    "finished_ts": now_string(),
}
# %%
print(result)
# %%
utils.notebook.exit(str(result).replace("'", '"'))
