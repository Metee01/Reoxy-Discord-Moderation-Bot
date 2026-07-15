"""
Reoxy Bot — Ana Giriş Noktası

Botu başlatır. Ortam değişkenlerini ve loglama sistemini yükler.
Kullanım: python bot.py
"""

import os
import sys

from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Loglama sistemini başlat
from core.logger import setup_logging

setup_logging()

from loguru import logger
from core.bot import ReoxyBot


def main() -> None:
    """Bot'u başlatır."""
    token = os.getenv("DISCORD_TOKEN")

    if not token:
        logger.critical(
            "DISCORD_TOKEN bulunamadı! "
            ".env dosyasına DISCORD_TOKEN=your_token_here satırını ekleyin."
        )
        sys.exit(1)

    bot = ReoxyBot()

    try:
        logger.info("Reoxy Bot başlatılıyor...")
        bot.run(token, log_handler=None)  # Loguru kullandığımız için discord.py log handler'ını devre dışı bırak
    except KeyboardInterrupt:
        logger.info("Bot kullanıcı tarafından durduruldu.")
    except Exception as e:
        logger.critical(f"Bot başlatılamadı: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
