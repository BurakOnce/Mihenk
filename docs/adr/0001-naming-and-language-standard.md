# ADR-0001: English identifiers, Turkish data content

- **Status:** Accepted
- **Date:** 2026-09-10
- **Phase:** 0
- **Decision owner:** Burak Önce

---

## Context

Mihenk models a Turkish automotive distributor. The business vocabulary is
Turkish — *araç, bayi, iş emri, yedek parça, garanti*. The technical stack is
not: Delta / Parquet metadata, Fabric Warehouse T-SQL, PySpark and Power BI DAX
all sit between the business and its data.

Every schema, table and column name in this project has to pass through all four
of those layers unchanged. A naming choice made once in Phase 0 propagates into
roughly two hundred identifiers across six phases, so changing it later means
rewriting the generator, the notebooks, the DDL and the semantic model at once.
It is effectively a one-time decision.

Two things pull in opposite directions:

- Data modelling is partly a communication job. A dimensional model that uses
  the business's own words is easier for that business to validate.
- Turkish has a locale-dependent case mapping. `"İSTANBUL".lower()` yields
  `"i̇stanbul"` under a Turkish locale and `"i̇stanbul"` vs `"istanbul"`
  inconsistently across Python, T-SQL and Spark. Turkish-cased identifiers
  therefore make any `upper()` / `lower()` normalisation locale-dependent.

## Options considered

| # | Option | Pros | Cons |
|---|---|---|---|
| A | **All English identifiers** (`dim_vehicle`, `fact_vehicle_sale`) | Matches Kimball literature term for term; every code sample, library and Fabric doc uses the same vocabulary; zero encoding risk; portable to a non-Turkish reviewer or team | The business says "araç", the model says "vehicle" — one translation hop between stakeholder and schema |
| B | **Turkish identifiers with Turkish characters** (`dim_araç`, `müşteri_no`) | Perfect one-to-one match with the business vocabulary | Locale-dependent case mapping becomes a silent correctness risk in three engines; Parquet/Delta column names, DAX identifiers and Python attribute access all have to tolerate non-ASCII; unreadable to any reviewer who does not read Turkish |
| C | **Turkish vocabulary, ASCII-folded** (`dim_arac`, `musteri_no`) | Business vocabulary preserved; no encoding risk | `arac` / `musteri` are neither correct Turkish nor English — they read as damaged text; still opaque to a non-Turkish reviewer; the fold has to be applied consistently by hand with no tooling to enforce it |

## Decision

**Option A.** All identifiers — schemas, tables, columns, views, procedures,
files, folders, notebooks, pipelines, code comments and documentation — are
English, `snake_case`, ASCII only.

**Data content is not touched.** Customer names, dealer names, city names and
free-text fields keep their full Turkish characters in `NVARCHAR` / Spark
`string` columns. Stripping them would be a data quality defect, and the MDM
matching exercise in Phase 3 depends on Turkish character variants being present
in the source data.

Business terms map to the **industry-standard English term**, not to a
dictionary equivalent: *iş emri* becomes `repair_order` because "Repair Order"
is what dealer management systems actually call it; *donanım paketi* becomes
`trim`. The mapping is recorded in
[`docs/naming_standard.md`](../naming_standard.md) so the translation hop is
documented rather than implicit.

The full rule set lives in `docs/naming_standard.md`. This ADR records only
*why*.

## Consequences

**What this makes easier**

- One vocabulary across Spark, T-SQL, DAX and Python, with no transliteration
  layer anywhere.
- No locale-dependent case-folding risk on identifiers.
- Object names line up with dimensional modelling literature, which makes design
  intent legible: `fact_repair_order` being an accumulating snapshot is a
  recognisable pattern, `fact_is_emri` is not.
- Readable by a reviewer who does not speak Turkish.

**What this makes harder — the price we are paying**

- A permanent translation hop between business stakeholders and the schema. A
  service manager asking about "iş emri kapanma süresi" has to be mapped to
  `fact_repair_order.closed_date`. The glossary in `docs/naming_standard.md` §1
  and the generated data dictionary exist to absorb this cost, but it does not
  disappear.
- Some translations are judgement calls that a Turkish reader may disagree with
  (`trim` for *donanım paketi*, `dealer` for *bayi*). These are defensible but
  not self-evident, so they are documented explicitly.
- Report-level naming needs a second pass in Phase 5: end users see Power BI, and
  Power BI table and measure names may need to be Turkish even though the
  underlying model is English. That decision is deferred to Phase 5 and will get
  its own ADR if it goes that way.

## Reversal conditions

Reversing this after Phase 1 means renaming across the generator, all Bronze and
Silver notebooks, all Gold DDL and the semantic model simultaneously — a day of
work with a high chance of missing a reference, since Fabric Warehouse does not
enforce foreign keys and a broken reference would fail silently at query time
rather than at deploy time.

The only reasonable trigger for reversal is a hard requirement that end users
query the Gold layer directly in Turkish. Even then the cheaper fix is a Turkish
view layer over the English tables, not a rename.

## Verification

No unverified platform behaviour. Non-ASCII identifiers are technically
*supported* by Delta and by Fabric Warehouse when quoted; this decision avoids
them for locale-safety and readability reasons, not because they are impossible.

## References

- [`docs/naming_standard.md`](../naming_standard.md) — the rules themselves
- [ADR-0002](0002-hybrid-spark-and-tsql-architecture.md) — the layer split these
  names have to survive
