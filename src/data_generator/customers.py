"""customers in two source systems - the master data management problem"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from faker import Faker

from . import reference as ref
from .config import Settings
from .identity import (
    ascii_fold,
    generate_corporate_email,
    generate_email,
    generate_mobile,
    generate_tckn,
    generate_vkn,
)
from .rng import stream
from .versioning import Versioned, spread_changes

TYPE_INDIVIDUAL, TYPE_CORPORATE = "INDIVIDUAL", "CORPORATE"

PRESENCE_BOTH, PRESENCE_DMS_ONLY, PRESENCE_CRM_ONLY = "BOTH", "DMS_ONLY", "CRM_ONLY"
_PRESENCE_MIX = ((PRESENCE_BOTH, 0.65), (PRESENCE_DMS_ONLY, 0.20), (PRESENCE_CRM_ONLY, 0.15))

_CORPORATE_SUFFIXES = (
    "A.Ş.", "AŞ", "A.S.", "Anonim Şirketi",
    "Ltd. Şti.", "LTD.ŞTİ.", "Ltd.Sti.", "Limited Şirketi",
    "San. ve Tic. A.Ş.", "SANAYİ VE TİCARET A.Ş.", "San.Tic.Ltd.Şti.",
)

_CORPORATE_STEMS = (
    "Lojistik", "İnşaat", "Tekstil", "Gıda", "Enerji", "Turizm", "Tarım",
    "Makine", "Kimya", "Nakliyat", "Otomotiv", "Bilişim", "Sağlık", "Eğitim",
)

_LEAD_SOURCES = ("WEB", "SHOWROOM", "CALL_CENTER", "REFERRAL", "CAMPAIGN", "FLEET")

DIFFICULTY_EASY, DIFFICULTY_HARD, DIFFICULTY_NONE = "EASY", "HARD", "NONE"

@dataclass
class CustomerUniverse:
    """the two source views, plus the ground truth linking them"""

    dms: list[Versioned] = field(default_factory=list)
    crm: list[Versioned] = field(default_factory=list)

    truth: list[dict] = field(default_factory=list)

    dms_ids: list[str] = field(default_factory=list)
    customer_home: dict[str, str] = field(default_factory=dict)
    customer_type: dict[str, str] = field(default_factory=dict)
    customer_since: dict[str, date] = field(default_factory=dict)

def _abbreviate_first(name: str) -> str:
    """'mehmet ali yılmaz' -> 'm. ali yılmaz'. very common in turkish records"""
    parts = name.split()
    if len(parts) < 2:
        return name
    return f"{parts[0][0]}. " + " ".join(parts[1:])

def _swap_corporate_suffix(rng: random.Random, name: str) -> str:
    """rewrite the legal-form suffix in a different but equivalent style"""
    for suffix in sorted(_CORPORATE_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix):
            stem = name[: -len(suffix)].strip()
            alternatives = [s for s in _CORPORATE_SUFFIXES if s != suffix]
            return f"{stem} {rng.choice(alternatives)}"
    return f"{name} {rng.choice(_CORPORATE_SUFFIXES)}"

def _incidental_variant(rng: random.Random, name: str, is_corporate: bool) -> str:
    """apply one hard-to-match distortion"""
    options = ["fold", "whitespace", "punctuation"]
    options.append("suffix" if is_corporate else "abbreviate")

    choice = rng.choice(options)
    if choice == "fold":

        return ascii_fold(name)
    if choice == "whitespace":
        return name.replace(" ", "  ", 1) + " "
    if choice == "punctuation":
        return name.replace(".", "").replace("-", " ")
    if choice == "suffix":
        return _swap_corporate_suffix(rng, name)
    return _abbreviate_first(name)

def _make_canonical(
    rng: random.Random, faker: Faker, index: int, settings: Settings
) -> dict:
    """one real person or company, before either system got hold of them"""
    is_corporate = rng.random() < 0.22
    province = rng.choices(
        ref.PROVINCES, weights=[p.population_m for p in ref.PROVINCES], k=1
    )[0]

    if rng.random() < 0.35:
        acquired = settings.timeline.start
    else:
        acquired = settings.timeline.start + timedelta(
            days=rng.randint(1, settings.timeline.days - 1)
        )

    phone_dms, phone_crm = generate_mobile(rng)

    if is_corporate:
        stem = faker.last_name()
        name = f"{stem} {rng.choice(_CORPORATE_STEMS)} {rng.choice(_CORPORATE_SUFFIXES)}"
        return {
            "canonical_id": f"CAN{index:06d}",
            "customer_type": TYPE_CORPORATE,
            "display_name": name,
            "identity_no": generate_vkn(rng),
            "birth_date": None,
            "gender": None,
            "email": generate_corporate_email(rng, name),
            "phone_dms": phone_dms,
            "phone_crm": phone_crm,
            "province_code": province.plate_code,
            "city": province.name,
            "address_line": f"{rng.randint(1, 400)}. Cadde No:{rng.randint(1, 120)}",
            "acquired_on": acquired,
        }

    first_name = faker.first_name()
    last_name = faker.last_name()
    return {
        "canonical_id": f"CAN{index:06d}",
        "customer_type": TYPE_INDIVIDUAL,
        "display_name": f"{first_name} {last_name}",
        "identity_no": generate_tckn(rng),
        "birth_date": faker.date_of_birth(minimum_age=21, maximum_age=78).isoformat(),
        "gender": rng.choice(["M", "F"]),
        "email": generate_email(rng, first_name, last_name),
        "phone_dms": phone_dms,
        "phone_crm": phone_crm,
        "province_code": province.plate_code,
        "city": province.name,
        "address_line": f"{rng.randint(1, 400)}. Sokak No:{rng.randint(1, 120)}",
        "acquired_on": acquired,
    }

def _dms_view(rng: random.Random, canonical: dict, customer_id: str, hard: bool) -> Versioned:
    """the dms record: legacy conventions, upper case, identity number always present"""
    name = canonical["display_name"]
    if hard:
        name = _incidental_variant(rng, name, canonical["customer_type"] == TYPE_CORPORATE)

    return Versioned(
        key=customer_id,
        created_on=canonical["acquired_on"],
        base={
            "customer_id": customer_id,
            "customer_type": canonical["customer_type"],

            "full_name": name.upper(),
            "identity_no": canonical["identity_no"],
            "birth_date": canonical["birth_date"],
            "phone": canonical["phone_dms"],

            "email": canonical["email"] if rng.random() > 0.20 else "",
            "address_line": canonical["address_line"],
            "city_code": canonical["province_code"],
            "city": canonical["city"],
            "created_date": canonical["acquired_on"].isoformat(),
            "is_active": 1,
        },
    )

def _crm_view(rng: random.Random, canonical: dict, crm_id: str, hard: bool) -> Versioned:
    """the crm record: title case, nested contacts, identity number often missing"""
    name = canonical["display_name"]
    if hard:
        name = _incidental_variant(rng, name, canonical["customer_type"] == TYPE_CORPORATE)

    contacts = [{"contact_type": "GSM", "value": canonical["phone_crm"], "is_primary": True}]
    if rng.random() < 0.85:
        contacts.append(
            {"contact_type": "EMAIL", "value": canonical["email"], "is_primary": False}
        )
    if rng.random() < 0.18:
        second_dms, second_crm = generate_mobile(rng)
        contacts.append({"contact_type": "GSM", "value": second_crm, "is_primary": False})

    return Versioned(
        key=crm_id,
        created_on=canonical["acquired_on"],
        base={
            "crm_id": crm_id,
            "customer_type": canonical["customer_type"],
            "full_name": name.title(),

            "identity_no": canonical["identity_no"] if rng.random() < 0.40 else None,
            "primary_email": canonical["email"],
            "city": canonical["city"],
            "lead_source": rng.choice(_LEAD_SOURCES),
            "consent_kvkk": rng.random() < 0.78,
            "contacts": contacts,
            "is_active": 1,
        },
    )

def _apply_customer_changes(
    rng: random.Random, record: Versioned, settings: Settings, *, is_crm: bool
) -> None:
    """contact detail churn, which drives the incremental extract"""
    earliest = record.created_on + timedelta(days=60)
    if earliest >= settings.timeline.end:
        return

    if rng.random() < 0.09:
        for when in spread_changes(rng, earliest, settings.timeline.end, 1, min_gap_days=120):
            _, new_crm = generate_mobile(rng)
            if is_crm:
                contacts = [dict(c) for c in record.base["contacts"]]
                contacts[0]["value"] = new_crm
                record.add_change(when, contacts=contacts)
            else:
                record.add_change(when, phone=new_crm.replace("+90 ", "0").replace(" ", ""))

    if rng.random() < 0.06:
        for when in spread_changes(rng, earliest, settings.timeline.end, 1, min_gap_days=120):
            province = rng.choice(ref.PROVINCES)
            if is_crm:
                record.add_change(when, city=province.name)
            else:
                record.add_change(
                    when, city=province.name, city_code=province.plate_code
                )

def generate_customers(settings: Settings) -> CustomerUniverse:
    """build the customer universe across both source systems"""
    rng = stream(settings.seed, "customers")
    faker = Faker("tr_TR")
    faker.seed_instance(rng.randint(0, 2**31))

    presence_options, presence_weights = zip(*_PRESENCE_MIX)
    universe = CustomerUniverse()

    dms_counter = 0
    crm_counter = 0

    for index in range(1, settings.volumes.customers + 1):
        canonical = _make_canonical(rng, faker, index, settings)
        presence = rng.choices(presence_options, weights=presence_weights, k=1)[0]

        hard = presence == PRESENCE_BOTH and rng.random() < settings.dirty.customer_name_variant

        dms_id = crm_id = None

        if presence in (PRESENCE_BOTH, PRESENCE_DMS_ONLY):
            dms_counter += 1
            dms_id = f"CUS{dms_counter:06d}"
            record = _dms_view(rng, canonical, dms_id, hard)
            _apply_customer_changes(rng, record, settings, is_crm=False)
            universe.dms.append(record)
            universe.dms_ids.append(dms_id)
            universe.customer_home[dms_id] = canonical["province_code"]
            universe.customer_type[dms_id] = canonical["customer_type"]
            universe.customer_since[dms_id] = canonical["acquired_on"]

        if presence in (PRESENCE_BOTH, PRESENCE_CRM_ONLY):
            crm_counter += 1
            crm_id = f"CRM{crm_counter:06d}"
            record = _crm_view(rng, canonical, crm_id, hard)
            _apply_customer_changes(rng, record, settings, is_crm=True)
            universe.crm.append(record)

        if presence == PRESENCE_BOTH:
            difficulty = DIFFICULTY_HARD if hard else DIFFICULTY_EASY
        else:
            difficulty = DIFFICULTY_NONE

        universe.truth.append(
            {
                "canonical_id": canonical["canonical_id"],
                "customer_type": canonical["customer_type"],
                "dms_customer_id": dms_id or "",
                "crm_id": crm_id or "",
                "presence": presence,
                "match_difficulty": difficulty,
            }
        )

    return universe
