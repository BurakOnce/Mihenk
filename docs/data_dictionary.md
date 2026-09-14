# Data dictionary

**GENERATED FILE — do not edit by hand.**

Produced by `tools/generate_docs.py`, parsed from the `CREATE TABLE`
statements in `sql/` and the source metadata in `data/_manifest.json`.
Column descriptions come from two places, and the difference is visible:

- **plain text** is an inline comment written in the DDL — somebody
  explained that column deliberately;
- **_italic text_** is derived from the column suffix contract in
  [`naming_standard.md`](naming_standard.md) §5. A column called
  `net_sale_amount` is a monetary value in lira because the standard says
  every `_amount` is, and repeating that four hundred times by hand would
  guarantee that some of them eventually said something different.

A column with neither is a genuine documentation gap and shows as blank,
which is a visible problem rather than a silent one.

Generated: 2026-09-13 09:15:35

**29 tables** across 2 schemas.

---

## Contents

- **`ctl`** — 7 tables
  - [`ctl.dq_result`](#ctldqresult)
  - [`ctl.dq_rule`](#ctldqrule)
  - [`ctl.dq_violation`](#ctldqviolation)
  - [`ctl.pipeline_run_log`](#ctlpipelinerunlog)
  - [`ctl.source_config`](#ctlsourceconfig)
  - [`ctl.vin_transliteration`](#ctlvintransliteration)
  - [`ctl.vin_weight`](#ctlvinweight)
- **`gold`** — 22 tables
  - [`gold.agg_monthly_dealer_model_sale`](#goldaggmonthlydealermodelsale)
  - [`gold.agg_monthly_dealer_target`](#goldaggmonthlydealertarget)
  - [`gold.agg_monthly_service_summary`](#goldaggmonthlyservicesummary)
  - [`gold.dim_customer`](#golddimcustomer)
  - [`gold.dim_date`](#golddimdate)
  - [`gold.dim_dealer`](#golddimdealer)
  - [`gold.dim_employee`](#golddimemployee)
  - [`gold.dim_model_trim`](#golddimmodeltrim)
  - [`gold.dim_part`](#golddimpart)
  - [`gold.dim_service_type`](#golddimservicetype)
  - [`gold.dim_supplier`](#golddimsupplier)
  - [`gold.dim_transaction_flag`](#golddimtransactionflag)
  - [`gold.dim_vehicle`](#golddimvehicle)
  - [`gold.fact_data_quality`](#goldfactdataquality)
  - [`gold.fact_part_purchase`](#goldfactpartpurchase)
  - [`gold.fact_recall_coverage`](#goldfactrecallcoverage)
  - [`gold.fact_repair_order`](#goldfactrepairorder)
  - [`gold.fact_repair_order_line`](#goldfactrepairorderline)
  - [`gold.fact_vehicle_inventory_daily`](#goldfactvehicleinventorydaily)
  - [`gold.fact_vehicle_sale`](#goldfactvehiclesale)
  - [`gold.ref_province`](#goldrefprovince)
  - [`gold.ref_public_holiday`](#goldrefpublicholiday)

---

## Schema `ctl`

### ctl.dq_result

Defined in `sql/00_control/30_dq_framework.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `result_id` | `BIGINT` | no | _Natural key from a source system._ |
| `batch_id` | `VARCHAR(40)` | no | _Natural key from a source system._ |
| `rule_id` | `INT` | no | _Natural key from a source system._ |
| `rule_code` | `VARCHAR(40)` | no | _Short coded value._ |
| `target_table` | `VARCHAR(120)` | no |  |
| `rows_evaluated` | `BIGINT` | no |  |
| `rows_violated` | `BIGINT` | no |  |
| `violation_rate` | `DECIMAL(9,6)` | no | _Ratio stored as 0-1, not 0-100._ |
| `severity` | `VARCHAR(10)` | no |  |
| `outcome` | `VARCHAR(10)` | no |  |
| `error_message` | `VARCHAR(4000)` | yes |  |
| `executed_ts` | `DATETIME2(3)` | no | _Point in time._ |
| `duration_seconds` | `INT` | yes |  |

### ctl.dq_rule

Defined in `sql/00_control/30_dq_framework.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `rule_id` | `INT` | no | _Natural key from a source system._ |
| `rule_code` | `VARCHAR(40)` | no | _Short coded value._ |
| `rule_name` | `VARCHAR(150)` | no | _Display name._ |
| `target_layer` | `VARCHAR(10)` | no |  |
| `target_table` | `VARCHAR(120)` | no |  |
| `target_column` | `VARCHAR(60)` | yes |  |
| `rule_type` | `VARCHAR(20)` | no |  |
| `violation_sql` | `VARCHAR(4000)` | no |  |
| `severity` | `VARCHAR(10)` | no |  |
| `quarantine_on_fail` | `BIT` | no |  |
| `max_violation_rate` | `DECIMAL(5,4)` | yes | _Ratio stored as 0-1, not 0-100._ |
| `is_active` | `BIT` | no | _Boolean flag._ |
| `description` | `VARCHAR(500)` | yes |  |
| `created_ts` | `DATETIME2(3)` | no | _Point in time._ |

### ctl.dq_violation

Defined in `sql/00_control/30_dq_framework.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `violation_id` | `BIGINT` | no | _Natural key from a source system._ |
| `batch_id` | `VARCHAR(40)` | no | _Natural key from a source system._ |
| `rule_id` | `INT` | no | _Natural key from a source system._ |
| `rule_code` | `VARCHAR(40)` | no | _Short coded value._ |
| `target_table` | `VARCHAR(120)` | no |  |
| `business_key` | `VARCHAR(200)` | no |  |
| `detail` | `VARCHAR(1000)` | yes |  |
| `detected_ts` | `DATETIME2(3)` | no | _Point in time._ |

### ctl.pipeline_run_log

Defined in `sql/00_control/20_pipeline_run_log.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `run_id` | `BIGINT` | no | _Natural key from a source system._ |
| `batch_id` | `VARCHAR(40)` | no | _Natural key from a source system._ |
| `source_id` | `INT` | yes | _Natural key from a source system._ |
| `layer` | `VARCHAR(10)` | no |  |
| `step_name` | `VARCHAR(120)` | no | _Display name._ |
| `status` | `VARCHAR(15)` | no |  |
| `start_ts` | `DATETIME2(3)` | no | _Point in time._ |
| `end_ts` | `DATETIME2(3)` | yes | _Point in time._ |
| `duration_seconds` | `INT` | yes |  |
| `rows_read` | `BIGINT` | yes |  |
| `rows_written` | `BIGINT` | yes |  |
| `rows_rejected` | `BIGINT` | yes |  |
| `files_read` | `INT` | yes |  |
| `watermark_from` | `VARCHAR(40)` | yes |  |
| `watermark_to` | `VARCHAR(40)` | yes |  |
| `error_message` | `VARCHAR(4000)` | yes |  |
| `created_ts` | `DATETIME2(3)` | no | _Point in time._ |

### ctl.source_config

Defined in `sql/00_control/10_source_config.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `source_id` | `INT` | no | _Natural key from a source system._ |
| `source_system` | `VARCHAR(30)` | no |  |
| `entity` | `VARCHAR(60)` | no |  |
| `target_table` | `VARCHAR(120)` | no |  |
| `file_pattern` | `VARCHAR(400)` | no |  |
| `is_date_partitioned` | `BIT` | no | _Boolean flag._ |
| `file_format` | `VARCHAR(10)` | no |  |
| `delimiter` | `VARCHAR(3)` | yes |  |
| `decimal_mark` | `VARCHAR(1)` | yes |  |
| `encoding` | `VARCHAR(30)` | no |  |
| `has_header` | `BIT` | no | _Boolean flag._ |
| `sheet_name` | `VARCHAR(60)` | yes | _Display name._ |
| `load_type` | `VARCHAR(15)` | no |  |
| `watermark_column` | `VARCHAR(60)` | yes |  |
| `watermark_value` | `VARCHAR(40)` | yes |  |
| `key_columns` | `VARCHAR(200)` | no |  |
| `is_active` | `BIT` | no | _Boolean flag._ |
| `load_order` | `INT` | no |  |
| `retry_limit` | `INT` | no |  |
| `description` | `VARCHAR(300)` | yes |  |
| `created_ts` | `DATETIME2(3)` | no | _Point in time._ |
| `updated_ts` | `DATETIME2(3)` | no | _Point in time._ |

### ctl.vin_transliteration

Defined in `sql/00_control/50_vin_reference.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `vin_character` | `VARCHAR(1)` | no |  |
| `numeric_value` | `INT` | no |  |

### ctl.vin_weight

Defined in `sql/00_control/50_vin_reference.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `vin_position` | `INT` | no |  |
| `weight` | `INT` | no |  |

---

## Schema `gold`

### gold.agg_monthly_dealer_model_sale

Defined in `sql/03_gold/20_facts.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `month_key` | `INT` | no |  |
| `dealer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `model_trim_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `sale_count` | `INT` | no | _Row or event count._ |
| `new_sale_count` | `INT` | no | _Row or event count._ |
| `used_sale_count` | `INT` | no | _Row or event count._ |
| `trade_in_count` | `INT` | no | _Row or event count._ |
| `list_price_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `discount_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `net_sale_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `gross_margin_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `avg_discount_rate` | `DECIMAL(9,6)` | yes | _Ratio stored as 0-1, not 0-100._ |
| `avg_days_in_stock` | `DECIMAL(9,2)` | yes |  |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.agg_monthly_dealer_target

Defined in `sql/03_gold/20_facts.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `month_key` | `INT` | no |  |
| `dealer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `target_sale_count` | `DECIMAL(18,2)` | yes | _Row or event count._ |
| `target_sale_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `target_service_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `actual_sale_count` | `INT` | yes | _Row or event count._ |
| `actual_sale_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `actual_service_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.agg_monthly_service_summary

Defined in `sql/03_gold/20_facts.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `month_key` | `INT` | no |  |
| `dealer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `service_type_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `repair_order_count` | `INT` | no | _Row or event count._ |
| `open_order_count` | `INT` | no | _Row or event count._ |
| `labour_hours_sold` | `DECIMAL(14,2)` | yes |  |
| `available_labour_hours` | `DECIMAL(14,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `labour_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `part_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `warranty_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `customer_payable_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `avg_cycle_hours` | `DECIMAL(12,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `avg_parts_wait_hours` | `DECIMAL(12,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `orders_with_parts_wait` | `INT` | yes |  |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.dim_customer

Defined in `sql/03_gold/10_dimensions.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `customer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `master_customer_id` | `VARCHAR(20)` | no | _Natural key from a source system._ |
| `customer_type` | `VARCHAR(15)` | yes |  |
| `full_name` | `VARCHAR(200)` | yes | _Display name._ |
| `identity_hash` | `VARCHAR(64)` | yes | _Salted SHA-256. For joining and counting, never for reading._ |
| `identity_no_masked` | `VARCHAR(20)` | yes | _Partially redacted for human display._ |
| `phone_hash` | `VARCHAR(64)` | yes | _Salted SHA-256. For joining and counting, never for reading._ |
| `phone_masked` | `VARCHAR(20)` | yes | _Partially redacted for human display._ |
| `email_hash` | `VARCHAR(64)` | yes | _Salted SHA-256. For joining and counting, never for reading._ |
| `email_masked` | `VARCHAR(100)` | yes | _Partially redacted for human display._ |
| `city` | `VARCHAR(40)` | yes |  |
| `city_code` | `VARCHAR(2)` | yes | _Short coded value._ |
| `region` | `VARCHAR(30)` | yes |  |
| `lead_source` | `VARCHAR(20)` | yes |  |
| `consent_kvkk` | `BIT` | yes |  |
| `customer_since_date` | `DATE` | yes | _Calendar date, no time part._ |
| `source_presence` | `VARCHAR(10)` | yes |  |
| `match_score` | `INT` | yes |  |
| `is_inferred` | `BIT` | no | _1 when this member was created because a fact referenced it before the dimension had seen it._ |
| `valid_from` | `DATE` | no | _Inclusive start of this version's validity._ |
| `valid_to` | `DATE` | no | _Exclusive end. The open version uses 9999-12-31._ |
| `is_current` | `BIT` | no | _1 for the open version. Redundant with valid_to on purpose - see naming_standard.md §6._ |
| `_row_hash` | `VARCHAR(64)` | yes | _Hash of the tracked attributes. A change here is what opens a new version._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.dim_date

Defined in `sql/03_gold/00_dim_date.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `date_key` | `INT` | no |  |
| `full_date` | `DATE` | no | _Calendar date, no time part._ |
| `day_of_month` | `INT` | no |  |
| `day_of_year` | `INT` | no |  |
| `day_of_week` | `INT` | no |  |
| `day_name_tr` | `VARCHAR(12)` | no |  |
| `day_name_en` | `VARCHAR(12)` | no |  |
| `day_abbr_tr` | `VARCHAR(4)` | no |  |
| `iso_week` | `INT` | no |  |
| `iso_year` | `INT` | no |  |
| `week_start_date` | `DATE` | no | _Calendar date, no time part._ |
| `month_number` | `INT` | no |  |
| `month_name_tr` | `VARCHAR(12)` | no |  |
| `month_name_en` | `VARCHAR(12)` | no |  |
| `month_key` | `INT` | no |  |
| `month_year_label` | `VARCHAR(8)` | no |  |
| `first_day_of_month` | `DATE` | no |  |
| `last_day_of_month` | `DATE` | no |  |
| `days_in_month` | `INT` | no |  |
| `quarter_number` | `INT` | no |  |
| `quarter_label` | `VARCHAR(8)` | no |  |
| `year_number` | `INT` | no |  |
| `fiscal_year` | `INT` | no |  |
| `fiscal_quarter` | `INT` | no |  |
| `fiscal_month` | `INT` | no |  |
| `is_weekend` | `BIT` | no | _Boolean flag._ |
| `is_public_holiday` | `BIT` | no | _Boolean flag._ |
| `is_half_day` | `BIT` | no | _Boolean flag._ |
| `holiday_name` | `VARCHAR(60)` | yes | _Display name._ |
| `is_working_day` | `BIT` | no | _Boolean flag._ |
| `same_date_last_year_key` | `INT` | yes |  |
| `same_month_last_year_key` | `INT` | yes |  |

### gold.dim_dealer

Defined in `sql/03_gold/10_dimensions.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `dealer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `dealer_code` | `VARCHAR(20)` | no | _Short coded value._ |
| `dealer_name` | `VARCHAR(120)` | yes | _Display name._ |
| `dealer_type` | `VARCHAR(15)` | yes |  |
| `province_code` | `VARCHAR(2)` | yes | _Short coded value._ |
| `city` | `VARCHAR(40)` | yes |  |
| `region` | `VARCHAR(30)` | yes |  |
| `address_line` | `VARCHAR(200)` | yes |  |
| `phone` | `VARCHAR(30)` | yes |  |
| `workshop_bay_count` | `INT` | yes | _Row or event count._ |
| `monthly_capacity_hours` | `INT` | yes | _Duration in hours. Null means the stage has not happened._ |
| `opening_date` | `DATE` | yes | _Calendar date, no time part._ |
| `is_active` | `BIT` | yes | _Boolean flag._ |
| `is_inferred` | `BIT` | no | _1 when this member was created because a fact referenced it before the dimension had seen it._ |
| `valid_from` | `DATE` | no | _Inclusive start of this version's validity._ |
| `valid_to` | `DATE` | no | _Exclusive end. The open version uses 9999-12-31._ |
| `is_current` | `BIT` | no | _1 for the open version. Redundant with valid_to on purpose - see naming_standard.md §6._ |
| `_row_hash` | `VARCHAR(64)` | yes | _Hash of the tracked attributes. A change here is what opens a new version._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.dim_employee

Defined in `sql/03_gold/10_dimensions.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `employee_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `employee_id` | `VARCHAR(20)` | no | _Natural key from a source system._ |
| `full_name` | `VARCHAR(120)` | yes | _Display name._ |
| `first_name` | `VARCHAR(60)` | yes | _Display name._ |
| `last_name` | `VARCHAR(60)` | yes | _Display name._ |
| `dealer_code` | `VARCHAR(20)` | yes | _Short coded value._ |
| `role_code` | `VARCHAR(20)` | yes | _Short coded value._ |
| `email` | `VARCHAR(120)` | yes |  |
| `hire_date` | `DATE` | yes | _Calendar date, no time part._ |
| `is_active` | `BIT` | yes | _Boolean flag._ |
| `is_inferred` | `BIT` | no | _1 when this member was created because a fact referenced it before the dimension had seen it._ |
| `valid_from` | `DATE` | no | _Inclusive start of this version's validity._ |
| `valid_to` | `DATE` | no | _Exclusive end. The open version uses 9999-12-31._ |
| `is_current` | `BIT` | no | _1 for the open version. Redundant with valid_to on purpose - see naming_standard.md §6._ |
| `_row_hash` | `VARCHAR(64)` | yes | _Hash of the tracked attributes. A change here is what opens a new version._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.dim_model_trim

Defined in `sql/03_gold/10_dimensions.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `model_trim_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `model_trim_code` | `VARCHAR(20)` | no | _Short coded value._ |
| `brand` | `VARCHAR(30)` | yes |  |
| `model_name` | `VARCHAR(40)` | yes | _Display name._ |
| `trim_name` | `VARCHAR(30)` | yes | _Display name._ |
| `model_year` | `INT` | yes |  |
| `body_type` | `VARCHAR(20)` | yes |  |
| `segment` | `VARCHAR(10)` | yes |  |
| `engine_cc` | `INT` | yes |  |
| `fuel_type` | `VARCHAR(15)` | yes |  |
| `transmission` | `VARCHAR(15)` | yes |  |
| `warranty_months` | `INT` | yes |  |
| `warranty_km` | `INT` | yes |  |
| `list_price_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `is_active` | `BIT` | yes | _Boolean flag._ |
| `is_inferred` | `BIT` | no | _1 when this member was created because a fact referenced it before the dimension had seen it._ |
| `valid_from` | `DATE` | no | _Inclusive start of this version's validity._ |
| `valid_to` | `DATE` | no | _Exclusive end. The open version uses 9999-12-31._ |
| `is_current` | `BIT` | no | _1 for the open version. Redundant with valid_to on purpose - see naming_standard.md §6._ |
| `_row_hash` | `VARCHAR(64)` | yes | _Hash of the tracked attributes. A change here is what opens a new version._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.dim_part

Defined in `sql/03_gold/10_dimensions.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `part_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `part_no` | `VARCHAR(30)` | no | _Human-facing document number. Degenerate dimension on a fact._ |
| `part_name` | `VARCHAR(120)` | yes | _Display name._ |
| `part_group_code` | `VARCHAR(15)` | yes | _Short coded value._ |
| `part_group_name` | `VARCHAR(60)` | yes | _Display name._ |
| `is_genuine` | `BIT` | yes | _Boolean flag._ |
| `supplier_id` | `VARCHAR(20)` | yes | _Natural key from a source system._ |
| `unit_of_measure` | `VARCHAR(5)` | yes |  |
| `list_price_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `is_active` | `BIT` | yes | _Boolean flag._ |
| `is_inferred` | `BIT` | no | _1 when this member was created because a fact referenced it before the dimension had seen it._ |
| `valid_from` | `DATE` | no | _Inclusive start of this version's validity._ |
| `valid_to` | `DATE` | no | _Exclusive end. The open version uses 9999-12-31._ |
| `is_current` | `BIT` | no | _1 for the open version. Redundant with valid_to on purpose - see naming_standard.md §6._ |
| `_row_hash` | `VARCHAR(64)` | yes | _Hash of the tracked attributes. A change here is what opens a new version._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.dim_service_type

Defined in `sql/03_gold/10_dimensions.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `service_type_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `service_type_code` | `VARCHAR(15)` | no | _Short coded value._ |
| `service_type_name_tr` | `VARCHAR(60)` | yes |  |
| `service_type_name_en` | `VARCHAR(60)` | yes |  |
| `is_warranty_eligible` | `BIT` | yes | _Boolean flag._ |
| `is_scheduled` | `BIT` | yes | _Boolean flag._ |
| `typical_labour_hours` | `DECIMAL(9,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `_row_hash` | `VARCHAR(64)` | yes | _Hash of the tracked attributes. A change here is what opens a new version._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.dim_supplier

Defined in `sql/03_gold/10_dimensions.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `supplier_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `supplier_id` | `VARCHAR(20)` | no | _Natural key from a source system._ |
| `supplier_name` | `VARCHAR(120)` | yes | _Display name._ |
| `country_code` | `VARCHAR(2)` | yes | _Short coded value._ |
| `is_domestic` | `BIT` | yes | _Boolean flag._ |
| `lead_time_days` | `INT` | yes | _Duration in whole days._ |
| `contact_email` | `VARCHAR(120)` | yes |  |
| `is_active` | `BIT` | yes | _Boolean flag._ |
| `_row_hash` | `VARCHAR(64)` | yes | _Hash of the tracked attributes. A change here is what opens a new version._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.dim_transaction_flag

Defined in `sql/03_gold/10_dimensions.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `transaction_flag_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `is_campaign` | `BIT` | no | _Boolean flag._ |
| `payment_type` | `VARCHAR(10)` | no |  |
| `channel` | `VARCHAR(15)` | no |  |
| `is_used_vehicle` | `BIT` | no | _Boolean flag._ |
| `is_warranty` | `BIT` | no | _Boolean flag._ |
| `has_trade_in` | `BIT` | no | _Boolean flag._ |
| `flag_description` | `VARCHAR(200)` | yes |  |
| `_row_hash` | `VARCHAR(64)` | yes | _Hash of the tracked attributes. A change here is what opens a new version._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.dim_vehicle

Defined in `sql/03_gold/10_dimensions.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `vehicle_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `vin` | `VARCHAR(20)` | no |  |
| `model_trim_code` | `VARCHAR(20)` | yes | _Short coded value._ |
| `model_year` | `INT` | yes |  |
| `colour` | `VARCHAR(30)` | yes |  |
| `production_date` | `DATE` | yes | _Calendar date, no time part._ |
| `arrival_date` | `DATE` | yes | _Calendar date, no time part._ |
| `engine_no` | `VARCHAR(30)` | yes | _Human-facing document number. Degenerate dimension on a fact._ |
| `status` | `VARCHAR(20)` | yes |  |
| `stock_dealer_code` | `VARCHAR(20)` | yes | _Short coded value._ |
| `plate_hash` | `VARCHAR(64)` | yes | _Salted SHA-256. For joining and counting, never for reading._ |
| `plate_masked` | `VARCHAR(20)` | yes | _Partially redacted for human display._ |
| `master_customer_id` | `VARCHAR(20)` | yes | _Natural key from a source system._ |
| `owner_since_date` | `DATE` | yes | _Calendar date, no time part._ |
| `dealer_cost_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `vin_well_formed` | `BIT` | yes |  |
| `vin_check_digit_valid` | `BIT` | yes |  |
| `is_inferred` | `BIT` | no | _1 when this member was created because a fact referenced it before the dimension had seen it._ |
| `valid_from` | `DATE` | no | _Inclusive start of this version's validity._ |
| `valid_to` | `DATE` | no | _Exclusive end. The open version uses 9999-12-31._ |
| `is_current` | `BIT` | no | _1 for the open version. Redundant with valid_to on purpose - see naming_standard.md §6._ |
| `_row_hash` | `VARCHAR(64)` | yes | _Hash of the tracked attributes. A change here is what opens a new version._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.fact_data_quality

Defined in `sql/03_gold/20_facts.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `batch_id` | `VARCHAR(40)` | no | _Natural key from a source system._ |
| `rule_code` | `VARCHAR(40)` | no | _Short coded value._ |
| `executed_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `target_table` | `VARCHAR(120)` | no |  |
| `target_layer` | `VARCHAR(10)` | yes |  |
| `rule_type` | `VARCHAR(20)` | yes |  |
| `severity` | `VARCHAR(10)` | no |  |
| `outcome` | `VARCHAR(10)` | no |  |
| `rows_evaluated` | `BIGINT` | no |  |
| `rows_violated` | `BIGINT` | no |  |
| `violation_rate` | `DECIMAL(9,6)` | no | _Ratio stored as 0-1, not 0-100._ |
| `rows_quarantined` | `BIGINT` | yes |  |
| `rule_execution_count` | `INT` | no | _Row or event count._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.fact_part_purchase

Defined in `sql/03_gold/20_facts.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `po_no` | `VARCHAR(30)` | no | _Human-facing document number. Degenerate dimension on a fact._ |
| `po_line_no` | `INT` | no | _Human-facing document number. Degenerate dimension on a fact._ |
| `order_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `promised_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `delivery_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `supplier_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `part_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `ordered_quantity` | `DECIMAL(18,3)` | yes | _Countable amount._ |
| `received_quantity` | `DECIMAL(18,3)` | yes | _Countable amount._ |
| `shortfall_quantity` | `DECIMAL(18,3)` | yes | _Countable amount._ |
| `unit_cost_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `line_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `delay_days` | `INT` | yes | _Duration in whole days._ |
| `is_late` | `BIT` | yes | _Boolean flag._ |
| `po_line_count` | `INT` | no | _Row or event count._ |
| `status` | `VARCHAR(15)` | yes |  |
| `currency_code` | `VARCHAR(3)` | yes | _Short coded value._ |
| `fx_rate_to_try` | `DECIMAL(18,6)` | yes |  |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.fact_recall_coverage

Defined in `sql/03_gold/20_facts.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `campaign_code` | `VARCHAR(20)` | no | _Short coded value._ |
| `vehicle_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `vin` | `VARCHAR(20)` | no |  |
| `launch_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `notified_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `completed_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `model_trim_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `dealer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `campaign_name` | `VARCHAR(120)` | yes | _Display name._ |
| `campaign_category` | `VARCHAR(15)` | yes |  |
| `is_completed` | `BIT` | no | _Boolean flag._ |
| `days_to_complete` | `INT` | yes |  |
| `days_outstanding` | `INT` | yes |  |
| `coverage_count` | `INT` | no | _Row or event count._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.fact_repair_order

Defined in `sql/03_gold/20_facts.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `repair_order_no` | `VARCHAR(30)` | no | _Human-facing document number. Degenerate dimension on a fact._ |
| `appointment_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `checkin_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `inspection_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `parts_ready_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `repair_start_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `repair_end_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `qc_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `delivery_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `checkin_ts` | `DATETIME2(0)` | yes | _Point in time._ |
| `inspection_ts` | `DATETIME2(0)` | yes | _Point in time._ |
| `parts_wait_start_ts` | `DATETIME2(0)` | yes | _Point in time._ |
| `parts_ready_ts` | `DATETIME2(0)` | yes | _Point in time._ |
| `repair_start_ts` | `DATETIME2(0)` | yes | _Point in time._ |
| `repair_end_ts` | `DATETIME2(0)` | yes | _Point in time._ |
| `qc_ts` | `DATETIME2(0)` | yes | _Point in time._ |
| `delivery_ts` | `DATETIME2(0)` | yes | _Point in time._ |
| `vehicle_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `customer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `dealer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `service_advisor_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `technician_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `service_type_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `transaction_flag_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `inspection_wait_hours` | `DECIMAL(12,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `parts_wait_hours` | `DECIMAL(12,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `repair_duration_hours` | `DECIMAL(12,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `qc_wait_hours` | `DECIMAL(12,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `collection_wait_hours` | `DECIMAL(12,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `total_cycle_hours` | `DECIMAL(12,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `touch_time_hours` | `DECIMAL(12,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `labour_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `part_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `warranty_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `customer_payable_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `total_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `labour_hours_sold` | `DECIMAL(12,2)` | yes |  |
| `repair_order_count` | `INT` | no | _Row or event count._ |
| `odometer_km` | `BIGINT` | yes |  |
| `plate_masked` | `VARCHAR(20)` | yes | _Partially redacted for human display._ |
| `status` | `VARCHAR(25)` | yes |  |
| `is_open` | `BIT` | no | _Boolean flag._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.fact_repair_order_line

Defined in `sql/03_gold/20_facts.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `repair_order_no` | `VARCHAR(30)` | no | _Human-facing document number. Degenerate dimension on a fact._ |
| `line_no` | `INT` | no | _Human-facing document number. Degenerate dimension on a fact._ |
| `checkin_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `vehicle_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `customer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `dealer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `technician_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `service_type_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `part_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `line_type` | `VARCHAR(10)` | no |  |
| `operation_code` | `VARCHAR(20)` | yes | _Short coded value._ |
| `quantity` | `DECIMAL(18,3)` | yes |  |
| `labour_hours` | `DECIMAL(12,2)` | yes | _Duration in hours. Null means the stage has not happened._ |
| `unit_price_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `discount_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `line_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `warranty_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `customer_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `line_count` | `INT` | no | _Row or event count._ |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.fact_vehicle_inventory_daily

Defined in `sql/03_gold/20_facts.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `snapshot_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `vehicle_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `dealer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `model_trim_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `days_in_stock` | `INT` | no |  |
| `stock_value_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `vehicle_count` | `INT` | no | _Row or event count._ |
| `age_band` | `VARCHAR(15)` | no |  |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.fact_vehicle_sale

Defined in `sql/03_gold/20_facts.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `contract_no` | `VARCHAR(30)` | no | _Human-facing document number. Degenerate dimension on a fact._ |
| `contract_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `delivery_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `invoice_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `registration_date_key` | `INT` | no | _Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown._ |
| `vehicle_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `trade_in_vehicle_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `customer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `dealer_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `salesperson_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `model_trim_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `transaction_flag_sk` | `BIGINT` | no | _Surrogate key. Unique per dimension VERSION, not per entity._ |
| `list_price_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `discount_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `discount_rate` | `DECIMAL(9,6)` | yes | _Ratio stored as 0-1, not 0-100._ |
| `net_sale_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `trade_in_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `vehicle_cost_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `gross_margin_amount` | `DECIMAL(18,2)` | yes | _Monetary value in Turkish Lira, converted in Silver._ |
| `sale_count` | `INT` | no | _Row or event count._ |
| `days_in_stock` | `INT` | yes |  |
| `order_to_delivery_days` | `INT` | yes | _Duration in whole days._ |
| `currency_code` | `VARCHAR(3)` | yes | _Short coded value._ |
| `fx_rate_to_try` | `DECIMAL(18,6)` | yes |  |
| `sale_type` | `VARCHAR(10)` | yes |  |
| `_batch_id` | `VARCHAR(40)` | yes | _The run that wrote this row. Deleting by it is what makes a reload idempotent._ |
| `_loaded_ts` | `DATETIME2(3)` | no | _When this row was written._ |

### gold.ref_province

Defined in `sql/03_gold/05_ref_province.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `province_code` | `VARCHAR(2)` | no | _Short coded value._ |
| `province_name` | `VARCHAR(40)` | no | _Display name._ |
| `region` | `VARCHAR(30)` | no |  |
| `population_m` | `DECIMAL(9,2)` | yes |  |

### gold.ref_public_holiday

Defined in `sql/03_gold/00_dim_date.sql`

| Column | Type | Null | Description |
|---|---|---|---|
| `holiday_date` | `DATE` | no | _Calendar date, no time part._ |
| `holiday_name` | `VARCHAR(60)` | no | _Display name._ |
| `is_half_day` | `BIT` | no | _Boolean flag._ |

---
