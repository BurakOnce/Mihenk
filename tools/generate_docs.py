"""generate the data dictionary and the lineage diagram from the code itself"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = REPO_ROOT / "sql"
NOTEBOOK_DIR = REPO_ROOT / "fabric" / "notebooks"
MANIFEST = REPO_ROOT / "data" / "_manifest.json"
OUT_DICTIONARY = REPO_ROOT / "docs" / "data_dictionary.md"
OUT_LINEAGE = REPO_ROOT / "docs" / "lineage.md"

REPORT_PAGES = {
    "Sales": ["gold.fact_vehicle_sale", "gold.agg_monthly_dealer_model_sale",
              "gold.agg_monthly_dealer_target", "gold.fact_vehicle_inventory_daily"],
    "Aftersales": ["gold.fact_repair_order", "gold.fact_repair_order_line",
                   "gold.agg_monthly_service_summary"],
    "Warranty and recall": ["gold.fact_recall_coverage", "gold.fact_repair_order"],
    "Procurement": ["gold.fact_part_purchase"],
    "Data quality": ["gold.fact_data_quality"],
}

LAYER_ORDER = ["ctl", "bronze", "silver", "gold"]

CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?P<schema>\w+)\.(?P<table>\w+)\s*\((?P<body>.*?)\n\)\s*;",
    re.S | re.I,
)

COLUMN_LINE = re.compile(
    r"^\s{4}(?P<name>[A-Za-z_][\w]*)\s+"
    r"(?P<type>[A-Za-z0-9_]+(?:\s*\(\s*[\d,\s]+\s*\))?)"
    r"(?P<nullability>\s+NOT\s+NULL|\s+NULL)?\s*,?\s*"
    r"(?:--\s*(?P<comment>.*))?$",
    re.I,
)

SUFFIX_MEANINGS = [
    ("_sk", "Surrogate key. Unique per dimension VERSION, not per entity."),
    ("_id", "Natural key from a source system."),
    ("_no", "Human-facing document number. Degenerate dimension on a fact."),
    ("_code", "Short coded value."),
    ("_date_key", "Foreign key to gold.dim_date, YYYYMMDD. -1 when unknown."),
    ("_date", "Calendar date, no time part."),
    ("_ts", "Point in time."),
    ("_amount", "Monetary value in Turkish Lira, converted in Silver."),
    ("_quantity", "Countable amount."),
    ("_hours", "Duration in hours. Null means the stage has not happened."),
    ("_days", "Duration in whole days."),
    ("_rate", "Ratio stored as 0-1, not 0-100."),
    ("_count", "Row or event count."),
    ("_hash", "Salted SHA-256. For joining and counting, never for reading."),
    ("_masked", "Partially redacted for human display."),
    ("_name", "Display name."),
]
TECHNICAL_COLUMNS = {
    "valid_from": "Inclusive start of this version's validity.",
    "valid_to": "Exclusive end. The open version uses 9999-12-31.",
    "is_current": "1 for the open version. Redundant with valid_to on purpose - see naming_standard.md §6.",
    "is_inferred": "1 when this member was created because a fact referenced it before the dimension had seen it.",
    "_row_hash": "Hash of the tracked attributes. A change here is what opens a new version.",
    "_batch_id": "The run that wrote this row. Deleting by it is what makes a reload idempotent.",
    "_loaded_ts": "When this row was written.",
    "_ingest_ts": "When this row landed in Bronze.",
    "_silver_ts": "When this row was cleansed.",
    "_source_system": "Which source system produced it.",
    "_source_file": "Full path of the file it came from.",
}

def _is_section_divider(text: str) -> bool:
    """`--- measures ---` groups columns; it does not describe one"""
    stripped = text.strip("- ").strip()
    return not stripped or set(text.strip()) <= {"-", " "} or (
        text.strip().startswith("---") and text.strip().endswith("---")
    )

def _derive_description(column_name: str) -> str:
    """fall back to the naming standard when there is no inline comment"""
    if column_name in TECHNICAL_COLUMNS:
        return TECHNICAL_COLUMNS[column_name]
    for suffix, meaning in SUFFIX_MEANINGS:
        if column_name.endswith(suffix):
            return meaning
    if column_name.startswith("is_") or column_name.startswith("has_"):
        return "Boolean flag."
    return ""

def parse_tables() -> dict[str, dict]:
    """every create table in sql/, with its columns and inline comments"""
    tables: dict[str, dict] = {}

    for path in sorted(SQL_DIR.rglob("*.sql")):
        text = path.read_text(encoding="utf-8")

        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

        for match in CREATE_TABLE.finditer(text):
            schema, table = match.group("schema"), match.group("table")
            if table.startswith("#"):
                continue
            full = f"{schema}.{table}"

            columns = []

            pending: list[str] = []
            for line in match.group("body").splitlines():
                stripped = line.strip()
                if stripped.startswith("--"):
                    text_only = stripped.lstrip("-").strip()

                    if _is_section_divider(text_only):
                        pending.clear()
                        continue
                    pending.append(text_only)
                    continue
                col = COLUMN_LINE.match(line)
                if not col:
                    if not stripped:
                        pending.clear()
                    continue
                comment = (col.group("comment") or "").strip()
                if _is_section_divider(comment):
                    comment = ""
                if pending and not comment:
                    comment = " ".join(pending)
                if not comment:

                    derived = _derive_description(col.group("name"))
                    if derived:
                        comment = f"_{derived}_"
                columns.append(
                    {
                        "name": col.group("name"),
                        "type": re.sub(r"\s+", "", col.group("type")).upper(),
                        "nullable": "NOT NULL" not in (col.group("nullability") or "").upper(),
                        "comment": comment.strip(),
                    }
                )
                pending.clear()

            if columns:
                tables[full] = {
                    "schema": schema,
                    "table": table,
                    "columns": columns,
                    "defined_in": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
                }

    return tables

SPARK_READ = re.compile(r'spark\.table\(\s*["\']([\w.]+)["\']')
SPARK_WRITE = re.compile(r'(?:merge_into_silver\(\s*\w+\s*,\s*|saveAsTable\(\s*)["\']([\w.]+)["\']')

SQL_READ = re.compile(r"\bFROM\s+((?:silver|bronze|ctl|gold)\.\w+)", re.I)
SQL_JOIN = re.compile(r"\bJOIN\s+((?:silver|bronze|ctl|gold)\.\w+)", re.I)
SQL_WRITE = re.compile(r"\bINSERT\s+INTO\s+(gold\.\w+)", re.I)

def parse_lineage() -> dict:
    """read what each layer actually reads and writes"""
    edges: set[tuple[str, str]] = set()
    sources: dict[str, dict] = {}

    if MANIFEST.exists():
        for entry in json.loads(MANIFEST.read_text(encoding="utf-8")):
            node = f"{entry['source_system']}:{entry['entity']}"
            sources[node] = entry
            edges.add((node, entry["target_table"]))

    for path in sorted(NOTEBOOK_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        reads = {t for t in SPARK_READ.findall(text) if t.startswith(("bronze.", "silver."))}
        writes = {t for t in SPARK_WRITE.findall(text) if t.startswith("silver.")}
        for target in writes:
            for source in reads:
                if source != target:
                    edges.add((source, target))

    for path in sorted((SQL_DIR / "03_gold").glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

        for block in re.split(r"\bCREATE\s+PROCEDURE\b", text, flags=re.I)[1:]:
            reads = set(SQL_READ.findall(block)) | set(SQL_JOIN.findall(block))
            writes = set(SQL_WRITE.findall(block))
            for target in writes:
                for source in reads:
                    edges.add((source.lower(), target.lower()))

    for page, tables in REPORT_PAGES.items():
        for table in tables:
            edges.add((table, f"report:{page}"))

    return {"edges": sorted(edges), "sources": sources}

def render_dictionary(tables: dict[str, dict], sources: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    source_by_target = {
        entry["target_table"]: entry for entry in sources.values()
    }

    out = [
        "# Data dictionary",
        "",
        "**GENERATED FILE — do not edit by hand.**",
        "",
        "Produced by `tools/generate_docs.py`, parsed from the `CREATE TABLE`",
        "statements in `sql/` and the source metadata in `data/_manifest.json`.",
        "Column descriptions come from two places, and the difference is visible:",
        "",
        "- **plain text** is an inline comment written in the DDL — somebody",
        "  explained that column deliberately;",
        "- **_italic text_** is derived from the column suffix contract in",
        "  [`naming_standard.md`](naming_standard.md) §5. A column called",
        "  `net_sale_amount` is a monetary value in lira because the standard says",
        "  every `_amount` is, and repeating that four hundred times by hand would",
        "  guarantee that some of them eventually said something different.",
        "",
        "A column with neither is a genuine documentation gap and shows as blank,",
        "which is a visible problem rather than a silent one.",
        "",
        f"Generated: {now}",
        "",
        f"**{len(tables)} tables** across {len({t['schema'] for t in tables.values()})} schemas.",
        "",
        "---",
        "",
        "## Contents",
        "",
    ]

    by_schema: dict[str, list[str]] = defaultdict(list)
    for name, table in tables.items():
        by_schema[table["schema"]].append(name)

    for schema in sorted(by_schema, key=lambda s: (LAYER_ORDER.index(s) if s in LAYER_ORDER else 99, s)):
        out.append(f"- **`{schema}`** — {len(by_schema[schema])} tables")
        for name in sorted(by_schema[schema]):
            anchor = name.replace(".", "").replace("_", "")
            out.append(f"  - [`{name}`](#{anchor})")
    out.append("")
    out.append("---")
    out.append("")

    for schema in sorted(by_schema, key=lambda s: (LAYER_ORDER.index(s) if s in LAYER_ORDER else 99, s)):
        out.append(f"## Schema `{schema}`")
        out.append("")
        for name in sorted(by_schema[schema]):
            table = tables[name]
            out.append(f"### {name}")
            out.append("")
            out.append(f"Defined in `{table['defined_in']}`")

            origin = source_by_target.get(name)
            if origin:
                out.append("")
                out.append(
                    f"Loaded from **{origin['source_system']}** "
                    f"`{origin['file_pattern']}` "
                    f"({origin['file_format']}, {origin['encoding']}, "
                    f"{origin['load_type']}"
                    + (f", watermark `{origin['watermark_column']}`"
                       if origin['watermark_column'] else "")
                    + ")"
                )
                out.append("")
                out.append(f"Business key: `{', '.join(origin['key_columns'])}`")

            out.append("")
            out.append("| Column | Type | Null | Description |")
            out.append("|---|---|---|---|")
            for column in table["columns"]:
                comment = column["comment"].replace("|", "\\|")
                out.append(
                    f"| `{column['name']}` | `{column['type']}` | "
                    f"{'yes' if column['nullable'] else 'no'} | {comment} |"
                )
            out.append("")
        out.append("---")
        out.append("")

    return "\n".join(out)

def render_lineage(lineage: dict, tables: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    edges = lineage["edges"]
    sources = lineage["sources"]

    def node_id(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "_", name)

    def label(name: str) -> str:
        if name.startswith("report:"):
            return name.split(":", 1)[1]
        if ":" in name:
            system, entity = name.split(":", 1)
            entry = sources.get(name, {})
            return f"{system}<br/>{entity}<br/><i>{entry.get('file_format', '')}</i>"
        return name.split(".", 1)[1]

    nodes = sorted({n for edge in edges for n in edge})
    groups = {
        "SRC": [n for n in nodes if ":" in n and not n.startswith("report:")],
        "BRZ": [n for n in nodes if n.startswith("bronze.")],
        "SLV": [n for n in nodes if n.startswith("silver.")],
        "CTL": [n for n in nodes if n.startswith("ctl.")],
        "GLD": [n for n in nodes if n.startswith("gold.")],
        "RPT": [n for n in nodes if n.startswith("report:")],
    }
    titles = {
        "SRC": "Source systems",
        "BRZ": "Bronze — Lakehouse Delta",
        "SLV": "Silver — Lakehouse Delta",
        "CTL": "Control — Warehouse",
        "GLD": "Gold — Warehouse star schema",
        "RPT": "Power BI",
    }

    out = [
        "# Lineage",
        "",
        "**GENERATED FILE — do not edit by hand.**",
        "",
        "Produced by `tools/generate_docs.py`. The edges are derived from what the",
        "code actually reads and writes, not from a diagram someone drew:",
        "",
        "| Hop | Derived from |",
        "|---|---|",
        "| source file → Bronze | `data/_manifest.json`, written by the generator |",
        "| Bronze → Silver | `spark.table(...)` and `merge_into_silver(...)` calls in the Silver notebooks |",
        "| Silver → Gold | `FROM silver.*` and `INSERT INTO gold.*` in the Gold load procedures |",
        "| Gold → report page | **declared by hand** in `tools/generate_docs.py` — a .pbix carries no machine-readable link back to its tables |",
        "",
        "So the first three hops cannot claim a dependency the code does not have,",
        "or miss one it does. The fourth can, and is flagged here rather than",
        "presented as if it were extracted.",
        "",
        f"Generated: {now}",
        "",
        f"**{len(nodes)} nodes, {len(edges)} edges.**",
        "",
        "---",
        "",
        "## Full lineage",
        "",
        "```mermaid",
        "flowchart LR",
    ]

    for group, members in groups.items():
        if not members:
            continue
        out.append(f'    subgraph {group}["{titles[group]}"]')
        out.append("        direction TB")
        for node in members:
            shape = "([{}])" if group in ("SRC", "RPT") else "[{}]"
            out.append(f'        {node_id(node)}{shape.format(chr(34) + label(node) + chr(34))}')
        out.append("    end")

    for source, target in edges:
        out.append(f"    {node_id(source)} --> {node_id(target)}")

    out += [
        "```",
        "",
        "---",
        "",
        "## Where each Gold table comes from",
        "",
        "| Gold table | Reads from |",
        "|---|---|",
    ]

    upstream: dict[str, list[str]] = defaultdict(list)
    for source, target in edges:
        upstream[target].append(source)

    for table in sorted(n for n in nodes if n.startswith("gold.")):
        parents = sorted(set(upstream.get(table, [])))
        out.append(f"| `{table}` | {', '.join(f'`{p}`' for p in parents) or '—'} |")

    out += [
        "",
        "---",
        "",
        "## Impact analysis — what breaks if a source changes",
        "",
        "Read downwards: change the source on the left and everything to the right",
        "of it needs re-testing.",
        "",
        "| Source | Bronze | Silver | Gold |",
        "|---|---|---|---|",
    ]

    def descendants(node: str, prefix: str) -> set[str]:
        seen, stack = set(), [node]
        while stack:
            current = stack.pop()
            for source, target in edges:
                if source == current and target not in seen:
                    seen.add(target)
                    stack.append(target)
        return {n for n in seen if n.startswith(prefix)}

    for source in sorted(groups["SRC"]):
        out.append(
            f"| `{source}` "
            f"| {', '.join(sorted(f'`{n}`' for n in descendants(source, 'bronze.'))) or '—'} "
            f"| {', '.join(sorted(f'`{n}`' for n in descendants(source, 'silver.'))) or '—'} "
            f"| {', '.join(sorted(f'`{n}`' for n in descendants(source, 'gold.'))) or '—'} |"
        )

    out.append("")
    return "\n".join(out)

def main() -> int:
    tables = parse_tables()
    lineage = parse_lineage()

    OUT_DICTIONARY.parent.mkdir(parents=True, exist_ok=True)
    OUT_DICTIONARY.write_text(
        render_dictionary(tables, lineage["sources"]), encoding="utf-8"
    )
    print(f"wrote {OUT_DICTIONARY.relative_to(REPO_ROOT)}  "
          f"({len(tables)} tables, "
          f"{sum(len(t['columns']) for t in tables.values())} columns)")

    OUT_LINEAGE.write_text(render_lineage(lineage, tables), encoding="utf-8")
    print(f"wrote {OUT_LINEAGE.relative_to(REPO_ROOT)}  "
          f"({len(lineage['edges'])} edges)")

    all_columns = [c for t in tables.values() for c in t["columns"]]
    total = len(all_columns)
    written = sum(1 for c in all_columns if c["comment"] and not c["comment"].startswith("_"))
    derived = sum(1 for c in all_columns if c["comment"].startswith("_"))
    missing = [
        f"{name}.{c['name']}"
        for name, table in tables.items()
        for c in table["columns"]
        if not c["comment"]
    ]

    print(f"\ncolumn descriptions: {total} columns")
    print(f"  written by hand in the DDL : {written:>4}  ({written / total:.0%})")
    print(f"  derived from the standard  : {derived:>4}  ({derived / total:.0%})")
    print(f"  no description at all      : {len(missing):>4}  ({len(missing) / total:.0%})")
    if missing:
        print("  columns still needing one:")
        for name in missing[:8]:
            print(f"    {name}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
