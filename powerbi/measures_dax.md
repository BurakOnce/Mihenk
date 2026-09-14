# DAX measures

Every measure in the semantic model, with the reasoning. They live in a
dedicated `_Measures` table so the field list groups them together rather than
scattering them across the fact tables they happen to read.

Three rules applied throughout:

- **`DIVIDE`, never `/`.** A denominator of zero returns `BLANK()` rather than
  an error that breaks the whole visual. Every ratio below uses it.
- **No implicit measures.** Every fact column is hidden and every number a user
  can drag is a measure defined here. An implicit `Sum of net_sale_amount`
  cannot be corrected centrally when the definition of net revenue changes.
- **Base measures, then variants.** `Net Sale Amount` is defined once; the
  year-on-year, target and per-unit versions all reference it. Redefining the
  aggregation in each variant is how two visuals end up disagreeing.

---

## 1. Sales

### Base

```dax
Sale Count =
SUM ( 'Vehicle Sale'[sale_count] )
```

Summing a constant-1 column rather than `COUNTROWS`. It behaves identically
today and keeps working if the grain ever changes to allow a multi-unit
contract — a fleet order for twelve vans — without every measure needing to be
rewritten.

```dax
Net Sale Amount =
SUM ( 'Vehicle Sale'[net_sale_amount] )

List Price Amount =
SUM ( 'Vehicle Sale'[list_price_amount] )

Discount Amount =
SUM ( 'Vehicle Sale'[discount_amount] )

Gross Margin Amount =
SUM ( 'Vehicle Sale'[gross_margin_amount] )
```

### Discount rate — the one people get wrong

```dax
Discount Rate =
DIVIDE ( [Discount Amount], [List Price Amount] )
```

**Not** `AVERAGE('Vehicle Sale'[discount_rate])`. Averaging the per-contract
rates treats a 780,000 lira hatchback and a 3,450,000 lira SUV as equally
important, so a shift in model mix vanishes from the number entirely. The
weighted rate — total discount over total list — is what the business actually
loses.

This is the single most common measure error in an automotive model and it is
worth being able to say why in one sentence.

### Margin

```dax
Gross Margin Rate =
DIVIDE ( [Gross Margin Amount], [Net Sale Amount] )

Average Selling Price =
DIVIDE ( [Net Sale Amount], [Sale Count] )
```

### Days in stock

```dax
Average Days In Stock =
AVERAGEX (
    FILTER ( 'Vehicle Sale', 'Vehicle Sale'[sale_type] = "NEW" ),
    'Vehicle Sale'[days_in_stock]
)
```

Filtered to new vehicles deliberately. A used car's days-in-stock is measured
from when it was taken in as a trade-in, which is a different clock and a
different business question; mixing them produces a number that answers neither.

For the **current** stock position — cars that have not sold and therefore never
appear in the sales fact — use the snapshot measures in §5.

### Trade-in and campaign rates

```dax
Trade In Count =
CALCULATE ( [Sale Count], 'Vehicle Sale'[trade_in_vehicle_sk] > 0 )

Trade In Rate =
DIVIDE ( [Trade In Count], [Sale Count] )
```

`> 0` rather than `<> -2`. Both work, but `> 0` reads as "points at a real
vehicle" and survives someone adding a third special member later.

### Order to delivery

```dax
Average Order To Delivery Days =
AVERAGE ( 'Vehicle Sale'[order_to_delivery_days] )
```

### Role-playing dates

The sales fact has four date keys. One relationship to `Date` is active
(`contract_date_key`); the rest are inactive and activated per measure.

```dax
Net Sale Amount by Delivery =
CALCULATE (
    [Net Sale Amount],
    USERELATIONSHIP ( 'Vehicle Sale'[delivery_date_key], 'Date'[date_key] )
)

Net Sale Amount by Registration =
CALCULATE (
    [Net Sale Amount],
    USERELATIONSHIP ( 'Vehicle Sale'[registration_date_key], 'Date'[date_key] )
)
```

Which one is active matters and is a business decision, not a technical one.
**Contract date is active** because that is when the sale was made and when the
salesperson's commission is earned. Registration date is when the state
recognises it, and finance may well want that — hence the measure.

### Year on year

```dax
Net Sale Amount LY =
CALCULATE ( [Net Sale Amount], SAMEPERIODLASTYEAR ( 'Date'[full_date] ) )

Net Sale Amount YoY % =
DIVIDE ( [Net Sale Amount] - [Net Sale Amount LY], [Net Sale Amount LY] )
```

`SAMEPERIODLASTYEAR` needs `Date` marked as a date table in the model, with
`full_date` as the date column. Without that it silently returns wrong results
for partial periods rather than erroring.

**Inflation warning.** Turkish list prices roughly tripled across this dataset.
A year-on-year revenue comparison is therefore mostly measuring inflation, and
presenting it without saying so would be misleading. Pair it with the unit
measure:

```dax
Sale Count YoY % =
VAR Current = [Sale Count]
VAR Prior = CALCULATE ( [Sale Count], SAMEPERIODLASTYEAR ( 'Date'[full_date] ) )
RETURN DIVIDE ( Current - Prior, Prior )
```

Units grew 8%, revenue grew 45%: that gap is the story, and only showing both
tells it.

### Target achievement

```dax
Target Sale Count =
SUM ( 'Dealer Target'[target_sale_count] )

Target Sale Amount =
SUM ( 'Dealer Target'[target_sale_amount] )

Sales Target Achievement % =
DIVIDE ( [Sale Count], [Target Sale Count] )
```

Targets live at dealer-month grain in `agg_monthly_dealer_target`, not on the
transaction fact. Joining a monthly target to a transaction fact would either
fan it across every contract — making it sum to the target times the contract
count — or force an aggregation on every query.

---

## 2. Aftersales

### Base

```dax
Repair Order Count =
SUM ( 'Repair Order'[repair_order_count] )

Labour Amount = SUM ( 'Repair Order'[labour_amount] )
Part Amount   = SUM ( 'Repair Order'[part_amount] )

Service Revenue =
[Labour Amount] + [Part Amount]

Customer Payable Amount = SUM ( 'Repair Order'[customer_payable_amount] )
Warranty Amount         = SUM ( 'Repair Order'[warranty_amount] )
```

### Workshop utilisation — and the trap in the denominator

```dax
Labour Hours Sold =
SUM ( 'Repair Order'[labour_hours_sold] )

Available Labour Hours =
SUM ( 'Service Summary'[available_labour_hours] )

Workshop Utilisation % =
DIVIDE ( [Labour Hours Sold], [Available Labour Hours] )
```

The denominator is not a constant. It is the dealer's capacity per working day
multiplied by the working days in the period — and a month containing Kurban
Bayramı has three or four fewer than one that does not.

Calculating against calendar days would show a false productivity collapse every
Ramadan, every year, and somebody would eventually be asked to explain a dip
that is not real. `dim_date.is_working_day` already knows which days count, and
`agg_monthly_service_summary` uses it, so the denominator is right by
construction.

This measure and its denominator are worth being able to defend in detail —
"utilisation" is the number an aftersales director is judged on.

### Cycle time, and the split that makes it actionable

```dax
Average Cycle Hours =
AVERAGE ( 'Repair Order'[total_cycle_hours] )

Average Touch Time Hours =
AVERAGE ( 'Repair Order'[touch_time_hours] )

Average Parts Wait Hours =
AVERAGE ( 'Repair Order'[parts_wait_hours] )

Parts Wait Share of Cycle % =
DIVIDE ( [Average Parts Wait Hours], [Average Cycle Hours] )
```

Total cycle time is one number that hides everything. In this dataset the median
is 73 hours and the p90 is 196 — and the difference is almost entirely parts
waiting, not work. `Parts Wait Share of Cycle %` is the measure that turns "the
workshop is slow" into "the parts supply chain is slow", which is a different
department and a different fix.

Nulls are preserved rather than coalesced. An order still in the workshop has no
cycle time, and `AVERAGE` correctly ignores it. Replacing those nulls with zero
would drag the average down and make the workshop look faster than it is.

```dax
Orders Awaiting Parts =
CALCULATE ( [Repair Order Count], NOT ISBLANK ( 'Repair Order'[parts_wait_hours] ) )

Open Order Count =
CALCULATE ( [Repair Order Count], 'Repair Order'[is_open] = TRUE () )
```

### Service retention — the hardest measure in the model

The share of vehicles sold by the network that came back to the network for
service. It is the number that tells a distributor whether its aftersales
business has a future, and it is hard because it spans two facts with different
grains and a time offset.

```dax
Service Retention Rate =
VAR SoldVehicles =
    CALCULATETABLE (
        VALUES ( 'Vehicle Sale'[vehicle_sk] ),
        'Vehicle Sale'[sale_type] = "NEW",
        ALL ( 'Date' )
    )
VAR ServicedVehicles =
    CALCULATETABLE (
        VALUES ( 'Repair Order'[vehicle_sk] ),
        REMOVEFILTERS ( 'Vehicle Sale' )
    )
VAR Retained =
    COUNTROWS ( INTERSECT ( SoldVehicles, ServicedVehicles ) )
RETURN
    DIVIDE ( Retained, COUNTROWS ( SoldVehicles ) )
```

Three things in there are deliberate:

- **`ALL('Date')` on the sold set.** The question is "of the cars we have ever
  sold, how many came back", not "of the cars sold this month". Leaving the date
  filter on would compare a month's sales against that same month's service
  visits and return almost zero, because a new car does not need servicing for a
  year.
- **`REMOVEFILTERS('Vehicle Sale')` on the serviced set.** Without it, the sales
  fact's filter context propagates through the shared vehicle dimension and
  restricts the service side to the same cars, making the intersection trivially
  equal to the sold set and the answer always 100%.
- **`INTERSECT` on surrogate keys, not VINs.** The key is what the model joins
  on, and a Type 2 vehicle has several surrogate keys — which is a genuine
  wrinkle here. For a strict version, intersect on the natural key instead:
  `VALUES('Vehicle'[vin])`.

### Revenue per vehicle

```dax
Serviced Vehicle Count =
DISTINCTCOUNT ( 'Repair Order'[vehicle_sk] )

Service Revenue per Vehicle =
DIVIDE ( [Service Revenue], [Serviced Vehicle Count] )
```

---

## 3. Warranty and recall

```dax
Warranty Cost Ratio =
DIVIDE (
    [Warranty Amount],
    CALCULATE ( [Net Sale Amount], REMOVEFILTERS ( 'Repair Order' ) )
)
```

Warranty cost as a share of sales revenue — the manufacturer quality metric.
`REMOVEFILTERS` on the repair order table stops the aftersales filter context
restricting the sales denominator.

```dax
Claim Count           = COUNTROWS ( 'Warranty Claim' )
Claimed Amount        = SUM ( 'Warranty Claim'[claimed_amount] )
Approved Amount       = SUM ( 'Warranty Claim'[approved_amount] )

Claim Approval Rate by Value =
DIVIDE ( [Approved Amount], [Claimed Amount] )

Unreimbursed Warranty Amount =
[Claimed Amount] - [Approved Amount]
```

By value, not by count. A distributor approving 95% of claims while paying only
the standard labour time on each is not approving 95% of the money, and the
dealer's P&L follows the money. In this dataset the value rate is 82.5%, so
17.5% of warranty work performed is never reimbursed — a real cost that the
aftersales report and the finance report would otherwise disagree about.

```dax
Recall Coverage Count =
SUM ( 'Recall Coverage'[coverage_count] )

Recall Completed Count =
CALCULATE ( [Recall Coverage Count], 'Recall Coverage'[is_completed] = TRUE () )

Recall Completion Rate =
DIVIDE ( [Recall Completed Count], [Recall Coverage Count] )

Recall Outstanding Count =
[Recall Coverage Count] - [Recall Completed Count]

Average Days Outstanding =
AVERAGE ( 'Recall Coverage'[days_outstanding] )
```

`Recall Outstanding Count` is the whole reason `fact_recall_coverage` is a
factless fact. It counts vehicles for something that has *not* happened, and no
table recording only completed work can answer it.

---

## 4. Procurement

```dax
PO Line Count       = SUM ( 'Part Purchase'[po_line_count] )
Purchase Amount     = SUM ( 'Part Purchase'[line_amount] )
Ordered Quantity    = SUM ( 'Part Purchase'[ordered_quantity] )
Received Quantity   = SUM ( 'Part Purchase'[received_quantity] )

Late Line Count =
CALCULATE ( [PO Line Count], 'Part Purchase'[is_late] = TRUE () )

Supplier On Time Rate =
DIVIDE ( [PO Line Count] - [Late Line Count], [PO Line Count] )

Average Delay Days =
AVERAGE ( 'Part Purchase'[delay_days] )

Fill Rate =
DIVIDE ( [Received Quantity], [Ordered Quantity] )
```

`Average Delay Days` is kept signed. Clamping negatives to zero would hide early
delivery, which is also supplier behaviour worth seeing — and a supplier who is
consistently three days early is telling you your lead times are wrong.

---

## 5. Inventory — semi-additive, and the classic trap

`fact_vehicle_inventory_daily` holds one row per vehicle per day. Summing
`vehicle_count` across a month gives the number of vehicle-days, not the number
of vehicles — a stock of 300 cars over 30 days reports as 9,000.

```dax
Vehicles In Stock =
CALCULATE (
    SUM ( 'Vehicle Inventory'[vehicle_count] ),
    LASTDATE ( 'Date'[full_date] )
)

Stock Value Amount =
CALCULATE (
    SUM ( 'Vehicle Inventory'[stock_value_amount] ),
    LASTDATE ( 'Date'[full_date] )
)

Average Stock Age Days =
CALCULATE (
    AVERAGE ( 'Vehicle Inventory'[days_in_stock] ),
    LASTDATE ( 'Date'[full_date] )
)

Aged Stock Count =
CALCULATE (
    [Vehicles In Stock],
    'Vehicle Inventory'[age_band] IN { "91-180", "180+" }
)

Aged Stock Share % =
DIVIDE ( [Aged Stock Count], [Vehicles In Stock] )
```

`LASTDATE` takes the closing position of whatever period is in context: the last
day of the month at month level, the last day of the year at year level. That is
what "how much stock did we have" means for a balance.

**These measures must not be used in a running total**, and the model should
carry that warning as a description on each of them. It is the most common
semi-additive mistake and it produces a number that looks plausible.

---

## 6. Data quality

```dax
Rules Evaluated  = COUNTROWS ( 'Data Quality' )
Rows Violated    = SUM ( 'Data Quality'[rows_violated] )
Rows Evaluated   = SUM ( 'Data Quality'[rows_evaluated] )

Violation Rate =
DIVIDE ( [Rows Violated], [Rows Evaluated] )

Critical Violations =
CALCULATE ( [Rows Violated], 'Data Quality'[severity] = "critical" )

Failed Rule Count =
CALCULATE ( [Rules Evaluated], 'Data Quality'[outcome] = "FAILED" )

Errored Rule Count =
CALCULATE ( [Rules Evaluated], 'Data Quality'[outcome] = "ERROR" )
```

`Errored Rule Count` deserves its own card on the page, coloured red at anything
above zero. A rule that could not run finds no violations, and reporting that as
a clean result means a silently disabled check looks exactly like clean data.
That is the failure mode a data quality page exists to prevent.

```dax
Quarantine Rate =
DIVIDE (
    SUM ( 'Data Quality'[rows_quarantined] ),
    [Rows Evaluated]
)

Violation Rate vs Last Batch =
VAR Current = [Violation Rate]
VAR Prior =
    CALCULATE (
        [Violation Rate],
        OFFSET ( -1, ALLSELECTED ( 'Data Quality'[batch_id] ), ORDERBY ( 'Data Quality'[batch_id] ) )
    )
RETURN Current - Prior
```

The trend matters more than the level. A steady 1.8% violation rate is the
business as usual; the same rate jumping to 4% overnight means a source system
changed, and that is the alert worth having.

---

## Measure naming

Title Case with spaces, no prefixes, no Hungarian notation. `Net Sale Amount`,
not `_netSaleAmt` or `M_NetSale`. Report users read these names in the field
list and in tooltips, and they are the only part of the model a business user
ever sees.

Where a measure could be misread, the meaning goes in the model's description
property rather than into the name — `Discount Rate` with a description saying
"weighted: total discount over total list price, not the average of per-contract
rates" is better than a measure called `Weighted Discount Rate` that nobody can
find because they were looking for "Discount".
