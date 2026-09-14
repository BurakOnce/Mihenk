# Spark Learning Log

I came into this project knowing SQL well and Spark not at all. Fabric Lakehouse
notebooks are PySpark, so learning it was one of the stated goals of the build
rather than a side effect.

This file is the honest record of that.

---

## The state of it, plainly

**The Spark in this repository is written but has not been run.**

No Fabric capacity was available: the Fabric trial requires a managed work or
school account, and the tenant available to me — an auto-provisioned one created
by signing up to Power BI with a personal address — was refused. The paid F-SKU
route was left for later.

So every claim below is "I wrote this and can explain why", not "I ran this and
watched it work". Those are different things and this file will not blur them.
When the notebooks do run, this file gets updated with what actually happened —
including whatever turns out to be wrong, because that is the interesting part.

What that means concretely:

| | |
|---|---|
| **Can explain** | why each option is set, what each function does, what the SQL equivalent is, what the failure mode is if it is wrong |
| **Cannot claim** | that it executed, that the performance is acceptable, that a Fabric-specific behaviour matches the documentation |

Two Spark-adjacent things *were* verified, locally in plain Python, because they
could be:

- the ISO 3779 check-digit algorithm the Silver notebook implements — checked
  against five published reference VINs, 5,000 generated ones with zero
  mismatches, and 2,000 deliberately corrupted ones detected at 100%;
- the `translate()`-based transliteration approach itself, which is the part of
  that implementation that is Spark-specific in shape.

---

## Status

| # | Concept | Status |
|---|---|---|
| 1 | `spark.read` / `df.write.format("delta")` | Written, not run |
| 2 | `spark.sql()` | Written, not run |
| 3 | `select`, `withColumn`, `filter`, `join`, `groupBy` | Written, not run |
| 4 | Window functions — `row_number()` for deduplication | Written, not run |
| 5 | `DeltaTable.merge()` — idempotent upsert | Written, not run |
| 6 | Partitioning and `OPTIMIZE` | Written, not run — conceptual by design |

---

## 1. Reading and writing — `spark.read` / `df.write.format("delta")`

**What it does:** `spark.read.format(...).option(...).load(path)` returns a
DataFrame. `df.write.format("delta").mode("append").saveAsTable(name)` writes it.

**Where I used it:** `01_bronze_ingest` — all four readers (CSV, JSON, JSON
Lines, and Excel via pandas because Spark cannot read xlsx).

**SQL equivalent:** `SELECT * FROM OPENROWSET(...)` for the read; `INSERT INTO`
for the write. `mode("overwrite")` is `TRUNCATE` then `INSERT`.

**What I had to think about:**

- `inferSchema` off. Everything lands as string. Letting Spark guess means a
  column silently changes type when next month's file happens to look different.
  Typing is Silver's job, where it is explicit.
- `encoding` from the config. The DMS feed is `windows-1254`, and reading it as
  UTF-8 turns every Turkish character into a replacement glyph **with no error
  raised**. I verified this at the byte level locally: the file genuinely fails
  a UTF-8 decode.
- `multiline` for JSON. Spark's default JSON reader expects one object per line.
  The CRM export is a single array across many lines and without
  `.option("multiline", "true")` Spark reports a handful of corrupt records and
  nothing worth noticing.
- `mode("PERMISSIVE")` stated explicitly rather than left as the default,
  because `DROPMALFORMED` would lose rows without telling anyone.

**Still don't know:** how Spark behaves reading 918 date-partitioned folders in
one `load()` call versus enumerating them — I wrote the enumeration because the
folder name *is* the watermark, but I have not compared them.

---

## 2. `spark.sql()`

**What it does:** runs SQL against registered tables and returns a DataFrame.
The bridge from what I already know.

**Where I used it:** the FX forward fill in `00_silver_common`, the quarantine
aggregation in `40_silver_dq`, the DQ rules themselves (which are stored as SQL
text and executed here), and every `DELETE FROM ... WHERE _batch_id = ...`.

**SQL equivalent:** it *is* SQL.

**What I had to think about:** the FX forward fill is a non-equi join with a
`LEAD` to find where each rate stops applying. As a chain of DataFrame calls it
is unreadable; as SQL it is eight lines anyone can check. That is the rule I
settled on — **if the SQL reads better, write the SQL**, and most set-based
logic does.

The exceptions where the DataFrame API genuinely wins: anything applied
programmatically over a list of columns (the audit stamping loops over
`business_columns`), and array handling.

---

## 3. DataFrame transformations

**What it does:** `select`, `withColumn`, `filter`, `join`, `groupBy` — the same
operations as SQL, as method calls.

**Where I used it:** throughout the Silver notebooks.

**SQL equivalent:**

| DataFrame | SQL |
|---|---|
| `df.select(a, b)` | `SELECT a, b` |
| `df.withColumn("x", expr)` | `SELECT *, expr AS x` |
| `df.filter(cond)` | `WHERE cond` |
| `df.join(other, on="k", how="left")` | `LEFT JOIN other ON ...` |
| `df.groupBy("k").agg(F.sum("v"))` | `GROUP BY k` with `SUM(v)` |
| `df.dropDuplicates([...])` | `SELECT DISTINCT` on those columns |

**What caught me out:** `withColumn` returns a *new* DataFrame; it does not
mutate. Obvious once stated, and the source of a real bug I made — I wrote
`contracts["customer_id"] == xref["dms_customer_id"]` as a join condition inside
a chain that had already reassigned `contracts`, so the reference pointed at a
pre-join version. Spark resolves that by lineage and it usually works, right up
until an intermediate step makes it ambiguous.

The second bug was worse and more instructive: after joining the DMS and CRM
customer frames, both sides had columns called `match_name` and `identity_hash`.
Spark resolves the ambiguity **silently**, and the scoring was comparing a
column against itself and finding everything equal. Prefixing every derived
column on both sides removed the entire class of problem.

**Lazy evaluation:** nothing runs until an action — `.count()`, `.show()`,
`.write`. A cell returning instantly means nothing happened yet.

---

## 4. Window functions — `row_number()`

**What it does:** ranks rows within a partition. The tool for "keep the latest
row per key".

**Where I used it:** `latest_by_key` in `00_silver_common`, which every Silver
entity uses to collapse 44 monthly snapshots into one current row. Also the
mutual-best-match resolution in the MDM notebook.

**SQL equivalent:** exact.

```python
Window.partitionBy("dealer_code").orderBy(F.col("last_modified_ts").desc())
```
```sql
OVER (PARTITION BY dealer_code ORDER BY last_modified_ts DESC)
```

**What I had to think about:** the tie-breaker. Two rows with the same key and
the same timestamp get resolved arbitrarily, and *arbitrarily* means differently
on different runs — which would make the whole platform non-reproducible.
`_ingest_ts` then `_row_hash` as secondary sorts makes it deterministic.

This is the concept I was most comfortable with going in, because the SQL is
identical. Learning it in Spark was learning the syntax, not the idea.

---

## 5. `DeltaTable.merge()`

**What it does:** `MERGE INTO`. Upsert on a key, with conditions per branch.

**Where I used it:** `merge_into_silver` in `00_silver_common`, used by every
Silver table.

**SQL equivalent:**

```python
target.alias("t").merge(source.alias("s"), "t.key = s.key") \
    .whenMatchedUpdateAll(condition="t._row_hash <> s._row_hash") \
    .whenNotMatchedInsertAll().execute()
```
```sql
MERGE INTO target t USING source s ON t.key = s.key
WHEN MATCHED AND t._row_hash <> s._row_hash THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

**What I had to think about:** the `_row_hash` condition is what makes the
operation *idempotent* rather than merely repeatable. Without it every matched
row is rewritten on every run — correct but wasteful, and it makes the Delta
history useless because every version touches every row. With it, a second run
writes nothing at all.

**The finding I did not expect.** I wrote the Gold SCD Type 2 load twice, with
and without MERGE, because whether Fabric Warehouse supports it was an open
question. Doing that showed that **MERGE is not load-bearing for SCD Type 2**: a
changed entity needs the old version closed *and* a new one opened, MERGE takes
at most one action per matched row, so the insert is a separate statement either
way — which leaves MERGE doing only the close, which a plain `UPDATE ... WHERE
EXISTS` does equally well.

MERGE *is* load-bearing for an upsert, which is a different operation and is
what Silver uses it for. Being able to say which is which is worth more than
being able to write either.

**Still don't know:** how `DeltaTable.merge()` performs on the 626,000-row
repair order line table, or whether the Delta history grows in a way that needs
`VACUUM` scheduling.

---

## 6. Partitioning and `OPTIMIZE`

**What it does:** `OPTIMIZE` compacts many small files into fewer large ones.
`ZORDER BY` co-locates rows sharing a value so a filtered query can skip files.

**Where I used it:** `10_silver_master` runs
`OPTIMIZE bronze.workshop_repair_order_line ZORDER BY (vin)`.

**SQL equivalent:** no direct one. The nearest relational analogue is a
clustered index rebuild, and the analogy is loose enough to be misleading.

**Why it is there:** the workshop feed arrives as 1,836 files averaging under
60 KB, because a real daily drop looks like that. Spark spends more time opening
files than reading them — the **small-file problem**. It is the one performance
characteristic of a lakehouse that has no equivalent in a relational warehouse,
which is why it is worth knowing even at a conceptual level.

**What I decided NOT to do, and why.** I did not partition
`silver.repair_order`. The obvious move is to partition by check-in year, but
180,000 rows across four years is 45,000 rows per partition — far below the
point where partition pruning pays for itself. Delta already keeps per-file
min/max statistics and skips files on a date filter without any partitioning,
and the directory overhead would recreate the small-file problem `OPTIMIZE` just
solved. It becomes the right call at perhaps fifty times this volume.

Being able to say *when* partitioning starts paying is more useful than
partitioning by reflex and calling it tuning.

**Still don't know:** what file size `OPTIMIZE` actually targets in Fabric,
whether auto-compaction is on by default, and how `VACUUM` retention interacts
with time travel.

---

## What I still do not understand

Kept deliberately. A list of known gaps is worth more than a list of claimed
skills, and "I have not needed it yet, here is what I would read first" is a
better answer than a bluff.

- **Partitioning strategy at scale.** I can explain why not to partition this
  dataset. I could not confidently choose a partition column for a 500-million
  row table.
- **The Spark UI.** I have never read a query plan or a stage breakdown. If a
  notebook were slow I would currently guess rather than diagnose, and that is
  the first thing I would fix with real capacity.
- **Shuffles and skew.** I know a wide transformation causes a shuffle and that
  skewed keys cause stragglers. I have not seen either happen or tuned for them.
- **Broadcast joins.** I know the small-table-broadcast idea and that Spark
  usually decides automatically. I have not had to override it.
- **Structured Streaming.** Not touched at all. Everything here is batch, which
  is right for a nightly dealer feed, but it means I have no streaming
  experience to claim.
- **Delta time travel and `VACUUM`.** I understand the concept and that
  retention interacts with it. I have not used either.

---

## What learning it changed about how I write

The thing I did not expect: **most of Silver reads better as SQL than as
DataFrame chains**, and knowing that is itself the useful outcome. I went in
assuming "learning Spark" meant learning to write everything in the DataFrame
API. It turned out to mean learning where each one belongs.

The DataFrame API earns its place for anything applied programmatically over a
list of columns, for array and struct handling, and for anything that has to be
driven by a specification rather than written out. Everything else — joins,
aggregations, window functions, filters — is clearer as SQL, and `spark.sql()`
makes that a free choice rather than a compromise.
