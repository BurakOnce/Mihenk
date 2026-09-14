# Defence notes

Every non-obvious decision in this project, the alternatives that were
considered, and what each choice costs. Written to be read before a technical
discussion, not during one.

The organising principle throughout: **a decision with no stated downside is a
decision that was not actually made.** Every entry below has one.

---

## Part 1 — The decisions

### 1.1 Architecture

**Why a hybrid Spark/T-SQL platform rather than one engine?**
→ [ADR-0002](adr/0002-hybrid-spark-and-tsql-architecture.md)

Silver work is row-level algorithms — fuzzy name matching, VIN check digits, PII
hashing, shredding nested JSON. Gold work is set-based dimensional modelling.
All-Spark would put the modelling I am strongest at onto the tool I am weakest
at; all-T-SQL would make the JSON shredding awkward and abandon the Spark
learning goal.

**The cost:** two engines, two failure modes, and a boundary at Silver→Gold that
is the highest-risk part of the build. Debugging skills do not transfer between
a Spark notebook and a T-SQL procedure.

**Was there an abort plan?** Yes, written before starting: if Silver was not
producing correct output by the end of day two, it moved to T-SQL, with JSON
pre-flattened during generation and MDM matching downgraded from a similarity
score to a deterministic key match. Deciding the abort condition while nothing
is at stake is the entire reason it is written down.

---

**Why is the control plane (`ctl`) in the Warehouse rather than the Lakehouse?**

`pipeline_run_log` is an OLTP workload wearing analytics clothing: a row is
INSERTed when a step starts and UPDATEd when it ends. Delta can do that, but
every small update rewrites files, and the Data Factory ForEach runs sources in
parallel — Delta's optimistic concurrency throws on concurrent writes to one
table. The Warehouse gives real transactional single-row UPDATE and a SQL
connection Data Factory uses natively.

Also: the DQ procedures and the Gold loads are T-SQL and read `ctl` constantly.
Keeping it in the same engine avoids an engine switch on the hot path.

---

**Why does Bronze write nothing to the Warehouse?**

Deliberate risk avoidance. Whether the Warehouse can read Lakehouse tables at
all is ADR-0002 item 4 and is unverified. The Bronze notebook returns row counts
through `notebookutils.notebook.exit`, the pipeline parses them and calls a
stored procedure. So the design has **no dependency** on that verification.

---

### 1.2 Modelling

**Why is vehicle ownership on `dim_vehicle` and not a bridge table?**
→ [ADR-0003](adr/0003-vehicle-ownership-modelling.md)

The data has no simultaneous owners. `dim_vehicle` is Type 2 for status and
plate regardless, so ownership rides along at no extra cost, and a fact
resolving one `vehicle_sk` gets the vehicle *and* its owner as of that day. A
bridge would mean a range join per fact — slower and a known source of subtle
duplication when ranges overlap by a day.

**The cost, stated plainly:** leasing is modelled wrongly and knowingly. In
reality the leasing company owns the vehicle and the customer uses it; here the
customer is the owner. That is 4% of contracts. It is accepted because the
source systems do not distinguish the two either, and recording a distinction
the data does not contain would be inventing information.

**When would it flip?** When a vehicle needs more than one current relationship
— legal owner versus registered user — or at a few million vehicles where
version inflation from unrelated attribute changes starts to cost query time.
The bridge is derivable from the existing `dim_vehicle` history with one
backfill, so choosing this now defers the other rather than closing it off.

---

**Why is `fact_repair_order` an accumulating snapshot?**

A repair order is a process with waiting rooms, not a transaction: appointment →
check-in → inspection → waiting for parts → repair → quality control → handover.
Each stage has its own timestamp and the *gaps between them* are the measures
the aftersales report exists for.

Total cycle time is one number that hides everything. In this dataset the median
is 73 hours and the p90 is 196, and almost all of that spread is parts waiting,
not work. Splitting touch time from wait time turns "the workshop is slow" into
"the parts supply chain is slow" — a different department and a different fix.

**The consequence people miss:** later stage columns are null until the stage
happens, and 1,090 orders end the timeline mid-process. That is the pattern
working. An accumulating snapshot in which every row is complete demonstrates
nothing.

---

**Why build a 1.6-million-row periodic snapshot for inventory?**

Because "average days in stock" cannot be derived from the sales fact. The sales
fact only knows about cars that *sold*; the 10,891 that never did are invisible
to it, and they are precisely the ones consuming floorplan cost.

A periodic snapshot is the only fact type that can count something for **not
happening**.

**The cost:** 1.6 million rows, semi-additive measures that are wrong if summed
across days, and the largest table in the model to watch for Direct Lake
fallback.

---

**Why is `fact_recall_coverage` factless?**

The question it answers is a negative one: *which vehicles are in scope and have
still not been seen?* A table recording only completed work cannot answer that.
The factless fact records the relationship itself, so `is_completed = 0` is the
answer.

---

**Why is `dim_supplier` Type 1 when almost everything else is Type 2?**

Nobody asks what a supplier's lead time was last year when analysing a purchase
order. They ask about the lead time recorded *on* the order, which is a fact
column. Making every dimension Type 2 by reflex is a common and expensive habit
— it doubles the load complexity and the row count for history nobody queries.

---

**Why a junk dimension, and when would it be wrong?**

Six low-cardinality flags collapse into one key instead of six fact columns.
Power BI gets six slicers from one table, and adding a seventh flag means adding
a column rather than altering a fact table with hundreds of thousands of rows.

It is built from the combinations that **actually occur**, not the full cartesian
product — a slicer offering combinations that return zero rows is a slicer people
stop trusting.

**When it degenerates:** add one genuinely high-cardinality attribute and it
becomes a second fact table. The combination count has to stay in the low
hundreds.

---

**Why `-1` for Unknown instead of a null foreign key?**

A null fails the join, and Power BI answers a failed join by creating a **blank
row**: the fact disappears from every visual sliced by that dimension, the totals
stop matching the grand total, and nothing anywhere says so.

`-1` with an "Unknown" label keeps the rows visible, keeps the measures additive,
and lets a report show *how much* is unknown — which is a data quality signal in
its own right.

`-2` is a separate member for "not applicable", because a sale with no trade-in
is a different fact from a trade-in we could not identify, and conflating them
makes "how many sales had no trade-in" unanswerable.

---

**Why keep `is_current` when `valid_to = '9999-12-31'` says the same thing?**

`WHERE is_current = 1` avoids scattering a magic literal through every query, it
survives the sentinel value ever changing, and a BIT predicate is cheaper for
the optimiser than a date comparison.

**The risk accepted:** two sources of truth that can disagree. The load sets both
in the same statement, and `gold.vw_scd2_integrity` asserts
`(is_current = 1) = (valid_to = '9999-12-31')` on every row. That check is the
rent paid for the redundancy.

---

### 1.3 Data quality

**Why are the rules data rather than code?**

Adding a rule is a row in `ctl.dq_rule`. But the real payoff is that **the same
rule definition runs in two engines**: the Warehouse stored procedure and the
Spark runner in `40_silver_dq`. Written as procedural code, discovering that the
Warehouse cannot read Silver would mean rewriting every rule.

`violation_sql` returns exactly `(business_key, detail)` for every rule type,
which is what lets one runner execute a null check, a uniqueness check, a
referential check and a cross-row window function without knowing the
difference.

---

**Why compute the VIN check digit in Silver and store it, rather than in the rule?**

Because the alternative ties the rule to one engine. `ctl.vw_vin_check_digit`
computes it in T-SQL; pointing the rule at that view means the rule can only ever
run in the Warehouse. Stored as a boolean column, the rule is
`WHERE vin_check_digit_valid = 0` — engine-neutral SQL.

Rules as data only pays off if the rules do not secretly depend on one engine.

---

**Why does the VIN check digit rule matter at all?**

It is the difference between "I wrote a data quality check" and "I understood the
domain". A VIN can be exactly 17 legal characters and still be wrong; only
position 9 catches a transposition, which is exactly what human transcription
produces. A length-and-alphabet regex waves it straight through.

It is a **warning**, not critical — the vehicle is almost certainly real and one
character is wrong, and quarantining the repair order would lose genuine revenue
to fix a typo.

---

**Why is `VIN_ORPHAN` a warning when other referential failures are critical?**

Because in automotive it is often legitimate. A car bought from another dealer in
the network arriving for service is a normal business event, not a defect. Gold
answers it with an inferred member rather than dropping the fact. The rule exists
to *measure how often it happens*, not to reject it.

---

**How do you know the DQ framework works?**

Because it can be measured. The generator writes `_injection_log.csv` recording
every deliberately injected defect — entity, business key, column, before and
after, and the rule code that should catch it. `90_mdm_evaluation` joins that to
`silver.dq_violation` and reports recall per rule.

The rule codes are **imported from `data_generator.dirty`** when the seed SQL is
generated, and the generator refuses to build if any injectable defect type has
no rule looking for it. Verified by deliberately adding a fake defect code and
watching the build fail.

---

**Was the generator's output actually clean before injection?**

Yes, and it was audited the way a SQL rule would audit it — sorting by
`checkin_ts` rather than by processing order. That distinction caught a real bug:
two repair orders for the same VIN on the same day were given independent random
check-in times, so ordering by timestamp produced **596 phantom odometer
rollbacks** that nobody injected. A car does not visit the workshop twice in a
day; guarded, and the pre-injection audit is now zero on every rule.

Without that audit, those 596 would have been scored as detections and the
measured recall would have been quietly wrong.

---

### 1.4 MDM

**Why blocking, and how were the keys chosen?**

21,253 DMS records against 20,034 CRM records is 425 million comparisons. That is
not a performance problem to optimise later; it is the difference between a
notebook that finishes and one that does not.

Four blocking keys — identity hash, phone, email, name prefix plus city — chosen
to **fail in different ways**, so a pair missed by one is usually caught by
another.

**Recall is won or lost here.** A pair no block generates can never be matched no
matter how good the scoring is, because the scorer never sees it. Any missing
recall should be investigated in the blocking before the weights.

---

**Why that scoring threshold?**

55, chosen so no single weak signal carries a match. Identity alone (60) clears
it; phone (30) plus an identical name (25) clears it; a shared city and a similar
name (20) does not. The nearest genuine call is phone + similar name + city = 50,
which stays below — two people in the same city with similar names sharing a
phone number is more likely a family than a duplicate.

A customer-type mismatch is **−40**, larger than any positive combination short
of identity plus phone. An individual and a sole trader share a phone and an
address routinely, and merging them would corrupt every segmentation.

---

**Why mutual best match instead of clustering?**

The problem is bipartite — both sides are already deduplicated to one row per key
— so a cluster is at most one record from each side. That avoids connected
components entirely, which would be the hardest part of the notebook and is
genuinely awkward in Spark.

**It is conservative, deliberately.** Where two people have near-identical
records it matches neither rather than guessing. For a customer master feeding
financial reporting that is the right direction to be wrong in: a false merge
silently combines two people's purchase history and is nearly impossible to
detect afterwards, while a missed merge shows up as a duplicate somebody reports.

---

**Which survivorship rule is worth defending?**

The name. The obvious rule — take the most recent — is wrong. Recency answers
"which value is current", but an abbreviated or character-stripped name was never
*more* correct, it was only written later. So the rule takes the most **complete**
value: length plus a triple weighting for characters that survived the trip, so
`GÜLBEYAN ŞENER` beats `G. ŞENER` and the version that kept its Turkish
characters beats the folded one.

---

**Why is `master_customer_id` persisted rather than derived?**

Deriving it from whichever source record is the anchor breaks the moment a
CRM-only lead buys a car: the anchor changes, the id changes, `dim_customer` sees
a brand new entity, and every historical fact still points at the old one — the
customer's purchase history splits in two.

So the existing cross-reference is read first, any source record already assigned
keeps its id, and only genuinely new clusters get new ones. That also makes the
notebook idempotent.

---

### 1.5 The things that went wrong

Kept because they are more interesting than the things that went right.

| Found | What it was | How it was caught |
|---|---|---|
| Engine numbers not reproducible | Derived with `hash()`, which Python randomises per process — every run produced different data | Writing the reproducibility test |
| Part re-sourcing wrote back the same supplier | A change event that changed nothing, so SCD2 correctly opened no version — but it would have looked like the loader lost one | Reading the code back |
| 596 phantom odometer rollbacks | Same-day repair orders got independent random check-in times | Auditing the way a SQL rule would, not the way the generator does |
| Median days-in-stock of 269 | 35,000 arrivals against 24,500 new sales — supply exceeded demand and FIFO aged the queue without bound | Measuring the distribution instead of assuming it |
| Negative days-in-stock | A trade-in is recorded on the *delivery* date of the sale that brought it in, so a used car could be resold before it arrived | The same measurement |
| 44% of workshop volume from cars we never sold | The external vehicle pool was unthrottled | Sanity-checking the share |
| MDM comparing a column against itself | Both sides had columns called `match_name`; Spark resolved the ambiguity silently | Reading the code before running it |
| A silent `str.replace` that did nothing | A patch targeted text an earlier patch had already changed, and reported success | Re-measuring the output rather than trusting the patch |

The last one changed how the rest of the build was done: every subsequent edit
asserted that its target existed before replacing it.

---

### 1.6 — What running it for real, on Fabric, found that reading the code never would

On 2026-09-13/14, an Azure F2 capacity was provisioned and the full pipeline —
Bronze notebook, Data Factory pipeline, all four Silver notebooks, and every
Gold DDL/load procedure — was run for real for the first time. 17 genuine
defects surfaced, none of which local testing, code review, or the ADR's own
verification table anticipated. This is the strongest evidence in the project
for the thesis stated everywhere else in this document: an untested claim is
not a fact.

| # | Found | Root cause | Caught by |
|---|---|---|---|
| 1 | `ctl.dq_rule` insert failing | `description` was `VARCHAR(500)`; the longest real rule description is 792 characters | Actually inserting all 25 rules, not just creating the table |
| 2 | Bronze write failing with `SCHEMA_NOT_FOUND` | A schema-enabled Lakehouse needs `CREATE SCHEMA IF NOT EXISTS bronze` before the first write — nothing creates it implicitly | Running the notebook, not just reading it |
| 3 | `latest_by_key` undefined after `%run 00_silver_common` | `tools/build_notebooks.py` left `%run` commented out (`# %run x`) in the compiled `.ipynb` — the `.py` source comments it so the file stays valid Python, but the converter never stripped the `# ` back off | The notebook actually executing and the function being missing |
| 4 | Same again, worse | Four functions in `00_silver_common.py` — `normalise_for_matching`, `latest_by_key`, `convert_to_try`, `merge_into_silver` — were silently absorbed into a preceding markdown cell's text because a `# %%` boundary was missing after the markdown note. They were never real code cells at all | Testing each imported name individually rather than trusting "the notebook ran" |
| 5 | `OPTIMIZE ... ZORDER BY (vin)` failing on `repair_order_line` | The line table has no `vin` column — only the header does. One shared Z-ORDER key was assumed for both | Running the optimize step against the real table, not just the header |
| 6 | `unionByName()` called with many DataFrames at once | It takes exactly one `other` frame — not the SQL-style variadic `UNION ALL` a T-SQL background suggests | More than one rule producing a violation, which zero-rule test runs never exercise |
| 7 | `json.loads` failing on the exported rule set | SQL Server's `FOR JSON PATH` result, copied from the query-grid preview, picked up literal line breaks mid-string | Comparing the copied length against the source row count instead of assuming the copy was clean |
| 8 | 13 of 25 DQ rules erroring in the Spark runner | `ISNULL(a,b)` (2-arg) and `CONVERT(VARCHAR(n),x,style)` are T-SQL-only; Spark's `isnull()` takes one argument and has no `CONVERT` at all — "rules as data, engine-agnostic" was a design goal that had never actually been exercised on both engines | Running the same rule set through the Spark path for the first time |
| 9 | `PLATE_FORMAT`/`PLATE_PROVINCE` still not fully correct after the fix above | They referenced `plate_number`, a column PII masking removes from Silver entirely (only `plate_masked`/`plate_hash` survive); and their `[0-9]`-class `LIKE` patterns are T-SQL syntax Spark's `LIKE` doesn't support (only `%`/`_`) | The same run; the column-name half is fixed, the Spark-dialect half is a documented, accepted limitation |
| 10 | `spark.createDataFrame(results)` failing on a clean run | `error_message` is `None` on every row once no rule errors, and Spark can't infer a type from an all-null column — a *healthier* run broke the code the earlier, buggier run had accidentally exercised | An explicit schema, once results actually looked correct |
| 11 | `spark.read.text("Files/_dq_rules.json")` silently returning 0 rows | The file existed at the right size (confirmed via `notebookutils.fs.ls`) but the Spark reader wouldn't see it; `notebookutils.fs.head()` read it correctly | Checking the file system directly instead of trusting the read path |
| 12 | `IDENTITY(1,1)` rejected twice | `INT IDENTITY` fails outright (Fabric Warehouse IDENTITY is BIGINT-only); `BIGINT IDENTITY(1,1)` *also* fails — no explicit seed/increment allowed, only the bare, implicit form | Actually running the ADR-0002 verification query rather than trusting the "expected to fail" note written when nothing was Fabric-tested |
| 13 | `sys.columns AS a CROSS JOIN sys.columns AS b` (the standard tally-table trick) rejected | System catalog views cannot be joined in Fabric's distributed query engine — a restriction with no equivalent on standalone SQL Server, so nothing local ever surfaced it | `gold.usp_populate_dim_date` failing the moment it ran on real Fabric |
| 14 | The replacement also rejected — twice | `ROW_NUMBER() OVER (ORDER BY (SELECT NULL))` fails the same way even over a plain `VALUES` table; `GENERATE_SERIES` is the form Fabric actually accepts (and needs SQL Server 2022+, which the local test box doesn't have) | Bisecting the exact statement by testing constructs standalone rather than guessing from an opaque `Line 13` error that always pointed at the same line regardless of which statement inside a procedure actually failed |
| 15 | `CREATE TABLE #t` + a separate `INSERT INTO #t SELECT` rejected, unconditionally | Confirmed down to the single simplest possible case — a two-column temp table fed from one other table. `SELECT ... INTO #t` (CTAS-style, creating the table from the query itself) is the only form Fabric accepts. This touched every Gold load/backfill procedure that stages data in a temp table — five files, a dozen sites | The same bisection; this single finding invalidated a T-SQL idiom used throughout the entire Gold layer |
| 16 | Every Gold backfill/load procedure erroring with `Invalid object name 'bronze.X'` / `'silver.X'` | Unqualified two-part names only resolve to objects *inside* the Warehouse's own database. Bronze and Silver physically live in the Lakehouse, so every cross-item reference needs the three-part form `mihenk_lh.bronze.X` / `mihenk_lh.silver.X` — ADR-0002 documented that the boundary needed *testing*, not that every call site already used the right syntax | Running `gold.usp_initial_load` for the first time — 15+ procedures across 5 files failed identically |
| 17 | `usp_backfill_dim_model_trim` erroring with "Error converting data type varchar to numeric" | Backfill reads straight from raw Bronze (Silver only holds current state; SCD2 history has to come from Bronze's snapshots), and Bronze's Turkish comma-decimal money fields (`"1989500,0"`) don't implicitly `CAST` to `DECIMAL` the way Silver's Python-side `parse_decimal(turkish=True)` handles them. Three backfill procedures (model_trim, part, vehicle) had this gap | Real historical Bronze data reaching a numeric column for the first time |
| 18 | `fact_vehicle_sale` and `fact_repair_order` silently doubled on some rows | `gold.dim_transaction_flag`'s `-1` "Bilinmiyor" sentinel was seeded with the *exact same* attribute combination (`0, 'NA', 'NA', 0, 0, 0`) as a genuine real flag row. A natural-key join across six boolean/string columns matched both, fanning out every fact with that combination into two rows — one with a real `transaction_flag_sk`, one with `-1` | Comparing `COUNT(*)` against `COUNT(DISTINCT natural_key)` after the load, rather than trusting "it ran without error" |

**The pattern across all 18:** every one of them is invisible to code review and
invisible to local (non-Fabric) SQL Server testing. Numbers 12–16 in particular
are Fabric Warehouse behaviours — IDENTITY's real constraints, the ban on
joining system catalog views, the ban on `CREATE TABLE #t` + `INSERT`, the need
for fully-qualified cross-item names — that no amount of reading T-SQL
documentation written for standalone SQL Server would have predicted, because
they are specific to Fabric's distributed engine. This is exactly the risk
ADR-0002 named and could only ever describe as "Pending" until a real capacity
existed to test against.

---

## Part 2 — Questions to expect

**"Why is everything in English when the business is Turkish?"**
→ [ADR-0001](adr/0001-naming-and-language-standard.md). Identifiers are English
and ASCII; **data keeps its Turkish characters**. Turkish has a locale-dependent
case mapping — `"İSTANBUL".lower()` differs by locale across Python, T-SQL and
Spark — so any `upper()`/`lower()` normalisation on a Turkish identifier is a
silent correctness bug in three engines. The cost is a permanent translation hop
between stakeholders and the schema, absorbed by the glossary in the naming
standard.

That hazard is not theoretical: Python's `.upper()` turns `"Eğitim"` into
`"EĞITIM"` rather than `"EĞİTİM"`, and that shows up in the generated DMS data as
a third MDM divergence — because it is exactly what legacy Turkish systems do.

---

**"How would you add a seventh source system?"**

Add it to the generator, run `python -m data_generator --clean`, run
`python tools/generate_ctl_seed.py`, apply the regenerated seed file. The
pipeline does not change — it reads `ctl.source_config` and loops. That is the
claim the whole design is built to support and it is testable.

---

**"This is a nightly batch. What about streaming?"**

It should be batch. A dealer network closes at 18:00 and the files arrive
overnight; a streaming architecture would add operational complexity for latency
nobody asked for. The one candidate is the workshop feed — a service manager
would genuinely like to see workshop status during the day — and the honest
answer is that I have no Structured Streaming experience to claim, which is in
the [Spark learning log](spark_learning_log.md).

---

**"What happens when a batch fails halfway?"**

Nothing is lost. Every layer's batch owns its rows and can reclaim them, and the
watermark is advanced only after the load has succeeded *and* been logged. A
crash leaves the old watermark, the next run re-reads the same window, and Bronze
deletes its own batch before appending — so re-reading is harmless.

**Between duplicated work and lost data, always choose duplicated work.**

---

**"Show me something you would do differently."**

Three, in order of how much they bother me:

1. **`dim_customer` has no backfilled history.** Every other Type 2 dimension
   reconstructs its versions from Bronze's 44 snapshots. Customer does not,
   because that would mean re-running the MDM matcher at each historical point,
   and its output would legitimately differ at each. It is a day of work for a
   dimension whose attributes rarely change, and I chose not to spend it — but it
   means customer attribute history before go-live does not exist, and a report
   asking which city somebody lived in during 2023 gets their 2026 city.

2. **The monthly service seasonality is muted** against the configured weights,
   because fleet growth raises the baseline and partially masks it. Realistic,
   but I would rather the model separated the two effects than blended them.

3. **PII masking is applied in Silver, not at ingestion.** Bronze holds clear
   national IDs and phone numbers. That is defensible — Bronze must be replayable
   and masking is a transformation — but in a deployment handling real customer
   data I would want Bronze itself encrypted at rest with tighter access than the
   rest of the Lakehouse, and I have not designed that.

---

**"What has not been tested?"**

As of 2026-09-14, everything has been run for real, at least once, end to end:
Bronze via the Data Factory pipeline (17 sources), all four Silver notebooks,
and the full Gold layer via `gold.usp_initial_load` — on an Azure pay-as-you-go
F2 capacity (the Fabric Trial was refused for this tenant; see
`fabric/setup_steps.md` §0). Every item in ADR-0002's verification table has a
real result and a date, not "Pending". Eighteen genuine defects were found this
way and fixed — see §1.6 above; the honest framing is not "nothing was found"
but "everything found was fixed and is now documented."

What's still thinner than the rest: Power BI's Direct Lake behaviour on a real
report (ADR-0002 item 7) has not been exercised against actual visuals yet, and
the platform has had exactly one real end-to-end run — it has not yet been
re-run a second time to confirm the whole chain is idempotent the way each
individual notebook's own idempotency check is.

**I would rather say this than present untested code as working** — and this
project's whole arc is the same sentence twice: first written when nothing had
run, now written again after nearly everything had, because a claim earns
nothing from being repeated with more confidence, only from being checked again.

---

## Part 3 — Delegated decisions

Decisions made on my behalf during the build, recorded so they can be defended
rather than discovered. Each was a genuine fork.

| # | Decision | Chosen | Why | Cost |
|---|---|---|---|---|
| 1 | DMS file encoding | `windows-1254` | Turkish DMS systems really emit it; one option in Bronze fixes it; it forces `ctl.source_config` to carry an encoding column | If Phase 2 gets it wrong it looks like corruption rather than a config miss |
| 2 | Ownership modelling | Deferred to Phase 4 | Nothing upstream depended on it; deciding with real data beats deciding on paper | Had to be remembered — it was a Phase 4 gate |
| 3 | Data volumes | Full (35k vehicles, 180k orders) | The difference is two minutes of generation; `--scale` covers iteration | 150 MB and slower uploads |
| 4 | How sources expose change | Small tables monthly full snapshot, large tables watermark incremental | Mirrors how real extracts are built and makes `ctl.source_config` exercise **both** load types | The generator has to carry an attribute change history per entity |
| 5 | Package layout | `pyproject.toml` + editable install | Standard; `python -m data_generator` works anywhere | One extra file |
| 6 | RNG streams | Per-module derived sub-seeds | One global seed means adding a module shifts every downstream draw and yesterday's dataset can never be reproduced | A few lines of infrastructure |
| 7 | Dirty data timing | Injected at write time, on a copy, with a ground-truth log | Keeps deliberate defects separable from accidental ones; turns "I wrote DQ rules" into "I measured them" | Extra bookkeeping; the log must stay out of Bronze |
| 8 | Timeline | 2023-01-01 → 2026-08-31 | Three complete years for year-on-year plus a YTD tail; ends before today so no future-dated rows | — |
| 9 | Religious holidays | Hardcoded 2023–2026 | Lunar calendar needs a Hijri library; four years is not worth a dependency | Flagged as approximate in code |
| 10 | Source amounts | Written unconverted, in contract currency | Converting in the generator would delete the reference-data join that makes the FX table worth having | Silver has to get the forward fill right |
| 11 | Arrival scheduling | Split: demand-driven plus closing stock | Aiming all 35,000 at the sales curve pushed median days-in-stock to 269 — a car park, not a dealer network | One more concept in the generator |
| 12 | Trade-in reconditioning | Ten-day floor | Without it a used car could be resold before it arrived, producing negative days-in-stock | — |
| 13 | External vehicle pool | 20% of fleet, 40% tradeable, 45% of the rest serviced | First run put 44% of workshop volume on cars the network never sold | Two throttles to explain |
| 14 | Repair orders | Two passes: mileage-driven maintenance, then unscheduled to hit the target | A flat per-vehicle rate would hit the total but lose the cadence that makes service intervals mean anything | More complex than one pass |
| 15 | Stage timing | Shop time, not wall clock | Adding eight hours to a Friday afternoon must land on Monday. Verified: zero weekend check-ins across 180,070 orders | — |
| 16 | Unfinished orders | 1,090 left mid-process on purpose | An accumulating snapshot where every row is complete demonstrates nothing | — |
| 17 | Repair order header totals | Redundant with the line sum, deliberately | Gives Phase 3 a reconciliation with a knowable answer. Verified zero mismatches before injection | The redundancy can drift if a load is wrong — which is the point |
| 18 | Warranty weighting | 1.25× rather than 2.4× | At 2.4× warranty reached 21% of all repair orders — a fifth of workshop capacity on manufacturer-funded repair | — |
| 19 | Documentation | Generated from the DDL and the code | A hand-written dictionary is wrong within a month | The generator is another thing to maintain; 20% of columns still have no description and the tool says so |

---

## Part 4 — The ten-minute demo

Ordered so that if it is cut short, the most interesting thing has already been
shown.

**0:00 — The problem, not the architecture.** One sentence: a distributor sells
cars through 40 dealers, services them, and buys parts — and cannot answer "which
customers do we have" because the same person is in DMS and CRM twice.

**1:00 — Show a hard MDM pair.** From the generator output:

```
DMS  'Y. DURAN'                       CRM  'Yesil Duran'                       id_no=None
DMS  'YILMAZ NAKLIYAT A.Ş.'           CRM  'Yilmaz Nakliyat San. Ve Tic. A.S.'
```

59% of matchable pairs have no national ID in CRM. Then show `_mdm_truth.csv` —
"and here is how I know whether I got them right."

**3:00 — The aftersales cycle-time split.** The stacked bar: median cycle 73
hours, p90 196, and almost all of the spread is parts waiting rather than work.
"Total cycle time would have hidden that. This is why the fact is an
accumulating snapshot."

**5:00 — The data quality page.** Rule table, `Errored Rule Count` card. Then:
"the rule codes are imported from the module that injects the defects — if they
drift, the build fails." Show the guard failing.

**6:30 — The VIN check digit.** One rule, four lines of SQL, backed by the ISO
tables as reference data. "This is the difference between a data quality check
and understanding the domain."

**8:00 — What running it for real actually found.** Not the architecture
diagram — the list of 18 things that only broke once real Fabric, real data,
and a real run existed to break them on: a sentinel dimension row seeded with
the same attributes as a real one, silently doubling two fact tables; a
notebook's own build step commenting out the `%run` that was supposed to load
its shared functions; Fabric Warehouse refusing `INSERT INTO #t` outright and
accepting only `SELECT ... INTO #t`. "Every one of these is invisible to code
review. That's the argument for running it, not just writing it."

**9:00 — The one thing to remember.** The generator's output is *provably clean*
before injection, so every defect the platform finds is one that was put there on
purpose and can be scored against an answer key. That is what makes any number in
this project mean something.
