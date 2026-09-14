# Architecture Decision Records

An ADR captures one decision: what forced it, what the alternatives were, what
was chosen, and what price that choice carries. It is written **when the
decision is still open**, not afterwards — a record written after the fact is a
justification, and it reads like one.

## Rules

1. One decision per record. If a record needs the word "also", it is two ADRs.
2. Numbers are sequential and never reused, even for rejected or superseded
   records.
3. An ADR is never edited to change its decision. It is superseded by a new one,
   and its status is updated to point there. The history of what we believed at
   the time is the whole value of the file.
4. Every ADR has a non-empty "what this makes harder" section.
5. Anything resting on unverified Microsoft Fabric behaviour goes in the
   Verification table with a status, and stays `Pending` until it is actually
   tested in the tenant.

## Index

| # | Title | Status | Phase |
|---|---|---|---|
| [0001](0001-naming-and-language-standard.md) | English identifiers with Turkish data content | Accepted | 0 |
| [0002](0002-hybrid-spark-and-tsql-architecture.md) | Silver in PySpark, Gold in T-SQL | Accepted | 0 |
| [0003](0003-vehicle-ownership-modelling.md) | Vehicle ownership as SCD2 on dim_vehicle, not a bridge | Accepted | 4 |

Template: [`0000-template.md`](0000-template.md)
