
# %% tags=["parameters"]
batch_id = "manual-dev-run"
config_json = """
{
  "source_id": 1,
  "source_system": "dms",
  "entity": "dealer",
  "target_table": "bronze.dms_dealer",
  "file_pattern": "dms/dealer_*.csv",
  "is_date_partitioned": 0,
  "file_format": "csv",
  "delimiter": ";",
  "decimal_mark": ",",
  "encoding": "windows-1254",
  "has_header": 1,
  "sheet_name": null,
  "load_type": "full",
  "watermark_column": null,
  "watermark_value": null,
  "key_columns": "dealer_code"
}
"""

# %%
import json
from datetime import datetime, timezone

from pyspark.sql import DataFrame, functions as F

# %%
try:
    import notebookutils
    utils = notebookutils
except ImportError:
    import mssparkutils as utils

# %%
config = json.loads(config_json)

# %%
SOURCE_SYSTEM = config["source_system"]
# %%
ENTITY = config["entity"]
# %%
TARGET_TABLE = config["target_table"]
# %%
FILE_FORMAT = config["file_format"]
# %%
LOAD_TYPE = config["load_type"]

# %%
FILES_ROOT = "Files"

# %%
print(f"batch      : {batch_id}")
# %%
print(f"source     : {SOURCE_SYSTEM}.{ENTITY}  ->  {TARGET_TABLE}")
# %%
print(f"format     : {FILE_FORMAT}   load: {LOAD_TYPE}")
# %%
print(f"pattern    : {config['file_pattern']}")
# %%
print(f"watermark  : {config['watermark_column']} > {config['watermark_value']}")

# %%
def resolve_paths(config: dict) -> list[str]:
    """bu çalıştırmanın okuması gereken yolları döndür"""
    pattern = config["file_pattern"]

    if not config["is_date_partitioned"]:
        return [f"{FILES_ROOT}/{pattern}"]

    entity_root = f"{FILES_ROOT}/{pattern.split('/*/')[0]}"
    watermark = config.get("watermark_value")

    folders = [item.name.rstrip("/") for item in utils.fs.ls(entity_root) if item.isDir]

    if config["load_type"] == "incremental" and watermark:

        folders = [f for f in folders if f > watermark[:10]]

    folders.sort()
    print(f"  {len(folders)} day folder(s) to read"
          + (f", from {folders[0]} to {folders[-1]}" if folders else ""))
    return [f"{entity_root}/{folder}/" for folder in folders]

# %%
paths = resolve_paths(config)
# %%
if not paths:

    utils.notebook.exit(json.dumps(
        {"status": "SKIPPED", "reason": "no new files", "rows_read": 0, "rows_written": 0,
         "rows_rejected": 0, "files_read": 0, "watermark_to": ""}
    ))

# %%
def read_csv(paths: list[str], config: dict) -> DataFrame:
    reader = (
        spark.read.format("csv")
        .option("header", "true" if config["has_header"] else "false")
        .option("sep", config["delimiter"] or ",")
        .option("encoding", config["encoding"] or "utf-8")

        .option("inferSchema", "false")

        .option("mode", "PERMISSIVE")
    )
    return reader.load(paths)

# %%
def read_json(paths: list[str], multiline: bool) -> DataFrame:
    return (
        spark.read.format("json")
        .option("multiline", "true" if multiline else "false")
        .load(paths)
    )

# %%
def read_xlsx(config: dict) -> DataFrame:
    """excel pandas ile okunur, sonra spark'a verilir"""
    import glob as _glob

    import pandas as pd

    local_pattern = f"/lakehouse/default/{FILES_ROOT}/{config['file_pattern']}"
    matches = sorted(_glob.glob(local_pattern))
    if not matches:
        raise FileNotFoundError(f"no workbook matched {local_pattern}")

    frames = [
        pd.read_excel(path, sheet_name=config["sheet_name"], dtype=str)
        for path in matches
    ]
    combined = pd.concat(frames, ignore_index=True)

    combined = combined.astype(str).where(combined.notna(), None)
    return spark.createDataFrame(combined)

# %%
if FILE_FORMAT == "csv":
    raw = read_csv(paths, config)
elif FILE_FORMAT == "json":
    raw = read_json(paths, multiline=True)
elif FILE_FORMAT == "jsonl":
    raw = read_json(paths, multiline=False)
elif FILE_FORMAT == "xlsx":
    raw = read_xlsx(config)
else:
    raise ValueError(f"unsupported file_format {FILE_FORMAT!r} for {TARGET_TABLE}")

# %%
rows_read = raw.count()
# %%
print(f"  read {rows_read:,} rows across {len(paths)} path(s)")
# %%
raw.printSchema()

# %%
business_columns = [c for c in raw.columns if not c.startswith("_")]

# %%
bronze = (
    raw
    .withColumn("_ingest_ts", F.current_timestamp())
    .withColumn("_source_system", F.lit(SOURCE_SYSTEM))
    .withColumn("_source_file", F.input_file_name())
    .withColumn("_batch_id", F.lit(batch_id))
    .withColumn(
        "_row_hash",
        F.sha2(
            F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"), F.lit(""))
                                for c in business_columns]),
            256,
        ),
    )
)

# %%
if FILE_FORMAT == "xlsx":
    bronze = bronze.withColumn("_source_file", F.lit(config["file_pattern"]))

# %%
print(f"  {len(business_columns)} business columns + 5 audit columns")

# %%
table_exists = spark.catalog.tableExists(TARGET_TABLE)

# %%
if table_exists:

    safe_batch = batch_id.replace("'", "''")
    deleted = spark.sql(
        f"DELETE FROM {TARGET_TABLE} WHERE _batch_id = '{safe_batch}'"
    )
    print(f"  cleared any previous rows for batch {batch_id}")

# %%
(
    bronze.write
    .format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(TARGET_TABLE)
)

# %%
rows_written = spark.sql(
    f"SELECT COUNT(*) AS n FROM {TARGET_TABLE} WHERE _batch_id = '{batch_id}'"
).collect()[0]["n"]

# %%
print(f"  wrote {rows_written:,} rows to {TARGET_TABLE}")

# %%
new_watermark = None
# %%
if LOAD_TYPE == "incremental":
    if config["is_date_partitioned"]:
        new_watermark = paths[-1].rstrip("/").split("/")[-1]
    elif config["watermark_column"] and config["watermark_column"] in raw.columns:
        new_watermark = (
            raw.agg(F.max(F.col(config["watermark_column"])).alias("m"))
            .collect()[0]["m"]
        )
        new_watermark = str(new_watermark) if new_watermark is not None else None

# %%
result = {
    "status": "SUCCEEDED",
    "source_id": config["source_id"],
    "target_table": TARGET_TABLE,
    "rows_read": int(rows_read),
    "rows_written": int(rows_written),
    "rows_rejected": int(rows_read - rows_written),
    "files_read": len(paths),
    "watermark_from": config.get("watermark_value"),
    "watermark_to": new_watermark,
    "finished_ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
}

# %%
print(json.dumps(result, indent=2))
# %%
utils.notebook.exit(json.dumps(result))
