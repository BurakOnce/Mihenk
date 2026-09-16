"""distribütör portalı: garanti talebi sonuçları ve geri çağırma kampanyaları"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from .config import Settings
from .master import MasterData
from .rng import clamp, stream
from .vehicles import VehicleFleet
from .workshop import WorkshopResult

CLAIM_APPROVED, CLAIM_REJECTED, CLAIM_PENDING = "APPROVED", "REJECTED", "PENDING"

_REJECTION_REASONS = (
    "OUTSIDE_WARRANTY_PERIOD",
    "MISSING_DOCUMENTATION",
    "OPERATION_NOT_COVERED",
    "CUSTOMER_INDUCED_DAMAGE",
    "DUPLICATE_CLAIM",
    "LABOUR_TIME_EXCEEDS_STANDARD",
)

_RECALL_SUBJECTS = (
    ("Yakıt hattı bağlantı kontrolü", "SAFETY"),
    ("Ön süspansiyon salıncak civatası", "SAFETY"),
    ("Motor kontrol ünitesi yazılım güncellemesi", "SOFTWARE"),
    ("Ön cam silecek motoru", "COMFORT"),
    ("Arka fren hortumu kontrolü", "SAFETY"),
    ("Klima kompresör kayışı", "COMFORT"),
    ("Emniyet kemeri gergi mekanizması", "SAFETY"),
    ("Direksiyon kutusu contası", "SAFETY"),
    ("Batarya soğutma yazılımı", "SOFTWARE"),
    ("Far yükseklik ayar motoru", "COMFORT"),
    ("Turbo besleme hortumu", "SAFETY"),
    ("Gösterge paneli yazılımı", "SOFTWARE"),
    ("Arka kapı kilit mekanizması", "COMFORT"),
    ("Yakıt seviye sensörü", "COMFORT"),
    ("Ön panel kaynak noktası kontrolü", "SAFETY"),
)

@dataclass
class PortalResult:
    warranty_claims: list[dict] = field(default_factory=list)
    recall_campaigns: list[dict] = field(default_factory=list)
    recall_coverage: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

def _generate_claims(
    rng: random.Random, settings: Settings, workshop: WorkshopResult
) -> tuple[list[dict], dict]:
    claims: list[dict] = []
    counts = {CLAIM_APPROVED: 0, CLAIM_REJECTED: 0, CLAIM_PENDING: 0}
    claimed_total = 0.0
    approved_total = 0.0
    seq = 0

    for order in workshop.repair_orders:
        if not order["is_warranty"] or order["total_warranty_amount"] <= 0:
            continue

        if not order["delivery_ts"]:
            continue

        if rng.random() < 0.06:
            continue

        delivery = date.fromisoformat(order["delivery_ts"][:10])
        claim_date = delivery + timedelta(days=rng.randint(0, 9))
        if claim_date > settings.timeline.end:
            continue

        seq += 1
        claimed = float(order["total_warranty_amount"])

        decision_date = claim_date + timedelta(days=rng.randint(6, 45))
        if decision_date > settings.timeline.end:
            status, decision_date, approved, reason = CLAIM_PENDING, None, 0.0, ""
        else:
            roll = rng.random()
            if roll < 0.79:
                status, reason = CLAIM_APPROVED, ""
                approved = claimed
            elif roll < 0.90:

                status, reason = CLAIM_APPROVED, ""
                approved = round(claimed * rng.uniform(0.55, 0.92), 2)
            else:
                status = CLAIM_REJECTED
                reason = rng.choice(_REJECTION_REASONS)
                approved = 0.0

        counts[status] += 1
        claimed_total += claimed
        approved_total += approved

        claims.append(
            {
                "claim_no": f"GRT{claim_date.year}{seq:06d}",
                "repair_order_no": order["repair_order_no"],
                "vin": order["vin"],
                "dealer_code": order["dealer_code"],
                "service_type_code": order["service_type_code"],
                "claim_date": claim_date.isoformat(),
                "decision_date": decision_date.isoformat() if decision_date else None,
                "status": status,
                "claimed_amount": round(claimed, 2),
                "approved_amount": round(approved, 2),
                "currency_code": "TRY",
                "rejection_reason": reason or None,
            }
        )

    stats = {
        "warranty_claims": len(claims),
        "approved": counts[CLAIM_APPROVED],
        "rejected": counts[CLAIM_REJECTED],
        "pending": counts[CLAIM_PENDING],
        "claimed_amount": round(claimed_total, 2),
        "approved_amount": round(approved_total, 2),
        "approval_value_rate": round(approved_total / claimed_total, 4) if claimed_total else 0,
    }
    return claims, stats

def _generate_recalls(
    rng: random.Random,
    settings: Settings,
    master: MasterData,
    fleet: VehicleFleet,
) -> tuple[list[dict], list[dict], dict]:
    """gerçek geri çağırmalar gibi model ve üretim aralığına göre kapsamlanan kampanyalar"""
    campaigns: list[dict] = []
    coverage: list[dict] = []

    trims_by_model: dict[str, list[str]] = {}
    for trim in master.model_trims:
        trims_by_model.setdefault(trim.base["model_name"], []).append(trim.key)
    model_names = sorted(trims_by_model)

    vehicles_by_trim: dict[str, list] = {}
    for vehicle in fleet.all():
        vehicles_by_trim.setdefault(vehicle.model_trim_code, []).append(vehicle)

    subjects = list(_RECALL_SUBJECTS)
    rng.shuffle(subjects)

    for index in range(1, settings.volumes.recall_campaigns + 1):
        subject, category = subjects[(index - 1) % len(subjects)]
        code = f"KMP{index:03d}"

        affected_models = rng.sample(model_names, k=min(rng.randint(1, 2), len(model_names)))
        affected_trims = [t for m in affected_models for t in trims_by_model[m]]

        window_end = settings.timeline.start + timedelta(
            days=rng.randint(0, max(settings.timeline.days - 200, 1))
        )
        window_start = window_end - timedelta(days=rng.randint(60, 400))

        launch = window_end + timedelta(days=rng.randint(90, 500))
        if launch > settings.timeline.end:
            launch = settings.timeline.end - timedelta(days=rng.randint(10, 120))

        months_live = max((settings.timeline.end - launch).days / 30.44, 0.0)
        completion_rate = clamp(0.16 + months_live * 0.055, 0.10, 0.93)

        if category == "SAFETY":
            completion_rate = clamp(completion_rate * 1.18, 0.10, 0.96)

        affected_vins = 0
        for trim_code in affected_trims:
            for vehicle in vehicles_by_trim.get(trim_code, []):
                if not (window_start <= vehicle.production_date <= window_end):
                    continue
                affected_vins += 1

                notified = launch + timedelta(days=rng.randint(0, 30))
                completed_date = None
                if notified <= settings.timeline.end and rng.random() < completion_rate:
                    completed_date = notified + timedelta(days=rng.randint(5, 210))
                    if completed_date > settings.timeline.end:
                        completed_date = None

                coverage.append(
                    {
                        "campaign_code": code,
                        "vin": vehicle.vin,
                        "notified_date": notified.isoformat()
                        if notified <= settings.timeline.end else None,
                        "completed_date": completed_date.isoformat()
                        if completed_date else None,
                        "is_completed": int(completed_date is not None),
                    }
                )

        campaigns.append(
            {
                "campaign_code": code,
                "campaign_name": subject,
                "category": category,
                "launch_date": launch.isoformat(),
                "affected_models": affected_models,
                "affected_model_trim_codes": affected_trims,
                "production_from": window_start.isoformat(),
                "production_to": window_end.isoformat(),
                "affected_vehicle_count": affected_vins,
            }
        )

    completed = sum(row["is_completed"] for row in coverage)
    stats = {
        "recall_campaigns": len(campaigns),
        "recall_coverage_rows": len(coverage),
        "recall_completed": completed,
        "recall_outstanding": len(coverage) - completed,
        "recall_completion_rate": round(completed / len(coverage), 4) if coverage else 0,
    }
    return campaigns, coverage, stats

def generate_portal(
    settings: Settings,
    master: MasterData,
    fleet: VehicleFleet,
    workshop: WorkshopResult,
) -> PortalResult:
    rng = stream(settings.seed, "portal")

    claims, claim_stats = _generate_claims(rng, settings, workshop)
    campaigns, coverage, recall_stats = _generate_recalls(rng, settings, master, fleet)

    return PortalResult(
        warranty_claims=claims,
        recall_campaigns=campaigns,
        recall_coverage=coverage,
        stats={**claim_stats, **recall_stats},
    )
