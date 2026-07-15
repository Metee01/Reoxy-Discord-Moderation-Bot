"""
Reoxy Bot — Embed Oluşturucular

Tutarlı ve profesyonel görünüm için merkezi embed oluşturma fonksiyonları.
Tema: Koyu arka plan, pembe-mor gradient vurgular.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import discord

from utils.constants import ACTION_EMOJIS, ACTION_LABELS, ActionType, Colors, Emojis

if TYPE_CHECKING:
    pass


def _base_embed(
    title: str,
    description: str,
    color: discord.Color,
    *,
    footer_text: str | None = None,
) -> discord.Embed:
    """
    Temel embed şablonu oluşturur.

    Tüm embed'lerde ortak: zaman damgası ve footer.
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(),
    )
    embed.set_footer(
        text=footer_text or "Reoxy Bot • Moderasyon Sistemi",
    )
    return embed


# ══════════════════════════════════════════════
#  Genel Amaçlı Embed'ler
# ══════════════════════════════════════════════

def success_embed(title: str, description: str | None = None) -> discord.Embed:
    """
    Başarılı işlem embed'i (yeşil).

    Args:
        title: Başlık. description verilmezse bu değer açıklama olarak kullanılır.
        description: Açıklama metni (opsiyonel).
    """
    if description is None:
        return _base_embed(
            title=f"{Emojis.SUCCESS}  Başarılı",
            description=title,
            color=Colors.SUCCESS,
        )
    return _base_embed(
        title=f"{Emojis.SUCCESS}  {title}",
        description=description,
        color=Colors.SUCCESS,
    )


def error_embed(title: str, description: str | None = None) -> discord.Embed:
    """
    Hata embed'i (kırmızı).

    Args:
        title: Başlık. description verilmezse bu değer açıklama olarak kullanılır.
        description: Açıklama metni (opsiyonel).
    """
    if description is None:
        return _base_embed(
            title=f"{Emojis.ERROR}  Hata",
            description=title,
            color=Colors.ERROR,
        )
    return _base_embed(
        title=f"{Emojis.ERROR}  {title}",
        description=description,
        color=Colors.ERROR,
    )


def warning_embed(title: str, description: str | None = None) -> discord.Embed:
    """
    Uyarı embed'i (kehribar).

    Args:
        title: Başlık. description verilmezse bu değer açıklama olarak kullanılır.
        description: Açıklama metni (opsiyonel).
    """
    if description is None:
        return _base_embed(
            title=f"{Emojis.WARNING}  Uyarı",
            description=title,
            color=Colors.WARNING,
        )
    return _base_embed(
        title=f"{Emojis.WARNING}  {title}",
        description=description,
        color=Colors.WARNING,
    )


def info_embed(title: str, description: str | None = None) -> discord.Embed:
    """
    Bilgi embed'i (indigo).

    Args:
        title: Başlık. description verilmezse bu değer açıklama olarak kullanılır.
        description: Açıklama metni (opsiyonel).
    """
    if description is None:
        return _base_embed(
            title=f"{Emojis.INFO}  Bilgi",
            description=title,
            color=Colors.INFO,
        )
    return _base_embed(
        title=f"{Emojis.INFO}  {title}",
        description=description,
        color=Colors.INFO,
    )


# ══════════════════════════════════════════════
#  Moderasyon Embed'leri
# ══════════════════════════════════════════════

def mod_action_embed(
    action: str,
    user: discord.User | discord.Member,
    moderator: discord.User | discord.Member,
    reason: str = "Sebep belirtilmedi",
    *,
    duration: str | None = None,
    extra_fields: list[tuple[str, str, bool]] | None = None,
) -> discord.Embed:
    """
    Moderasyon işlemi sonucu embed'i (kanal yanıtı).

    Args:
        action: İşlem türü (ActionType sabitleri).
        user: Hedef kullanıcı.
        moderator: İşlemi yapan moderatör.
        reason: İşlem sebebi.
        duration: Süre (varsa).
        extra_fields: Ek alanlar [(name, value, inline), ...].
    """
    emoji = ACTION_EMOJIS.get(action, Emojis.MODERATION)
    label = ACTION_LABELS.get(action, action.capitalize())

    embed = _base_embed(
        title=f"{emoji}  {label}",
        description=f"**{user.mention}** kullanıcısına **{label.lower()}** işlemi uygulandı.",
        color=Colors.MODERATION,
    )

    embed.add_field(name=f"{Emojis.USER} Kullanıcı", value=f"{user} (`{user.id}`)", inline=True)
    embed.add_field(name=f"{Emojis.SHIELD} Moderatör", value=f"{moderator.mention}", inline=True)

    if duration:
        embed.add_field(name="⏱️ Süre", value=duration, inline=True)

    embed.add_field(name="📝 Sebep", value=reason, inline=False)

    if extra_fields:
        for name, value, inline in extra_fields:
            embed.add_field(name=name, value=value, inline=inline)

    embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)

    return embed


def mod_log_embed(
    action: str,
    user: discord.User | discord.Member | discord.Object,
    moderator: discord.User | discord.Member,
    reason: str = "Sebep belirtilmedi",
    *,
    duration: str | None = None,
    case_id: int | None = None,
) -> discord.Embed:
    """
    Moderasyon log kanalı için detaylı embed.

    Args:
        action: İşlem türü.
        user: Hedef kullanıcı (Object olabilir — forceban).
        moderator: İşlemi yapan moderatör.
        reason: Sebep.
        duration: Süre.
        case_id: Veritabanı log ID'si.
    """
    emoji = ACTION_EMOJIS.get(action, Emojis.MODERATION)
    label = ACTION_LABELS.get(action, action.capitalize())

    # User bilgisi — Object ise sadece ID göster
    if isinstance(user, discord.Object):
        user_text = f"ID: `{user.id}`"
        user_mention = f"<@{user.id}>"
    else:
        user_text = f"{user} (`{user.id}`)"
        user_mention = user.mention

    embed = _base_embed(
        title=f"{emoji}  {label}",
        description=(
            f"{Emojis.ARROW_RIGHT} **Kullanıcı:** {user_mention}\n"
            f"{Emojis.ARROW_RIGHT} **Moderatör:** {moderator.mention}\n"
            f"{Emojis.ARROW_RIGHT} **Sebep:** {reason}"
        ),
        color=Colors.MODERATION,
        footer_text=f"Reoxy Bot • Vaka #{case_id}" if case_id else "Reoxy Bot • Moderasyon Logu",
    )

    if duration:
        embed.add_field(name="⏱️ Süre", value=duration, inline=True)

    embed.add_field(name=f"{Emojis.USER} Kullanıcı Detay", value=user_text, inline=True)
    embed.add_field(name=f"{Emojis.CALENDAR} Tarih", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=True)

    # Thumbnail — sadece gerçek User nesnelerinde
    if hasattr(user, "display_avatar") and user.display_avatar:
        embed.set_thumbnail(url=user.display_avatar.url)

    return embed


def dm_notification_embed(
    action: str,
    guild_name: str,
    reason: str = "Sebep belirtilmedi",
    *,
    duration: str | None = None,
) -> discord.Embed:
    """
    Kullanıcıya DM ile gönderilecek bildirim embed'i.

    Args:
        action: İşlem türü.
        guild_name: Sunucu adı.
        reason: Sebep.
        duration: Süre (varsa).
    """
    emoji = ACTION_EMOJIS.get(action, Emojis.MODERATION)
    label = ACTION_LABELS.get(action, action.capitalize())

    description_parts = [
        f"**{guild_name}** sunucusunda size **{label.lower()}** işlemi uygulandı.",
        "",
        f"**📝 Sebep:** {reason}",
    ]

    if duration:
        description_parts.append(f"**⏱️ Süre:** {duration}")

    embed = _base_embed(
        title=f"{emoji}  {label} — Bildirim",
        description="\n".join(description_parts),
        color=Colors.WARNING,
        footer_text=f"Reoxy Bot • {guild_name}",
    )

    return embed


def warn_list_embed(
    user: discord.User | discord.Member,
    warnings: list[dict],
    guild_name: str,
) -> discord.Embed:
    """
    Kullanıcının uyarı listesi embed'i.

    Args:
        user: Hedef kullanıcı.
        warnings: Uyarı sözlüklerinin listesi.
        guild_name: Sunucu adı.
    """
    if not warnings:
        embed = _base_embed(
            title=f"{Emojis.SUCCESS}  Uyarı Listesi",
            description=f"**{user}** kullanıcısının aktif uyarısı bulunmuyor.",
            color=Colors.SUCCESS,
        )
        embed.set_thumbnail(url=user.display_avatar.url if hasattr(user, "display_avatar") and user.display_avatar else None)
        return embed

    description_lines = [
        f"**{user}** kullanıcısının **{len(warnings)}** aktif uyarısı var:\n"
    ]

    for i, warn in enumerate(warnings, 1):
        created = warn.get("created_at", "Bilinmiyor")
        description_lines.append(
            f"**`#{warn['id']}`** {Emojis.DOT} <@{warn['moderator_id']}> tarafından\n"
            f"　　📝 {warn['reason']}\n"
            f"　　{Emojis.CALENDAR} {created}\n"
        )

    embed = _base_embed(
        title=f"{Emojis.WARN}  Uyarı Listesi — {user}",
        description="\n".join(description_lines),
        color=Colors.WARNING,
        footer_text=f"Reoxy Bot • {guild_name}",
    )

    embed.set_thumbnail(url=user.display_avatar.url if hasattr(user, "display_avatar") and user.display_avatar else None)

    return embed
