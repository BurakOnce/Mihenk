# Fabric setup

What to create, where, and in what order. Written so that someone with a fresh
workspace can reproduce the platform from this repository alone.

Everything here is *reproducible*, but note honestly: at the time of writing the
platform has been built and its artefacts exported, and the verification items in
[ADR-0002](../docs/adr/0002-hybrid-spark-and-tsql-architecture.md) are still
`Pending` because no Fabric capacity was available. Those items are listed in
§7 and are the first thing to run once capacity exists.

---

## 0. Capacity — read this before anything else

Every Fabric item below (Lakehouse, Warehouse, Notebook, Pipeline) requires the
workspace to be assigned to a **Fabric capacity**. Neither a Power BI Pro licence
nor the "Fabric (Free)" entitlement is enough — those allow Power BI content, not
Lakehouse or Warehouse items.

Three ways to get one:

| Route | Cost | Catch |
|---|---|---|
| **Fabric Trial** | Free, 60 days | Requires a work/school account in a managed tenant. Self-service tenants created by signing up to Power BI with a personal email are frequently refused, with the message "Fabric trial is not available for your account" |
| **Azure F-SKU, pay-as-you-go** | ~$0.36/hour at F2 | Needs an Azure subscription and a card. F2 is enough for this project. **Pause the capacity in the Azure portal when not working** — it bills by the hour whether anything runs or not |
| **Existing organisational capacity** | — | Ask whoever administers it to assign your workspace |

If the trial is refused, the Azure F2 route is the reliable one: create a
**Microsoft Fabric capacity** resource in the Azure portal (West Europe is the
closest region to Turkey), then assign it in **Workspace settings → License
info → Fabric capacity**.

---

## 1. Workspace and items

1. **app.fabric.microsoft.com** → Workspaces → **New workspace**
   - Name: `mihenk`
   - Advanced → Fabric capacity → select the capacity from §0
2. Inside the workspace, **+ New item**:

| Item | Type | Name |
|---|---|---|
| Lakehouse | Lakehouse | `mihenk_lh` |
| Warehouse | Warehouse | `mihenk_wh` |

Create the Lakehouse **first**. The Warehouse needs to reach the Lakehouse's SQL
endpoint by three-part naming later, and both being in the same workspace is what
makes that possible at all.

---

## 2. Generate and upload the source data

Locally:

```bash
python -m data_generator --clean
python tools/generate_ctl_seed.py
python tools/build_notebooks.py
```

That produces roughly 150 MB across 2,326 files in `data/`. Uploading that
through the browser is not realistic — the Lakehouse upload dialog handles a
handful of files, not two thousand across 1,845 folders.

**Use OneLake File Explorer** (Windows):

1. Download and install it from Microsoft (search "OneLake File Explorer")
2. Sign in with the same account; OneLake appears in Windows Explorer like
   OneDrive does
3. Navigate to `OneLake\mihenk\mihenk_lh.Lakehouse\Files\`
4. Copy the **contents** of the local `data/` folder there — the six source
   folders only:

```
Files/
├── crm/
├── dms/
├── finance/
├── parts/
├── portal/
└── workshop/
```

**Do not copy** `_injection_log.csv`, `_mdm_truth.csv` or `_manifest.json`. They
are answer keys and metadata, not source data. They live at the root of `data/`
precisely so that copying the six folders leaves them behind — a platform that
reads its own answer key is not measuring anything.

Expect the copy to take a while: the workshop feed alone is 1,836 small files.
That slowness is itself the point being demonstrated — see the note on the
small-file problem in §6.

Alternative: **Azure Storage Explorer** connected to the OneLake endpoint, which
handles bulk uploads more gracefully and shows progress properly.

---

## 3. Create the control plane

Open `mihenk_wh` → **New SQL query**, and run these in order. Each is a separate
file so a failure is easy to locate.

| # | File | What it creates |
|---|---|---|
| 1 | `sql/00_control/00_create_schemas.sql` | `ctl` and `gold` schemas |
| 2 | `sql/00_control/10_source_config.sql` | ingestion metadata table |
| 3 | `sql/00_control/20_pipeline_run_log.sql` | run log + reconciliation view |
| 4 | `sql/00_control/30_dq_framework.sql` | `dq_rule`, `dq_result`, `dq_violation` |
| 5 | `sql/00_control/40_dq_runner.sql` | `usp_run_dq_rules` + scorecard view |
| 6 | `sql/00_control/50_vin_reference.sql` | ISO 3779 tables + check-digit view |
| 7 | `sql/00_control/80_logging_procs.sql` | logging and watermark procedures |
| 8 | `sql/00_control/60_seed_source_config.sql` | 17 source rows (generated) |
| 9 | `sql/00_control/70_seed_dq_rules.sql` | 25 DQ rules (generated) |

Files 6 and 9 reference `silver.*` tables that do not exist until Phase 3. The
view in file 6 will fail to create until then — run it after the Silver notebook
has produced its tables, or create empty Silver tables first. The DQ rule rows in
file 9 are inert until `usp_run_dq_rules` is called, so seeding them early is
harmless.

Check it worked:

```sql
SELECT source_system, entity, load_type, encoding, watermark_column
FROM ctl.source_config ORDER BY load_order;
-- expect 17 rows, dms.* on windows-1254, workshop.* with checkin_ts

SELECT rule_code, COUNT(*) AS rules, severity
FROM ctl.dq_rule GROUP BY rule_code, severity ORDER BY rule_code;
-- expect 25 rules across 21 codes
```

---

## 4. Import the notebook

1. Workspace → **Import** → **Notebook** → **From this computer**
2. Select `fabric/notebooks/01_bronze_ingest.ipynb`
3. Open it, and in the left-hand **Explorer** pane add `mihenk_lh` as the
   **default Lakehouse**

That last step is not optional and is the single most common thing to get wrong.
Without a default Lakehouse the relative path `Files/dms/dealer_*.csv` resolves
to nothing, and the error message points at the file rather than at the missing
binding.

Test it by hand before wiring the pipeline: run the notebook as-is. The
parameters cell defaults to the DMS dealer feed, so a successful run reads 44
files and writes `bronze.dms_dealer`.

Then check the encoding actually worked:

```sql
SELECT TOP 5 dealer_code, dealer_name, city FROM bronze.dms_dealer;
```

City names must read `İstanbul`, `Şanlıurfa`, `Muğla`. If they show as `Ýstanbul`
or `?stanbul`, the `encoding` option did not take effect — check
`ctl.source_config.encoding` for that row.

---

## 5. Build the pipeline

`fabric/pipelines/pl_bronze_ingest.json` is the definition, but be realistic
about it: hand-authored Fabric pipeline JSON usually needs adjustment on import,
because connection references and artifact ids are tenant-specific. Every
`REPLACE_WITH_*` placeholder in that file is a GUID that only exists in your
workspace.

Two routes:

**a. Import the JSON**, then open the pipeline and repair each activity's
connection. Faster if the import succeeds.

**b. Build it in the UI** from the JSON as a specification. Slower, but it fails
in obvious places rather than subtle ones. The structure:

```
Set batch id            SetVariable   B + yyyyMMddHHmmss
Start batch             Script        EXEC ctl.usp_start_batch
Read source config      Lookup        SELECT ... FROM ctl.source_config
                                      firstRowOnly = false
For each source         ForEach       items = @activity('Read source config').output.value
                                      isSequential = true
  ├─ Log step start     Script        EXEC ctl.usp_log_step_start   -> returns run_id
  ├─ Run bronze         Notebook      01_bronze_ingest
  │                                   batch_id   = @variables('batch_id')
  │                                   config_json = @string(item())
  ├─ Log step success   Script        on Success  - EXEC ctl.usp_log_step_end
  ├─ Advance watermark  Script        on Success  - EXEC ctl.usp_advance_watermark
  └─ Log step failure   Script        on Failure  - EXEC ctl.usp_log_step_end 'FAILED'
End batch               Script        on Completed - EXEC ctl.usp_end_batch
```

Two decisions in there worth being able to defend:

**`isSequential = true`.** Running seventeen sources in parallel would be faster
and wrong for two reasons. `load_order` exists to put master data ahead of the
transactions that reference it, and parallelism discards that ordering. And the
`MAX(run_id) + 1` key generation in `ctl.usp_log_step_start` is only safe without
concurrency — Fabric Warehouse has no IDENTITY, so parallel logging would need a
different key strategy before it would be correct.

**`Advance watermark` runs last, and only on success.** The watermark is not
written when the notebook finishes reading; it is written after the rows are
committed *and* logged. A crash anywhere earlier leaves the old value, the next
run re-reads the same window, and Bronze deletes its own batch before appending —
so re-reading is harmless. Skipping would lose rows permanently.

---

## 5b. Silver, Gold and the daily orchestration

Bronze is only the first third. On its own, `pl_bronze_ingest` leaves Silver to
be run by hand from four notebooks and Gold to be run from SSMS with an `EXEC`.
That is fine for a first end-to-end run and wrong for anything that runs twice.
Three more pipelines close the gap; their definitions are in `fabric/pipelines/`
and follow exactly the same logging contract as Bronze.

```
pl_daily_load                    ← the only thing the schedule triggers
├─ Set batch id                  one batch_id for the whole night
├─ Bronze     InvokePipeline     pl_bronze_ingest      (batch_id)
├─ Silver     InvokePipeline     pl_silver_transform   (batch_id, pii_salt)   on Bronze success
└─ Gold       InvokePipeline     pl_gold_load          (batch_id)             on Silver success
```

**`pl_silver_transform`** — four notebooks, strictly in order, each one a logged
step:

```
Set batch id                 SetVariable   from parameter, or generated
Start batch                  Script        EXEC ctl.usp_start_batch @layer='silver'
Log start 10_silver_master   Script        EXEC ctl.usp_log_step_start  -> run_id
Run 10_silver_master         Notebook      batch_id, pii_salt
Log success / Log failure    Script        EXEC ctl.usp_log_step_end  (rows_written from exitValue)
Log start 20_silver_customer_mdm ... Run ... (batch_id, pii_salt, match_threshold=55) ... success/failure
Log start 30_silver_transaction  ... Run ... (batch_id, pii_salt)                    ... success/failure
Read dq rules                Lookup        SELECT ... FROM ctl.dq_rule WHERE is_active = 1
Log start 40_silver_dq       Script
Run 40_silver_dq             Notebook      batch_id, rules_json = @string(activity('Read dq rules').output.value)
Log success / Log failure    Script        (rows_quarantined from exitValue)
End batch                    Script        on Succeeded | Failed | Skipped of the last run
```

Each `Log start` depends on the *previous step's* `Log success`, so a failure
anywhere stops the chain: the failed step is logged with its error message, the
later steps are skipped, and `End batch` still closes the batch so
`ctl.vw_batch_reconciliation` shows an honest picture rather than a batch that
never ended.

**`pl_gold_load`** — two logged Script steps, no notebooks:

```
Start batch (gold)  →  Run usp_load_gold  →  Run usp_verify_gold  →  End batch
```

`usp_load_gold` is the incremental path (dimensions, inferred members, facts,
aggregates). The backfill procedures are deliberately *not* here — they are the
one-time first load (`usp_initial_load`) and re-running them is guarded anyway.

### Building them

Same two routes as §5. If importing the JSON, replace every `REPLACE_WITH_*`
placeholder: the four notebook ids, the three pipeline ids (for
`pl_daily_load`), the Warehouse connection. If building in the UI, the tables
above are the spec; the only non-obvious settings are:

- **Notebook activity parameters:** `batch_id` and `pii_salt` are type *string*;
  `match_threshold` is type *int* (a string here would make Spark compare
  `match_score >= "55"`). `rules_json` is string.
- **`Read dq rules` Lookup:** `firstRowOnly = false`. Its output is an array;
  `@string(...)` turns it into the JSON text the DQ notebook expects.
- **`End batch` dependency:** on the last `Run` activity with *Succeeded,
  Failed and Skipped* all ticked — not "Completed", which excludes Skipped.
- **`Log start` → `@source_id = NULL`:** Silver and Gold steps are not per-source,
  so `ctl.pipeline_run_log.source_id` stays empty for them; `step_name` carries
  the notebook or procedure name instead.
- **InvokePipeline in `pl_daily_load`:** `waitOnCompletion = true`, and the
  child's `batch_id` parameter bound to `@variables('batch_id')` so all three
  layers share one id.

### Scheduling

Only `pl_daily_load` gets a schedule (pipeline → Schedule → daily, e.g. 02:00).
The three children are never scheduled directly; running one by hand for a
re-run is fine and it will generate its own `batch_id` if none is passed.

### The one thing this changes about the notebooks

Nothing in their code. Every Silver notebook already had a
`tags=["parameters"]` cell and already returned its summary through
`notebookutils.notebook.exit`. The pipeline is the missing caller, not a
rewrite — which is the point of having built them that way.

**`pii_salt` is a pipeline parameter, not a notebook default.** The value in
the notebooks is a placeholder. In a real deployment the parameter is bound to a
Key Vault secret at the `pl_daily_load` level and flows down; nothing about the
salt lives in a `.py` file or in Git.

---

## 6. What to expect on the first run

| | |
|---|---|
| Sources | 17 |
| Bronze rows | ~1,066,933 |
| Longest step | `workshop.repair_order_line` — 626,073 rows across 918 folders |

The workshop feed is slow out of proportion to its size, and that is worth
understanding rather than tuning away: 1,836 files averaging under 60 KB each is
the **small-file problem**. Spark spends more time opening files than reading
them. It is here because a real daily drop looks exactly like this.

The fix is compaction, and it belongs in Phase 3 rather than here — Bronze's job
is to land the file faithfully:

```sql
-- run in a notebook cell against the Lakehouse
OPTIMIZE bronze_workshop_repair_order_line;
```

---

## 7. Verification checklist

These are the ADR-0002 items. Run them once capacity exists and record the result
in that ADR's table with a date.

```sql
-- 1) IDENTITY - expected to FAIL. If it fails, the surrogate key pattern in
--    Gold (ROW_NUMBER + MAX) is required rather than merely chosen.
CREATE TABLE ctl.zz_test_identity (id INT IDENTITY(1,1), t VARCHAR(10));

-- 2) PRIMARY KEY enforcement - expected to ACCEPT the duplicate
CREATE TABLE ctl.zz_test_pk (id INT NOT NULL, t VARCHAR(10));
ALTER TABLE ctl.zz_test_pk ADD CONSTRAINT pk_zz PRIMARY KEY NONCLUSTERED (id) NOT ENFORCED;
INSERT INTO ctl.zz_test_pk VALUES (1, 'a'), (1, 'b');
SELECT COUNT(*) FROM ctl.zz_test_pk;   -- 2 means constraints are not enforced

-- 3) MERGE - decides which SCD2 procedure Gold uses
CREATE TABLE ctl.zz_target (id INT, t VARCHAR(10));
CREATE TABLE ctl.zz_source (id INT, t VARCHAR(10));
INSERT INTO ctl.zz_target VALUES (1, 'old');
INSERT INTO ctl.zz_source VALUES (1, 'new'), (2, 'added');
MERGE ctl.zz_target AS tgt
USING ctl.zz_source AS src ON tgt.id = src.id
WHEN MATCHED THEN UPDATE SET tgt.t = src.t
WHEN NOT MATCHED THEN INSERT (id, t) VALUES (src.id, src.t);
SELECT * FROM ctl.zz_target ORDER BY id;   -- expect 1/'new' and 2/'added'

-- 4) Cross-item query, Warehouse -> Lakehouse SQL endpoint.
--    HARD PREREQUISITE for Phase 4. Replace mihenk_lh if named differently.
SELECT TOP 10 * FROM mihenk_lh.dbo.bronze_dms_dealer;

-- 6) Delta -> Warehouse type mapping. Inspect what DECIMAL, TIMESTAMP and long
--    string columns become when read across the endpoint.
SELECT TOP 1 * FROM mihenk_lh.dbo.bronze_dms_sales_contract;

-- cleanup
DROP TABLE IF EXISTS ctl.zz_test_identity;
DROP TABLE IF EXISTS ctl.zz_test_pk;
DROP TABLE IF EXISTS ctl.zz_target;
DROP TABLE IF EXISTS ctl.zz_source;
```

Item 5 (`DeltaTable.merge()` idempotency) runs in a notebook — the Silver
notebook exercises it directly, and running that notebook twice and comparing
row counts is the test.

Item 7 (Direct Lake with the Trial SKU) is a Phase 5 concern.

**If item 3 fails**, Gold uses the `UPDATE` + `INSERT` SCD Type 2 procedure
instead of the `MERGE` one. Both are written and both are in
`sql/03_gold/`; the choice is a one-line change in the load orchestration.

**If item 4 fails**, the DQ runner moves from the Warehouse stored procedure into
the Silver notebook, executing the same `violation_sql` rows through
`spark.sql()`. The rule definitions do not change — which is the main argument
for keeping rules as data rather than as code.

---

## 8. Fabric Warehouse gotchas found by actually running this

None of these are documented anywhere as clearly as they show up in practice.
All were found running this exact codebase on a real F2 capacity; every fix is
already applied in `sql/` and `fabric/notebooks/` — this section exists so the
next person (or the next `git blame`) knows why the code looks the way it does.

- **A schema-enabled Lakehouse doesn't create `bronze`/`silver` for you.**
  Run `spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")` (and `silver`) once,
  by hand, before the first notebook write — `saveAsTable("bronze.x")`
  otherwise fails with `SCHEMA_NOT_FOUND`.
- **`CREATE TABLE #t` + a separate `INSERT INTO #t SELECT` is rejected
  outright** — `"references an object that is not supported in distributed
  processing mode"` — confirmed down to the simplest possible case, nothing to
  do with query complexity. `SELECT ... INTO #t` (CTAS-style) is the only form
  that works, and it's used everywhere in `sql/03_gold/` as a result.
- **`sys.columns` cross-joined with itself** (the classic tally-table trick)
  is rejected the same way — system catalog views can't be joined in the
  distributed engine. `GENERATE_SERIES` (`ctl.util_numbers`, seeded in
  `sql/00_control/90_util_numbers.sql`) is the replacement, and it needs SQL
  Server 2022+ if you're also testing this locally.
- **`ROW_NUMBER() OVER (ORDER BY (SELECT NULL))` is *also* rejected**, even
  over a plain `VALUES`-derived table with no window-function history at all.
  It isn't specific to `sys.columns`.
- **Every cross-item reference to Bronze/Silver from a Warehouse procedure
  needs the full three-part name**: `mihenk_lh.bronze.x` / `mihenk_lh.silver.x`,
  never the unqualified `bronze.x` / `silver.x` — those only resolve to
  objects that live *in the Warehouse's own database*.
- **`IDENTITY` is real but narrow**: `BIGINT` only (not `INT`), and only the
  bare, implicit `IDENTITY` — no explicit `IDENTITY(seed, increment)`. Gold
  still doesn't use it (see ADR-0002 item 1's real result), but if you reach
  for it elsewhere, this is the actual constraint.
- **Delta `string` columns all become `varchar(8000)`** on the Warehouse SQL
  endpoint regardless of actual content length — there's no length metadata
  to inherit. Size Gold's own `VARCHAR(n)` columns deliberately; don't expect
  the source to constrain anything.
- **Raw Bronze money fields are still Turkish comma-decimal text**
  (`"1989500,0"`) — a plain `CAST(x AS DECIMAL)` fails. Anything reading
  straight from Bronze (the SCD2 backfill procedures, which exist specifically
  because Silver only holds current state) needs
  `TRY_CAST(REPLACE(x, ',', '.') AS DECIMAL(18,2))` — Silver's own
  `parse_decimal(turkish=True)` already handles this for anything reading
  from Silver instead.
- **A sentinel dimension row needs attribute values that can never occur
  naturally.** `gold.dim_transaction_flag`'s `-1` row was seeded with the same
  `(0, 'NA', 'NA', 0, 0, 0)` combination as a real row, and every natural-key
  join against it matched both — silently doubling the fact. Every load query
  joining a junk/degenerate dimension by attribute combination (not a single
  fake code like `'-1'`) needs an explicit `AND dim.surrogate_key > 0`.
