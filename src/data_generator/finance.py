"""finance: dealer targets and the published exchange rate table"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from . import reference as ref
from .config import Settings
from .master import MasterData
from .rng import clamp, stream

METRIC_SALES_COUNT = "VEHICLE_SALES_COUNT"
METRIC_SALES_AMOUNT = "VEHICLE_SALES_AMOUNT"
METRIC_SERVICE_AMOUNT = "SERVICE_REVENUE_AMOUNT"

@dataclass
class FinanceResult:
    budget: list[dict] = field(default_factory=list)
    fx_rates: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

def generate_finance(
    settings: Settings,
    master: MasterData,
    sales_contracts: list[dict],
    repair_orders: list[dict],
    fx_series: list[ref.FxRate],
    fx: ref.FxLookup,
) -> FinanceResult:
    rng = stream(settings.seed, "finance")

    actual_count: dict[tuple[str, int, int], int] = defaultdict(int)
    actual_amount: dict[tuple[str, int, int], float] = defaultdict(float)

    for contract in sales_contracts:
        contract_date = date.fromisoformat(contract["contract_date"])
        key = (contract["dealer_code"], contract_date.year, contract_date.month)
        actual_count[key] += 1
        actual_amount[key] += fx.to_try(
            float(contract["net_sale_amount"]), contract["currency_code"], contract_date
        )

    service_amount: dict[tuple[str, int, int], float] = defaultdict(float)
    for order in repair_orders:
        checkin = order["checkin_ts"]
        key = (order["dealer_code"], int(checkin[0:4]), int(checkin[5:7]))
        service_amount[key] += float(order["total_labour_amount"]) + float(
            order["total_part_amount"]
        )

    years = range(settings.timeline.start.year, settings.timeline.end.year + 1)
    bias: dict[tuple[str, int], float] = {}
    for dealer in master.dealers:
        for year in years:

            bias[(dealer.key, year)] = clamp(rng.gauss(1.06, 0.14), 0.78, 1.42)

    budget: list[dict] = []
    dealer_codes = [d.key for d in master.dealers]

    cursor_year, cursor_month = settings.timeline.start.year, settings.timeline.start.month
    while date(cursor_year, cursor_month, 1) <= settings.timeline.end:
        for dealer_code in dealer_codes:
            key = (dealer_code, cursor_year, cursor_month)
            dealer_bias = bias[(dealer_code, cursor_year)]

            count = actual_count.get(key, 0)
            amount = actual_amount.get(key, 0.0)
            service = service_amount.get(key, 0.0)

            rows = (
                (METRIC_SALES_COUNT, max(count * dealer_bias, 1.0), False),
                (METRIC_SALES_AMOUNT, max(amount * dealer_bias, 50_000.0), True),
                (METRIC_SERVICE_AMOUNT, max(service * dealer_bias, 25_000.0), True),
            )
            for metric, value, is_money in rows:

                rounded = round(value, -3) if is_money else round(value)
                budget.append(
                    {
                        "dealer_code": dealer_code,
                        "budget_year": cursor_year,
                        "budget_month": cursor_month,
                        "metric_code": metric,
                        "target_value": rounded,

                        "currency_code": "TRY" if is_money else "",
                    }
                )

        cursor_month += 1
        if cursor_month > 12:
            cursor_year, cursor_month = cursor_year + 1, 1

    fx_rows = [
        {
            "rate_date": rate.rate_date.isoformat(),
            "currency_code": rate.currency_code,
            "rate_to_try": rate.rate_to_try,
        }
        for rate in fx_series
    ]

    achievement = [
        actual_count[(dealer, year, month)] / target
        for dealer, year, month, target in (
            (row["dealer_code"], row["budget_year"], row["budget_month"], row["target_value"])
            for row in budget
            if row["metric_code"] == METRIC_SALES_COUNT and row["target_value"] > 0
        )
        if actual_count.get((dealer, year, month), 0) > 0
    ]
    achievement.sort()

    return FinanceResult(
        budget=budget,
        fx_rates=fx_rows,
        stats={
            "budget_rows": len(budget),
            "fx_rows": len(fx_rows),
            "months": len(budget) // (len(dealer_codes) * 3) if dealer_codes else 0,
            "dealers_with_targets": len(dealer_codes),
            "achievement_p10": round(achievement[len(achievement) // 10], 3) if achievement else 0,
            "achievement_median": round(achievement[len(achievement) // 2], 3) if achievement else 0,
            "achievement_p90": round(achievement[len(achievement) * 9 // 10], 3) if achievement else 0,
            "months_over_target": sum(1 for a in achievement if a >= 1.0),
            "months_measured": len(achievement),
        },
    )
