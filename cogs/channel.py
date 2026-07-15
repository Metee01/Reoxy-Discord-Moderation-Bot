"""
Reoxy Bot — Kanal ve Sohbet Yönetimi Cog'u

Kanal düzenini sağlayan araçlar:
1. Purge — toplu mesaj silme (kullanıcı/tür filtresi)
2. Slowmode — yavaş mod ayarlama
3. Lock / Unlock — kanal kilitleme / açma (eski izinleri geri yükleme)
4. Nuke — kanalı mesaj geçmişiyle birlikte yenileme

Tüm komutlar guild bazında açılıp kapatılabilir ve limitler özelleştirilebilir.
Yapılandırma `/kanal` slash komut grubu ile yönetilir (automod deseni).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from utils.constants import ActionType, Emojis
from utils.embeds import error_embed, info_embed, success_embed, warning_embed
from utils.time_parser import TimeParseError, format_duration, parse_duration
from database import queries

if TYPE_CHECKING:
    from core.bot import ReoxyBot


# ══════════════════════════════════════════════
#  Nuke Onay Görünümü
# ══════════════════════════════════════════════

class NukeConfirmView(discord.ui.View):
    """Nuke komutu için butonlu onay görünümü."""

    def __init__(self, author_id: int) -> None:
        super().__init__(timeout=30)
        self.value: bool | None = None
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Bu işlemi sadece komutu kullanan kişi onaylayabilir.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Onayla", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="İptal", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.value = False
        self.stop()
        await interaction.response.defer()


# ══════════════════════════════════════════════
#  Kanal Yönetimi Cog'u
# ══════════════════════════════════════════════

class Channel(commands.Cog):
    """Kanal ve Sohbet Yönetimi — Purge, Slowmode, Lock, Unlock, Nuke."""

    def __init__(self, bot: ReoxyBot) -> None:
        self.bot = bot
        # Config cache — automod deseni
        self._config_cache: dict[int, dict] = {}

    # ══════════════════════════════════════════════
    #  Cache Yönetimi
    # ══════════════════════════════════════════════

    async def _get_config(self, guild_id: int) -> dict:
        """Kanal config'ini cache'den veya DB'den alır."""
        if guild_id not in self._config_cache:
            self._config_cache[guild_id] = await queries.get_channel_config(
                self.bot.db, guild_id
            )
        return self._config_cache[guild_id]

    def _invalidate_config(self, guild_id: int) -> None:
        """Config cache'ini temizler (ayar değiştiğinde çağrılır)."""
        self._config_cache.pop(guild_id, None)

    # ══════════════════════════════════════════════
    #  Yardımcı Metotlar
    # ══════════════════════════════════════════════

    async def _log_to_modlog(
        self, guild: discord.Guild, action: str, channel_id: int,
        moderator: discord.Member, reason: str,
    ) -> None:
        """Moderasyon log kanalına işlemi kaydeder (veritabanı + kanal)."""
        try:
            await queries.add_mod_log(
                self.bot.db, guild.id, action, channel_id, moderator.id, reason
            )
        except Exception as exc:
            logger.warning("Kanal mod-log kaydedilemedi (guild={}): {}", guild.id, exc)

    # ══════════════════════════════════════════════
    #  1. PURGE — Toplu Mesaj Silme
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="purge", description="Belirtilen sayıda mesajı siler.")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(
        sayı="Silinecek mesaj sayısı",
        kullanıcı="Sadece bu kullanıcının mesajlarını sil",
        tür="Mesaj türü filtresi",
    )
    @app_commands.choices(
        tür=[
            app_commands.Choice(name="Tümü", value="all"),
            app_commands.Choice(name="Botlar", value="bots"),
            app_commands.Choice(name="Kullanıcılar (bot olmayan)", value="humans"),
            app_commands.Choice(name="Görseller", value="images"),
            app_commands.Choice(name="Linkler", value="links"),
        ]
    )
    async def purge(
        self,
        ctx: commands.Context[ReoxyBot],
        sayı: int,
        kullanıcı: discord.Member | None = None,
        tür: app_commands.Choice[str] | None = None,
    ) -> None:
        """Belirtilen sayıda mesajı siler. Kullanıcı veya tür filtresi uygulanabilir."""

        # Config kontrolü — komut bu guild'de açık mı?
        config = await self._get_config(ctx.guild.id)
        if not config.get("purge_enabled", True):
            return await ctx.send(
                embed=error_embed(
                    "Komut Devre Dışı",
                    "Bu sunucuda **purge** komutu yönetici tarafından kapatılmış.\n"
                    "Açmak için `/kanal purge-aç` komutunu kullanın.",
                ),
                ephemeral=True,
            )

        max_messages = config.get("purge_max_messages", 1000)

        # Geçerlilik kontrolleri
        if sayı < 1:
            return await ctx.send(
                embed=error_embed("Geçersiz Değer", "Silinecek mesaj sayısı en az **1** olmalıdır."),
                ephemeral=True,
            )

        if sayı > max_messages:
            return await ctx.send(
                embed=error_embed(
                    "Limit Aşıldı",
                    f"Bu sunucuda tek seferde en fazla **{max_messages}** mesaj silinebilir.\n"
                    f"Girdiğiniz değer: **{sayı}**",
                ),
                ephemeral=True,
            )

        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        else:
            await ctx.defer()

        filter_value = tür.value if tür else "all"

        def check_fn(msg: discord.Message) -> bool:
            if kullanıcı and msg.author.id != kullanıcı.id:
                return False
            if filter_value == "bots":
                return msg.author.bot
            if filter_value == "humans":
                return not msg.author.bot
            if filter_value == "images":
                return bool(msg.attachments)
            if filter_value == "links":
                content_lower = msg.content.lower()
                return any(
                    token in content_lower
                    for token in ("http://", "https://", "www.")
                )
            return True  # "all"

        try:
            deleted = await ctx.channel.purge(limit=sayı, check=check_fn)
        except discord.HTTPException as exc:
            logger.error("Purge başarısız (guild={}): {}", ctx.guild.id, exc)
            return await ctx.send(
                embed=error_embed("Mesajlar Silinirken Hata", f"Bir hata oluştu: {exc}"),
            )

        count = len(deleted)
        reason_parts = [f"{count} mesaj silindi"]
        if kullanıcı:
            reason_parts.append(f"Kullanıcı: {kullanıcı} ({kullanıcı.id})")
        if tür:
            reason_parts.append(f"Filtre: {tür.name}")
        reason = " | ".join(reason_parts)

        msg = await ctx.send(
            embed=success_embed(
                "Mesajlar Silindi",
                f"{Emojis.TRASH} **{count}** mesaj başarıyla silindi.",
            ),
        )
        await msg.delete(delay=5)

        await self._log_to_modlog(
            ctx.guild, ActionType.PURGE, ctx.channel.id, ctx.author, reason
        )
        logger.info(
            "Purge: {} kanalında {} mesaj silindi | Moderatör: {} (guild={})",
            ctx.channel, count, ctx.author, ctx.guild.id,
        )

    # ══════════════════════════════════════════════
    #  2. SLOWMODE — Yavaş Mod
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="slowmode", description="Kanal yavaş modunu ayarlar.")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(
        süre="Yavaş mod süresi (örn: 5s, 10s, 1m, 5m, 1h) veya 0/kapat",
        kanal="Hedef kanal (belirtilmezse mevcut kanal)",
    )
    async def slowmode(
        self,
        ctx: commands.Context[ReoxyBot],
        süre: str,
        kanal: discord.TextChannel | None = None,
    ) -> None:
        """Kanalın yavaş modunu ayarlar veya kapatır."""

        # Config kontrolü
        config = await self._get_config(ctx.guild.id)
        if not config.get("slowmode_enabled", True):
            return await ctx.send(
                embed=error_embed(
                    "Komut Devre Dışı",
                    "Bu sunucuda **slowmode** komutu yönetici tarafından kapatılmış.\n"
                    "Açmak için `/kanal slowmode-aç` komutunu kullanın.",
                ),
                ephemeral=True,
            )

        max_seconds = config.get("slowmode_max_seconds", 21600)
        target = kanal or ctx.channel

        # Süre çözümleme
        if süre in ("0", "kapat", "kapalı"):
            seconds = 0
        else:
            try:
                delta = parse_duration(süre)
                seconds = int(delta.total_seconds())
            except TimeParseError:
                return await ctx.send(
                    embed=error_embed(
                        "Geçersiz Süre Formatı",
                        "Örnekler: `5s`, `30s`, `1m`, `5m`, `1h` veya kapatmak için `0`",
                    ),
                    ephemeral=True,
                )

        # Limit kontrolü (Discord maksimum 6 saat = 21600 sn)
        if seconds < 0:
            return await ctx.send(
                embed=error_embed("Geçersiz Değer", "Yavaş mod süresi negatif olamaz."),
                ephemeral=True,
            )
        if seconds > 21600:
            return await ctx.send(
                embed=error_embed(
                    "Süre Aşıldı",
                    "Yavaş mod süresi en fazla **6 saat (21600 saniye)** olabilir (Discord limiti).",
                ),
                ephemeral=True,
            )
        if seconds > max_seconds:
            return await ctx.send(
                embed=error_embed(
                    "Limit Aşıldı",
                    f"Bu sunucuda yavaş mod en fazla **{format_duration_from_seconds(max_seconds)}** olabilir.\n"
                    f"Girdiğiniz değer: **{format_duration_from_seconds(seconds)}**",
                ),
                ephemeral=True,
            )

        # Uygula
        try:
            await target.edit(slowmode_delay=seconds)
        except discord.HTTPException as exc:
            logger.error("Slowmode ayarlanamadı (guild={}): {}", ctx.guild.id, exc)
            return await ctx.send(
                embed=error_embed("Yavaş Mod Ayarlanırken Hata", f"Bir hata oluştu: {exc}"),
            )

        if seconds == 0:
            description = f"{Emojis.CLOCK} {target.mention} kanalında yavaş mod **kapatıldı**."
            reason = "Yavaş mod kapatıldı"
        else:
            formatted = format_duration_from_seconds(seconds)
            description = (
                f"{Emojis.CLOCK} {target.mention} kanalında yavaş mod **{formatted}** olarak ayarlandı."
            )
            reason = f"Yavaş mod {formatted} olarak ayarlandı"

        await ctx.send(embed=success_embed("Yavaş Mod Güncellendi", description))

        await self._log_to_modlog(
            ctx.guild, ActionType.SLOWMODE, target.id, ctx.author, reason
        )
        logger.info(
            "Slowmode: {} → {} sn | Moderatör: {} (guild={})",
            target, seconds, ctx.author, ctx.guild.id,
        )

    # ══════════════════════════════════════════════
    #  3. LOCK — Kanal Kilitleme
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="lock", description="Kanalı yazıya kapatır.")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(
        kanal="Kilitlenecek kanal (belirtilmezse mevcut kanal)",
        sebep="Kilitleme sebebi",
    )
    async def lock(
        self,
        ctx: commands.Context[ReoxyBot],
        kanal: discord.TextChannel | None = None,
        *,
        sebep: str = "Sebep belirtilmedi",
    ) -> None:
        """Belirtilen kanalı @everyone için yazıya kapatır."""
        sebep = sebep[:512]

        # Config kontrolü
        config = await self._get_config(ctx.guild.id)
        if not config.get("lock_enabled", True):
            return await ctx.send(
                embed=error_embed(
                    "Komut Devre Dışı",
                    "Bu sunucuda **lock** komutu yönetici tarafından kapatılmış.\n"
                    "Açmak için `/kanal lock-aç` komutunu kullanın.",
                ),
                ephemeral=True,
            )

        target = kanal or ctx.channel
        everyone_role = ctx.guild.default_role
        save_perms = config.get("lock_save_permissions", True)

        # Mevcut @everyone izinlerini kaydet (geri yükleme için)
        if save_perms:
            overwrite = target.overwrites_for(everyone_role)
            perm_data = {
                "send_messages": overwrite.send_messages,
                "send_messages_in_threads": overwrite.send_messages_in_threads,
                "create_public_threads": overwrite.create_public_threads,
                "add_reactions": overwrite.add_reactions,
            }
            try:
                await queries.save_channel_permissions(
                    self.bot.db, ctx.guild.id, target.id, perm_data
                )
            except Exception as exc:
                logger.warning("İzin kaydedilemedi (channel={}): {}", target.id, exc)

        # Kilitle
        try:
            await target.set_permissions(
                everyone_role, send_messages=False, reason=sebep
            )
        except discord.HTTPException as exc:
            logger.error("Kanal kilitlenemedi (guild={}): {}", ctx.guild.id, exc)
            return await ctx.send(
                embed=error_embed("Kanal Kilitlenirken Hata", f"Bir hata oluştu: {exc}"),
            )

        # Kanala bildirim
        await target.send(
            embed=warning_embed(
                "Kanal Kilitlendi",
                f"{Emojis.LOCK} Bu kanal kilitlendi.\n\n"
                f"**Sebep:** {sebep}\n**Yetkili:** {ctx.author.mention}",
            )
        )

        # Komut kanalı farklıysa ek bilgi
        if ctx.channel.id != target.id:
            await ctx.send(
                embed=success_embed(
                    "Kanal Kilitlendi",
                    f"{Emojis.LOCK} {target.mention} kanalı başarıyla kilitlendi.",
                )
            )

        await self._log_to_modlog(
            ctx.guild, ActionType.LOCK, target.id, ctx.author, sebep
        )
        logger.info(
            "Lock: {} kilitlendi | Moderatör: {} (guild={})",
            target, ctx.author, ctx.guild.id,
        )

    # ══════════════════════════════════════════════
    #  4. UNLOCK — Kanal Kilidi Açma
    # ══════════════════════════════════════════════

    @commands.hybrid_command(name="unlock", description="Kanalın kilidini açar.")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(
        kanal="Kilidi açılacak kanal (belirtilmezse mevcut kanal)",
        sebep="Açma sebebi",
    )
    async def unlock(
        self,
        ctx: commands.Context[ReoxyBot],
        kanal: discord.TextChannel | None = None,
        *,
        sebep: str = "Sebep belirtilmedi",
    ) -> None:
        """Belirtilen kanalın kilidini açar. Mümkünse eski izinleri geri yükler."""
        sebep = sebep[:512]

        # Config kontrolü (lock_enabled unlock için de geçerli)
        config = await self._get_config(ctx.guild.id)
        if not config.get("lock_enabled", True):
            return await ctx.send(
                embed=error_embed(
                    "Komut Devre Dışı",
                    "Bu sunucuda **lock/unlock** komutları yönetici tarafından kapatılmış.\n"
                    "Açmak için `/kanal lock-aç` komutunu kullanın.",
                ),
                ephemeral=True,
            )

        target = kanal or ctx.channel
        everyone_role = ctx.guild.default_role

        # Kaydedilmiş izinleri geri yükle (varsa)
        saved = await queries.get_saved_permissions(
            self.bot.db, ctx.guild.id, target.id
        )

        try:
            if saved:
                # Kaydedilmiş izinleri geri yükle
                overwrite = target.overwrites_for(everyone_role)
                overwrite.send_messages = saved.get("send_messages")
                overwrite.send_messages_in_threads = saved.get("send_messages_in_threads")
                overwrite.create_public_threads = saved.get("create_public_threads")
                overwrite.add_reactions = saved.get("add_reactions")
                await target.set_permissions(everyone_role, overwrite=overwrite, reason=sebep)
                # Geri yükleme sonrası kaydı temizle
                await queries.delete_saved_permissions(
                    self.bot.db, ctx.guild.id, target.id
                )
                restored_note = "\n*Önceki izinler geri yüklendi.*"
            else:
                # Kayıt yoksa send_messages iznini kalıta sıfırla
                await target.set_permissions(
                    everyone_role, send_messages=None, reason=sebep
                )
                restored_note = ""
        except discord.HTTPException as exc:
            logger.error("Kanal kilidi açılamadı (guild={}): {}", ctx.guild.id, exc)
            return await ctx.send(
                embed=error_embed("Kanal Kilidi Açılırken Hata", f"Bir hata oluştu: {exc}"),
            )

        # Kanala bildirim
        await target.send(
            embed=success_embed(
                "Kanal Kilidi Açıldı",
                f"{Emojis.UNLOCK} Bu kanalın kilidi açıldı.\n\n"
                f"**Sebep:** {sebep}\n**Yetkili:** {ctx.author.mention}{restored_note}",
            )
        )

        # Komut kanalı farklıysa ek bilgi
        if ctx.channel.id != target.id:
            await ctx.send(
                embed=success_embed(
                    "Kanal Kilidi Açıldı",
                    f"{Emojis.UNLOCK} {target.mention} kanalının kilidi başarıyla açıldı.",
                )
            )

        await self._log_to_modlog(
            ctx.guild, ActionType.UNLOCK, target.id, ctx.author, sebep
        )
        logger.info(
            "Unlock: {} kilidi açıldı | Moderatör: {} (guild={})",
            target, ctx.author, ctx.guild.id,
        )

    # ══════════════════════════════════════════════
    #  5. NUKE — Kanal Yenileme
    # ══════════════════════════════════════════════

    @commands.hybrid_command(
        name="nuke", description="Kanalı tüm mesajlarıyla birlikte yeniler."
    )
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(kanal="Yenilenecek kanal (belirtilmezse mevcut kanal)")
    async def nuke(
        self,
        ctx: commands.Context[ReoxyBot],
        kanal: discord.TextChannel | None = None,
    ) -> None:
        """Kanalı tüm mesajlarıyla birlikte silip, aynı ayarlarla sıfırdan oluşturur."""

        # Config kontrolü
        config = await self._get_config(ctx.guild.id)
        if not config.get("nuke_enabled", True):
            return await ctx.send(
                embed=error_embed(
                    "Komut Devre Dışı",
                    "Bu sunucuda **nuke** komutu yönetici tarafından kapatılmış.\n"
                    "Açmak için `/kanal nuke-aç` komutunu kullanın.",
                ),
                ephemeral=True,
            )

        target = kanal or ctx.channel
        require_confirm = config.get("nuke_require_confirm", True)

        # Onay gerekliyse butonlu görüşümü göster
        if require_confirm:
            view = NukeConfirmView(author_id=ctx.author.id)
            confirm_msg = await ctx.send(
                embed=warning_embed(
                    "Kanal Yenileme Onayı",
                    f"{Emojis.NUKE} **{target.mention}** kanalı tüm mesajlarıyla birlikte yenilenecek.\n\n"
                    f"⚠️ **Bu işlem geri alınamaz!**\n\nOnaylıyor musunuz?",
                ),
                view=view,
            )
            timed_out = await view.wait()

            if timed_out or view.value is None:
                for child in view.children:
                    child.disabled = True  # type: ignore[union-attr]
                await confirm_msg.edit(
                    embed=warning_embed("İşlem İptal Edildi", "⏰ Zaman aşımı, nuke iptal edildi."),
                    view=view,
                )
                return

            if not view.value:
                for child in view.children:
                    child.disabled = True  # type: ignore[union-attr]
                await confirm_msg.edit(
                    embed=info_embed("İşlem İptal Edildi", "❌ Nuke işlemi iptal edildi."),
                    view=view,
                )
                return

        # Onaylandı (veya onay gerektirmiyor) — kanalı yenile
        reason = f"Nuke: {ctx.author} ({ctx.author.id})"
        position = target.position

        try:
            # Klonla → pozisyonu koru → eskisini sil
            new_channel = await target.clone(reason=reason)
            await new_channel.edit(position=position)
            await target.delete(reason=reason)
        except discord.HTTPException as exc:
            logger.error("Nuke başarısız (guild={}): {}", ctx.guild.id, exc)
            return await ctx.send(
                embed=error_embed("Kanal Yenilenirken Hata", f"Bir hata oluştu: {exc}"),
            )

        await new_channel.send(
            embed=success_embed(
                "Kanal Yenilendi",
                f"{Emojis.NUKE} Bu kanal başarıyla yenilendi.\n\n"
                f"**Yetkili:** {ctx.author.mention}",
            )
        )

        await self._log_to_modlog(
            new_channel.guild, ActionType.NUKE, new_channel.id, ctx.author, reason
        )
        logger.info(
            "Nuke: {} → {} yenilendi | Moderatör: {} (guild={})",
            target, new_channel, ctx.author, ctx.guild.id,
        )

    # ══════════════════════════════════════════════════════════════
    #  YAPILANDIRMA KOMUTLARI — /kanal slash grubu
    # ══════════════════════════════════════════════════════════════

    kanal_group = app_commands.Group(
        name="kanal",
        description="Kanal yönetimi komut ayarları",
        default_permissions=discord.Permissions(administrator=True),
    )

    # ── Durum Görüntüleme ──

    @kanal_group.command(name="durum", description="Kanal komutlarının durumunu gösterir.")
    async def kanal_status(self, interaction: discord.Interaction) -> None:
        """Tüm kanal komutlarının açık/kapalı ve limitlerini gösterir."""
        config = await queries.get_channel_config(self.bot.db, interaction.guild.id)

        def status(enabled: bool) -> str:
            return f"{Emojis.TOGGLE_ON} **Açık**" if enabled else f"{Emojis.TOGGLE_OFF} **Kapalı**"

        description = (
            f"## {Emojis.SETTINGS} Kanal Yönetimi Ayarları\n\n"
            f"### {Emojis.TRASH} Purge (Mesaj Silme)\n"
            f"{Emojis.ARROW_RIGHT} **Durum:** {status(config['purge_enabled'])}\n"
            f"{Emojis.ARROW_RIGHT} **Maks. Mesaj:** {config['purge_max_messages']}\n\n"
            f"### {Emojis.CLOCK} Slowmode (Yavaş Mod)\n"
            f"{Emojis.ARROW_RIGHT} **Durum:** {status(config['slowmode_enabled'])}\n"
            f"{Emojis.ARROW_RIGHT} **Maks. Süre:** {format_duration_from_seconds(config['slowmode_max_seconds'])}\n\n"
            f"### {Emojis.LOCK} Lock / Unlock (Kanal Kilitleme)\n"
            f"{Emojis.ARROW_RIGHT} **Durum:** {status(config['lock_enabled'])}\n"
            f"{Emojis.ARROW_RIGHT} **İzin Kaydet:** {status(config['lock_save_permissions'])}\n\n"
            f"### {Emojis.NUKE} Nuke (Kanal Yenileme)\n"
            f"{Emojis.ARROW_RIGHT} **Durum:** {status(config['nuke_enabled'])}\n"
            f"{Emojis.ARROW_RIGHT} **Onay Gerekli:** {status(config['nuke_require_confirm'])}\n"
        )

        embed = info_embed("Kanal Yönetimi Durumu", description)
        await interaction.response.send_message(embed=embed)

    # ── Purge Aç/Kapat ──

    @kanal_group.command(name="purge-aç", description="Purge komutunu açar.")
    async def purge_enable(self, interaction: discord.Interaction) -> None:
        await queries.update_channel_config(self.bot.db, interaction.guild.id, purge_enabled=True)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Purge Açıldı",
            f"{Emojis.TOGGLE_ON} **Purge** komutu bu sunucuda **aktif** edildi.",
        )
        await interaction.response.send_message(embed=embed)

    @kanal_group.command(name="purge-kapat", description="Purge komutunu kapatır.")
    async def purge_disable(self, interaction: discord.Interaction) -> None:
        await queries.update_channel_config(self.bot.db, interaction.guild.id, purge_enabled=False)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Purge Kapatıldı",
            f"{Emojis.TOGGLE_OFF} **Purge** komutu bu sunucuda **deaktif** edildi.",
        )
        await interaction.response.send_message(embed=embed)

    @kanal_group.command(name="purge-limit", description="Purge için maksimum mesaj sayısını ayarlar.")
    @app_commands.describe(limit="Maksimum silinebilir mesaj sayısı (1-1000)")
    async def purge_limit(self, interaction: discord.Interaction, limit: int) -> None:
        if not 1 <= limit <= 1000:
            return await interaction.response.send_message(
                embed=error_embed("Geçersiz Değer", "Limit **1 ile 1000** arasında olmalıdır."),
                ephemeral=True,
            )
        await queries.update_channel_config(
            self.bot.db, interaction.guild.id, purge_max_messages=limit
        )
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Purge Limiti Güncellendi",
            f"{Emojis.SETTINGS} Purge için maksimum mesaj sayısı **{limit}** olarak ayarlandı.",
        )
        await interaction.response.send_message(embed=embed)

    # ── Slowmode Aç/Kapat ──

    @kanal_group.command(name="slowmode-aç", description="Slowmode komutunu açar.")
    async def slowmode_enable(self, interaction: discord.Interaction) -> None:
        await queries.update_channel_config(self.bot.db, interaction.guild.id, slowmode_enabled=True)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Slowmode Açıldı",
            f"{Emojis.TOGGLE_ON} **Slowmode** komutu bu sunucuda **aktif** edildi.",
        )
        await interaction.response.send_message(embed=embed)

    @kanal_group.command(name="slowmode-kapat", description="Slowmode komutunu kapatır.")
    async def slowmode_disable(self, interaction: discord.Interaction) -> None:
        await queries.update_channel_config(self.bot.db, interaction.guild.id, slowmode_enabled=False)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Slowmode Kapatıldı",
            f"{Emojis.TOGGLE_OFF} **Slowmode** komutu bu sunucuda **deaktif** edildi.",
        )
        await interaction.response.send_message(embed=embed)

    @kanal_group.command(name="slowmode-limit", description="Slowmode için maksimum süreyi ayarlar.")
    @app_commands.describe(süre="Maksimum yavaş mod süresi (örn: 30m, 1h, 6h)")
    async def slowmode_limit(self, interaction: discord.Interaction, süre: str) -> None:
        try:
            delta = parse_duration(süre)
            seconds = int(delta.total_seconds())
        except TimeParseError:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Geçersiz Süre Formatı",
                    "Örnekler: `30m`, `1h`, `6h`",
                ),
                ephemeral=True,
            )

        if not 0 <= seconds <= 21600:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Süre Aşıldı",
                    "Maksimum yavaş mod süresi **6 saatten** fazla olamaz (Discord limiti).",
                ),
                ephemeral=True,
            )

        await queries.update_channel_config(
            self.bot.db, interaction.guild.id, slowmode_max_seconds=seconds
        )
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Slowmode Limiti Güncellendi",
            f"{Emojis.SETTINGS} Maksimum yavaş mod süresi **{format_duration_from_seconds(seconds)}** olarak ayarlandı.",
        )
        await interaction.response.send_message(embed=embed)

    # ── Lock Aç/Kapat ──

    @kanal_group.command(name="lock-aç", description="Lock/Unlock komutlarını açar.")
    async def lock_enable(self, interaction: discord.Interaction) -> None:
        await queries.update_channel_config(self.bot.db, interaction.guild.id, lock_enabled=True)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Lock/Unlock Açıldı",
            f"{Emojis.TOGGLE_ON} **Lock/Unlock** komutları bu sunucuda **aktif** edildi.",
        )
        await interaction.response.send_message(embed=embed)

    @kanal_group.command(name="lock-kapat", description="Lock/Unlock komutlarını kapatır.")
    async def lock_disable(self, interaction: discord.Interaction) -> None:
        await queries.update_channel_config(self.bot.db, interaction.guild.id, lock_enabled=False)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Lock/Unlock Kapatıldı",
            f"{Emojis.TOGGLE_OFF} **Lock/Unlock** komutları bu sunucuda **deaktif** edildi.",
        )
        await interaction.response.send_message(embed=embed)

    @kanal_group.command(name="lock-kaydet", description="Lock sırasında eski izinlerin kaydedilip kaydedilmeyeceğini açar/kapatır.")
    @app_commands.describe(durum="Açık ise lock sırasında izinler kaydedilir (önerilen)")
    async def lock_save_toggle(self, interaction: discord.Interaction, durum: bool) -> None:
        await queries.update_channel_config(
            self.bot.db, interaction.guild.id, lock_save_permissions=durum
        )
        self._invalidate_config(interaction.guild.id)
        if durum:
            desc = f"{Emojis.TOGGLE_ON} Lock sırasında **izinler kaydedilecek** ve unlock'ta geri yüklenecek."
        else:
            desc = f"{Emojis.TOGGLE_OFF} Lock sırasında izinler kaydedilmeyecek — unlock sadece sıfırlama yapar."
        embed = success_embed("İzin Kaydetme Ayarı Güncellendi", desc)
        await interaction.response.send_message(embed=embed)

    # ── Nuke Aç/Kapat ──

    @kanal_group.command(name="nuke-aç", description="Nuke komutunu açar.")
    async def nuke_enable(self, interaction: discord.Interaction) -> None:
        await queries.update_channel_config(self.bot.db, interaction.guild.id, nuke_enabled=True)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Nuke Açıldı",
            f"{Emojis.TOGGLE_ON} **Nuke** komutu bu sunucuda **aktif** edildi.",
        )
        await interaction.response.send_message(embed=embed)

    @kanal_group.command(name="nuke-kapat", description="Nuke komutunu kapatır.")
    async def nuke_disable(self, interaction: discord.Interaction) -> None:
        await queries.update_channel_config(self.bot.db, interaction.guild.id, nuke_enabled=False)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Nuke Kapatıldı",
            f"{Emojis.TOGGLE_OFF} **Nuke** komutu bu sunucuda **deaktif** edildi.",
        )
        await interaction.response.send_message(embed=embed)

    @kanal_group.command(name="nuke-onay", description="Nuke için buton onayının gerekli olup olmadığını ayarlar.")
    @app_commands.describe(durum="Açık ise nuke öncesi onay butonu gösterilir (önerilen)")
    async def nuke_confirm_toggle(self, interaction: discord.Interaction, durum: bool) -> None:
        await queries.update_channel_config(
            self.bot.db, interaction.guild.id, nuke_require_confirm=durum
        )
        self._invalidate_config(interaction.guild.id)
        if durum:
            desc = f"{Emojis.TOGGLE_ON} Nuke öncesi **onay butonu** gösterilecek."
        else:
            desc = f"{Emojis.TOGGLE_OFF} Nuke **anında** uygulanacak (onay istenmeyecek)."
        embed = success_embed("Nuke Onay Ayarı Güncellendi", desc)
        await interaction.response.send_message(embed=embed)


# ══════════════════════════════════════════════
#  Yardımcı Fonksiyon (saniye → okunabilir süre)
# ══════════════════════════════════════════════

def format_duration_from_seconds(seconds: int) -> str:
    """
    Saniyeyi okunabilir Türkçe süre string'ine çevirir.
    time_parser.format_duration ile uyumlu (timedelta bekler).
    """
    from datetime import timedelta
    return format_duration(timedelta(seconds=seconds))


# ══════════════════════════════════════════════
#  Cog Setup
# ══════════════════════════════════════════════

async def setup(bot: ReoxyBot) -> None:
    """Channel cog'unu bota yükler."""
    await bot.add_cog(Channel(bot))
