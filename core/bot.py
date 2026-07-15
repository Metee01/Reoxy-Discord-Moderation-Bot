"""
Reoxy Bot — Ana Bot Sınıfı

commands.Bot alt sınıfı. Cog yükleme, veritabanı başlatma
ve yaşam döngüsü yönetimi.
"""

from __future__ import annotations

import discord
from discord.ext import commands
from loguru import logger

from core.config import Config
from core.database import Database
from web.server import HealthServer


class ReoxyBot(commands.Bot):
    """Reoxy moderasyon botunun ana sınıfı."""

    def __init__(self) -> None:
        # Yapılandırmayı yükle
        Config.load()

        # Intent'leri ayarla — moderasyon için gerekli tüm intent'ler
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.moderation = True

        # Bot prefix
        prefix = Config.get("bot", "prefix", default="!")

        super().__init__(
            command_prefix=prefix,
            intents=intents,
            description=Config.get("bot", "description", default="Reoxy Moderasyon Botu"),
            help_command=None,  # Özel help komutu daha sonra eklenecek
        )

        # Veritabanı yöneticisi
        self.db = Database()

        # Health check sunucusu (Render.com için)
        self._health_server = HealthServer()

    async def setup_hook(self) -> None:
        """
        Bot başlatılmadan önce çalışır.
        Veritabanı bağlantısı kurar ve cog'ları yükler.
        """
        # Veritabanı bağlantısı
        await self.db.connect()
        logger.info("Veritabanı bağlantısı kuruldu")

        # Health check sunucusunu başlat (Render.com)
        await self._health_server.start()

        # Cog'ları yükle
        cog_extensions = [
            "cogs.moderation",
            "cogs.automod",
            "cogs.channel",
            "cogs.general",
        ]

        for ext in cog_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Cog yüklendi: {ext}")
            except Exception as e:
                logger.error(f"Cog yüklenemedi: {ext} — {e}")

        # Slash komutlarını senkronize et
        synced = await self.tree.sync()
        logger.info(f"{len(synced)} slash komutu senkronize edildi")

    async def on_ready(self) -> None:
        """Bot bağlandığında çalışır."""
        # Aktivite durumunu ayarla
        activity_text = Config.get("bot", "activity", default="Sunucuyu koruyor 🛡️")
        activity_type_str = Config.get("bot", "activity_type", default="watching")

        activity_types = {
            "playing": discord.ActivityType.playing,
            "streaming": discord.ActivityType.streaming,
            "listening": discord.ActivityType.listening,
            "watching": discord.ActivityType.watching,
            "competing": discord.ActivityType.competing,
        }

        activity_type = activity_types.get(activity_type_str, discord.ActivityType.watching)
        activity = discord.Activity(type=activity_type, name=activity_text)
        await self.change_presence(activity=activity, status=discord.Status.online)

        logger.info(f"{'═' * 50}")
        logger.info(f"  {self.user.name} çevrimiçi!")
        logger.info(f"  ID: {self.user.id}")
        logger.info(f"  Sunucu sayısı: {len(self.guilds)}")
        logger.info(f"  discord.py v{discord.__version__}")
        logger.info(f"{'═' * 50}")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """Global komut hata yakalayıcı."""
        from utils.embeds import error_embed

        if isinstance(error, commands.CommandNotFound):
            return  # Bilinmeyen komutları sessizce yoksay

        if isinstance(error, commands.MissingPermissions):
            missing = ", ".join(f"`{p}`" for p in error.missing_permissions)
            embed = error_embed(
                "Yetersiz Yetki",
                f"Bu komutu kullanmak için şu izinlere sahip olmanız gerekiyor:\n{missing}",
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        if isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(f"`{p}`" for p in error.missing_permissions)
            embed = error_embed(
                "Bot Yetkisi Yetersiz",
                f"Bu işlemi gerçekleştirmek için şu izinlere ihtiyacım var:\n{missing}",
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        if isinstance(error, commands.MemberNotFound):
            embed = error_embed(
                "Kullanıcı Bulunamadı",
                f"Belirtilen kullanıcı bulunamadı. Lütfen geçerli bir kullanıcı etiketleyin veya ID girin.",
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        if isinstance(error, commands.MissingRequiredArgument):
            embed = error_embed(
                "Eksik Parametre",
                f"**`{error.param.name}`** parametresi gereklidir.\n"
                f"Kullanım: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        if isinstance(error, commands.BadArgument):
            embed = error_embed(
                "Geçersiz Parametre",
                f"Girdiğiniz değer geçersiz. Lütfen doğru formatta girin.\n"
                f"Kullanım: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        if isinstance(error, commands.CommandOnCooldown):
            embed = error_embed(
                "Bekleme Süresi",
                f"Bu komutu tekrar kullanabilmek için **{error.retry_after:.1f} saniye** beklemeniz gerekiyor.",
            )
            await ctx.send(embed=embed, delete_after=error.retry_after)
            return

        # Beklenmeyen hatalar
        logger.error(f"Beklenmeyen hata — {ctx.command}: {error}", exc_info=error)
        embed = error_embed(
            "Beklenmeyen Hata",
            "Bir hata oluştu. Bu durum geliştiricilere bildirildi.",
        )
        await ctx.send(embed=embed, delete_after=10)

    async def close(self) -> None:
        """Bot kapatılırken veritabanı bağlantısını düzgün kapatır."""
        await self._health_server.stop()
        await self.db.close()
        logger.info("Bot kapatılıyor...")
        await super().close()
