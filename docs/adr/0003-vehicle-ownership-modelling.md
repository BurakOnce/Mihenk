# ADR-0003: Vehicle ownership tracked as SCD Type 2 on dim_vehicle, not as a bridge

- **Status:** Accepted
- **Date:** 2026-09-10
- **Phase:** 4 (deferred from Phase 1)
- **Decision owner:** Burak Önce

---

## Context

A VIN is the natural key of `dim_vehicle`, and it changes hands. In the
generated dataset 3,006 vehicles end the timeline with two owners: sold new,
traded in against a replacement, reconditioned, sold again to somebody else.

So "who owned vehicle `NM7XK2DE2PT000100` in March 2024" has an answer that
depends on when you ask, and getting it right is the defining modelling problem
of this domain. A repair order in 2024 belongs to the owner at that time, not to
whoever owns the car today — and a report that attributes it to the current owner
would move revenue between customers silently.

This decision was deliberately deferred from Phase 1. The generator emits the
same ownership events either way, so nothing upstream depended on it, and
deciding it with the actual data in hand is better than deciding it on paper.

## Options considered

| # | Option | Pros | Cons |
|---|---|---|---|
| A | **SCD Type 2 on `dim_vehicle`**, with `master_customer_id` as a tracked attribute alongside status and plate | One structure. `dim_vehicle` already needs Type 2 for status (`IN_STOCK` → `SOLD` → `USED_STOCK`) and plate, so ownership rides along at no extra cost. A fact joins to one `vehicle_sk` and gets the vehicle *and* its owner as of that day. Point-in-time queries are the ordinary Type 2 pattern | Cannot represent two owners at once. A vehicle version is created every time *any* tracked attribute changes, so an ownership question has to look through versions created by unrelated plate changes |
| B | **A separate bridge table** `br_vehicle_ownership` with `vin`, `master_customer_id`, `valid_from`, `valid_to`, `ownership_type` | Separates two genuinely different histories - what the vehicle *is* versus who *holds* it. Supports several simultaneous relationships, which is what leasing actually looks like: the leasing company owns it, the driver uses it, the employer pays for it. Ownership can be queried without touching the vehicle dimension | A second Type 2-shaped structure to load and reconcile. Every fact wanting an owner needs a range join rather than a surrogate key lookup, which is slower and much easier to get wrong. Two places where "as of" logic has to agree |
| C | **Both** - Type 2 on the dimension for the current owner, bridge for history | Fast common case, complete history | Two sources of truth for the same fact. When they disagree - and they will - there is no principled answer to which is right |

## Decision

**Option A.** Ownership is a Type 2 attribute of `dim_vehicle`:
`master_customer_id`, `owner_since_date`, alongside `status`, `plate_hash` and
`stock_dealer_code`.

Facts carry `vehicle_sk`, which resolves to the vehicle *version* current on the
transaction date, and the owner comes with it.

Three things decided it:

1. **The data has no simultaneous owners.** Every vehicle in this dataset has
   exactly one owner at a time. Building a structure to represent a
   many-to-one-at-a-point-in-time relationship that the source systems do not
   record would be speculative generality — a bridge table whose bridging column
   is always 1.

2. **`dim_vehicle` is Type 2 regardless.** Status and plate change and their
   history is needed. Given that the versions exist anyway, putting ownership
   on a second structure means maintaining two histories that have to be kept
   consistent with each other, for no gain.

3. **The join is simpler and therefore more likely to be right.** A fact row
   already resolves `vehicle_sk` by VIN and transaction date. Getting the owner
   from that same lookup costs nothing. A bridge would mean a second range join
   per fact — `WHERE fact_date BETWEEN valid_from AND valid_to` — which is both
   slower and a well-known source of subtle duplication when the ranges overlap
   by a day.

## Consequences

**What this makes easier**

- Point-in-time ownership is the ordinary Type 2 lookup every other dimension
  already uses. Nothing special to explain, nothing special to test.
- One load procedure. `usp_load_dim_vehicle` handles ownership and every other
  attribute in the same pass.
- Power BI gets it for free: the customer relationship on `fact_repair_order`
  goes through `dim_vehicle` and is automatically as-of-transaction.

**What this makes harder — the price being paid**

- **Version inflation.** A plate change creates a new vehicle version even though
  ownership did not change, so a query asking only about ownership has to look
  through versions it does not care about. With 35,000 vehicles and a handful of
  changes each this is measured in tens of thousands of rows — irrelevant at this
  scale, and it would stop being irrelevant at a few million vehicles.
- **Leasing is modelled wrongly, and knowingly.** 4% of contracts are leases. In
  reality the leasing company owns the vehicle and the customer uses it; here the
  customer is recorded as the owner. That is a real inaccuracy. It is accepted
  because the source systems do not distinguish the two either — recording a
  distinction the data does not contain would be inventing information.
- **A future requirement to separate ownership from usage means migrating**, not
  extending. See below.

## Reversal conditions

Two triggers, both concrete:

1. **A vehicle needs more than one current relationship** — most likely when
   leasing has to distinguish legal owner from registered user, or when fleet
   customers need the employing company and the assigned driver both recorded.
2. **Vehicle count reaches the low millions**, where version inflation from
   unrelated attribute changes starts to cost real query time.

**Migration path if either fires.** `br_vehicle_ownership` is derivable from the
existing `dim_vehicle` history without any new source data:

```sql
SELECT vehicle_id AS vin, master_customer_id, valid_from, valid_to
FROM gold.dim_vehicle
WHERE master_customer_id IS NOT NULL
GROUP BY vehicle_id, master_customer_id, valid_from, valid_to
```

collapsing adjacent versions that share an owner. So choosing A now does not
close off B later; it defers it at the cost of one backfill. Choosing B now would
mean carrying the cost immediately for a capability nothing currently asks for.

## Verification

No unverified platform behaviour. The decision rests on the shape of the data
and on the requirements as they stand, both of which are known.

## References

- [ADR-0002](0002-hybrid-spark-and-tsql-architecture.md) — the layer this
  decision lives in
- `sql/03_gold/40_dim_loads.sql` — `usp_load_dim_vehicle`
- `docs/naming_standard.md` §6 — the SCD Type 2 column contract
