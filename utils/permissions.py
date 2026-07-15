"""
Reoxy Bot — Yetki Kontrolleri

Moderasyon komutları için yetki doğrulama yardımcıları.
- Rol hiyerarşisi kontrolü
- Self-action engelleme
- Bot yetki kontrolü
"""

from __future__ import annotations

import discord

from utils.embeds import error_embed


class PermissionCheckError(Exception):
    """Yetki kontrolü başarısız olduğunda fırlatılır."""

    def __init__(self, embed: discord.Embed) -> None:
        self.embed = embed
        super().__init__(embed.description)


def check_hierarchy(
    author: discord.Member,
    target: discord.Member,
    bot_member: discord.Member,
    action_name: str = "bu işlemi",
) -> discord.Embed | None:
    """
    Rol hiyerarşisi ve yetki kontrollerini yapar.

    Kontroller:
    1. Kullanıcı kendine işlem yapamaz
    2. Bot'a işlem yapılamaz
    3. Hedefin rolü moderatörden düşük olmalı
    4. Hedefin rolü bot'un rolünden düşük olmalı
    5. Sunucu sahibine işlem yapılamaz

    Args:
        author: Komutu çalıştıran moderatör.
        target: Hedef kullanıcı.
        bot_member: Bot'un sunucudaki Member nesnesi.
        action_name: İşlem adı (hata mesajlarında kullanılır).

    Returns:
        Hata embed'i (kontrol başarısız) veya None (kontrol başarılı).
    """
    # 1. Kendine işlem yapma kontrolü
    if author.id == target.id:
        return error_embed(
            "İşlem Reddedildi",
            f"Kendinize **{action_name}** uygulayamazsınız.",
        )

    # 2. Bot'a işlem yapma kontrolü
    if target.id == bot_member.id:
        return error_embed(
            "İşlem Reddedildi",
            f"Bana **{action_name}** uygulayamazsınız. 🤖",
        )

    # 3. Sunucu sahibi kontrolü
    if target.guild.owner_id == target.id:
        return error_embed(
            "İşlem Reddedildi",
            f"Sunucu sahibine **{action_name}** uygulayamazsınız.",
        )

    # 4. Moderatör hiyerarşi kontrolü
    if author.top_role <= target.top_role and author.id != author.guild.owner_id:
        return error_embed(
            "Yetersiz Yetki",
            f"**{target.display_name}** sizinle aynı veya daha yüksek role sahip. "
            f"**{action_name.capitalize()}** işlemi uygulanamaz.",
        )

    # 5. Bot hiyerarşi kontrolü
    if bot_member.top_role <= target.top_role:
        return error_embed(
            "Bot Yetkisi Yetersiz",
            f"**{target.display_name}** benim rolümle aynı veya daha yüksek role sahip. "
            f"**{action_name.capitalize()}** işlemi uygulanamıyor.",
        )

    return None  # Tüm kontroller başarılı


def check_bot_permissions(
    bot_member: discord.Member,
    *permissions: str,
) -> discord.Embed | None:
    """
    Bot'un gerekli izinlere sahip olup olmadığını kontrol eder.

    Args:
        bot_member: Bot'un sunucudaki Member nesnesi.
        *permissions: Kontrol edilecek izin adları (örn: "ban_members").

    Returns:
        Hata embed'i veya None.
    """
    bot_perms = bot_member.guild_permissions
    missing = [perm for perm in permissions if not getattr(bot_perms, perm, False)]

    if missing:
        perm_names = ", ".join(f"`{p}`" for p in missing)
        return error_embed(
            "Bot Yetkisi Yetersiz",
            f"Bu işlemi gerçekleştirmek için şu izinlere ihtiyacım var:\n{perm_names}\n\n"
            f"Lütfen bot rolünün izinlerini kontrol edin.",
        )

    return None
