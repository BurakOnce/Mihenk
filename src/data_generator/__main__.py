"""command line entry point: generate the whole dataset"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path

from . import reference as ref
from .config import Settings
from .customers import generate_customers
from .dirty import inject_defects
from .finance import generate_finance
from .master import generate_master_data
from .parts_supply import generate_part_purchases
from .portal import generate_portal
from .rng import stream
from .sales import generate_sales
from .sources import write_all
from .vehicles import generate_fleet
from .workshop import generate_workshop
from .writers import SourceWriter

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m data_generator",
        description="Generate the MIHENK source-system dataset.",
    )
    parser.add_argument(
        "--scale", type=float, default=1.0,
        help="multiply every volume (default 1.0; try 0.05 while developing)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="override MIHENK_SEED; the same seed always produces the same dataset",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="override MIHENK_OUTPUT_PATH",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="delete the contents of the output folder before writing",
    )
    return parser.parse_args(argv)

class _Timer:
    """prints each stage as it finishes, with a running total"""

    def __init__(self) -> None:
        self.start = time.perf_counter()
        self.marks: list[tuple[str, float]] = []

    def mark(self, label: str) -> None:
        elapsed = time.perf_counter() - self.start
        previous = self.marks[-1][1] if self.marks else 0.0
        self.marks.append((label, elapsed))
        print(f"  {label:<26} {elapsed - previous:>6.1f}s   (total {elapsed:>6.1f}s)")

def _prepare_output(path: Path, clean: bool) -> None:
    """make sure we are not writing a new dataset on top of an old one"""
    path.mkdir(parents=True, exist_ok=True)
    existing = [entry for entry in path.iterdir() if entry.name != ".gitkeep"]
    if not existing:
        return

    if not clean:
        print(
            f"\nERROR: {path} already contains {len(existing)} entries.\n"
            "Generating on top of a previous run would leave stale files that\n"
            "no longer match _manifest.json. Re-run with --clean to replace it,\n"
            "or point --output somewhere else.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    print(f"  removing {len(existing)} existing entries from {path}")
    for entry in existing:
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    settings = Settings.from_env(scale=args.scale)

    overrides: dict = {}
    if args.seed is not None:
        overrides["seed"] = args.seed
    if args.output is not None:
        overrides["output_path"] = args.output.resolve()
    if overrides:
        settings = replace(settings, **overrides)

    print(settings.describe())
    _prepare_output(settings.output_path, args.clean)

    timer = _Timer()
    print("generating:")

    master = generate_master_data(settings)
    timer.mark("master data")

    customers = generate_customers(settings)
    timer.mark("customers (DMS + CRM)")

    fleet = generate_fleet(settings, master)
    timer.mark("vehicle fleet")

    fx_series = ref.build_fx_series(
        stream(settings.seed, "fx"),
        settings.timeline.start,
        settings.timeline.end,
        settings.economics.usd_try_anchors,
        settings.economics.eur_try_anchors,
    )
    fx = ref.FxLookup(fx_series)
    timer.mark("fx series")

    sales = generate_sales(settings, master, customers, fleet, fx)
    timer.mark("sales contracts")

    workshop = generate_workshop(settings, master, customers, fleet)
    timer.mark("repair orders")

    parts = generate_part_purchases(settings, master, workshop, fx)
    timer.mark("part purchases")

    portal = generate_portal(settings, master, fleet, workshop)
    timer.mark("warranty + recalls")

    finance = generate_finance(
        settings, master, sales.contracts, workshop.repair_orders, fx_series, fx
    )
    timer.mark("finance")

    injection = inject_defects(
        settings, master, fleet,
        contracts=sales.contracts,
        repair_orders=workshop.repair_orders,
        repair_order_lines=workshop.lines,
        purchase_lines=parts.purchase_lines,
    )
    timer.mark("defect injection")

    writer = SourceWriter(settings.output_path)
    write_all(
        settings, writer,
        master=master, customers=customers, fleet=fleet, sales=sales,
        workshop=workshop, parts=parts, portal=portal, finance=finance,
        injection_log=injection.log,
    )
    timer.mark("writing files")

    print("\n" + writer.summary())
    _print_simulation_summary(sales, workshop, parts, portal, finance, injection)

    print(f"\noutput   : {settings.output_path}")
    print(f"manifest : {settings.output_path / '_manifest.json'}  "
          f"(seed rows for ctl.source_config)")
    print(f"answer keys (never ingest these):")
    print(f"  {settings.output_path / '_injection_log.csv'}")
    print(f"  {settings.output_path / '_mdm_truth.csv'}")
    return 0

def _print_simulation_summary(sales, workshop, parts, portal, finance, injection) -> None:
    print("\nsimulation")
    print("-" * 74)
    for label, stats in (
        ("sales", sales.stats),
        ("workshop", workshop.stats),
        ("procurement", parts.stats),
        ("portal", portal.stats),
        ("finance", finance.stats),
    ):
        print(f"  {label}:")
        for key, value in stats.items():
            formatted = f"{value:,}" if isinstance(value, int) else value
            print(f"    {key:<26} {formatted}")

    print(f"  injected defects: {injection.stats['injected_total']:,}")
    for rule, count in sorted(injection.stats["by_rule"].items(), key=lambda kv: -kv[1]):
        print(f"    {rule:<26} {count:>7,}")

if __name__ == "__main__":
    raise SystemExit(main())
