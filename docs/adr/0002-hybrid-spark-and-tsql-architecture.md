# ADR-0002: Silver built in PySpark, Gold built in T-SQL

- **Status:** Accepted
- **Date:** 2026-09-10
- **Phase:** 0
- **Decision owner:** Burak Önce

---

## Context

Microsoft Fabric offers two compute engines over the same OneLake storage, and
both can do most of this job:

- **Lakehouse + PySpark notebooks** — Delta tables, full Python ecosystem,
  distributed compute, Delta MERGE.
- **Warehouse + T-SQL** — full T-SQL surface, stored procedures, the
  transactional semantics of a relational warehouse.

The platform has to move data through Bronze → Silver → Gold, and the engine
choice per layer is open. The work in each layer is genuinely different in
character:

- **Silver work** is cleansing, deduplication, reference mapping, PII masking,
  fuzzy customer matching for MDM, and a VIN check-digit calculation. Several of
  these are row-level algorithms rather than set operations.
- **Gold work** is dimensional modelling: surrogate key assignment, SCD Type 2
  version management, fact loading with key lookups, aggregate builds. These are
  set-based operations that relational engines were built for.

Two constraints shape the decision beyond pure suitability:

1. **Skill.** I am strong in SQL and learning Spark on this project. Spark is a
   deliberate learning goal, not an accident — Fabric Lakehouse notebooks are
   PySpark and I want that skill. But it is also the single largest schedule
   risk in a 3–5 day build.
2. **Time.** Three facts and ten dimensions have to land inside the budget.

The relevant Fabric Warehouse limitations are listed in the Verification table
below rather than asserted here, because several of them change between Fabric
releases.

## Options considered

| # | Option | Pros | Cons |
|---|---|---|---|
| A | **All Spark** — Bronze, Silver and Gold as Delta tables built in PySpark notebooks | One engine, one language, one set of concepts; `DeltaTable.merge()` handles SCD2 cleanly; no cross-engine boundary to debug | Puts the entire project on my weakest skill, including the modelling work I am strongest at; Power BI Direct Lake over Lakehouse works but the Warehouse gives a more familiar governance and permission story; loses the chance to demonstrate T-SQL depth, which is a real strength |
| B | **All T-SQL** — land files into the Warehouse and do everything relationally | Fastest for me; every step in a language I already know | Fuzzy string matching, hashing and VIN check-digit logic in pure T-SQL is awkward and slow to write; semi-structured JSON sources need shredding before they can be loaded at all; and it abandons the Spark learning goal, which was a stated objective of the project |
| C | **Hybrid** — Bronze and Silver in PySpark on the Lakehouse, Gold in T-SQL on the Warehouse | Each engine does the work it is actually good at; Spark is learned where it genuinely pays (cleansing semi-structured data at scale); dimensional modelling stays in T-SQL where I am fastest and most defensible; matches the reference pattern Microsoft publishes for Fabric medallion architectures | Two engines, two languages, one boundary to cross; requires cross-item querying between Lakehouse SQL endpoint and Warehouse to work reliably; more setup and more documentation |

## Decision

**Option C.** 

| Layer | Engine | Item |
|---|---|---|
| Landing | Files | Lakehouse — OneLake `Files/` |
| Bronze | PySpark notebook | Lakehouse — Delta tables |
| Silver | PySpark notebook | Lakehouse — Delta tables |
| Gold | T-SQL stored procedures | Warehouse |
| Control (`ctl`) | T-SQL | Warehouse |
| Semantic model | Direct Lake | Power BI over the Warehouse |

The boundary is crossed at Silver → Gold using three-part naming from the
Warehouse against the Lakehouse SQL endpoint, which is why Verification item 4
below is a hard prerequisite for Phase 4.

The `ctl` schema lives in the Warehouse rather than the Lakehouse because it is
written by both the Data Factory pipeline and the Gold procedures, and
transactional row-level updates to a run log are a relational workload, not a
Delta one.

## Consequences

**What this makes easier**

- Semi-structured JSON sources (CRM, distributor portal) get shredded in Spark,
  which is what Spark is for. Doing this in T-SQL would mean either pre-flattening
  in Python before upload — moving transformation logic outside the platform — or
  fighting `OPENJSON`.
- Row-level algorithms in Silver (VIN check digit, fuzzy name matching for MDM,
  PII hashing) are written in Python, where they are readable and testable.
- SCD Type 2 and surrogate key assignment stay in T-SQL, where the set-based
  logic is explicit and I can defend every line of it.
- Spark is learned on the part of the pipeline where its advantage is real,
  rather than everywhere at once.
- It is the pattern Microsoft's own Fabric medallion guidance describes, so the
  choice is conventional rather than novel — which is the right kind of boring
  for a data platform.

**What this makes harder — the price we are paying**

- **Two engines means two failure modes.** A Silver bug is debugged in a Spark
  notebook; a Gold bug in a T-SQL procedure. Skills and tooling do not transfer.
- **The Silver → Gold boundary is the highest-risk part of the build.**
  Cross-item querying has to work, and type mapping between Delta and Warehouse
  T-SQL types has to be checked column by column — particularly `DECIMAL`
  precision, `TIMESTAMP` vs `DATETIME2`, and Delta `string` vs `VARCHAR` length.
- **More setup.** Two Fabric items, two sets of permissions, and a
  `fabric/setup_steps.md` that has to be accurate enough for someone else to
  reproduce.
- **Data lands twice** in a sense: Silver Delta tables are read by the Warehouse
  rather than owned by it. Lineage documentation has to make that hop explicit or
  it looks like data appears from nowhere.

## Reversal conditions

This decision has one explicit, pre-agreed abort path.

**Trigger:** if by the end of Day 2 the Silver notebook is not producing correct
output — Delta MERGE failing, the Spark learning curve consuming the schedule, or
the cross-engine boundary not resolving — Silver moves to T-SQL in the Warehouse.

**What that costs:** JSON sources would need flattening during generation in
Phase 1 rather than in Silver, and the MDM fuzzy matching would drop from a
similarity score to a deterministic normalised-key match. Both are real
capability reductions and would be recorded honestly.

**What that preserves:** Bronze stays in PySpark regardless. Even in the fallback
the project demonstrates Spark ingestion, and Gold is unaffected.

This is scope management, not failure. Deciding the abort condition now, while
nothing is at stake, is the entire reason it is written down here — a Day 2
decision made under schedule pressure without a pre-agreed trigger is just panic.

## Verification

Fabric behaviour changes between releases. Nothing below is treated as fact until
it has been run in our own tenant. Each item blocks a specific phase.

All items below were run for real on 2026-09-13/14 against an Azure pay-as-you-go
F2 capacity (the Fabric Trial was refused for this tenant — see
`fabric/setup_steps.md` §0), workspace `mihenk`, `mihenk_lh` Lakehouse and
`mihenk_wh` Warehouse, after the full Bronze → Silver pipeline had actually run.

| # | What to verify | How | Blocks | Result | Verified on |
|---|---|---|---|---|---|
| 1 | `IDENTITY` columns in a Warehouse table | `CREATE TABLE ctl.t (id INT IDENTITY(1,1))` | Phase 4 | **Partially supported, not what was assumed.** `INT IDENTITY` fails (`Identity column 'id' must be of data type BIGINT`); `BIGINT IDENTITY(1,1)` *also* fails (`does not support specifying SEED or INCREMENT`); bare `BIGINT IDENTITY` (implicit 1,1) succeeds and auto-increments correctly. So IDENTITY is real in Fabric Warehouse, just narrower than T-SQL generally: BIGINT only, default seed/step only. Gold still uses the `ROW_NUMBER()+MAX` pattern regardless, because seed/increment control and cross-batch determinism matter more here than the syntax being available. | 2026-09-14 |
| 2 | `MERGE` statement support in Warehouse | Minimal two-table `MERGE` with `WHEN MATCHED` / `WHEN NOT MATCHED` | Phase 4 | **Works exactly as documented for standard T-SQL** — matched row updated, unmatched row inserted, single statement. Gold's `MERGE`-based SCD2 procedure is the one actually in use, not the `UPDATE`+`INSERT` fallback. | 2026-09-14 |
| 3 | `PRIMARY KEY` / `FOREIGN KEY` enforcement | Create a `NOT ENFORCED` PK, insert a duplicate key, count rows | Phase 4 | **Confirmed not enforced** — `INSERT` of two rows sharing a PK value both succeed, `COUNT(*)` returns 2. Referential integrity is entirely on `ctl.dq_rule`'s shoulders. This is not theoretical: the local SQL Server test run this same night caught two real bugs (a CTE-scope error and a duplicate-holiday-date collision in `gold.usp_populate_dim_date`) that a `NOT ENFORCED` Fabric Warehouse would have accepted silently. | 2026-09-14 |
| 4 | Cross-item query: Warehouse → Lakehouse SQL endpoint | `SELECT TOP 10 * FROM mihenk_lh.silver.dealer` using three-part naming, same workspace | **Phase 4 — hard prerequisite** | **Works.** Returned 10 rows from `silver.dealer` and 1 row from `silver.sales_contract` with no errors. One adjacent limitation found while testing this: `sys.columns` / `OBJECT_ID()` cannot see across the boundary (returns nothing for a cross-item object) — `sp_describe_first_result_set` on an actual query does, and is what item 6 below used. | 2026-09-14 |
| 5 | `DeltaTable.merge()` in a Lakehouse notebook | Upsert into a small Delta table, run twice, compare row counts | Phase 3 | **Confirmed idempotent.** `10_silver_master`'s own second-pass check (re-running `load_entity()` against all 7 master specs and asserting `inserted == 0 and updated == 0`) reported `OK` for every entity on the real run. | 2026-09-14 |
| 6 | Delta → Warehouse type mapping | `sp_describe_first_result_set` on `SELECT * FROM mihenk_lh.silver.sales_contract` | Phase 4 | **Mostly clean, one real gotcha.** `decimal(18,2)`/`decimal(9,6)`/`decimal(18,6)` map through with precision and scale intact. Spark `DateType` → SQL `date` exactly. Spark `TimestampType` → `datetime2(6)`, not the `datetime2(3)` Gold's own DDL uses for `_loaded_ts` — narrows on insert, not a blocker, but worth knowing before writing a Gold load that compares timestamps for equality. The real gotcha: **every Delta `string` column, regardless of actual content length, becomes `varchar(8000)`** on the SQL endpoint — there is no length metadata to inherit. Gold's dimension/fact `VARCHAR(n)` columns are deliberately sized (e.g. `VARCHAR(20)` for a dealer code) and rely on the load procedure's own `CAST`, not on anything the source column enforces. | 2026-09-14 |
| 7 | Direct Lake over Warehouse with the Trial SKU | Build a minimal semantic model and confirm it does not fall back to DirectQuery | Phase 5 | Pending — the Fabric Trial route itself was refused for this tenant (see §0), so this item is being re-scoped to Direct Lake over the paid F2 capacity instead of the Trial SKU specifically. | |

Results are recorded in this table with a date, and any surprise gets its own ADR.

## References

- [ADR-0001](0001-naming-and-language-standard.md) — the identifier rules both
  engines share
- `fabric/setup_steps.md` — the concrete setup this decision implies
- `docs/architecture.md` — layer contracts
