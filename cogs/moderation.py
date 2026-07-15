"""
Reoxy Bot — Moderasyon Komutları Cog'u

Kick, Ban, Soft-Ban, Force-Ban, Timeout, Untimeout,
Unban, Warn, Warnings, Delwarn, Clearwarns ve Modlog komutları.

Tüm komutlar hybrid (hem slash hem prefix) olarak çalışır.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from utils.constants import ActionType, Emojis
from utils.embeds import (
    dm_notification_embed,
    error_embed,
    mod_action_embed,
    mod_log_embed,
    success_embed,
    warn_list_embed,
)
from utils.permissions import check_hierarchy
from utils.time_parser import TimeParseError, format_duration, parse_duration
from database import queries

if TYPE_CHECKING:
    from core.bot import ReoxyBot


class Moderation(commands.Cog):
    """Moderasyon Komutları — Sunucu yönetimi için temel araçlar."""

    def __init__(self, bot: ReoxyBot) -> None:
        self.bot = bot

    # ══════════════════════════════════════════════
    #  Yardımcı Metotlar
    # ══════════════════════════════════════════════

    async def _send_dm(
        self, user: discord.User | discord.Member, embed: discord.Embed
    ) -> bool:
        """Kullanıcıya DM göndermeyi dener. Başarılıysa True döner."""
        try:
            await user.send(embed=embed)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    async def _log_to_channel(
        self, guild: discord.Guild, embed: discord.Embed
    ) -> None:
        """Moderasyon log kanalına embed gönderir. Kanal yoksa sessizce atlar."""
        try:
            config = await queries.get_guild_config(self.bot.db, guild.id)
            channel_id = config.get("mod_log_channel")

            if channel_id is None:
                return

            channel = guild.get_channel(channel_id)
            if channel is None:
                return

            await channel.send(embed=embed)
        except Exception as exc:
            logger.warning(
                "Mod-log kanalına mesaj gönderilemedi (guild={}): {}", guild.id, exc
            )

    async def _log_action(
        self,
        guild_id: int,
        action: str,
        user_id: int,
        moderator_id: int,
        reason: str,
        duration: str | None = None,
    ) -> int:
        """Moderasyon eylemini veritabanına kaydeder ve vaka numarasını döndürür."""
        case_id = await queries.add_mod_log(
            self.bot.db, guild_id, action, user_id, moderator_id, reason, duration
        )
        return case_id

    # ══════════════════════════════════════════════
    #  1. KICK — Sunucudan Atma
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="kick", description="Kullanıcıyı sunucudan atar.")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @app_commands.default_permissions(kick_members=True)
    @app_commands.describe(
        kullanıcı="Atılacak kullanıcı", sebep="Atılma sebebi"
    )
    async def kick(
        self,
        ctx: commands.Context[ReoxyBot],
        kullanıcı: discord.Member,
        *,
        sebep: str = "Sebep belirtilmedi",
    ) -> None:
        """Belirtilen kullanıcıyı sunucudan atar."""
        sebep = sebep[:512]

        # Yetki hiyerarşisi kontrolü
        hierarchy_error = check_hierarchy(
            ctx.author, kullanıcı, ctx.guild.me, "sunucudan atma"
        )
        if hierarchy_error:
            return await ctx.send(embed=hierarchy_error)

        # DM bildirimi
        dm_embed = dm_notification_embed(
            action=ActionType.KICK,
            guild_name=ctx.guild.name,
            reason=sebep,
        )
        dm_sent = await self._send_dm(kullanıcı, dm_embed)

        # Kullanıcıyı at
        await kullanıcı.kick(reason=sebep)
        logger.info(
            "Kullanıcı atıldı: {} (ID: {}) | Moderatör: {} | Sebep: {}",
            kullanıcı, kullanıcı.id, ctx.author, sebep,
        )

        # Yanıt
        embed = mod_action_embed(
            action=ActionType.KICK,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            extra_fields=[("📩 DM Bildirimi", "Gönderildi" if dm_sent else "Gönderilemedi", True)],
        )
        await ctx.send(embed=embed)

        # Mod-log kanalına gönder
        case_id = await self._log_action(
            ctx.guild.id, ActionType.KICK, kullanıcı.id, ctx.author.id, sebep
        )
        log_embed = mod_log_embed(
            action=ActionType.KICK,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            case_id=case_id,
        )
        await self._log_to_channel(ctx.guild, log_embed)

    # ══════════════════════════════════════════════
    #  2. BAN — Yasaklama
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="ban", description="Kullanıcıyı sunucudan yasaklar.")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(
        kullanıcı="Yasaklanacak kullanıcı",
        mesaj_silme_günü="Silinecek mesaj günü (0-7)",
        sebep="Yasaklama sebebi",
    )
    async def ban(
        self,
        ctx: commands.Context[ReoxyBot],
        kullanıcı: discord.Member,
        mesaj_silme_günü: int = 0,
        *,
        sebep: str = "Sebep belirtilmedi",
    ) -> None:
        """Belirtilen kullanıcıyı sunucudan yasaklar."""
        sebep = sebep[:512]

        # Mesaj silme günü doğrulaması
        if not 0 <= mesaj_silme_günü <= 7:
            return await ctx.send(
                embed=error_embed("Geçersiz Parametre", "Mesaj silme günü **0 ile 7** arasında olmalıdır.")
            )

        # Yetki hiyerarşisi kontrolü
        hierarchy_error = check_hierarchy(
            ctx.author, kullanıcı, ctx.guild.me, "yasaklama"
        )
        if hierarchy_error:
            return await ctx.send(embed=hierarchy_error)

        # DM bildirimi
        dm_embed = dm_notification_embed(
            action=ActionType.BAN, guild_name=ctx.guild.name, reason=sebep
        )
        dm_sent = await self._send_dm(kullanıcı, dm_embed)

        # Kullanıcıyı yasakla
        await kullanıcı.ban(reason=sebep, delete_message_days=mesaj_silme_günü)
        logger.info(
            "Kullanıcı yasaklandı: {} (ID: {}) | Moderatör: {} | Sebep: {}",
            kullanıcı, kullanıcı.id, ctx.author, sebep,
        )

        # Yanıt
        embed = mod_action_embed(
            action=ActionType.BAN,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            extra_fields=[
                ("🗑️ Mesaj Silme", f"Son {mesaj_silme_günü} gün", True),
                ("📩 DM Bildirimi", "Gönderildi" if dm_sent else "Gönderilemedi", True),
            ],
        )
        await ctx.send(embed=embed)

        # Log
        case_id = await self._log_action(
            ctx.guild.id, ActionType.BAN, kullanıcı.id, ctx.author.id, sebep
        )
        log_embed = mod_log_embed(
            action=ActionType.BAN,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            case_id=case_id,
        )
        await self._log_to_channel(ctx.guild, log_embed)

    # ══════════════════════════════════════════════
    #  3. SOFTBAN — Hızlı Temizlik
    # ══════════════════════════════════════════════

    @commands.hybrid_command(
        name="softban",
        description="Kullanıcıyı yasaklayıp mesajlarını siler ve yasağı kaldırır.",
    )
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(
        kullanıcı="Hedef kullanıcı",
        gün="Mesaj silme günü (1-7)",
        sebep="Sebep",
    )
    async def softban(
        self,
        ctx: commands.Context[ReoxyBot],
        kullanıcı: discord.Member,
        gün: int = 7,
        *,
        sebep: str = "Sebep belirtilmedi",
    ) -> None:
        """Kullanıcıyı yasaklayıp mesajlarını siler, ardından yasağı kaldırır."""
        sebep = sebep[:512]

        # Gün doğrulaması
        if not 1 <= gün <= 7:
            return await ctx.send(
                embed=error_embed("Geçersiz Parametre", "Mesaj silme günü **1 ile 7** arasında olmalıdır.")
            )

        # Yetki hiyerarşisi kontrolü
        hierarchy_error = check_hierarchy(
            ctx.author, kullanıcı, ctx.guild.me, "soft-ban"
        )
        if hierarchy_error:
            return await ctx.send(embed=hierarchy_error)

        # DM bildirimi
        dm_embed = dm_notification_embed(
            action=ActionType.SOFTBAN, guild_name=ctx.guild.name, reason=sebep
        )
        dm_sent = await self._send_dm(kullanıcı, dm_embed)

        # Ban → Mesajları sil → Unban
        await ctx.guild.ban(kullanıcı, reason=f"Softban: {sebep}", delete_message_days=gün)
        await ctx.guild.unban(kullanıcı, reason="Softban — yasak otomatik kaldırıldı")
        logger.info(
            "Softban uygulandı: {} (ID: {}) | {} gün mesaj silindi | Moderatör: {}",
            kullanıcı, kullanıcı.id, gün, ctx.author,
        )

        # Yanıt
        embed = mod_action_embed(
            action=ActionType.SOFTBAN,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            extra_fields=[
                ("🗑️ Silinen Mesajlar", f"Son {gün} gün", True),
                ("📩 DM Bildirimi", "Gönderildi" if dm_sent else "Gönderilemedi", True),
            ],
        )
        await ctx.send(embed=embed)

        # Log
        case_id = await self._log_action(
            ctx.guild.id, ActionType.SOFTBAN, kullanıcı.id, ctx.author.id, sebep
        )
        log_embed = mod_log_embed(
            action=ActionType.SOFTBAN,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            case_id=case_id,
        )
        await self._log_to_channel(ctx.guild, log_embed)

    # ══════════════════════════════════════════════
    #  4. FORCEBAN — ID ile Yasaklama
    # ══════════════════════════════════════════════

    @commands.hybrid_command(
        name="forceban",
        description="Sunucuda olmayan bir kullanıcıyı ID ile yasaklar.",
    )
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(
        kullanıcı_id="Yasaklanacak kullanıcı ID'si",
        sebep="Sebep",
    )
    async def forceban(
        self,
        ctx: commands.Context[ReoxyBot],
        kullanıcı_id: str,
        *,
        sebep: str = "Sebep belirtilmedi",
    ) -> None:
        """Sunucuda bulunmayan bir kullanıcıyı ID ile yasaklar."""
        sebep = sebep[:512]

        # ID doğrulama
        try:
            user_id = int(kullanıcı_id)
        except ValueError:
            return await ctx.send(
                embed=error_embed(
                    "Geçersiz ID",
                    "Lütfen geçerli bir sayısal kullanıcı ID'si girin.",
                )
            )

        # Zaten yasaklı mı?
        try:
            await ctx.guild.fetch_ban(discord.Object(id=user_id))
            return await ctx.send(
                embed=error_embed("Zaten Yasaklı", "Bu kullanıcı zaten yasaklı listesinde.")
            )
        except discord.NotFound:
            pass  # Yasaklı değil, devam et

        # Yasakla
        await ctx.guild.ban(discord.Object(id=user_id), reason=f"Forceban: {sebep}")
        logger.info(
            "Forceban uygulandı: ID {} | Moderatör: {} | Sebep: {}",
            user_id, ctx.author, sebep,
        )

        # Kullanıcı bilgisini almaya çalış (embed için)
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            user = None

        # Yanıt
        if user:
            embed = mod_action_embed(
                action=ActionType.FORCEBAN,
                user=user,
                moderator=ctx.author,
                reason=sebep,
            )
        else:
            embed = success_embed(
                "Force-Ban Uygulandı",
                f"**ID: `{user_id}`** başarıyla yasaklandı.\n\n📝 **Sebep:** {sebep}",
            )
        await ctx.send(embed=embed)

        # Log
        log_user = user or discord.Object(id=user_id)
        case_id = await self._log_action(
            ctx.guild.id, ActionType.FORCEBAN, user_id, ctx.author.id, sebep
        )
        log_embed = mod_log_embed(
            action=ActionType.FORCEBAN,
            user=log_user,
            moderator=ctx.author,
            reason=sebep,
            case_id=case_id,
        )
        await self._log_to_channel(ctx.guild, log_embed)

    # ══════════════════════════════════════════════
    #  5. TIMEOUT — Susturma
    # ══════════════════════════════════════════════

    @commands.hybrid_command(
        name="timeout", description="Kullanıcıyı belirli bir süre susturur."
    )
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        kullanıcı="Susturulacak kullanıcı",
        süre="Süre (örn: 10m, 1h, 2d, 1d12h)",
        sebep="Sebep",
    )
    async def timeout(
        self,
        ctx: commands.Context[ReoxyBot],
        kullanıcı: discord.Member,
        süre: str,
        *,
        sebep: str = "Sebep belirtilmedi",
    ) -> None:
        """Kullanıcıyı belirtilen süre boyunca susturur (timeout)."""
        sebep = sebep[:512]

        # Süre çözümleme
        try:
            duration_td = parse_duration(süre)
        except TimeParseError as exc:
            return await ctx.send(
                embed=error_embed("Geçersiz Süre", str(exc))
            )

        # Maksimum 28 gün kontrolü
        max_duration = datetime.timedelta(days=28)
        if duration_td > max_duration:
            return await ctx.send(
                embed=error_embed(
                    "Süre Aşıldı",
                    "Susturma süresi en fazla **28 gün** olabilir.",
                )
            )

        # Yetki hiyerarşisi kontrolü
        hierarchy_error = check_hierarchy(
            ctx.author, kullanıcı, ctx.guild.me, "susturma"
        )
        if hierarchy_error:
            return await ctx.send(embed=hierarchy_error)

        formatted = format_duration(duration_td)

        # DM bildirimi
        dm_embed = dm_notification_embed(
            action=ActionType.TIMEOUT,
            guild_name=ctx.guild.name,
            reason=sebep,
            duration=formatted,
        )
        dm_sent = await self._send_dm(kullanıcı, dm_embed)

        # Sustur
        await kullanıcı.timeout(duration_td, reason=sebep)
        logger.info(
            "Timeout uygulandı: {} (ID: {}) | Süre: {} | Moderatör: {}",
            kullanıcı, kullanıcı.id, formatted, ctx.author,
        )

        # Yanıt
        embed = mod_action_embed(
            action=ActionType.TIMEOUT,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            duration=formatted,
            extra_fields=[("📩 DM Bildirimi", "Gönderildi" if dm_sent else "Gönderilemedi", True)],
        )
        await ctx.send(embed=embed)

        # Log
        case_id = await self._log_action(
            ctx.guild.id, ActionType.TIMEOUT, kullanıcı.id, ctx.author.id,
            sebep, duration=formatted,
        )
        log_embed = mod_log_embed(
            action=ActionType.TIMEOUT,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            duration=formatted,
            case_id=case_id,
        )
        await self._log_to_channel(ctx.guild, log_embed)

    # ══════════════════════════════════════════════
    #  6. UNTIMEOUT — Susturma Kaldırma
    # ══════════════════════════════════════════════

    @commands.hybrid_command(
        name="untimeout", description="Kullanıcının susturmasını kaldırır."
    )
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        kullanıcı="Susturması kaldırılacak kullanıcı",
        sebep="Sebep",
    )
    async def untimeout(
        self,
        ctx: commands.Context[ReoxyBot],
        kullanıcı: discord.Member,
        *,
        sebep: str = "Sebep belirtilmedi",
    ) -> None:
        """Kullanıcının aktif timeout süresini kaldırır."""
        sebep = sebep[:512]

        # Kullanıcı gerçekten susturulmuş mu?
        if not kullanıcı.is_timed_out():
            return await ctx.send(
                embed=error_embed(
                    "İşlem Gerekli Değil",
                    f"**{kullanıcı.display_name}** şu anda susturulmuş değil.",
                )
            )

        # Susturmayı kaldır
        await kullanıcı.timeout(None, reason=sebep)
        logger.info(
            "Untimeout uygulandı: {} (ID: {}) | Moderatör: {}",
            kullanıcı, kullanıcı.id, ctx.author,
        )

        # Yanıt
        embed = mod_action_embed(
            action=ActionType.UNTIMEOUT,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
        )
        await ctx.send(embed=embed)

        # Log
        case_id = await self._log_action(
            ctx.guild.id, ActionType.UNTIMEOUT, kullanıcı.id, ctx.author.id, sebep
        )
        log_embed = mod_log_embed(
            action=ActionType.UNTIMEOUT,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            case_id=case_id,
        )
        await self._log_to_channel(ctx.guild, log_embed)

    # ══════════════════════════════════════════════
    #  7. UNBAN — Yasak Kaldırma
    # ══════════════════════════════════════════════

    @commands.hybrid_command(
        name="unban", description="Kullanıcının yasağını kaldırır."
    )
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(
        kullanıcı_id="Yasağı kaldırılacak kullanıcı ID'si",
        sebep="Sebep",
    )
    async def unban(
        self,
        ctx: commands.Context[ReoxyBot],
        kullanıcı_id: str,
        *,
        sebep: str = "Sebep belirtilmedi",
    ) -> None:
        """Yasaklanmış bir kullanıcının yasağını kaldırır."""
        sebep = sebep[:512]

        # ID doğrulama
        try:
            user_id = int(kullanıcı_id)
        except ValueError:
            return await ctx.send(
                embed=error_embed(
                    "Geçersiz ID",
                    "Lütfen geçerli bir sayısal kullanıcı ID'si girin.",
                )
            )

        # Yasaklı mı kontrolü
        try:
            await ctx.guild.fetch_ban(discord.Object(id=user_id))
        except discord.NotFound:
            return await ctx.send(
                embed=error_embed(
                    "Kullanıcı Bulunamadı",
                    "Bu kullanıcı yasaklı listesinde bulunamadı.",
                )
            )

        # Yasağı kaldır
        await ctx.guild.unban(discord.Object(id=user_id), reason=sebep)
        logger.info(
            "Unban uygulandı: ID {} | Moderatör: {} | Sebep: {}",
            user_id, ctx.author, sebep,
        )

        # Kullanıcı bilgisini almaya çalış
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            user = None

        # Yanıt
        if user:
            embed = mod_action_embed(
                action=ActionType.UNBAN,
                user=user,
                moderator=ctx.author,
                reason=sebep,
            )
        else:
            embed = success_embed(
                "Yasak Kaldırıldı",
                f"**ID: `{user_id}`** kullanıcısının yasağı kaldırıldı.\n\n📝 **Sebep:** {sebep}",
            )
        await ctx.send(embed=embed)

        # Log
        log_user = user or discord.Object(id=user_id)
        case_id = await self._log_action(
            ctx.guild.id, ActionType.UNBAN, user_id, ctx.author.id, sebep
        )
        log_embed = mod_log_embed(
            action=ActionType.UNBAN,
            user=log_user,
            moderator=ctx.author,
            reason=sebep,
            case_id=case_id,
        )
        await self._log_to_channel(ctx.guild, log_embed)

    # ══════════════════════════════════════════════
    #  8. WARN — Uyarı Sistemi
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="warn", description="Kullanıcıya uyarı verir.")
    @commands.has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        kullanıcı="Uyarılacak kullanıcı", sebep="Uyarı sebebi"
    )
    async def warn(
        self,
        ctx: commands.Context[ReoxyBot],
        kullanıcı: discord.Member,
        *,
        sebep: str,
    ) -> None:
        """Kullanıcıya uyarı verir. Eşik aşılırsa otomatik ceza uygulanır."""
        sebep = sebep[:512]

        # Yetki hiyerarşisi kontrolü
        hierarchy_error = check_hierarchy(
            ctx.author, kullanıcı, ctx.guild.me, "uyarı verme"
        )
        if hierarchy_error:
            return await ctx.send(embed=hierarchy_error)

        # Veritabanına uyarıyı ekle
        warning_id = await queries.add_warning(
            self.bot.db, ctx.guild.id, kullanıcı.id, ctx.author.id, sebep
        )

        # Aktif uyarı sayısını al
        active_warnings = await queries.get_active_warnings(
            self.bot.db, ctx.guild.id, kullanıcı.id
        )
        warn_count = len(active_warnings)

        # Sunucu ayarlarını al
        config = await queries.get_guild_config(self.bot.db, ctx.guild.id)
        warn_threshold = config.get("warn_threshold", 3)
        warn_action = config.get("warn_action", "timeout")
        mute_duration = config.get("mute_duration", 3600)

        # DM bildirimi
        dm_embed = dm_notification_embed(
            action=ActionType.WARN, guild_name=ctx.guild.name, reason=sebep
        )
        await self._send_dm(kullanıcı, dm_embed)

        # Yanıt (aktif uyarı sayısıyla birlikte)
        embed = mod_action_embed(
            action=ActionType.WARN,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            extra_fields=[
                (f"{Emojis.WARNING} Aktif Uyarı", f"**{warn_count}** / {warn_threshold}", True),
                ("🆔 Uyarı ID", f"`#{warning_id}`", True),
            ],
        )
        await ctx.send(embed=embed)

        # Log
        case_id = await self._log_action(
            ctx.guild.id, ActionType.WARN, kullanıcı.id, ctx.author.id, sebep
        )
        log_embed = mod_log_embed(
            action=ActionType.WARN,
            user=kullanıcı,
            moderator=ctx.author,
            reason=sebep,
            case_id=case_id,
        )
        await self._log_to_channel(ctx.guild, log_embed)

        # ── Eşik kontrolü: Otomatik ceza ──
        if warn_count >= warn_threshold:
            auto_reason = f"Otomatik ceza: {warn_count} uyarıya ulaşıldı ({warn_count}/{warn_threshold})"

            if warn_action == "timeout":
                duration_td = datetime.timedelta(seconds=mute_duration)
                formatted = format_duration(duration_td)

                try:
                    await kullanıcı.timeout(duration_td, reason=auto_reason)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    logger.warning("Otomatik timeout uygulanamadı: {} — {}", kullanıcı.id, exc)
                    return

                # Otomatik ceza bildirimi — kanala
                auto_embed = success_embed(
                    "Otomatik Ceza Uygulandı",
                    f"**{kullanıcı.mention}** uyarı eşiğine ulaştı "
                    f"(**{warn_count}/{warn_threshold}**).\n\n"
                    f"Otomatik olarak **{formatted}** süreyle susturuldu.",
                )
                await ctx.send(embed=auto_embed)

                # DM — otomatik ceza
                auto_dm = dm_notification_embed(
                    action=ActionType.TIMEOUT,
                    guild_name=ctx.guild.name,
                    reason=auto_reason,
                    duration=formatted,
                )
                await self._send_dm(kullanıcı, auto_dm)

                # Log — otomatik ceza
                auto_case = await self._log_action(
                    ctx.guild.id, ActionType.TIMEOUT, kullanıcı.id,
                    self.bot.user.id, auto_reason, duration=formatted,
                )
                auto_log = mod_log_embed(
                    action=ActionType.TIMEOUT,
                    user=kullanıcı,
                    moderator=ctx.guild.me,
                    reason=auto_reason,
                    duration=formatted,
                    case_id=auto_case,
                )
                await self._log_to_channel(ctx.guild, auto_log)

            elif warn_action == "ban":
                # DM — ban öncesinde gönder
                auto_dm = dm_notification_embed(
                    action=ActionType.BAN,
                    guild_name=ctx.guild.name,
                    reason=auto_reason,
                )
                await self._send_dm(kullanıcı, auto_dm)

                try:
                    await kullanıcı.ban(reason=auto_reason)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    logger.warning("Otomatik ban uygulanamadı: {} — {}", kullanıcı.id, exc)
                    return

                # Otomatik ceza bildirimi — kanala
                auto_embed = success_embed(
                    "Otomatik Ceza Uygulandı",
                    f"**{kullanıcı.mention}** uyarı eşiğine ulaştı "
                    f"(**{warn_count}/{warn_threshold}**).\n\n"
                    f"Otomatik olarak **sunucudan yasaklandı**.",
                )
                await ctx.send(embed=auto_embed)

                # Log — otomatik ceza
                auto_case = await self._log_action(
                    ctx.guild.id, ActionType.BAN, kullanıcı.id,
                    self.bot.user.id, auto_reason,
                )
                auto_log = mod_log_embed(
                    action=ActionType.BAN,
                    user=kullanıcı,
                    moderator=ctx.guild.me,
                    reason=auto_reason,
                    case_id=auto_case,
                )
                await self._log_to_channel(ctx.guild, auto_log)

    # ══════════════════════════════════════════════
    #  9. WARNINGS — Uyarı Listesi
    # ══════════════════════════════════════════════

    @commands.hybrid_command(
        name="warnings", description="Kullanıcının uyarılarını listeler."
    )
    @commands.has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(kullanıcı="Uyarıları görüntülenecek kullanıcı")
    async def warnings(
        self,
        ctx: commands.Context[ReoxyBot],
        kullanıcı: discord.Member,
    ) -> None:
        """Belirtilen kullanıcının aktif uyarılarını listeler."""

        active_warns = await queries.get_active_warnings(
            self.bot.db, ctx.guild.id, kullanıcı.id
        )
        embed = warn_list_embed(
            user=kullanıcı, warnings=active_warns, guild_name=ctx.guild.name
        )
        await ctx.send(embed=embed)

    # ══════════════════════════════════════════════
    #  10. DELWARN — Uyarı Silme
    # ══════════════════════════════════════════════

    @commands.hybrid_command(
        name="delwarn", description="Belirli bir uyarıyı siler."
    )
    @commands.has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(uyarı_id="Silinecek uyarı ID'si")
    async def delwarn(
        self,
        ctx: commands.Context[ReoxyBot],
        uyarı_id: int,
    ) -> None:
        """Belirtilen ID'ye sahip uyarıyı deaktive eder (siler)."""

        result = await queries.deactivate_warning(self.bot.db, uyarı_id, ctx.guild.id)

        if not result:
            return await ctx.send(
                embed=error_embed(
                    "Uyarı Bulunamadı",
                    f"**`#{uyarı_id}`** numaralı uyarı bulunamadı veya zaten silinmiş.",
                )
            )

        await ctx.send(
            embed=success_embed(
                "Uyarı Silindi",
                f"**`#{uyarı_id}`** numaralı uyarı başarıyla silindi.",
            )
        )

        # Log
        case_id = await self._log_action(
            ctx.guild.id, ActionType.DELWARN, 0, ctx.author.id,
            f"Uyarı #{uyarı_id} silindi",
        )
        log_embed = mod_log_embed(
            action=ActionType.DELWARN,
            user=discord.Object(id=0),
            moderator=ctx.author,
            reason=f"Uyarı #{uyarı_id} silindi",
            case_id=case_id,
        )
        await self._log_to_channel(ctx.guild, log_embed)

    # ══════════════════════════════════════════════
    #  11. CLEARWARNS — Uyarı Sıfırlama
    # ══════════════════════════════════════════════

    @commands.hybrid_command(
        name="clearwarns",
        description="Kullanıcının tüm uyarılarını siler.",
    )
    @commands.has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(kullanıcı="Uyarıları silinecek kullanıcı")
    async def clearwarns(
        self,
        ctx: commands.Context[ReoxyBot],
        kullanıcı: discord.Member,
    ) -> None:
        """Belirtilen kullanıcının tüm aktif uyarılarını siler."""

        cleared_count = await queries.clear_warnings(
            self.bot.db, ctx.guild.id, kullanıcı.id
        )

        if cleared_count == 0:
            return await ctx.send(
                embed=error_embed(
                    "Uyarı Bulunamadı",
                    f"**{kullanıcı.display_name}** adlı kullanıcının aktif uyarısı bulunmuyor.",
                )
            )

        await ctx.send(
            embed=success_embed(
                "Uyarılar Temizlendi",
                f"**{kullanıcı.display_name}** adlı kullanıcının "
                f"**{cleared_count}** uyarısı başarıyla silindi.",
            )
        )

        # Log
        case_id = await self._log_action(
            ctx.guild.id, ActionType.CLEARWARNS, kullanıcı.id, ctx.author.id,
            f"{cleared_count} uyarı temizlendi",
        )
        log_embed = mod_log_embed(
            action=ActionType.CLEARWARNS,
            user=kullanıcı,
            moderator=ctx.author,
            reason=f"{cleared_count} uyarı temizlendi",
            case_id=case_id,
        )
        await self._log_to_channel(ctx.guild, log_embed)

    # ══════════════════════════════════════════════
    #  12. MODLOG — Log Kanalı Ayarlama
    # ══════════════════════════════════════════════

    @commands.hybrid_command(
        name="modlog", description="Moderasyon log kanalını ayarlar."
    )
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(kanal="Moderasyon loglarının gönderileceği kanal")
    async def modlog(
        self,
        ctx: commands.Context[ReoxyBot],
        kanal: discord.TextChannel,
    ) -> None:
        """Moderasyon eylemlerinin loglanacağı kanalı ayarlar."""

        await queries.set_mod_log_channel(self.bot.db, ctx.guild.id, kanal.id)
        logger.info(
            "Mod-log kanalı ayarlandı: #{} (ID: {}) | Sunucu: {} | Ayarlayan: {}",
            kanal.name, kanal.id, ctx.guild.name, ctx.author,
        )

        await ctx.send(
            embed=success_embed(
                "Log Kanalı Ayarlandı",
                f"Moderasyon log kanalı başarıyla {kanal.mention} olarak ayarlandı.\n\n"
                f"Bundan sonra tüm moderasyon işlemleri bu kanala loglanacak.",
            )
        )


# ══════════════════════════════════════════════
#  Cog Setup
# ══════════════════════════════════════════════

async def setup(bot: ReoxyBot) -> None:
    """Moderation cog'unu bota yükler."""
    await bot.add_cog(Moderation(bot))
