"""türk kimlik ve iletişim bilgileri: tckn, vkn, telefon, e-posta"""

from __future__ import annotations

import random
import unicodedata

def generate_tckn(rng: random.Random) -> str:
    """yayınlanmış kontrol kurallarını sağlayan sentetik bir tckn"""
    digits = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(8)]

    odd_sum = sum(digits[0:9:2])
    even_sum = sum(digits[1:8:2])

    d10 = ((odd_sum * 7) - even_sum) % 10
    digits.append(d10)
    digits.append(sum(digits) % 10)

    return "".join(str(d) for d in digits)

def is_valid_tckn(value: str) -> bool:
    """bir tckn'nin formatını ve iki kontrol hanesini doğrula"""
    if not isinstance(value, str) or len(value) != 11 or not value.isdigit():
        return False
    if value[0] == "0":
        return False

    digits = [int(c) for c in value]
    odd_sum = sum(digits[0:9:2])
    even_sum = sum(digits[1:8:2])

    if ((odd_sum * 7) - even_sum) % 10 != digits[9]:
        return False
    return sum(digits[:10]) % 10 == digits[10]

def generate_vkn(rng: random.Random) -> str:
    """on haneli kurumsal vergi numarası"""
    return "".join(str(rng.randint(0, 9)) for _ in range(10))

_MOBILE_PREFIXES = (
    "530", "531", "532", "533", "534", "535", "536", "537", "538", "539",
    "541", "542", "543", "544", "545", "546", "547", "548", "549",
    "550", "551", "552", "553", "554", "555", "559",
    "505", "506", "507",
)

def generate_mobile(rng: random.Random) -> tuple[str, str]:
    """tek bir cep numarası, iki kaynak sistem formatında"""
    prefix = rng.choice(_MOBILE_PREFIXES)
    body = f"{rng.randint(0, 9_999_999):07d}"
    dms = f"0{prefix}{body}"
    crm = f"+90 {prefix} {body[:3]} {body[3:5]} {body[5:]}"
    return dms, crm

def ascii_fold(text: str) -> str:
    """türkçe karakterleri düzleştir: 'şükrü öztürk' -> 'sukru ozturk'"""
    manual = str.maketrans({"ı": "i", "İ": "I", "ş": "s", "Ş": "S", "ğ": "g", "Ğ": "G"})
    text = text.translate(manual)
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))

_EMAIL_DOMAINS = (
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com",
    "yandex.com", "icloud.com",
)

def generate_email(rng: random.Random, first_name: str, last_name: str) -> str:
    """kişinin kendi adından türetilmiş makul bir kişisel e-posta"""
    first = ascii_fold(first_name).lower().replace(" ", "")
    last = ascii_fold(last_name).lower().replace(" ", "")
    shape = rng.choice(["dot", "joined", "initial", "numbered"])

    if shape == "dot":
        local = f"{first}.{last}"
    elif shape == "joined":
        local = f"{first}{last}"
    elif shape == "initial":
        local = f"{first[:1]}{last}"
    else:
        local = f"{first}{last}{rng.randint(1, 99)}"

    return f"{local}@{rng.choice(_EMAIL_DOMAINS)}"

def generate_corporate_email(rng: random.Random, company_name: str) -> str:
    """ticari unvandan türetilmiş bir şirket e-postası"""
    stem = ascii_fold(company_name).lower()
    stem = "".join(c for c in stem if c.isalnum())[:18] or "firma"
    box = rng.choice(["info", "muhasebe", "satinalma", "filo", "iletisim"])
    return f"{box}@{stem}.com.tr"
