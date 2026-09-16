
# %%
from datetime import datetime, timezone

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, Window, functions as F

# %%
try:
    import notebookutils
    utils = notebookutils
except ImportError:
    import mssparkutils as utils

# %%
DATE_FORMATS = ["yyyy-MM-dd", "dd.MM.yyyy", "dd/MM/yyyy"]
# %%
TIMESTAMP_FORMATS = ["yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd'T'HH:mm:ss", "yyyy-MM-dd"]

# %%
SILVER_AUDIT_COLUMNS = ["_silver_ts", "_batch_id", "_source_system", "_row_hash"]

# %%
def parse_date(column: str, formats: list[str] = None) -> "F.Column":
    """ayrıştırabilen ilk format kazanır; hiçbiri ayrıştıramazsa null"""
    formats = formats or DATE_FORMATS
    return F.coalesce(*[F.to_date(F.col(column), fmt) for fmt in formats])

# %%
def parse_timestamp(column: str) -> "F.Column":
    return F.coalesce(*[F.to_timestamp(F.col(column), fmt) for fmt in TIMESTAMP_FORMATS])

# %%
def parse_decimal(column: str, turkish: bool = False, precision: int = 18, scale: int = 2):
    """metin tutarı decimal'e çevirir, türkçe virgül ayracını da ele alır"""
    source = F.col(column)
    if turkish:
        source = F.regexp_replace(F.regexp_replace(source, r"\.", ""), ",", ".")

    return F.when(F.trim(source) == "", None).otherwise(
        source.cast(f"decimal({precision},{scale})")
    )

# %%
def clean_string(column: str) -> "F.Column":
    """kırp, içerideki boşlukları tekle, boş değerleri null yap"""
    cleaned = F.regexp_replace(F.trim(F.col(column)), r"\s+", " ")
    return F.when(cleaned == "", None).otherwise(cleaned)

# %%
TURKISH_FOLD = [
    ("İ", "I"), ("I", "I"), ("ı", "i"), ("i", "i"),
    ("Ş", "S"), ("ş", "s"),
    ("Ğ", "G"), ("ğ", "g"),
    ("Ü", "U"), ("ü", "u"),
    ("Ö", "O"), ("ö", "o"),
    ("Ç", "C"), ("ç", "c"),
]

# %%
# %% [markdown]
# spark.lower() locale-bağımsız - türkçe İ/ı harflerini yanlış çevirebilir.
# önce kendim çeviriyorum, sonra upper() çağırıyorum.

# %%
def normalise_for_matching(column: str) -> "F.Column":
    """bulanık karşılaştırma için ascii, büyük harf, noktalamasız anahtar"""
    result = F.col(column)
    for source_char, target_char in TURKISH_FOLD:
        result = F.regexp_replace(result, source_char, target_char)
    result = F.upper(result)

    result = F.regexp_replace(result, r"[^A-Z0-9 ]", " ")
    return F.trim(F.regexp_replace(result, r"\s+", " "))

# %%
COMPANY_SUFFIXES = [
    "SANAYI VE TICARET ANONIM SIRKETI",
    "SANAYI VE TICARET LIMITED SIRKETI",
    "SAN VE TIC A S", "SAN TIC LTD STI", "SAN VE TIC LTD STI",
    "ANONIM SIRKETI", "LIMITED SIRKETI",
    "LTD STI", "A S", "AS", "LTD",
]

# %%
def strip_company_suffix(column: "F.Column") -> "F.Column":
    """şirket türü ekini kaldır ki karşılaştırılan şey ticari unvan olsun"""
    result = column
    for suffix in COMPANY_SUFFIXES:
        result = F.regexp_replace(result, f" {suffix}$", "")
    return F.trim(result)

# %%
def hash_pii(column: str, salt: str) -> "F.Column":
    """tuzlu sha-256. kaynaklar arası deterministik ki mdm hâlâ eşleştirebilsin"""
    return F.when(
        F.col(column).isNull() | (F.trim(F.col(column)) == ""), None
    ).otherwise(
        F.sha2(F.concat(F.lit(salt), F.trim(F.col(column))), 256)
    )

# %%
def mask_identity_no(column: str) -> "F.Column":
    """`12345678901` -> `123*****901`. doğrulamaya yeter, kullanmaya yetmez"""
    source = F.trim(F.col(column))
    return F.when(F.length(source) < 8, None).otherwise(
        F.concat(F.substring(source, 1, 3), F.lit("*****"), F.substring(source, -3, 3))
    )

# %%
def mask_phone(column: str) -> "F.Column":
    source = F.regexp_replace(F.trim(F.col(column)), r"[^0-9]", "")
    return F.when(F.length(source) < 7, None).otherwise(
        F.concat(F.substring(source, 1, 4), F.lit("*****"), F.substring(source, -2, 2))
    )

# %%
def mask_email(column: str) -> "F.Column":
    """`sukru.ozturk@gmail.com` -> `s***@gmail.com`. alan adı kalıyor, kişisel değil"""
    source = F.trim(F.col(column))
    local = F.substring_index(source, "@", 1)
    domain = F.substring_index(source, "@", -1)
    return F.when(~source.contains("@"), None).otherwise(
        F.concat(F.substring(local, 1, 1), F.lit("***@"), domain)
    )

# %%
def mask_plate(column: str) -> "F.Column":
    """`34 abc 12` -> `34 *** 12`. il kodu kalıyor, bölgesel analiz için lazım"""
    source = F.trim(F.col(column))
    return F.when(F.length(source) < 5, None).otherwise(
        F.regexp_replace(source, r"(?<= )[A-Z]+(?= )", "***")
    )

# %%
_VIN_LETTERS = "ABCDEFGH" "JKLMNPR" "STUVWXYZ"
# %%
_VIN_VALUES = "12345678" "1234579" "23456789"
# %%
_VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

# %%
def vin_is_well_formed(column: str) -> "F.Column":
    """sadece yapısal kontrol: 17 karakter, i, o veya q yok"""
    vin = F.upper(F.trim(F.col(column)))
    return (
        vin.isNotNull()
        & (F.length(vin) == 17)
        & (~vin.rlike("[IOQ]"))
        & vin.rlike("^[A-HJ-NPR-Z0-9]{17}$")
    )

# %%
def vin_check_digit(column: str) -> "F.Column":
    """iso 3779'a göre 9. pozisyonda olması gereken karakter"""
    vin = F.upper(F.trim(F.col(column)))
    digits = F.translate(vin, _VIN_LETTERS, _VIN_VALUES)

    total = F.lit(0)
    for position, weight in enumerate(_VIN_WEIGHTS, start=1):
        if weight == 0:

            continue
        total = total + (F.substring(digits, position, 1).cast("int") * F.lit(weight))

    remainder = total % 11
    return F.when(remainder == 10, F.lit("X")).otherwise(remainder.cast("string"))

# %%
def vin_check_digit_valid(column: str) -> "F.Column":
    """9. pozisyon hesaplanan haneyle eşleşiyorsa 1, değilse 0"""
    vin = F.upper(F.trim(F.col(column)))
    return F.when(~vin_is_well_formed(column), None).otherwise(
        F.when(F.substring(vin, 9, 1) == vin_check_digit(column), 1).otherwise(0)
    )

# %%
# %% [markdown]
# yeni öğrendiğim: window fonksiyonu. sql'deki
# `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` ile birebir aynı.

# %%
def latest_by_key(df: DataFrame, keys: list[str], order_by: str) -> DataFrame:
    """anahtar başına tek satır - en güncel olan, deterministik şekilde"""
    window = (
        Window.partitionBy(*keys)
        .orderBy(
            F.col(order_by).desc_nulls_last(),
            F.col("_ingest_ts").desc_nulls_last(),

            F.col("_row_hash").desc_nulls_last(),
        )
    )
    return (
        df.withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )

# %%
def build_fx_lookup(fx_df: DataFrame) -> DataFrame:
    """para birimi ve tarih başına tek satır, artı yapay bir try serisi"""
    rates = (
        fx_df.select(
            F.col("currency_code").alias("fx_currency"),
            F.to_date("rate_date").alias("fx_date"),
            F.col("rate_to_try").cast("decimal(18,6)").alias("fx_rate"),
        )
        .dropna(subset=["fx_currency", "fx_date", "fx_rate"])
        .dropDuplicates(["fx_currency", "fx_date"])
    )
    return rates

# %%
# %% [markdown]
# kur tablosu hafta sonu boş - forward fill için LEAD kullanıp bir sonraki
# yayınlanan tarihe kadar aynı kuru geçerli sayıyorum.

# %%
def convert_to_try(
    df: DataFrame,
    fx_rates: DataFrame,
    amount_columns: list[str],
    currency_column: str = "currency_code",
    date_column: str = "contract_date",
) -> DataFrame:
    """forward fill ile kur bağla ve verilen tutarları çevir"""
    df.createOrReplaceTempView("_txn")
    fx_rates.createOrReplaceTempView("_fx")

    converted = spark.sql(
        f"""
        SELECT
            t.*,
            CASE WHEN t.{currency_column} = 'TRY' THEN CAST(1.0 AS DECIMAL(18,6))
                 ELSE r.fx_rate END AS fx_rate_to_try,
            r.fx_date AS fx_rate_date
        FROM _txn AS t
        LEFT JOIN (
            SELECT
                f.fx_currency, f.fx_date, f.fx_rate,
                LEAD(f.fx_date) OVER (PARTITION BY f.fx_currency ORDER BY f.fx_date)
                    AS next_fx_date
            FROM _fx AS f
        ) AS r
          ON  r.fx_currency = t.{currency_column}
          AND t.{date_column} >= r.fx_date
          -- forward fill: bu kur bir sonraki yayınlanana kadar geçerli,
          -- son kur ise süresiz geçerli.
          AND (r.next_fx_date IS NULL OR t.{date_column} < r.next_fx_date)
        """
    )

    for column in amount_columns:
        converted = converted.withColumn(
            column,
            (F.col(column) * F.col("fx_rate_to_try")).cast("decimal(18,2)"),
        )
    return converted

# %%
# %% [markdown]
# yeni öğrendiğim: DeltaTable.merge() = sql'deki MERGE INTO.
# _row_hash karşılaştırması olmadan her satır her seferinde yeniden yazılır.

# %%
def merge_into_silver(
    df: DataFrame,
    table_name: str,
    key_columns: list[str],
    partition_by: list[str] = None,
) -> dict:
    """silver delta tablosuna upsert, ilk çalıştırmada tabloyu oluşturur"""
    if not spark.catalog.tableExists(table_name):
        writer = df.write.format("delta").mode("overwrite")
        if partition_by:
            writer = writer.partitionBy(*partition_by)
        writer.saveAsTable(table_name)
        return {"created": True, "rows": df.count(), "updated": 0, "inserted": df.count()}

    target = DeltaTable.forName(spark, table_name)
    condition = " AND ".join(f"t.{k} = s.{k}" for k in key_columns)

    (
        target.alias("t")
        .merge(df.alias("s"), condition)

        .whenMatchedUpdateAll(condition="t._row_hash <> s._row_hash")
        .whenNotMatchedInsertAll()
        .execute()
    )

    history = spark.sql(f"DESCRIBE HISTORY {table_name} LIMIT 1").collect()[0]
    metrics = history["operationMetrics"] or {}
    return {
        "created": False,
        "rows": df.count(),
        "updated": int(metrics.get("numTargetRowsUpdated", 0)),
        "inserted": int(metrics.get("numTargetRowsInserted", 0)),
    }

# %%
def quarantine(
    df: DataFrame,
    table_name: str,
    business_key_column: str,
    reason_column: str,
    batch_id: str,
) -> int:
    """hatalı satırları sebebiyle birlikte karantina tablosuna yönlendir"""
    if df.rdd.isEmpty():
        return 0

    quarantined = (
        df.withColumn("_quarantine_ts", F.current_timestamp())
        .withColumn("_quarantine_batch_id", F.lit(batch_id))
        .withColumnRenamed(business_key_column, "_business_key")
        .withColumnRenamed(reason_column, "_quarantine_reason")
    )
    (
        quarantined.write.format("delta")
        .mode("append")
        .option("mergeSchema", "true")
        .saveAsTable(table_name)
    )
    return quarantined.count()

# %%
def add_silver_audit(df: DataFrame, batch_id: str, source_system: str,
                     business_columns: list[str]) -> DataFrame:
    """satırı damgala ve hash'i temizlenmiş değerler üzerinden yeniden hesapla"""
    return (
        df.withColumn("_silver_ts", F.current_timestamp())
        .withColumn("_batch_id", F.lit(batch_id))
        .withColumn("_source_system", F.lit(source_system))
        .withColumn(
            "_row_hash",
            F.sha2(
                F.concat_ws(
                    "||",
                    *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in business_columns],
                ),
                256,
            ),
        )
    )

# %%
def now_string() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

# %%
print("silver common helpers loaded")
