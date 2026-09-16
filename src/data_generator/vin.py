"""iso 3779'a göre vin üretimi ve doğrulaması, kontrol hanesi dahil."""

from __future__ import annotations

import random
import string

VIN_LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"
VIN_ALPHABET = VIN_LETTERS + string.digits

FORBIDDEN_LETTERS = "IOQ"

VIN_LENGTH = 17
CHECK_DIGIT_POSITION = 8

_TRANSLITERATION = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}

# pozisyon 9 (check digit'in kendisi) ağırlığı 0 - kendini hesaba katmaz
_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)

def transliterate(char: str) -> int:
    """bir vin karakterinin sayısal değeri"""
    if char.isdigit():
        return int(char)
    try:
        return _TRANSLITERATION[char]
    except KeyError:
        raise ValueError(f"{char!r} is not a legal VIN character") from None

def check_digit(vin: str) -> str:
    """17 karakterlik bir vin için iso 3779 kontrol hanesini hesapla"""
    if len(vin) != VIN_LENGTH:
        raise ValueError(f"a VIN must be {VIN_LENGTH} characters, got {len(vin)}")

    total = sum(transliterate(c) * w for c, w in zip(vin.upper(), _WEIGHTS))
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)

def is_check_digit_valid(vin: str) -> bool:
    """9. pozisyon hesaplanan kontrol hanesiyle eşleşiyorsa true"""
    try:
        return check_digit(vin) == vin.upper()[CHECK_DIGIT_POSITION]
    except (ValueError, IndexError):
        return False

def is_well_formed(vin: str) -> bool:
    """sadece yapısal geçerlilik: uzunluk, alfabe, yasak harfler"""
    if not isinstance(vin, str) or len(vin) != VIN_LENGTH:
        return False
    upper = vin.upper()
    if any(c in FORBIDDEN_LETTERS for c in upper):
        return False
    return all(c in VIN_ALPHABET for c in upper)

def is_valid(vin: str) -> bool:
    """tamamen geçerli: yapısı doğru *ve* kontrol hanesi tutuyor"""
    return is_well_formed(vin) and is_check_digit_valid(vin)

_YEAR_LETTERS = "ABCDEFGHJKLMNPRSTVWXY"
_YEAR_BASE = 2010

_YEAR_TO_CODE = {_YEAR_BASE + i: c for i, c in enumerate(_YEAR_LETTERS)}
_CODE_TO_YEAR = {c: y for y, c in _YEAR_TO_CODE.items()}

def model_year_code(year: int) -> str:
    """model yılı için 10. pozisyon karakteri (desteklenen aralık 2010-2030)"""
    try:
        return _YEAR_TO_CODE[year]
    except KeyError:
        raise ValueError(f"model year {year} outside the supported 2010-2030 cycle") from None

def year_from_code(code: str) -> int | None:
    """`model_year_code`'un tersi. tanınmayan kod için none döner"""
    return _CODE_TO_YEAR.get(code.upper())

def build_vin(
    wmi: str,
    vds: str,
    model_year: int,
    plant_code: str,
    serial: int,
) -> str:
    """doğru kontrol haneli, yapısal olarak doğru bir vin oluştur"""
    if len(wmi) != 3:
        raise ValueError("WMI must be 3 characters")
    if len(vds) != 5:
        raise ValueError("VDS must be 5 characters")
    if len(plant_code) != 1:
        raise ValueError("plant code must be 1 character")

    body = (
        f"{wmi}{vds}"
        f"0"
        f"{model_year_code(model_year)}"
        f"{plant_code}"
        f"{serial:06d}"
    )
    return body[:CHECK_DIGIT_POSITION] + check_digit(body) + body[CHECK_DIGIT_POSITION + 1:]

def random_vds(rng: random.Random) -> str:
    """5 karakterlik tanımlayıcı blok, model/donanım başına bir kez kullanılır"""
    return "".join(rng.choice(VIN_ALPHABET) for _ in range(5))

def corrupt_format(rng: random.Random, vin: str) -> tuple[str, str]:
    """bir vin'in yapısını boz. (broken_vin, defect_name) döner"""
    mode = rng.choice(["truncated", "forbidden_letter", "too_long"])

    if mode == "truncated":
        return vin[:16], "vin_length"
    if mode == "forbidden_letter":
        position = rng.randrange(VIN_LENGTH)
        replacement = rng.choice(FORBIDDEN_LETTERS)
        return vin[:position] + replacement + vin[position + 1:], "vin_forbidden_letter"
    return vin + rng.choice(string.digits), "vin_length"

def corrupt_check_digit(rng: random.Random, vin: str) -> tuple[str, str]:
    """iki karakterin yerini değiştir; vin yapısal olarak doğru kalır ama kontrolden geçmez"""

    for _ in range(10):
        i = rng.randrange(11, VIN_LENGTH - 1)
        if vin[i] != vin[i + 1]:
            swapped = list(vin)
            swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
            candidate = "".join(swapped)
            if not is_check_digit_valid(candidate):
                return candidate, "vin_check_digit"

    current = vin[CHECK_DIGIT_POSITION]
    wrong = rng.choice([c for c in string.digits + "X" if c != current])
    return vin[:CHECK_DIGIT_POSITION] + wrong + vin[CHECK_DIGIT_POSITION + 1:], "vin_check_digit"
