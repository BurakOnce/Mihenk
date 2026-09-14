# Naming Standard

**Status:** Active since Phase 0. Any change requires a new ADR.
**Rationale:** [ADR-0001](adr/0001-naming-and-language-standard.md)

Every object in this platform — schema, table, column, file, notebook, pipeline,
measure — follows the rules below. The point is not aesthetics: consistent names
mean a reviewer can guess an object's name before looking it up, and the
generated documentation (`docs/data_dictionary.md`, `docs/lineage.md`) can be
built from metadata instead of hand-written.

---

## 1. Language

**All identifiers are English. All data content stays in its natural language.**

| Thing | Language | Example |
|---|---|---|
| Schema, table, column, view, procedure | English | `gold.dim_vehicle.plate_number` |
| File, folder, notebook, pipeline | English | `fabric/notebooks/01_bronze_ingest.ipynb` |
| Code comments and docstrings | English | `# Trim is the equipment package, not the model` |
| Documentation and ADRs | English | this file |
| **Data values** | **Whatever they really are** | customer name `Şükrü Öztürk`, city `İstanbul` |

The last row is the one that matters. Turkish characters are banned from
*identifiers*, not from *data*. Customer names, dealer names and city names are
stored with full Turkish characters in `NVARCHAR` / Spark `string` columns.
Losing them would be a data quality defect, not a simplification.

Business terms are translated to their **industry-standard English**, not to a
literal dictionary equivalent:

| Turkish business term | Identifier | Why this word |
|---|---|---|
| İş emri | `repair_order` | "Repair Order" (RO) is the universal term in dealer management systems |
| Donanım paketi | `trim` | Standard automotive term for an equipment level |
| Bayi | `dealer` | Not "branch" — a dealer is a legally separate franchise |
| Geri çağırma | `recall` | |
| Takas | `trade_in` | |
| Yetkili servis | `service` | |
| Periyodik bakım | `maintenance` | |
| Ekspertiz | `inspection` | |

---

## 2. Casing and characters

- `snake_case` everywhere. No camelCase, no PascalCase, no spaces.
- Lower case only. SQL keywords in DDL are UPPER CASE; identifiers are not.
- Allowed characters: `a-z`, `0-9`, `_`. Nothing else — no `ı`, `ş`, `ğ`, `ç`,
  `ö`, `ü`, no hyphens, no dots inside a name.
- Never a digit as the first character.
- Singular nouns for entities: `dim_vehicle`, not `dim_vehicles`.
- Do not abbreviate unless the abbreviation *is* the industry term. `vin`,
  `vat`, `sku`, `dq`, `sk`, `fx` are fine. `cust`, `veh`, `qty` are not — write
  `customer`, `vehicle`, `quantity`.

**Why the ASCII restriction:** the same column name has to survive Parquet /
Delta metadata, the Fabric Warehouse T-SQL parser, Power BI DAX and Python
attribute access. On top of that, Turkish has the dotted/dotless `i` problem:
`"İSTANBUL".lower()` gives a different result depending on locale, so any
`upper()` / `lower()` normalisation applied to a Turkish identifier is a silent
correctness bug waiting to happen. Cheap risk, so we remove it entirely.

---

## 3. Schemas (layers)

| Schema | Meaning | Lives in |
|---|---|---|
| `ctl` | Control plane: ingestion config, run log, DQ rules and results | Fabric Warehouse |
| `bronze` | Raw landed data, no transformation | Fabric Lakehouse (Delta) |
| `silver` | Cleansed, conformed, deduplicated, PII-masked | Fabric Lakehouse (Delta) |
| `gold` | Star schema for consumption | Fabric Warehouse |

---

## 4. Table name prefixes

| Prefix | Meaning | Example |
|---|---|---|
| `dim_` | Dimension | `gold.dim_vehicle` |
| `fact_` | Fact | `gold.fact_repair_order` |
| `agg_` | Pre-aggregated table | `gold.agg_monthly_dealer_model_sale` |
| `br_` | Bridge table (many-to-many) | `gold.br_vehicle_ownership` |
| `ref_` | Reference / lookup data | `silver.ref_fx_rate` |
| `quarantine_` | Rows rejected by a critical DQ rule | `silver.quarantine_repair_order` |
| *(none)* | Bronze / Silver entity tables mirror the source entity | `bronze.dms_sales_contract` |

Bronze tables carry a **source-system prefix** so two systems can hold the same
entity without collision: `bronze.dms_customer` and `bronze.crm_customer` are
different tables and must stay different until MDM merges them in Silver.

---

## 5. Column name suffixes

The suffix declares the column's *kind of meaning*. Reading a fact table's
column list should tell you which columns are keys, which are measures and which
are degenerate dimensions, without opening the DDL.

| Suffix | Meaning | Type | Example |
|---|---|---|---|
| `_sk` | Surrogate key (integer, platform-generated) | `BIGINT` | `vehicle_sk` |
| `_id` | Natural / business key from a source system | `VARCHAR` | `customer_id` |
| `_no` | Human-facing document number | `VARCHAR` | `repair_order_no` |
| `_code` | Short coded value | `VARCHAR` | `country_code` |
| `_date` | Calendar date, no time part | `DATE` | `delivery_date` |
| `_ts` | Point in time with a time part | `DATETIME2` | `checkin_ts` |
| `_amount` | Monetary value, **always TRY** after Silver | `DECIMAL(18,2)` | `net_sale_amount` |
| `_amount_src` | Monetary value in the original currency | `DECIMAL(18,2)` | `net_sale_amount_src` |
| `_quantity` | Countable amount | `DECIMAL(18,3)` | `ordered_quantity` |
| `_hours` | Duration in hours | `DECIMAL(9,2)` | `labour_hours` |
| `_days` | Duration in whole days | `INT` | `days_in_stock` |
| `_rate` | Ratio, stored as 0–1 (never 0–100) | `DECIMAL(9,6)` | `discount_rate` |
| `_count` | Row / event count in an aggregate | `BIGINT` | `sale_count` |

Booleans are named `is_<adjective>` or `has_<noun>` (`is_warranty`,
`is_used_vehicle`, `has_trade_in`) and typed `BIT`. Never a negative name —
`is_active`, never `is_not_active`, because `WHERE NOT is_not_active` is how
bugs happen.

**Currency rule:** any column ending in `_amount` is Turkish Lira, guaranteed by
Silver. Where the original currency must be preserved it goes into a parallel
`_amount_src` column plus `currency_code` and `fx_rate`. This makes "did you
remember to convert?" answerable from the column name alone.

---

## 6. Technical columns

Technical columns start with an underscore so they sort together and stay
visually distinct from business columns.

**Bronze audit columns — mandatory on every Bronze table:**

| Column | Meaning |
|---|---|
| `_ingest_ts` | When this row was written to Bronze |
| `_source_system` | Which source produced it (`dms`, `crm`, `workshop`, `parts`, `portal`, `finance`) |
| `_source_file` | Full path of the file it came from |
| `_batch_id` | Links the row to one row in `ctl.pipeline_run_log` |
| `_row_hash` | Hash of the business columns; drives change detection and idempotency |

**SCD Type 2 columns — mandatory on every Type 2 dimension:**

| Column | Meaning |
|---|---|
| `<entity>_sk` | Surrogate key — unique per *version*, not per entity |
| `<entity>_id` | Natural key — identical across all versions of one entity |
| `valid_from` | Inclusive start of this version's validity |
| `valid_to` | Exclusive end; the open version uses `9999-12-31` |
| `is_current` | `1` for the open version. Redundant with `valid_to` on purpose — it makes the most common query cheap and readable |
| `_row_hash` | Hash of the tracked attributes; a change here is what opens a new version |

**Special dimension members** — identical convention in every dimension:

| `_sk` | Meaning |
|---|---|
| `-1` | Unknown — the source value was null, blank or unmappable |
| `-2` | Not applicable — the relationship genuinely does not exist for this row |

Inferred (late-arriving) members get a normal positive `_sk` plus
`is_inferred = 1`, so they can be reported on and back-filled later.

---

## 7. Files and folders

- `NN_short_name.ext`, where `NN` is a two-digit execution order:
  `sql/03_gold/10_dim_vehicle.sql`, `fabric/notebooks/20_silver_customer.ipynb`.
  Execution order must be readable from a directory listing.
- ADRs: `docs/adr/NNNN-kebab-case-title.md`. Numbers are never reused.
- Notebooks: `NN_<layer>_<subject>.ipynb`.
- Pipelines: `pl_<subject>`, e.g. `pl_bronze_ingest`.
- Generator modules: one source system per module —
  `src/data_generator/dms.py`, `crm.py`, `workshop.py`.

---

## 8. Power BI

- Semantic model tables drop the `dim_` / `fact_` prefix and use Title Case with
  spaces: `dim_vehicle` becomes **Vehicle**, `fact_repair_order` becomes
  **Repair Order**. Report users should never see engineering prefixes.
- Measures are Title Case with spaces: `Net Sale Amount`, `Days In Stock`,
  `Service Retention Rate`.
- Measures live in a dedicated `_Measures` table.
- Every `_sk` column is hidden. Users filter on attributes, not on keys.

---

## 9. Target object catalog

The full set of Gold objects this project builds, named up front so Phases 1–4
have a fixed target and the data dictionary can be generated against it.

### Facts

| Object | Grain | Fact type |
|---|---|---|
| `gold.fact_vehicle_sale` | One sales contract line | Transaction |
| `gold.fact_repair_order` | One repair order | Accumulating snapshot |
| `gold.fact_repair_order_line` | One repair order line (part or labour) | Transaction |
| `gold.fact_part_purchase` | One purchase order line | Transaction |
| `gold.fact_vehicle_inventory_daily` | One vehicle per day held in stock | Periodic snapshot |
| `gold.fact_recall_coverage` | One VIN per recall campaign | Factless |
| `gold.fact_data_quality` | One DQ rule execution per batch | Governance |

### Dimensions

| Object | SCD | Natural key |
|---|---|---|
| `gold.dim_date` | n/a | `date_key` (`YYYYMMDD`) |
| `gold.dim_vehicle` | Type 2 | `vin` |
| `gold.dim_model_trim` | Type 2 | `model_trim_code` |
| `gold.dim_customer` | Type 2 | `master_customer_id` (MDM golden record) |
| `gold.dim_dealer` | Type 2 | `dealer_code` |
| `gold.dim_employee` | Type 2 | `employee_id` |
| `gold.dim_part` | Type 2 | `part_no` |
| `gold.dim_supplier` | Type 1 | `supplier_id` |
| `gold.dim_service_type` | Type 1 | `service_type_code` |
| `gold.dim_transaction_flag` | Type 1 | junk dimension, generated key |

### Aggregates

| Object | Grain |
|---|---|
| `gold.agg_monthly_dealer_model_sale` | Month × dealer × model/trim |
| `gold.agg_monthly_service_summary` | Month × dealer × service type |

### Control

| Object | Purpose |
|---|---|
| `ctl.source_config` | Metadata-driven ingestion definitions |
| `ctl.pipeline_run_log` | Per-batch execution audit and row reconciliation |
| `ctl.dq_rule` | Declarative data quality rule definitions |
| `ctl.dq_result` | Rule execution results per batch |
