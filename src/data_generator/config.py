"""project-defining configuration for the mihenk source data generator"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields, replace
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

@dataclass(frozen=True)
class Timeline:
    """the period the simulated business has been operating"""

    start: date = date(2023, 1, 1)
    end: date = date(2026, 8, 31)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def contains(self, d: date) -> bool:
        return self.start <= d <= self.end

@dataclass(frozen=True)
class Volumes:
    """row counts for each generated entity"""

    dealers: int = 40
    employees: int = 350
    customers: int = 25_000
    model_trims: int = 120
    parts: int = 4_000
    suppliers: int = 60

    vehicles: int = 35_000
    vehicle_sales: int = 30_000

    repair_orders: int = 180_000
    repair_order_lines: int = 600_000

    part_purchase_lines: int = 50_000

    recall_campaigns: int = 15

    def scaled(self, factor: float) -> Volumes:
        """return the same volumes multiplied by `factor`"""
        return replace(
            self,
            **{f.name: max(1, round(getattr(self, f.name) * factor)) for f in fields(self)},
        )

@dataclass(frozen=True)
class DirtyRatios:
    """share of rows deliberately corrupted, per defect type"""

    invalid_vin_format: float = 0.006

    invalid_vin_check_digit: float = 0.008

    duplicate_new_vehicle_sale: float = 0.003

    invalid_plate_format: float = 0.007
    invalid_plate_province: float = 0.004

    odometer_rollback: float = 0.009

    repair_order_date_out_of_order: float = 0.006
    negative_labour_hours: float = 0.004
    excessive_labour_hours: float = 0.002

    warranty_amount_overflow: float = 0.003

    orphan_part_no: float = 0.005
    orphan_vin: float = 0.004

    customer_name_variant: float = 0.180

    null_business_key: float = 0.003

    inconsistent_date_format: float = 0.010

@dataclass(frozen=True)
class Economics:
    """price and currency behaviour over the timeline"""

    annual_inflation: dict[int, float] = None

    usd_try_anchors: dict[date, float] = None
    eur_try_anchors: dict[date, float] = None

    def __post_init__(self) -> None:

        if self.annual_inflation is None:
            object.__setattr__(
                self,
                "annual_inflation",
                {2023: 0.55, 2024: 0.45, 2025: 0.32, 2026: 0.24},
            )
        if self.usd_try_anchors is None:
            object.__setattr__(
                self,
                "usd_try_anchors",
                {
                    date(2023, 1, 1): 18.70,
                    date(2023, 7, 1): 26.10,
                    date(2024, 1, 1): 29.50,
                    date(2024, 7, 1): 32.80,
                    date(2025, 1, 1): 35.40,
                    date(2025, 7, 1): 39.60,
                    date(2026, 1, 1): 43.20,
                    date(2026, 8, 31): 47.50,
                },
            )
        if self.eur_try_anchors is None:
            object.__setattr__(
                self,
                "eur_try_anchors",
                {
                    date(2023, 1, 1): 19.95,
                    date(2023, 7, 1): 28.60,
                    date(2024, 1, 1): 32.40,
                    date(2024, 7, 1): 35.50,
                    date(2025, 1, 1): 36.80,
                    date(2025, 7, 1): 45.10,
                    date(2026, 1, 1): 49.60,
                    date(2026, 8, 31): 54.80,
                },
            )

@dataclass(frozen=True)
class Seasonality:
    """monthly demand multipliers, january through december"""

    vehicle_sales: tuple[float, ...] = (
        0.72,
        0.85,
        1.02,
        1.05,
        1.08,
        1.00,
        0.88,
        0.86,
        1.06,
        1.10,
        1.15,
        1.60,
    )

    service: tuple[float, ...] = (
        0.92,
        0.90,
        1.00,
        1.05,
        1.22,
        1.18,
        0.95,
        0.82,
        1.05,
        1.12,
        1.30,
        1.20,
    )

    tax_change_dates: tuple[date, ...] = (
        date(2023, 7, 15),
        date(2024, 5, 2),
        date(2025, 11, 20),
    )

@dataclass(frozen=True)
class Settings:
    """everything the generator needs, assembled in one object"""

    seed: int
    output_path: Path
    scale: float
    log_level: str

    timeline: Timeline
    volumes: Volumes
    dirty: DirtyRatios
    economics: Economics
    seasonality: Seasonality

    encodings: dict[str, str] = None

    def __post_init__(self) -> None:
        if self.encodings is None:
            object.__setattr__(
                self,
                "encodings",
                {
                    "dms": "windows-1254",
                    "crm": "utf-8",
                    "workshop": "utf-8",
                    "parts": "utf-8",
                    "portal": "utf-8",
                    "finance": "utf-8",
                },
            )

    @classmethod
    def from_env(cls, scale: float = 1.0) -> Settings:
        """build settings from `.env`, falling back to documented defaults"""
        load_dotenv()

        seed = int(os.getenv("MIHENK_SEED", "20260101"))
        output_path = Path(os.getenv("MIHENK_OUTPUT_PATH", "./data")).resolve()
        log_level = os.getenv("MIHENK_LOG_LEVEL", "INFO").upper()

        volumes = Volumes()
        if scale != 1.0:
            volumes = volumes.scaled(scale)

        return cls(
            seed=seed,
            output_path=output_path,
            scale=scale,
            log_level=log_level,
            timeline=Timeline(),
            volumes=volumes,
            dirty=DirtyRatios(),
            economics=Economics(),
            seasonality=Seasonality(),
        )

    def describe(self) -> str:
        """one-screen summary, printed at the start of every run"""
        v = self.volumes
        return (
            f"MIHENK data generator\n"
            f"  seed        : {self.seed}\n"
            f"  scale       : {self.scale:g}\n"
            f"  timeline    : {self.timeline.start} -> {self.timeline.end} "
            f"({self.timeline.days} days)\n"
            f"  output      : {self.output_path}\n"
            f"  dealers     : {v.dealers:,}\n"
            f"  customers   : {v.customers:,}\n"
            f"  vehicles    : {v.vehicles:,}\n"
            f"  sales       : {v.vehicle_sales:,}\n"
            f"  repair ords : {v.repair_orders:,} ({v.repair_order_lines:,} lines)\n"
            f"  parts       : {v.parts:,}\n"
        )
