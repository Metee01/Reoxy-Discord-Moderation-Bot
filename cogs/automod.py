"""
Reoxy Bot — Otomatik Moderasyon (Automod) Cog'u

5 filtre sistemi:
1. Küfür/argo filtresi (kelime listesi)
2. Reklam/link engeli (discord.gg + URL)
3. Büyük harf (caps lock) engeli
4. Spam koruması (mesaj flood tespiti)
5. Emoji ve etiket (mention) spamı

Mesajlar gerçek zamanlı olarak on_message event'i ile taranır.
Yapılandırma komutları slash komut grubu olarak çalışır.
"""

from __future__ import annotations

import datetime
import re
import time
from collections import defaultdict
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands, tasks
from loguru import logger

from utils.constants import ActionType, Emojis
from utils.embeds import (
    dm_notification_embed,
    error_embed,
    info_embed,
    mod_log_embed,
    success_embed,
    warning_embed,
)
from database import queries

if TYPE_CHECKING:
    from core.bot import ReoxyBot


# ══════════════════════════════════════════════
#  Regex Desenleri
# ══════════════════════════════════════════════

# Discord davet linkleri
INVITE_PATTERN = re.compile(
    r"(discord\.gg|discord\.com/invite|discordapp\.com/invite)/[a-zA-Z0-9\-]+",
    re.IGNORECASE,
)

# Genel URL'ler
URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+|www\.[^\s<>\"']+",
    re.IGNORECASE,
)

# Emoji desenleri — hem Unicode hem özel Discord emojileri
CUSTOM_EMOJI_PATTERN = re.compile(r"<a?:\w+:\d+>")
UNICODE_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Yüz ifadeleri
    "\U0001F300-\U0001F5FF"  # Semboller ve piktogramlar
    "\U0001F680-\U0001F6FF"  # Ulaşım ve harita
    "\U0001F1E0-\U0001F1FF"  # Bayraklar
    "\U00002702-\U000027B0"  # Çeşitli semboller
    "\U0001F900-\U0001F9FF"  # Ek yüz ifadeleri
    "\U0001FA00-\U0001FA6F"  # Satranç, vb.
    "\U0001FA70-\U0001FAFF"  # Yeni semboller
    "\U00002600-\U000026FF"  # Çeşitli semboller
    "\U0000FE00-\U0000FE0F"  # Varyasyon seçicileri
    "\U0000200D"             # ZWJ
    "\U00002B50"             # Yıldız
    "\U0000231A-\U0000231B"  # Saat
    "\U000023E9-\U000023F3"  # İleri/geri
    "\U000025AA-\U000025AB"  # Kareler
    "\U000025FB-\U000025FE"  # Kareler 2
    "]+",
    re.UNICODE,
)


class AutoMod(commands.Cog):
    """Otomatik Moderasyon — Küfür, link, caps, spam ve emoji/mention filtreleri."""

    def __init__(self, bot: ReoxyBot) -> None:
        self.bot = bot
        # Cache'ler
        self._word_cache: dict[int, set[str]] = {}
        self._config_cache: dict[int, dict] = {}

        # Spam koruması: guild_id -> user_id -> [timestamp listesi]
        self._spam_tracker: dict[int, dict[int, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # Spam cleanup task
        self._cleanup_task.start()

    def cog_unload(self) -> None:
        """Cog kaldırılırken cleanup task'ı durdur."""
        self._cleanup_task.cancel()

    @tasks.loop(minutes=2)
    async def _cleanup_task(self) -> None:
        """Eski spam kayıtlarını temizler (bellek yönetimi)."""
        now = time.time()
        guilds_to_clean = []
        for guild_id, users in self._spam_tracker.items():
            users_to_clean = []
            for user_id, timestamps in users.items():
                # 60 saniyeden eski kayıtları temizle
                fresh = [t for t in timestamps if now - t < 60]
                if fresh:
                    users[user_id] = fresh
                else:
                    users_to_clean.append(user_id)
            for uid in users_to_clean:
                del users[uid]
            if not users:
                guilds_to_clean.append(guild_id)
        for gid in guilds_to_clean:
            del self._spam_tracker[gid]

    @_cleanup_task.before_loop
    async def _before_cleanup(self) -> None:
        await self.bot.wait_until_ready()

    # ══════════════════════════════════════════════
    #  Cache Yönetimi
    # ══════════════════════════════════════════════

    async def _get_config(self, guild_id: int) -> dict:
        """Automod config'ini cache'den veya DB'den alır."""
        if guild_id not in self._config_cache:
            self._config_cache[guild_id] = await queries.get_automod_config(
                self.bot.db, guild_id
            )
        return self._config_cache[guild_id]

    def _invalidate_config(self, guild_id: int) -> None:
        """Config cache'ini temizler (ayar değiştiğinde çağrılır)."""
        self._config_cache.pop(guild_id, None)

    async def _get_words(self, guild_id: int) -> set[str]:
        """Yasaklı kelime listesini cache'den veya DB'den alır."""
        if guild_id not in self._word_cache:
            words = await queries.get_automod_words(self.bot.db, guild_id)
            self._word_cache[guild_id] = set(words)
        return self._word_cache[guild_id]

    def _invalidate_words(self, guild_id: int) -> None:
        """Kelime cache'ini temizler."""
        self._word_cache.pop(guild_id, None)

    # ══════════════════════════════════════════════
    #  Yardımcı Metotlar
    # ══════════════════════════════════════════════

    async def _is_exempt(
        self, member: discord.Member, filter_type: str
    ) -> bool:
        """
        Kullanıcının filtreden muaf olup olmadığını kontrol eder.

        Muaf durumlar: Bot, sunucu sahibi, administrator, manage_messages, muaf rol
        """
        if member.bot:
            return True
        if member.guild.owner_id == member.id:
            return True
        if member.guild_permissions.administrator:
            return True
        if member.guild_permissions.manage_messages:
            return True

        role_ids = [r.id for r in member.roles]
        return await queries.is_role_whitelisted(
            self.bot.db, member.guild.id, role_ids, filter_type
        )

    async def _send_automod_log(
        self,
        guild: discord.Guild,
        action: str,
        user: discord.Member,
        reason: str,
        message_content: str = "",
    ) -> None:
        """Automod log kanalına detaylı embed gönderir."""
        config = await self._get_config(guild.id)
        channel_id = config.get("log_channel")

        if channel_id is None:
            guild_config = await queries.get_guild_config(self.bot.db, guild.id)
            channel_id = guild_config.get("mod_log_channel")

        if channel_id is None:
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            return

        truncated = (
            message_content[:200] + "..." if len(message_content) > 200 else message_content
        )

        embed = mod_log_embed(
            action=action,
            user=user,
            moderator=guild.me,
            reason=reason,
        )
        if truncated:
            embed.add_field(
                name="💬 Mesaj İçeriği",
                value=f"```{truncated}```",
                inline=False,
            )

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _take_action(
        self,
        message: discord.Message,
        action_type: str,
        action_config: str,
        reason: str,
    ) -> None:
        """
        Filtre tetiklendiğinde belirlenen aksiyonu uygular.

        Aksiyon türleri:
        - "delete": Sadece mesajı sil
        - "warn": Mesajı sil + uyarı ver
        - "timeout": Mesajı sil + 5 dk timeout
        """
        member = message.author

        # Mesajı sil
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

        if action_config == "warn":
            await queries.add_warning(
                self.bot.db,
                message.guild.id,
                member.id,
                self.bot.user.id,
                reason,
            )

            warn_count = await queries.get_active_warning_count(
                self.bot.db, message.guild.id, member.id
            )
            guild_config = await queries.get_guild_config(self.bot.db, message.guild.id)
            threshold = guild_config.get("warn_threshold", 3)

            embed = warning_embed(
                "Automod Uyarısı",
                f"{member.mention}, mesajınız **{reason.lower()}** nedeniyle silindi.\n\n"
                f"{Emojis.WARNING} Aktif uyarı: **{warn_count}/{threshold}**",
            )
            try:
                await message.channel.send(embed=embed, delete_after=10)
            except (discord.Forbidden, discord.HTTPException):
                pass

            dm_embed = dm_notification_embed(
                action=ActionType.WARN,
                guild_name=message.guild.name,
                reason=f"Automod: {reason}",
            )
            try:
                await member.send(embed=dm_embed)
            except (discord.Forbidden, discord.HTTPException):
                pass

            # Eşik kontrolü — otomatik timeout
            if warn_count >= threshold:
                mute_duration = guild_config.get("mute_duration", 3600)
                try:
                    await member.timeout(
                        datetime.timedelta(seconds=mute_duration),
                        reason=f"Otomatik ceza: {warn_count} uyarıya ulaşıldı",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass

        elif action_config == "timeout":
            try:
                await member.timeout(
                    datetime.timedelta(minutes=5),
                    reason=f"Automod: {reason}",
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

            embed = warning_embed(
                "Automod Susturma",
                f"{member.mention}, **{reason.lower()}** nedeniyle **5 dakika** susturuldunuz.",
            )
            try:
                await message.channel.send(embed=embed, delete_after=10)
            except (discord.Forbidden, discord.HTTPException):
                pass

        else:
            # Sadece sil ("delete" aksiyonu)
            embed = warning_embed(
                "Automod",
                f"{member.mention}, mesajınız **{reason.lower()}** nedeniyle silindi.",
            )
            try:
                await message.channel.send(embed=embed, delete_after=7)
            except (discord.Forbidden, discord.HTTPException):
                pass

        # Veritabanına log
        await queries.add_mod_log(
            self.bot.db,
            message.guild.id,
            action_type,
            member.id,
            self.bot.user.id,
            reason,
        )

        # Log kanalına gönder
        await self._send_automod_log(
            message.guild, action_type, member, reason, message.content
        )

    async def _take_spam_action(
        self,
        message: discord.Message,
        action_config: str,
        reason: str,
        messages_to_delete: list[discord.Message] | None = None,
    ) -> None:
        """
        Spam filtresi özel aksiyon: Birden fazla mesajı silebilir ve daha uzun timeout uygular.
        """
        member = message.author

        # Birden fazla spam mesajını sil
        if messages_to_delete:
            for msg in messages_to_delete:
                try:
                    await msg.delete()
                except (discord.Forbidden, discord.HTTPException):
                    pass
        else:
            try:
                await message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

        if action_config == "timeout":
            try:
                await member.timeout(
                    datetime.timedelta(minutes=5),
                    reason=f"Automod: {reason}",
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

            embed = warning_embed(
                "Spam Koruması",
                f"{member.mention}, **spam** nedeniyle **5 dakika** susturuldunuz.\n\n"
                f"Lütfen ardı ardına çok fazla mesaj göndermekten kaçının.",
            )
            try:
                await message.channel.send(embed=embed, delete_after=10)
            except (discord.Forbidden, discord.HTTPException):
                pass

        elif action_config == "warn":
            await queries.add_warning(
                self.bot.db,
                message.guild.id,
                member.id,
                self.bot.user.id,
                reason,
            )
            warn_count = await queries.get_active_warning_count(
                self.bot.db, message.guild.id, member.id
            )
            guild_config = await queries.get_guild_config(self.bot.db, message.guild.id)
            threshold = guild_config.get("warn_threshold", 3)

            embed = warning_embed(
                "Spam Uyarısı",
                f"{member.mention}, **spam** nedeniyle uyarıldınız.\n\n"
                f"{Emojis.WARNING} Aktif uyarı: **{warn_count}/{threshold}**",
            )
            try:
                await message.channel.send(embed=embed, delete_after=10)
            except (discord.Forbidden, discord.HTTPException):
                pass

            if warn_count >= threshold:
                mute_duration = guild_config.get("mute_duration", 3600)
                try:
                    await member.timeout(
                        datetime.timedelta(seconds=mute_duration),
                        reason=f"Otomatik ceza: {warn_count} uyarıya ulaşıldı",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass
        else:
            embed = warning_embed(
                "Spam Koruması",
                f"{member.mention}, spam mesajlarınız silindi.",
            )
            try:
                await message.channel.send(embed=embed, delete_after=7)
            except (discord.Forbidden, discord.HTTPException):
                pass

        await queries.add_mod_log(
            self.bot.db, message.guild.id, ActionType.AUTOMOD_SPAM,
            member.id, self.bot.user.id, reason,
        )
        await self._send_automod_log(
            message.guild, ActionType.AUTOMOD_SPAM, member, reason, message.content
        )

    # ══════════════════════════════════════════════
    #  Filtre Kontrolleri
    # ══════════════════════════════════════════════

    def _check_profanity(self, content: str, word_list: set[str]) -> str | None:
        """Mesajda yasaklı kelime olup olmadığını kontrol eder."""
        if not word_list:
            return None

        normalized = content.lower()

        tr_map = str.maketrans({
            "ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c",
            "İ": "i", "Ğ": "g", "Ü": "u", "Ş": "s", "Ö": "o", "Ç": "c",
        })
        normalized_ascii = normalized.translate(tr_map)

        leet_map = str.maketrans({
            "0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
            "7": "t", "@": "a", "$": "s",
        })
        normalized_leet = normalized_ascii.translate(leet_map)

        for word in word_list:
            word_lower = word.lower()
            word_ascii = word_lower.translate(tr_map)

            if word_lower in normalized:
                return word
            if word_ascii in normalized_ascii:
                return word
            if word_ascii in normalized_leet:
                return word

        return None

    def _check_links(
        self, content: str, *, block_invites: bool, block_all_urls: bool
    ) -> str | None:
        """Mesajda link olup olmadığını kontrol eder."""
        if block_invites and INVITE_PATTERN.search(content):
            return "Discord davet linki"
        if block_all_urls and URL_PATTERN.search(content):
            return "URL/link paylaşımı"
        return None

    def _check_caps(
        self, content: str, *, threshold: int, min_length: int
    ) -> bool:
        """Mesajdaki büyük harf oranını kontrol eder."""
        letters = [c for c in content if c.isalpha()]
        if len(letters) < min_length:
            return False
        upper_count = sum(1 for c in letters if c.isupper())
        upper_ratio = (upper_count / len(letters)) * 100
        return upper_ratio >= threshold

    def _check_spam(
        self,
        guild_id: int,
        user_id: int,
        *,
        max_messages: int,
        window_seconds: int,
    ) -> bool:
        """
        Kullanıcının spam yapıp yapmadığını sliding window ile kontrol eder.

        Returns:
            True ise spam tespit edildi.
        """
        now = time.time()
        timestamps = self._spam_tracker[guild_id][user_id]

        # Pencere dışındaki eski kayıtları temizle
        cutoff = now - window_seconds
        timestamps[:] = [t for t in timestamps if t > cutoff]

        # Yeni mesajı kaydet
        timestamps.append(now)

        return len(timestamps) > max_messages

    def _count_emojis(self, content: str) -> int:
        """Mesajdaki toplam emoji sayısını döndürür (Unicode + özel)."""
        custom_count = len(CUSTOM_EMOJI_PATTERN.findall(content))
        unicode_matches = UNICODE_EMOJI_PATTERN.findall(content)
        # Her Unicode emoji match'i birden fazla karakter içerebilir
        unicode_count = sum(len(m) for m in unicode_matches)
        return custom_count + unicode_count

    def _count_mentions(self, message: discord.Message) -> int:
        """Mesajdaki toplam mention sayısını döndürür (user + role + everyone/here)."""
        count = len(message.mentions)  # @user
        count += len(message.role_mentions)  # @role
        if message.mention_everyone:  # @everyone veya @here
            count += 1
        return count

    # ══════════════════════════════════════════════
    #  on_message Event — Ana Filtre Döngüsü
    # ══════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Her mesajı automod filtrelerinden geçirir."""

        # Temel kontroller
        if message.author.bot:
            return
        if message.guild is None:
            return
        if not message.content and not message.mentions:
            return

        config = await self._get_config(message.guild.id)

        # Hiçbir filtre açık değilse çık
        if not any([
            config.get("profanity_enabled"),
            config.get("link_filter_enabled"),
            config.get("caps_filter_enabled"),
            config.get("spam_enabled"),
            config.get("emoji_filter_enabled"),
            config.get("mention_filter_enabled"),
        ]):
            return

        member = message.author
        if not isinstance(member, discord.Member):
            return

        content = message.content or ""

        # ── 1. Spam Koruması (mesaj flood) ──
        # Spam her zaman ilk kontrol edilir (acil müdahale)
        if config.get("spam_enabled"):
            if not await self._is_exempt(member, "spam"):
                is_spam = self._check_spam(
                    message.guild.id,
                    member.id,
                    max_messages=config.get("spam_max_messages", 5),
                    window_seconds=config.get("spam_window_seconds", 5),
                )
                if is_spam:
                    logger.info(
                        "Spam filtresi tetiklendi: {} (guild={})",
                        member, message.guild.id,
                    )
                    # Spam tracker'ı sıfırla (aynı kullanıcı için tekrar tetiklememesi için)
                    self._spam_tracker[message.guild.id][member.id].clear()
                    await self._take_spam_action(
                        message,
                        config.get("spam_action", "timeout"),
                        "Mesaj spamı (flood)",
                    )
                    return

        # ── 2. Küfür Filtresi ──
        if config.get("profanity_enabled") and content:
            if not await self._is_exempt(member, "profanity"):
                word_list = await self._get_words(message.guild.id)
                found_word = self._check_profanity(content, word_list)
                if found_word:
                    logger.info(
                        "Küfür filtresi tetiklendi: {} (guild={}) | Kelime: {}",
                        member, message.guild.id, found_word,
                    )
                    await self._take_action(
                        message,
                        ActionType.AUTOMOD_PROFANITY,
                        config.get("profanity_action", "warn"),
                        "Küfür/argo kullanımı",
                    )
                    return

        # ── 3. Link Filtresi ──
        if config.get("link_filter_enabled") and content:
            if not await self._is_exempt(member, "link"):
                link_result = self._check_links(
                    content,
                    block_invites=config.get("link_block_invites", True),
                    block_all_urls=config.get("link_block_all_urls", False),
                )
                if link_result:
                    logger.info(
                        "Link filtresi tetiklendi: {} (guild={}) | Tür: {}",
                        member, message.guild.id, link_result,
                    )
                    await self._take_action(
                        message,
                        ActionType.AUTOMOD_LINK,
                        config.get("link_filter_action", "delete"),
                        link_result,
                    )
                    return

        # ── 4. Emoji Spamı ──
        if config.get("emoji_filter_enabled") and content:
            if not await self._is_exempt(member, "emoji"):
                emoji_count = self._count_emojis(content)
                max_emoji = config.get("emoji_max_count", 15)
                if emoji_count > max_emoji:
                    logger.info(
                        "Emoji filtresi tetiklendi: {} (guild={}) | Emoji: {}/{}",
                        member, message.guild.id, emoji_count, max_emoji,
                    )
                    await self._take_action(
                        message,
                        ActionType.AUTOMOD_EMOJI,
                        config.get("emoji_action", "delete"),
                        f"Aşırı emoji kullanımı ({emoji_count} emoji)",
                    )
                    return

        # ── 5. Mention Spamı ──
        if config.get("mention_filter_enabled"):
            if not await self._is_exempt(member, "mention"):
                mention_count = self._count_mentions(message)
                max_mention = config.get("mention_max_count", 5)
                if mention_count > max_mention:
                    logger.info(
                        "Mention filtresi tetiklendi: {} (guild={}) | Mention: {}/{}",
                        member, message.guild.id, mention_count, max_mention,
                    )
                    await self._take_action(
                        message,
                        ActionType.AUTOMOD_MENTION,
                        config.get("mention_action", "delete"),
                        f"Aşırı etiketleme ({mention_count} etiket)",
                    )
                    return

        # ── 6. Caps Lock Filtresi ──
        if config.get("caps_filter_enabled") and content:
            if not await self._is_exempt(member, "caps"):
                is_caps = self._check_caps(
                    content,
                    threshold=config.get("caps_threshold", 70),
                    min_length=config.get("caps_min_length", 10),
                )
                if is_caps:
                    logger.info(
                        "Caps filtresi tetiklendi: {} (guild={})",
                        member, message.guild.id,
                    )
                    await self._take_action(
                        message,
                        ActionType.AUTOMOD_CAPS,
                        config.get("caps_action", "delete"),
                        "Aşırı büyük harf kullanımı",
                    )
                    return

    # ══════════════════════════════════════════════════════════════
    #  YAPILANDIRMA KOMUTLARI — automod group
    # ══════════════════════════════════════════════════════════════

    automod_group = app_commands.Group(
        name="automod",
        description="Otomatik moderasyon ayarları",
        default_permissions=discord.Permissions(administrator=True),
    )

    # ── Yardımcı: aksiyon seçenekleri ──

    _action_choices = [
        app_commands.Choice(name="Mesajı Sil", value="delete"),
        app_commands.Choice(name="Uyarı Ver", value="warn"),
        app_commands.Choice(name="Sustur (5dk)", value="timeout"),
    ]

    _filter_choices = [
        app_commands.Choice(name="Tüm Filtreler", value="all"),
        app_commands.Choice(name="Küfür Filtresi", value="profanity"),
        app_commands.Choice(name="Link Filtresi", value="link"),
        app_commands.Choice(name="Caps Lock Filtresi", value="caps"),
        app_commands.Choice(name="Spam Koruması", value="spam"),
        app_commands.Choice(name="Emoji Filtresi", value="emoji"),
        app_commands.Choice(name="Etiket Filtresi", value="mention"),
    ]

    # ══════════════════════════════════════════════
    #  DURUM GÖSTERME
    # ══════════════════════════════════════════════

    @automod_group.command(name="durum", description="Automod ayarlarını gösterir.")
    async def automod_status(self, interaction: discord.Interaction) -> None:
        """Tüm automod filtrelerinin durumunu gösterir."""
        config = await queries.get_automod_config(self.bot.db, interaction.guild.id)

        def status(enabled: bool) -> str:
            return f"{Emojis.TOGGLE_ON} Açık" if enabled else f"{Emojis.TOGGLE_OFF} Kapalı"

        def action_label(action: str) -> str:
            labels = {"delete": "Mesajı Sil", "warn": "Uyarı Ver", "timeout": "Sustur (5dk)"}
            return labels.get(action, action)

        # Muaf roller
        whitelist = await queries.get_whitelist_roles(self.bot.db, interaction.guild.id)
        exempt_text = ""
        if whitelist:
            roles_by_filter: dict[str, list[str]] = {}
            for entry in whitelist:
                ft = entry["filter_type"]
                role = interaction.guild.get_role(entry["role_id"])
                role_mention = role.mention if role else f"<@&{entry['role_id']}>"
                roles_by_filter.setdefault(ft, []).append(role_mention)

            exempt_parts = []
            for ft, roles in roles_by_filter.items():
                ft_label = {
                    "all": "Tümü", "profanity": "Küfür", "link": "Link",
                    "caps": "Caps", "spam": "Spam", "emoji": "Emoji", "mention": "Etiket",
                }.get(ft, ft)
                exempt_parts.append(f"**{ft_label}:** {', '.join(roles)}")
            exempt_text = "\n".join(exempt_parts)

        description = (
            f"## {Emojis.AUTOMOD} Otomatik Moderasyon Ayarları\n\n"
            # Küfür
            f"### {Emojis.PROFANITY} Küfür/Argo Filtresi\n"
            f"{Emojis.ARROW_RIGHT} **Durum:** {status(config['profanity_enabled'])}\n"
            f"{Emojis.ARROW_RIGHT} **Aksiyon:** {action_label(config['profanity_action'])}\n\n"
            # Link
            f"### {Emojis.LINK} Link/Reklam Filtresi\n"
            f"{Emojis.ARROW_RIGHT} **Durum:** {status(config['link_filter_enabled'])}\n"
            f"{Emojis.ARROW_RIGHT} **Aksiyon:** {action_label(config['link_filter_action'])}\n"
            f"{Emojis.ARROW_RIGHT} **Davet Linkleri:** {status(config['link_block_invites'])}\n"
            f"{Emojis.ARROW_RIGHT} **Tüm URL'ler:** {status(config['link_block_all_urls'])}\n\n"
            # Caps
            f"### {Emojis.CAPS} Caps Lock Filtresi\n"
            f"{Emojis.ARROW_RIGHT} **Durum:** {status(config['caps_filter_enabled'])}\n"
            f"{Emojis.ARROW_RIGHT} **Aksiyon:** {action_label(config['caps_action'])}\n"
            f"{Emojis.ARROW_RIGHT} **Eşik:** %{config['caps_threshold']}\n"
            f"{Emojis.ARROW_RIGHT} **Min. Uzunluk:** {config['caps_min_length']} karakter\n\n"
            # Spam
            f"### {Emojis.SPAM} Spam Koruması\n"
            f"{Emojis.ARROW_RIGHT} **Durum:** {status(config['spam_enabled'])}\n"
            f"{Emojis.ARROW_RIGHT} **Aksiyon:** {action_label(config['spam_action'])}\n"
            f"{Emojis.ARROW_RIGHT} **Limit:** {config['spam_max_messages']} mesaj / {config['spam_window_seconds']} saniye\n\n"
            # Emoji
            f"### {Emojis.EMOJI} Emoji Spamı\n"
            f"{Emojis.ARROW_RIGHT} **Durum:** {status(config['emoji_filter_enabled'])}\n"
            f"{Emojis.ARROW_RIGHT} **Aksiyon:** {action_label(config['emoji_action'])}\n"
            f"{Emojis.ARROW_RIGHT} **Maks. Emoji:** {config['emoji_max_count']}\n\n"
            # Mention
            f"### {Emojis.MENTION} Etiket (Mention) Spamı\n"
            f"{Emojis.ARROW_RIGHT} **Durum:** {status(config['mention_filter_enabled'])}\n"
            f"{Emojis.ARROW_RIGHT} **Aksiyon:** {action_label(config['mention_action'])}\n"
            f"{Emojis.ARROW_RIGHT} **Maks. Etiket:** {config['mention_max_count']}\n"
        )

        if exempt_text:
            description += f"\n### {Emojis.EXEMPT} Muaf Roller\n{exempt_text}"

        embed = info_embed("Automod Durumu", description)
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════
    #  KÜFÜR FİLTRESİ KOMUTLARI
    # ══════════════════════════════════════════════

    @automod_group.command(name="küfür-aç", description="Küfür filtresini açar.")
    @app_commands.describe(aksiyon="Filtre tetiklendiğinde yapılacak işlem")
    @app_commands.choices(aksiyon=_action_choices)
    async def profanity_enable(
        self, interaction: discord.Interaction,
        aksiyon: app_commands.Choice[str] = None,
    ) -> None:
        updates = {"profanity_enabled": True}
        if aksiyon:
            updates["profanity_action"] = aksiyon.value
        await queries.update_automod_config(self.bot.db, interaction.guild.id, **updates)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Küfür Filtresi Açıldı",
            f"{Emojis.PROFANITY} Küfür/argo filtresi **aktif** edildi.\n"
            f"**Aksiyon:** {aksiyon.name if aksiyon else 'mevcut ayar'}\n\n"
            f"Yasaklı kelime eklemek için `/automod küfür-ekle` komutunu kullanın.",
        )
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="küfür-kapat", description="Küfür filtresini kapatır.")
    async def profanity_disable(self, interaction: discord.Interaction) -> None:
        await queries.update_automod_config(self.bot.db, interaction.guild.id, profanity_enabled=False)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed("Küfür Filtresi Kapatıldı", f"{Emojis.TOGGLE_OFF} Küfür/argo filtresi **deaktif** edildi.")
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="küfür-ekle", description="Yasaklı kelime listesine kelime ekler.")
    @app_commands.describe(kelimeler="Eklenecek kelime(ler), virgülle ayırın")
    async def profanity_add_word(self, interaction: discord.Interaction, kelimeler: str) -> None:
        words = [w.strip() for w in kelimeler.split(",") if w.strip()]
        if not words:
            return await interaction.response.send_message(
                embed=error_embed("Geçersiz Giriş", "En az bir kelime girmelisiniz."), ephemeral=True,
            )
        if len(words) > 50:
            return await interaction.response.send_message(
                embed=error_embed("Limit Aşıldı", "Tek seferde en fazla **50** kelime ekleyebilirsiniz."), ephemeral=True,
            )
        for w in words:
            if len(w) > 32:
                return await interaction.response.send_message(
                    embed=error_embed("Geçersiz Kelime", f"Kelime uzunluğu en fazla **32** karakter olabilir: `{w[:20]}...`"), ephemeral=True,
                )
        current_words = await queries.get_automod_words(self.bot.db, interaction.guild.id)
        if len(current_words) + len(words) > 500:
            return await interaction.response.send_message(
                embed=error_embed("Limit Aşıldı", f"Sunucuda toplamda en fazla **500** yasaklı kelime olabilir. Mevcut kelime sayısı: **{len(current_words)}**"), ephemeral=True,
            )
        added = await queries.add_automod_words_bulk(self.bot.db, interaction.guild.id, words, interaction.user.id)
        self._invalidate_words(interaction.guild.id)
        if added == 0:
            embed = error_embed("Kelime Eklenemedi", "Girilen kelimeler zaten listede mevcut.")
        else:
            word_display = ", ".join(f"`{w}`" for w in words[:10])
            embed = success_embed("Kelimeler Eklendi", f"**{added}** kelime yasaklı listeye eklendi.\n\n{word_display}")
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="küfür-sil", description="Yasaklı kelime listesinden kelime siler.")
    @app_commands.describe(kelime="Silinecek kelime")
    async def profanity_remove_word(self, interaction: discord.Interaction, kelime: str) -> None:
        removed = await queries.remove_automod_word(self.bot.db, interaction.guild.id, kelime)
        self._invalidate_words(interaction.guild.id)
        if removed:
            embed = success_embed("Kelime Silindi", f"`{kelime}` yasaklı listeden kaldırıldı.")
        else:
            embed = error_embed("Kelime Bulunamadı", f"`{kelime}` yasaklı listede bulunamadı.")
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="küfür-liste", description="Yasaklı kelime listesini gösterir.")
    async def profanity_list(self, interaction: discord.Interaction) -> None:
        words = await queries.get_automod_words(self.bot.db, interaction.guild.id)
        if not words:
            embed = info_embed("Yasaklı Kelime Listesi", "Henüz yasaklı kelime eklenmemiş.\n\nKelime eklemek için `/automod küfür-ekle` komutunu kullanın.")
        else:
            word_display = ", ".join(f"||`{w}`||" for w in words)
            embed = info_embed(f"Yasaklı Kelime Listesi — {len(words)} kelime", f"{word_display}\n\n*Kelimeler gizli tutulmuştur, görmek için üzerine tıklayın.*")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ══════════════════════════════════════════════
    #  LİNK FİLTRESİ KOMUTLARI
    # ══════════════════════════════════════════════

    @automod_group.command(name="link-aç", description="Link/reklam filtresini açar.")
    @app_commands.describe(aksiyon="Filtre tetiklendiğinde yapılacak işlem", davet_linkleri="Discord davet linklerini engelle", tüm_urller="Tüm URL'leri engelle")
    @app_commands.choices(aksiyon=_action_choices)
    async def link_enable(
        self, interaction: discord.Interaction,
        aksiyon: app_commands.Choice[str] = None,
        davet_linkleri: bool = True, tüm_urller: bool = False,
    ) -> None:
        updates = {"link_filter_enabled": True, "link_block_invites": davet_linkleri, "link_block_all_urls": tüm_urller}
        if aksiyon:
            updates["link_filter_action"] = aksiyon.value
        await queries.update_automod_config(self.bot.db, interaction.guild.id, **updates)
        self._invalidate_config(interaction.guild.id)
        desc = [f"{Emojis.LINK} Link/reklam filtresi **aktif** edildi.\n"]
        if davet_linkleri:
            desc.append(f"{Emojis.TOGGLE_ON} Discord davet linkleri **engelleniyor**")
        if tüm_urller:
            desc.append(f"{Emojis.TOGGLE_ON} Tüm URL'ler **engelleniyor**")
        desc.append(f"\nMuaf rol eklemek için `/automod muaf-ekle` komutunu kullanabilirsiniz.")
        embed = success_embed("Link Filtresi Açıldı", "\n".join(desc))
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="link-kapat", description="Link/reklam filtresini kapatır.")
    async def link_disable(self, interaction: discord.Interaction) -> None:
        await queries.update_automod_config(self.bot.db, interaction.guild.id, link_filter_enabled=False)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed("Link Filtresi Kapatıldı", f"{Emojis.TOGGLE_OFF} Link/reklam filtresi **deaktif** edildi.")
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════
    #  CAPS LOCK FİLTRESİ KOMUTLARI
    # ══════════════════════════════════════════════

    @automod_group.command(name="caps-aç", description="Caps lock filtresini açar.")
    @app_commands.describe(aksiyon="Filtre tetiklendiğinde yapılacak işlem", eşik="Maksimum büyük harf yüzdesi (varsayılan: 70)", min_uzunluk="Minimum mesaj uzunluğu (varsayılan: 10)")
    @app_commands.choices(aksiyon=_action_choices)
    async def caps_enable(
        self, interaction: discord.Interaction,
        aksiyon: app_commands.Choice[str] = None,
        eşik: int = 70, min_uzunluk: int = 10,
    ) -> None:
        if not 30 <= eşik <= 100:
            return await interaction.response.send_message(embed=error_embed("Geçersiz Eşik", "Eşik değeri **30 ile 100** arasında olmalıdır."), ephemeral=True)
        if min_uzunluk < 3:
            return await interaction.response.send_message(embed=error_embed("Geçersiz Uzunluk", "Minimum uzunluk en az **3** olmalıdır."), ephemeral=True)
        updates = {"caps_filter_enabled": True, "caps_threshold": eşik, "caps_min_length": min_uzunluk}
        if aksiyon:
            updates["caps_action"] = aksiyon.value
        await queries.update_automod_config(self.bot.db, interaction.guild.id, **updates)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Caps Lock Filtresi Açıldı",
            f"{Emojis.CAPS} Büyük harf filtresi **aktif** edildi.\n\n"
            f"**Eşik:** %{eşik} büyük harf\n**Min. uzunluk:** {min_uzunluk} karakter\n"
            f"**Aksiyon:** {aksiyon.name if aksiyon else 'mevcut ayar'}",
        )
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="caps-kapat", description="Caps lock filtresini kapatır.")
    async def caps_disable(self, interaction: discord.Interaction) -> None:
        await queries.update_automod_config(self.bot.db, interaction.guild.id, caps_filter_enabled=False)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed("Caps Lock Filtresi Kapatıldı", f"{Emojis.TOGGLE_OFF} Büyük harf filtresi **deaktif** edildi.")
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════
    #  SPAM KORUMASI KOMUTLARI
    # ══════════════════════════════════════════════

    @automod_group.command(name="spam-aç", description="Spam korumasını açar.")
    @app_commands.describe(
        aksiyon="Spam algılandığında yapılacak işlem",
        maks_mesaj="Pencere içinde izin verilen maksimum mesaj sayısı (varsayılan: 5)",
        pencere="Zaman penceresi — saniye cinsinden (varsayılan: 5)",
    )
    @app_commands.choices(aksiyon=_action_choices)
    async def spam_enable(
        self, interaction: discord.Interaction,
        aksiyon: app_commands.Choice[str] = None,
        maks_mesaj: int = 5, pencere: int = 5,
    ) -> None:
        """Spam korumasını açar. Kısa sürede çok mesaj atan kullanıcıları engeller."""
        if not 2 <= maks_mesaj <= 30:
            return await interaction.response.send_message(
                embed=error_embed("Geçersiz Değer", "Maksimum mesaj sayısı **2 ile 30** arasında olmalıdır."), ephemeral=True,
            )
        if not 2 <= pencere <= 60:
            return await interaction.response.send_message(
                embed=error_embed("Geçersiz Değer", "Zaman penceresi **2 ile 60** saniye arasında olmalıdır."), ephemeral=True,
            )
        updates = {"spam_enabled": True, "spam_max_messages": maks_mesaj, "spam_window_seconds": pencere}
        if aksiyon:
            updates["spam_action"] = aksiyon.value
        await queries.update_automod_config(self.bot.db, interaction.guild.id, **updates)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Spam Koruması Açıldı",
            f"{Emojis.SPAM} Spam koruması **aktif** edildi.\n\n"
            f"**Limit:** {maks_mesaj} mesaj / {pencere} saniye\n"
            f"**Aksiyon:** {aksiyon.name if aksiyon else 'Sustur (5dk)'}\n\n"
            f"Bu limiti aşan kullanıcılara otomatik olarak işlem uygulanacak.",
        )
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="spam-kapat", description="Spam korumasını kapatır.")
    async def spam_disable(self, interaction: discord.Interaction) -> None:
        await queries.update_automod_config(self.bot.db, interaction.guild.id, spam_enabled=False)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed("Spam Koruması Kapatıldı", f"{Emojis.TOGGLE_OFF} Spam koruması **deaktif** edildi.")
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="spam-ayar", description="Spam koruması parametrelerini günceller.")
    @app_commands.describe(
        maks_mesaj="Pencere içinde izin verilen maksimum mesaj sayısı",
        pencere="Zaman penceresi — saniye cinsinden",
        aksiyon="Spam algılandığında yapılacak işlem",
    )
    @app_commands.choices(aksiyon=_action_choices)
    async def spam_settings(
        self, interaction: discord.Interaction,
        maks_mesaj: int = None, pencere: int = None,
        aksiyon: app_commands.Choice[str] = None,
    ) -> None:
        """Spam koruması ayarlarını günceller."""
        updates = {}
        if maks_mesaj is not None:
            if not 2 <= maks_mesaj <= 30:
                return await interaction.response.send_message(
                    embed=error_embed("Geçersiz Değer", "Maksimum mesaj sayısı **2 ile 30** arasında olmalıdır."), ephemeral=True,
                )
            updates["spam_max_messages"] = maks_mesaj
        if pencere is not None:
            if not 2 <= pencere <= 60:
                return await interaction.response.send_message(
                    embed=error_embed("Geçersiz Değer", "Zaman penceresi **2 ile 60** saniye arasında olmalıdır."), ephemeral=True,
                )
            updates["spam_window_seconds"] = pencere
        if aksiyon:
            updates["spam_action"] = aksiyon.value
        if not updates:
            return await interaction.response.send_message(
                embed=error_embed("Eksik Parametre", "En az bir ayar belirtmelisiniz."), ephemeral=True,
            )
        await queries.update_automod_config(self.bot.db, interaction.guild.id, **updates)
        self._invalidate_config(interaction.guild.id)
        config = await queries.get_automod_config(self.bot.db, interaction.guild.id)
        embed = success_embed(
            "Spam Ayarları Güncellendi",
            f"{Emojis.SETTINGS} Yeni ayarlar:\n\n"
            f"**Limit:** {config['spam_max_messages']} mesaj / {config['spam_window_seconds']} saniye\n"
            f"**Aksiyon:** {{'delete': 'Mesajı Sil', 'warn': 'Uyarı Ver', 'timeout': 'Sustur (5dk)'}}.get(config['spam_action'], config['spam_action'])",
        )
        # Düzgün format
        action_labels = {"delete": "Mesajı Sil", "warn": "Uyarı Ver", "timeout": "Sustur (5dk)"}
        embed = success_embed(
            "Spam Ayarları Güncellendi",
            f"{Emojis.SETTINGS} Yeni ayarlar:\n\n"
            f"**Limit:** {config['spam_max_messages']} mesaj / {config['spam_window_seconds']} saniye\n"
            f"**Aksiyon:** {action_labels.get(config['spam_action'], config['spam_action'])}",
        )
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════
    #  EMOJİ SPAMI KOMUTLARI
    # ══════════════════════════════════════════════

    @automod_group.command(name="emoji-aç", description="Emoji spam filtresini açar.")
    @app_commands.describe(
        aksiyon="Filtre tetiklendiğinde yapılacak işlem",
        maks_emoji="Bir mesajda izin verilen maksimum emoji sayısı (varsayılan: 15)",
    )
    @app_commands.choices(aksiyon=_action_choices)
    async def emoji_enable(
        self, interaction: discord.Interaction,
        aksiyon: app_commands.Choice[str] = None,
        maks_emoji: int = 15,
    ) -> None:
        """Emoji spam filtresini açar."""
        if not 1 <= maks_emoji <= 100:
            return await interaction.response.send_message(
                embed=error_embed("Geçersiz Değer", "Maksimum emoji sayısı **1 ile 100** arasında olmalıdır."), ephemeral=True,
            )
        updates = {"emoji_filter_enabled": True, "emoji_max_count": maks_emoji}
        if aksiyon:
            updates["emoji_action"] = aksiyon.value
        await queries.update_automod_config(self.bot.db, interaction.guild.id, **updates)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Emoji Filtresi Açıldı",
            f"{Emojis.EMOJI} Emoji spam filtresi **aktif** edildi.\n\n"
            f"**Maks. Emoji:** {maks_emoji} (bu sayıyı aşan mesajlar işlem görür)\n"
            f"**Aksiyon:** {aksiyon.name if aksiyon else 'mevcut ayar'}\n\n"
            f"Hem Unicode 😀 hem de özel sunucu emojileri sayılır.",
        )
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="emoji-kapat", description="Emoji spam filtresini kapatır.")
    async def emoji_disable(self, interaction: discord.Interaction) -> None:
        await queries.update_automod_config(self.bot.db, interaction.guild.id, emoji_filter_enabled=False)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed("Emoji Filtresi Kapatıldı", f"{Emojis.TOGGLE_OFF} Emoji spam filtresi **deaktif** edildi.")
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="emoji-ayar", description="Emoji spam filtresi parametrelerini günceller.")
    @app_commands.describe(maks_emoji="Bir mesajda izin verilen maksimum emoji sayısı", aksiyon="Filtre tetiklendiğinde yapılacak işlem")
    @app_commands.choices(aksiyon=_action_choices)
    async def emoji_settings(
        self, interaction: discord.Interaction,
        maks_emoji: int = None, aksiyon: app_commands.Choice[str] = None,
    ) -> None:
        updates = {}
        if maks_emoji is not None:
            if not 1 <= maks_emoji <= 100:
                return await interaction.response.send_message(embed=error_embed("Geçersiz Değer", "Maksimum emoji sayısı **1 ile 100** arasında olmalıdır."), ephemeral=True)
            updates["emoji_max_count"] = maks_emoji
        if aksiyon:
            updates["emoji_action"] = aksiyon.value
        if not updates:
            return await interaction.response.send_message(embed=error_embed("Eksik Parametre", "En az bir ayar belirtmelisiniz."), ephemeral=True)
        await queries.update_automod_config(self.bot.db, interaction.guild.id, **updates)
        self._invalidate_config(interaction.guild.id)
        config = await queries.get_automod_config(self.bot.db, interaction.guild.id)
        action_labels = {"delete": "Mesajı Sil", "warn": "Uyarı Ver", "timeout": "Sustur (5dk)"}
        embed = success_embed(
            "Emoji Ayarları Güncellendi",
            f"{Emojis.SETTINGS} **Maks. Emoji:** {config['emoji_max_count']}\n"
            f"**Aksiyon:** {action_labels.get(config['emoji_action'], config['emoji_action'])}",
        )
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════
    #  ETİKET (MENTION) SPAMI KOMUTLARI
    # ══════════════════════════════════════════════

    @automod_group.command(name="etiket-aç", description="Etiket (mention) spam filtresini açar.")
    @app_commands.describe(
        aksiyon="Filtre tetiklendiğinde yapılacak işlem",
        maks_etiket="Bir mesajda izin verilen maksimum etiket sayısı (varsayılan: 5)",
    )
    @app_commands.choices(aksiyon=_action_choices)
    async def mention_enable(
        self, interaction: discord.Interaction,
        aksiyon: app_commands.Choice[str] = None,
        maks_etiket: int = 5,
    ) -> None:
        """Etiket (mention) spam filtresini açar."""
        if not 1 <= maks_etiket <= 50:
            return await interaction.response.send_message(
                embed=error_embed("Geçersiz Değer", "Maksimum etiket sayısı **1 ile 50** arasında olmalıdır."), ephemeral=True,
            )
        updates = {"mention_filter_enabled": True, "mention_max_count": maks_etiket}
        if aksiyon:
            updates["mention_action"] = aksiyon.value
        await queries.update_automod_config(self.bot.db, interaction.guild.id, **updates)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Etiket Filtresi Açıldı",
            f"{Emojis.MENTION} Etiket (mention) spam filtresi **aktif** edildi.\n\n"
            f"**Maks. Etiket:** {maks_etiket} (bu sayıyı aşan mesajlar işlem görür)\n"
            f"**Aksiyon:** {aksiyon.name if aksiyon else 'mevcut ayar'}\n\n"
            f"@kullanıcı, @rol ve @everyone/@here etiketleri sayılır.",
        )
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="etiket-kapat", description="Etiket (mention) spam filtresini kapatır.")
    async def mention_disable(self, interaction: discord.Interaction) -> None:
        await queries.update_automod_config(self.bot.db, interaction.guild.id, mention_filter_enabled=False)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed("Etiket Filtresi Kapatıldı", f"{Emojis.TOGGLE_OFF} Etiket spam filtresi **deaktif** edildi.")
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="etiket-ayar", description="Etiket spam filtresi parametrelerini günceller.")
    @app_commands.describe(maks_etiket="Bir mesajda izin verilen maksimum etiket sayısı", aksiyon="Filtre tetiklendiğinde yapılacak işlem")
    @app_commands.choices(aksiyon=_action_choices)
    async def mention_settings(
        self, interaction: discord.Interaction,
        maks_etiket: int = None, aksiyon: app_commands.Choice[str] = None,
    ) -> None:
        updates = {}
        if maks_etiket is not None:
            if not 1 <= maks_etiket <= 50:
                return await interaction.response.send_message(embed=error_embed("Geçersiz Değer", "Maksimum etiket sayısı **1 ile 50** arasında olmalıdır."), ephemeral=True)
            updates["mention_max_count"] = maks_etiket
        if aksiyon:
            updates["mention_action"] = aksiyon.value
        if not updates:
            return await interaction.response.send_message(embed=error_embed("Eksik Parametre", "En az bir ayar belirtmelisiniz."), ephemeral=True)
        await queries.update_automod_config(self.bot.db, interaction.guild.id, **updates)
        self._invalidate_config(interaction.guild.id)
        config = await queries.get_automod_config(self.bot.db, interaction.guild.id)
        action_labels = {"delete": "Mesajı Sil", "warn": "Uyarı Ver", "timeout": "Sustur (5dk)"}
        embed = success_embed(
            "Etiket Ayarları Güncellendi",
            f"{Emojis.SETTINGS} **Maks. Etiket:** {config['mention_max_count']}\n"
            f"**Aksiyon:** {action_labels.get(config['mention_action'], config['mention_action'])}",
        )
        await interaction.response.send_message(embed=embed)

    # ══════════════════════════════════════════════
    #  MUAF ROL YÖNETİMİ
    # ══════════════════════════════════════════════

    @automod_group.command(name="muaf-ekle", description="Bir rolü automod filtrelerinden muaf tutar.")
    @app_commands.describe(rol="Muaf tutulacak rol", filtre="Hangi filtreden muaf (varsayılan: tümü)")
    @app_commands.choices(filtre=_filter_choices)
    async def whitelist_add(
        self, interaction: discord.Interaction,
        rol: discord.Role, filtre: app_commands.Choice[str] = None,
    ) -> None:
        filter_type = filtre.value if filtre else "all"
        filter_label = filtre.name if filtre else "Tüm Filtreler"
        added = await queries.add_whitelist_role(self.bot.db, interaction.guild.id, rol.id, filter_type)
        if added:
            embed = success_embed(
                "Muaf Rol Eklendi",
                f"{Emojis.EXEMPT} {rol.mention} rolü **{filter_label}** için muaf tutuldu.\n\n"
                f"Bu role sahip kullanıcılar ilgili filtreden etkilenmeyecek.",
            )
        else:
            embed = error_embed("Zaten Muaf", f"{rol.mention} rolü bu filtre için zaten muaf listesinde.")
        await interaction.response.send_message(embed=embed)

    @automod_group.command(name="muaf-sil", description="Bir rolün automod muafiyetini kaldırır.")
    @app_commands.describe(rol="Muafiyeti kaldırılacak rol", filtre="Hangi filtre için muafiyet kaldırılsın")
    @app_commands.choices(filtre=_filter_choices)
    async def whitelist_remove(
        self, interaction: discord.Interaction,
        rol: discord.Role, filtre: app_commands.Choice[str] = None,
    ) -> None:
        filter_type = filtre.value if filtre else "all"
        removed = await queries.remove_whitelist_role(self.bot.db, interaction.guild.id, rol.id, filter_type)
        if removed:
            embed = success_embed("Muafiyet Kaldırıldı", f"{rol.mention} rolünün muafiyeti kaldırıldı.")
        else:
            embed = error_embed("Muafiyet Bulunamadı", f"{rol.mention} rolü bu filtre için muaf listesinde değil.")
        await interaction.response.send_message(embed=embed)

    # ── Log Kanalı Ayarı ──

    @automod_group.command(name="log-kanal", description="Automod log kanalını ayarlar.")
    @app_commands.describe(kanal="Automod loglarının gönderileceği kanal")
    async def automod_log_channel(
        self, interaction: discord.Interaction, kanal: discord.TextChannel,
    ) -> None:
        await queries.update_automod_config(self.bot.db, interaction.guild.id, log_channel=kanal.id)
        self._invalidate_config(interaction.guild.id)
        embed = success_embed(
            "Log Kanalı Ayarlandı",
            f"{Emojis.SETTINGS} Automod log kanalı {kanal.mention} olarak ayarlandı.\n\n"
            f"Tüm automod işlemleri bu kanala loglanacak.",
        )
        await interaction.response.send_message(embed=embed)


# ══════════════════════════════════════════════
#  Cog Setup
# ══════════════════════════════════════════════

async def setup(bot: ReoxyBot) -> None:
    """AutoMod cog'unu bota yükler."""
    await bot.add_cog(AutoMod(bot))
