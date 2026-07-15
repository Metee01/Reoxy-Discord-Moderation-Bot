"""
Reoxy Bot — Yapılandırma Yükleyici

config.yaml dosyasını yükler ve erişim sağlar.
"""

from pathlib import Path
from typing import Any

import yaml
from loguru import logger


class Config:
    """YAML tabanlı yapılandırma yöneticisi."""

    _data: dict[str, Any] = {}

    @classmethod
    def load(cls, path: str = "config.yaml") -> None:
        """
        Yapılandırma dosyasını yükler.

        Args:
            path: YAML dosyasının yolu.
        """
        config_path = Path(path)

        if not config_path.exists():
            logger.warning(f"Yapılandırma dosyası bulunamadı: {path}")
            cls._data = {}
            return

        with open(config_path, "r", encoding="utf-8") as f:
            cls._data = yaml.safe_load(f) or {}

        logger.info(f"Yapılandırma yüklendi: {path}")

    @classmethod
    def get(cls, *keys: str, default: Any = None) -> Any:
        """
        Nokta-ayrımlı anahtar ile yapılandırma değerine erişir.

        Kullanım:
            Config.get("bot", "prefix")  →  config["bot"]["prefix"]
            Config.get("colors", "primary", default=0x8B5CF6)

        Args:
            *keys: Hiyerarşik anahtarlar.
            default: Anahtar bulunamazsa dönecek varsayılan değer.

        Returns:
            Yapılandırma değeri veya varsayılan.
        """
        value = cls._data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    @classmethod
    def get_section(cls, section: str) -> dict[str, Any]:
        """
        Belirli bir bölümü (section) döndürür.

        Args:
            section: Bölüm adı (örn: "bot", "moderation", "colors").

        Returns:
            Bölüm sözlüğü veya boş sözlük.
        """
        return cls._data.get(section, {})

    @classmethod
    @property
    def raw(cls) -> dict[str, Any]:
        """Ham yapılandırma sözlüğünü döndürür."""
        return cls._data
