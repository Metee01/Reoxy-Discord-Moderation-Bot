"""
Reoxy Bot — Süre Çözümleyici

"10m", "1h30m", "2d", "1d12h" gibi süre string'lerini
datetime.timedelta nesnesine çevirir.
"""

import re
from datetime import timedelta


# Desteklenen süre birimleri ve çarpanları (saniye cinsinden)
_TIME_UNITS: dict[str, int] = {
    "s": 1,           # saniye
    "sn": 1,          # saniye (Türkçe kısaltma)
    "m": 60,          # dakika
    "dk": 60,         # dakika (Türkçe kısaltma)
    "h": 3600,        # saat
    "sa": 3600,       # saat (Türkçe kısaltma)
    "d": 86400,       # gün
    "g": 86400,       # gün (Türkçe kısaltma)
    "w": 604800,      # hafta
    "hf": 604800,     # hafta (Türkçe kısaltma)
}

# Regex: bir veya daha fazla "sayı + birim" çifti yakalar
_TIME_PATTERN = re.compile(
    r"(\d+)\s*(" + "|".join(sorted(_TIME_UNITS.keys(), key=len, reverse=True)) + r")",
    re.IGNORECASE,
)


class TimeParseError(Exception):
    """Süre çözümleme hatası."""

    def __init__(self, input_str: str) -> None:
        self.input_str = input_str
        super().__init__(
            f"'{input_str}' geçerli bir süre formatı değil. "
            f"Örnek: 10m, 1h30m, 2d, 1d12h"
        )


def parse_duration(duration_str: str) -> timedelta:
    """
    Süre string'ini timedelta nesnesine çevirir.

    Desteklenen formatlar:
        - 10m, 30dk → 10 dakika, 30 dakika
        - 1h, 2sa → 1 saat, 2 saat
        - 1d, 3g → 1 gün, 3 gün
        - 1w, 1hf → 1 hafta
        - 1h30m, 1d12h, 2d6h30m → Kombinasyonlar

    Args:
        duration_str: Çözümlenecek süre string'i.

    Returns:
        Çözümlenmiş timedelta nesnesi.

    Raises:
        TimeParseError: Geçersiz format.
    """
    duration_str = duration_str.strip()

    if not duration_str:
        raise TimeParseError(duration_str)

    matches = _TIME_PATTERN.findall(duration_str)

    if not matches:
        raise TimeParseError(duration_str)

    total_seconds = 0
    for amount_str, unit in matches:
        amount = int(amount_str)
        unit_lower = unit.lower()
        multiplier = _TIME_UNITS.get(unit_lower)

        if multiplier is None:
            raise TimeParseError(duration_str)

        total_seconds += amount * multiplier

    if total_seconds <= 0:
        raise TimeParseError(duration_str)

    return timedelta(seconds=total_seconds)


def format_duration(delta: timedelta) -> str:
    """
    timedelta nesnesini okunabilir Türkçe string'e çevirir.

    Args:
        delta: Formatlanacak timedelta nesnesi.

    Returns:
        Okunabilir süre string'i, örn: "1 gün, 2 saat, 30 dakika"
    """
    total_seconds = int(delta.total_seconds())

    if total_seconds <= 0:
        return "0 saniye"

    parts: list[str] = []

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        parts.append(f"{days} gün")
    if hours > 0:
        parts.append(f"{hours} saat")
    if minutes > 0:
        parts.append(f"{minutes} dakika")
    if seconds > 0 and not parts:  # Sadece saniye varsa göster
        parts.append(f"{seconds} saniye")

    return ", ".join(parts)
