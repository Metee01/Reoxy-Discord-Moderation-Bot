"""
Reoxy Bot — Sabit Değerler

Renkler, emojiler ve diğer sabit değerler burada merkezi olarak tanımlanır.
config.yaml'dan yüklenen değerler ile birleştirilir.
"""

import discord


# ──────────────────────────────────────────────
#  Varsayılan Renkler (config.yaml yüklenemezse)
# ──────────────────────────────────────────────

class Colors:
    """Embed renk paleti — Koyu tema, pembe-mor gradient vurgular."""

    PRIMARY = discord.Color(0x8B5CF6)       # Mor — Ana tema rengi
    SECONDARY = discord.Color(0xD946EF)     # Pembe-mor — İkincil vurgu
    SUCCESS = discord.Color(0x10B981)       # Zümrüt yeşili
    ERROR = discord.Color(0xEF4444)         # Kırmızı
    WARNING = discord.Color(0xF59E0B)       # Kehribar
    INFO = discord.Color(0x6366F1)          # İndigo
    MODERATION = discord.Color(0xD946EF)    # Pembe-mor
    MUTED = discord.Color(0x6B7280)         # Gri


# ──────────────────────────────────────────────
#  Emojiler
# ──────────────────────────────────────────────

class Emojis:
    """Standart Unicode emojiler."""

    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    MODERATION = "🔨"
    KICK = "👢"
    BAN = "🔨"
    TIMEOUT = "🔇"
    WARN = "⚠️"
    UNBAN = "🔓"
    UNTIMEOUT = "🔊"
    DELETE = "🗑️"
    USER = "👤"
    CALENDAR = "📅"
    SHIELD = "🛡️"
    LOADING = "⏳"
    ARROW_RIGHT = "▸"
    DOT = "•"
    DIVIDER = "─" * 30

    # Kanal yönetimi emojileri
    TRASH = "🗑️"
    CLOCK = "🕐"
    LOCK = "🔒"
    UNLOCK = "🔓"
    NUKE = "💥"
    BROOM = "🧹"
    SETTINGS = "⚙️"

    # Automod emojileri
    AUTOMOD = "🤖"
    FILTER = "🔍"
    PROFANITY = "🤬"
    LINK = "🔗"
    CAPS = "🔠"
    TOGGLE_ON = "🟢"
    TOGGLE_OFF = "🔴"
    EXEMPT = "🔰"
    SPAM = "🚫"
    EMOJI = "😀"
    MENTION = "📢"


# ──────────────────────────────────────────────
#  Moderasyon İşlem Türleri
# ──────────────────────────────────────────────

class ActionType:
    """Moderasyon işlem türü sabitleri (veritabanı ve log'larda kullanılır)."""

    KICK = "kick"
    BAN = "ban"
    SOFTBAN = "softban"
    FORCEBAN = "forceban"
    TIMEOUT = "timeout"
    UNTIMEOUT = "untimeout"
    UNBAN = "unban"
    WARN = "warn"
    DELWARN = "delwarn"
    CLEARWARNS = "clearwarns"

    # Kanal yönetimi işlem türleri
    PURGE = "purge"
    SLOWMODE = "slowmode"
    LOCK = "lock"
    UNLOCK = "unlock"
    NUKE = "nuke"

    # Automod işlem türleri
    AUTOMOD_PROFANITY = "automod_profanity"
    AUTOMOD_LINK = "automod_link"
    AUTOMOD_CAPS = "automod_caps"
    AUTOMOD_SPAM = "automod_spam"
    AUTOMOD_EMOJI = "automod_emoji"
    AUTOMOD_MENTION = "automod_mention"


# İşlem türü → Türkçe etiket eşlemesi
ACTION_LABELS: dict[str, str] = {
    ActionType.KICK: "Sunucudan Atma",
    ActionType.BAN: "Yasaklama",
    ActionType.SOFTBAN: "Soft-Ban",
    ActionType.FORCEBAN: "Force-Ban",
    ActionType.TIMEOUT: "Susturma",
    ActionType.UNTIMEOUT: "Susturma Kaldırma",
    ActionType.UNBAN: "Yasak Kaldırma",
    ActionType.WARN: "Uyarı",
    ActionType.DELWARN: "Uyarı Silme",
    ActionType.CLEARWARNS: "Uyarı Sıfırlama",
    ActionType.PURGE: "Toplu Mesaj Silme",
    ActionType.SLOWMODE: "Yavaş Mod",
    ActionType.LOCK: "Kanal Kilitleme",
    ActionType.UNLOCK: "Kanal Kilidi Açma",
    ActionType.NUKE: "Kanal Yenileme",
    ActionType.AUTOMOD_PROFANITY: "Küfür Filtresi",
    ActionType.AUTOMOD_LINK: "Link Filtresi",
    ActionType.AUTOMOD_CAPS: "Caps Lock Filtresi",
    ActionType.AUTOMOD_SPAM: "Spam Koruması",
    ActionType.AUTOMOD_EMOJI: "Emoji Spamı",
    ActionType.AUTOMOD_MENTION: "Etiket Spamı",
}

# İşlem türü → Emoji eşlemesi
ACTION_EMOJIS: dict[str, str] = {
    ActionType.KICK: Emojis.KICK,
    ActionType.BAN: Emojis.BAN,
    ActionType.SOFTBAN: Emojis.BAN,
    ActionType.FORCEBAN: Emojis.BAN,
    ActionType.TIMEOUT: Emojis.TIMEOUT,
    ActionType.UNTIMEOUT: Emojis.UNTIMEOUT,
    ActionType.UNBAN: Emojis.UNBAN,
    ActionType.WARN: Emojis.WARN,
    ActionType.DELWARN: Emojis.DELETE,
    ActionType.CLEARWARNS: Emojis.DELETE,
    ActionType.PURGE: Emojis.TRASH,
    ActionType.SLOWMODE: Emojis.CLOCK,
    ActionType.LOCK: Emojis.LOCK,
    ActionType.UNLOCK: Emojis.UNLOCK,
    ActionType.NUKE: Emojis.NUKE,
    ActionType.AUTOMOD_PROFANITY: Emojis.PROFANITY,
    ActionType.AUTOMOD_LINK: Emojis.LINK,
    ActionType.AUTOMOD_CAPS: Emojis.CAPS,
    ActionType.AUTOMOD_SPAM: Emojis.SPAM,
    ActionType.AUTOMOD_EMOJI: Emojis.EMOJI,
    ActionType.AUTOMOD_MENTION: Emojis.MENTION,
}
