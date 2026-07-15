"""
Reoxy Bot — Loglama Yapılandırması

Loguru tabanlı merkezi loglama sistemi.
Konsola renkli, dosyaya JSON formatında log yazar.
"""

import sys
from pathlib import Path

from loguru import logger


def setup_logging() -> None:
    """
    Loglama sistemini yapılandırır.

    - Konsol: Renkli, okunabilir format
    - Dosya: logs/reoxy.log, günlük rotasyon, 30 gün saklama
    """
    # Varsayılan Loguru handler'ını kaldır
    logger.remove()

    # ── Konsol Handler ──
    logger.add(
        sys.stderr,
        format=(
            "<level>{level: <8}</level> | "
            "<cyan>{time:YYYY-MM-DD HH:mm:ss}</cyan> | "
            "<magenta>{name}</magenta>:<magenta>{function}</magenta>:<magenta>{line}</magenta> | "
            "<level>{message}</level>"
        ),
        level="INFO",
        colorize=True,
    )

    # ── Dosya Handler ──
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "reoxy_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="00:00",       # Her gece yarısı yeni dosya
        retention="30 days",    # 30 gün sakla
        compression="zip",     # Eski logları sıkıştır
        encoding="utf-8",
    )

    logger.info("Loglama sistemi başlatıldı")
