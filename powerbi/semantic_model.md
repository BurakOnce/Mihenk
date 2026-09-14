# Semantic model and report pages

How to build the Direct Lake model over `mihenk_wh`, what the relationships are
and why, and what goes on each page.

---

## 1. Create the model

1. Open the **Warehouse** `mihenk_wh` in Fabric
2. **New semantic model**
3. Name it `MIHENK`
4. Select the tables listed in §2 — **not** every table in the warehouse

That last point matters. Selecting everything drags `ctl` tables, staging
objects and the `silver` cross-references into the model, and a business user
opening a field list of eighty tables stops using the report. The model is a
product for people who do not know the warehouse, and its table list is the
first thing they see.

---

## 2. Tables, and what they are renamed to

Engineering prefixes come off. Nobody outside the data team should have to know
what `dim_` means, and `fact_repair_order_line` is not a phrase anybody says.

| Warehouse object | Model name | Kind |
|---|---|---|
| `gold.dim_date` | **Date** | dimension, marked as date table |
| `gold.dim_vehicle` | **Vehicle** | dimension |
| `gold.dim_customer` | **Customer** | dimension |
| `gold.dim_dealer` | **Dealer** | dimension |
| `gold.dim_employee` | **Employee** | dimension |
| `gold.dim_model_trim` | **Model** | dimension |
| `gold.dim_part` | **Part** | dimension |
| `gold.dim_supplier` | **Supplier** | dimension |
| `gold.dim_service_type` | **Service Type** | dimension |
| `gold.dim_transaction_flag` | **Transaction Flag** | dimension |
| `gold.fact_vehicle_sale` | **Vehicle Sale** | fact |
| `gold.fact_repair_order` | **Repair Order** | fact |
| `gold.fact_repair_order_line` | **Repair Order Line** | fact |
| `gold.fact_part_purchase` | **Part Purchase** | fact |
| `gold.fact_vehicle_inventory_daily` | **Vehicle Inventory** | fact |
| `gold.fact_recall_coverage` | **Recall Coverage** | fact |
| `gold.fact_data_quality` | **Data Quality** | fact |
| `gold.agg_monthly_dealer_target` | **Dealer Target** | aggregate |
| `gold.agg_monthly_service_summary` | **Service Summary** | aggregate |
| `gold.ref_province` | **Province** | reference |
| `gold.security_user_dealer` | **Security User Dealer** | hidden, RLS only |

`Model` rather than `Model Trim`: a business user says "which model sold best",
and the trim is an attribute of it.

Also create an empty table called **`_Measures`** — Home → Enter data, one
column, one blank row — set every measure's home table to it, then hide the
column. It is the standard trick for grouping measures at the top of the field
list, and it costs nothing.

---

## 3. Relationships

Every one is **single direction, many-to-one, from fact to dimension**. No
bidirectional filters anywhere; §4 of `rls_setup.md` explains why that is a
security decision and not only a modelling one.

### Active relationships

| From | To | On |
|---|---|---|
| Vehicle Sale | Date | `contract_date_key` → `date_key` |
| Vehicle Sale | Vehicle | `vehicle_sk` |
| Vehicle Sale | Customer | `customer_sk` |
| Vehicle Sale | Dealer | `dealer_sk` |
| Vehicle Sale | Employee | `salesperson_sk` |
| Vehicle Sale | Model | `model_trim_sk` |
| Vehicle Sale | Transaction Flag | `transaction_flag_sk` |
| Repair Order | Date | `checkin_date_key` → `date_key` |
| Repair Order | Vehicle | `vehicle_sk` |
| Repair Order | Customer | `customer_sk` |
| Repair Order | Dealer | `dealer_sk` |
| Repair Order | Employee | `service_advisor_sk` |
| Repair Order | Service Type | `service_type_sk` |
| Repair Order Line | Date | `checkin_date_key` |
| Repair Order Line | Part | `part_sk` |
| Repair Order Line | Vehicle | `vehicle_sk` |
| Repair Order Line | Dealer | `dealer_sk` |
| Part Purchase | Date | `order_date_key` |
| Part Purchase | Supplier | `supplier_sk` |
| Part Purchase | Part | `part_sk` |
| Vehicle Inventory | Date | `snapshot_date_key` |
| Vehicle Inventory | Vehicle | `vehicle_sk` |
| Vehicle Inventory | Dealer | `dealer_sk` |
| Vehicle Inventory | Model | `model_trim_sk` |
| Recall Coverage | Date | `notified_date_key` |
| Recall Coverage | Vehicle | `vehicle_sk` |
| Recall Coverage | Model | `model_trim_sk` |
| Data Quality | Date | `executed_date_key` |
| Dealer Target | Dealer | `dealer_sk` |
| Service Summary | Dealer | `dealer_sk` |
| Service Summary | Service Type | `service_type_sk` |
| Customer | Province | `city_code` → `province_code` |
| Dealer | Province | `province_code` |

### Inactive relationships — the role-playing dates

| From | To | On | Activated by |
|---|---|---|---|
| Vehicle Sale | Date | `delivery_date_key` | `Net Sale Amount by Delivery` |
| Vehicle Sale | Date | `invoice_date_key` | a finance measure, if needed |
| Vehicle Sale | Date | `registration_date_key` | `Net Sale Amount by Registration` |
| Repair Order | Date | `delivery_date_key` | aftersales throughput measures |
| Repair Order | Date | `repair_start_date_key` | workshop loading measures |
| Recall Coverage | Date | `completed_date_key` | completion trend |
| Part Purchase | Date | `promised_date_key` | supplier promise analysis |
| Part Purchase | Date | `delivery_date_key` | actual receipt analysis |

Only one relationship between two tables can be active. The active one is a
business decision:

- **Vehicle Sale → contract date.** That is when the sale was made and when
  commission is earned.
- **Repair Order → check-in date.** That is when the workshop's capacity was
  consumed, which is what the aftersales report is about. Delivery date would
  push an order into the following month whenever a car sat waiting for a part,
  and workshop loading would be wrong by exactly the amount that matters.

### The Dealer Target join, and why it has no Date relationship

`Dealer Target` is at month grain and carries `month_key` (YYYYMM), not
`date_key`. Relating it to `Date` on `date_key` is impossible — there is no such
column — and creating a separate Month dimension for one table would fragment
the model.

Instead: no relationship, and the measures join on `month_key` through `Date`:

```dax
Target Sale Count =
CALCULATE (
    SUM ( 'Dealer Target'[target_sale_count] ),
    TREATAS ( VALUES ( 'Date'[month_key] ), 'Dealer Target'[month_key] )
)
```

`TREATAS` applies the date table's month selection to the aggregate as if a
relationship existed. It is the standard answer for joining two tables at
different grains and is worth knowing — the alternative, a second date table at
month grain, doubles the number of date slicers a user has to reason about.

---

## 4. Model settings

**Mark `Date` as a date table.** Table tools → Mark as date table → `full_date`.
Without it, `SAMEPERIODLASTYEAR` and every other time intelligence function
returns wrong answers for partial periods rather than erroring.

**Hide every `_sk` and `_key` column.** Users filter on attributes, never on
keys. A visible surrogate key is an invitation to drag it onto a visual and get
a meaningless count.

Also hide: `_batch_id`, `_loaded_ts`, `_row_hash`, every `*_raw` column, every
hash column (`identity_hash`, `plate_hash`, `phone_hash`, `email_hash`). The
hashes are for joining, not reading; the masked versions are what a human
should see.

**Sort-by columns.** `Date[month_year_label]` sorts correctly as text
(`2024-03`), so it needs none. `Date[month_name_tr]` does — set its sort-by to
`month_number`, or Aralık comes first alphabetically and every trend line is
scrambled.

**Set the current-version filter.** The Type 2 dimensions contain historical
versions, and a slicer listing a dealer three times because it changed name
twice is confusing. Two options:

- point the model at `gold.vw_dim_dealer_current` for the slicer experience, and
  lose point-in-time correctness on the facts; or
- keep the full dimension and add a report-level filter `is_current = TRUE` on
  slicer visuals only.

**Use the second.** The facts join to historical versions on purpose — that is
the entire reason the dimension is Type 2 — and a model that only exposes the
current version has thrown that away to tidy a slicer.

---

## 5. Report pages

Five pages, matching the five business questions.

### Sales

| Visual | Measures |
|---|---|
| KPI row | `Sale Count`, `Net Sale Amount`, `Gross Margin Rate`, `Sales Target Achievement %` |
| Monthly trend, dual axis | `Sale Count` (columns) and `Net Sale Amount` (line) |
| Dealer ranking table | `Sale Count`, `Net Sale Amount`, `Discount Rate`, `Average Days In Stock`, `Sales Target Achievement %` |
| Model mix | `Sale Count` by brand and model |
| Scatter | `Average Days In Stock` against `Discount Rate`, one point per dealer |
| Region map | `Net Sale Amount` by `Province[province_name]` |

The scatter is the page's one genuine finding rather than a number: stock age
and discount move together by construction in this data, and seeing a dealer sit
off that line is the question worth asking.

Put `Sale Count YoY %` next to `Net Sale Amount YoY %` on the KPI row. Revenue
grew far faster than units across this period because Turkish list prices
tripled, and showing revenue growth alone would be misleading.

### Aftersales

| Visual | Measures |
|---|---|
| KPI row | `Repair Order Count`, `Service Revenue`, `Workshop Utilisation %`, `Service Retention Rate` |
| Stacked bar, cycle time breakdown | `Average Touch Time Hours` and `Average Parts Wait Hours` by dealer |
| Utilisation trend | `Workshop Utilisation %` by month, with a reference line at 85% |
| Service mix | `Repair Order Count` by `Service Type` |
| Open orders table | `Open Order Count`, `Orders Awaiting Parts`, by dealer |
| Revenue per vehicle | `Service Revenue per Vehicle` by dealer |

The stacked cycle-time bar is the most valuable visual in the report. It turns
"our workshops are slow" into a split between time worked and time waiting, and
those are different departments.

### Warranty and recall

| Visual | Measures |
|---|---|
| KPI row | `Warranty Cost Ratio`, `Claim Approval Rate by Value`, `Recall Completion Rate` |
| Unreimbursed trend | `Unreimbursed Warranty Amount` by month |
| Rejection reasons | `Claim Count` by `rejection_reason` |
| Recall table | `Recall Coverage Count`, `Recall Outstanding Count`, `Average Days Outstanding` by campaign |
| Outstanding by campaign age | `Recall Outstanding Count` against campaign launch date |

`Recall Outstanding Count` is the number a safety recall is managed by, and it
should be the largest thing on the page.

### Procurement

| Visual | Measures |
|---|---|
| KPI row | `Supplier On Time Rate`, `Average Delay Days`, `Fill Rate` |
| Supplier scorecard | `PO Line Count`, `Supplier On Time Rate`, `Average Delay Days`, by supplier |
| Domestic vs import | `Supplier On Time Rate` split by `Supplier[is_domestic]` |
| Unit cost trend | average `unit_cost_amount` by month and part group |

**This page has no dealer RLS** — purchase orders are placed centrally and
`Part Purchase` has no dealer relationship. It must therefore be excluded from
dealer-facing reports explicitly rather than relying on the role to empty it.
See `rls_setup.md` §3.

### Data quality

| Visual | Measures |
|---|---|
| KPI row | `Violation Rate`, `Critical Violations`, `Failed Rule Count`, `Errored Rule Count` |
| Rule table | `Rows Evaluated`, `Rows Violated`, `Violation Rate`, outcome, severity |
| Trend | `Violation Rate` by batch |
| Layer reconciliation | rows read / written / rejected from `ctl.vw_batch_reconciliation` |
| Quarantine | `Quarantine Rate` by target table |

`Errored Rule Count` gets its own card, conditionally formatted red above zero.
A rule that could not run finds nothing, and a silently disabled check must not
look like clean data.

This page is the reason the platform is called Mihenk, and it should not be the
last tab. Put it second.

---

## 6. Direct Lake, and when it stops being Direct Lake

Direct Lake reads the Delta files behind the Warehouse directly — import-mode
speed with no refresh. It falls back to DirectQuery silently when it cannot, and
the report gets slower without anything saying why.

The usual causes, in the order they actually occur:

1. **A calculated column or calculated table** in the model. Direct Lake does
   not support them. Everything computed in this model is computed in Gold for
   exactly this reason, and adding a calculated column later would quietly
   disable Direct Lake for the whole model.
2. **Exceeding the capacity's row or memory guardrails.** `Vehicle Inventory` is
   1.6 million rows and is the table to watch; an F2 will fall back on it sooner
   than a larger SKU.
3. **An unsupported data type** in a column. Everything here is int, decimal,
   date, datetime2, varchar or bit, which are all fine.

Check it: Power BI Desktop → **Performance analyzer** → refresh a visual. A
DirectQuery entry in the trace means fallback has happened.

This is ADR-0002 verification item 7 and it is still `Pending`.
