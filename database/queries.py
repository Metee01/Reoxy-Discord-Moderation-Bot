"""
Reoxy Bot — Veritabanı Sorguları

Uyarı, moderasyon log ve sunucu yapılandırma işlemleri için
yüksek seviyeli async sorgu fonksiyonları.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.database import Database


# ══════════════════════════════════════════════
#  UYARI (Warning) Sorguları
# ══════════════════════════════════════════════

async def add_warning(
    db: Database,
    guild_id: int,
    user_id: int,
    moderator_id: int,
    reason: str = "Sebep belirtilmedi",
) -> int:
    """
    Yeni uyarı ekler.

    Returns:
        Eklenen uyarının ID'si.
    """
    # PostgreSQL'de INSERT ... RETURNING id kullanarak son eklenen id'yi alıyoruz
    row = await db.fetch_one(
        """
        INSERT INTO warnings (guild_id, user_id, moderator_id, reason)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        guild_id, user_id, moderator_id, reason,
    )
    return row["id"] if row else 0


async def get_active_warnings(
    db: Database,
    guild_id: int,
    user_id: int,
) -> list[dict[str, Any]]:
    """
    Kullanıcının aktif uyarılarını döndürür (yeniden eskiye sıralı).

    Returns:
        Uyarı sözlüklerinin listesi.
    """
    rows = await db.fetch_all(
        """
        SELECT id, moderator_id, reason, created_at
        FROM warnings
        WHERE guild_id = $1 AND user_id = $2 AND active = TRUE
        ORDER BY created_at DESC
        """,
        guild_id, user_id,
    )
    return [
        {
            "id": row["id"],
            "moderator_id": row["moderator_id"],
            "reason": row["reason"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


async def get_active_warning_count(
    db: Database,
    guild_id: int,
    user_id: int,
) -> int:
    """Kullanıcının aktif uyarı sayısını döndürür."""
    row = await db.fetch_one(
        """
        SELECT COUNT(*) FROM warnings
        WHERE guild_id = $1 AND user_id = $2 AND active = TRUE
        """,
        guild_id, user_id,
    )
    return row[0] if row else 0


async def deactivate_warning(db: Database, warning_id: int, guild_id: int) -> bool:
    """
    Belirli bir uyarıyı pasif yapar (soft-delete).

    Returns:
        İşlem başarılı mı (uyarı bulundu ve güncellendi mi).
    """
    res = await db.execute(
        """
        UPDATE warnings SET active = FALSE
        WHERE id = $1 AND guild_id = $2 AND active = TRUE
        """,
        warning_id, guild_id,
    )
    # res string'i örn. "UPDATE 1" veya "UPDATE 0"
    if res and res.startswith("UPDATE"):
        try:
            count = int(res.split()[1])
            return count > 0
        except (IndexError, ValueError):
            pass
    return False


async def clear_warnings(db: Database, guild_id: int, user_id: int) -> int:
    """
    Kullanıcının tüm aktif uyarılarını pasif yapar.

    Returns:
        Pasif yapılan uyarı sayısı.
    """
    res = await db.execute(
        """
        UPDATE warnings SET active = FALSE
        WHERE guild_id = $1 AND user_id = $2 AND active = TRUE
        """,
        guild_id, user_id,
    )
    if res and res.startswith("UPDATE"):
        try:
            return int(res.split()[1])
        except (IndexError, ValueError):
            pass
    return 0


# ══════════════════════════════════════════════
#  MODERASYON LOG Sorguları
# ══════════════════════════════════════════════

async def add_mod_log(
    db: Database,
    guild_id: int,
    action: str,
    user_id: int,
    moderator_id: int,
    reason: str = "Sebep belirtilmedi",
    duration: str | None = None,
) -> int:
    """
    Moderasyon log kaydı ekler.

    Returns:
        Eklenen log'un ID'si.
    """
    row = await db.fetch_one(
        """
        INSERT INTO mod_logs (guild_id, action, user_id, moderator_id, reason, duration)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        guild_id, action, user_id, moderator_id, reason, duration,
    )
    return row["id"] if row else 0


# ══════════════════════════════════════════════
#  SUNUCU YAPILANDIRMA Sorguları
# ══════════════════════════════════════════════

async def get_guild_config(db: Database, guild_id: int) -> dict[str, Any]:
    """
    Sunucu yapılandırmasını döndürür.
    Kayıt yoksa varsayılan değerlerle oluşturur.

    Returns:
        Yapılandırma sözlüğü.
    """
    row = await db.fetch_one(
        "SELECT * FROM guild_config WHERE guild_id = $1",
        guild_id,
    )

    if row is None:
        # Varsayılan yapılandırma oluştur
        await db.execute(
            "INSERT INTO guild_config (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO NOTHING",
            guild_id,
        )
        return {
            "guild_id": guild_id,
            "mod_log_channel": None,
            "warn_threshold": 3,
            "warn_action": "timeout",
            "mute_duration": 3600,
        }

    return {
        "guild_id": row["guild_id"],
        "mod_log_channel": row["mod_log_channel"],
        "warn_threshold": row["warn_threshold"],
        "warn_action": row["warn_action"],
        "mute_duration": row["mute_duration"],
    }


async def set_mod_log_channel(db: Database, guild_id: int, channel_id: int | None) -> None:
    """Moderasyon log kanalını ayarlar."""
    # Önce kayıt var mı kontrol et, yoksa oluştur
    await get_guild_config(db, guild_id)
    await db.execute(
        "UPDATE guild_config SET mod_log_channel = $1 WHERE guild_id = $2",
        channel_id, guild_id,
    )


async def set_warn_threshold(db: Database, guild_id: int, threshold: int) -> None:
    """Uyarı eşiğini ayarlar."""
    await get_guild_config(db, guild_id)
    await db.execute(
        "UPDATE guild_config SET warn_threshold = $1 WHERE guild_id = $2",
        threshold, guild_id,
    )


async def set_warn_action(db: Database, guild_id: int, action: str, duration: int = 3600) -> None:
    """Uyarı eşiğinde uygulanacak cezayı ayarlar."""
    await get_guild_config(db, guild_id)
    await db.execute(
        "UPDATE guild_config SET warn_action = $1, mute_duration = $2 WHERE guild_id = $3",
        action, duration, guild_id,
    )


# ══════════════════════════════════════════════
#  AUTOMOD YAPILANDIRMA Sorguları
# ══════════════════════════════════════════════

async def get_automod_config(db: Database, guild_id: int) -> dict[str, Any]:
    """
    Automod yapılandırmasını döndürür.
    Kayıt yoksa varsayılan değerlerle oluşturur.
    """
    row = await db.fetch_one(
        "SELECT * FROM automod_config WHERE guild_id = $1",
        guild_id,
    )

    defaults = {
        "guild_id": guild_id,
        "profanity_enabled": False,
        "profanity_action": "warn",
        "link_filter_enabled": False,
        "link_filter_action": "delete",
        "link_block_invites": True,
        "link_block_all_urls": False,
        "caps_filter_enabled": False,
        "caps_threshold": 70,
        "caps_min_length": 10,
        "caps_action": "delete",
        "log_channel": None,
        "spam_enabled": False,
        "spam_max_messages": 5,
        "spam_window_seconds": 5,
        "spam_action": "timeout",
        "emoji_filter_enabled": False,
        "emoji_max_count": 15,
        "emoji_action": "delete",
        "mention_filter_enabled": False,
        "mention_max_count": 5,
        "mention_action": "delete",
    }

    if row is None:
        await db.execute(
            "INSERT INTO automod_config (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO NOTHING",
            guild_id,
        )
        return defaults

    result = {}
    for key, default_val in defaults.items():
        # PostgreSQL'de record field'a dict gibi erişebiliyoruz
        val = row[key]
        if val is None:
            result[key] = default_val
        else:
            if isinstance(default_val, bool):
                result[key] = bool(val)
            else:
                result[key] = val
    return result


async def update_automod_config(
    db: Database, guild_id: int, **kwargs: Any
) -> None:
    """
    Automod yapılandırmasını günceller.

    Kullanım:
        await update_automod_config(db, guild_id, profanity_enabled=True, caps_threshold=80)
    """
    # Önce kayıt var mı kontrol et
    await get_automod_config(db, guild_id)

    valid_columns = {
        "profanity_enabled", "profanity_action",
        "link_filter_enabled", "link_filter_action",
        "link_block_invites", "link_block_all_urls",
        "caps_filter_enabled", "caps_threshold", "caps_min_length", "caps_action",
        "log_channel",
        "spam_enabled", "spam_max_messages", "spam_window_seconds", "spam_action",
        "emoji_filter_enabled", "emoji_max_count", "emoji_action",
        "mention_filter_enabled", "mention_max_count", "mention_action",
    }

    updates = {k: v for k, v in kwargs.items() if k in valid_columns}
    if not updates:
        return

    # asyncpg parametrik binding için $1, $2, ... desenini dinamik oluşturuyoruz
    set_clauses = []
    values = []
    # guild_id en son parametre ($len+1) olacak
    for idx, (col, val) in enumerate(updates.items(), start=1):
        set_clauses.append(f"{col} = ${idx}")
        values.append(val)
    
    guild_param_idx = len(updates) + 1
    values.append(guild_id)
    
    set_clause = ", ".join(set_clauses)

    await db.execute(
        f"UPDATE automod_config SET {set_clause} WHERE guild_id = ${guild_param_idx}",
        *values,
    )


# ══════════════════════════════════════════════
#  AUTOMOD KELİME LİSTESİ Sorguları
# ══════════════════════════════════════════════

async def add_automod_word(
    db: Database, guild_id: int, word: str, added_by: int
) -> bool:
    """
    Yasaklı kelime ekler.

    Returns:
        Başarılıysa True, kelime zaten varsa False.
    """
    try:
        await db.execute(
            "INSERT INTO automod_words (guild_id, word, added_by) VALUES ($1, $2, $3) ON CONFLICT (guild_id, word) DO NOTHING",
            guild_id, word.lower().strip(), added_by,
        )
        return True
    except Exception:
        return False


async def remove_automod_word(db: Database, guild_id: int, word: str) -> bool:
    """
    Yasaklı kelimeyi siler.

    Returns:
        Başarılıysa True, kelime bulunamadıysa False.
    """
    res = await db.execute(
        "DELETE FROM automod_words WHERE guild_id = $1 AND word = $2",
        guild_id, word.lower().strip(),
    )
    if res and res.startswith("DELETE"):
        try:
            return int(res.split()[1]) > 0
        except (IndexError, ValueError):
            pass
    return False


async def get_automod_words(db: Database, guild_id: int) -> list[str]:
    """Sunucunun yasaklı kelime listesini döndürür."""
    rows = await db.fetch_all(
        "SELECT word FROM automod_words WHERE guild_id = $1 ORDER BY word",
        guild_id,
    )
    return [row["word"] for row in rows]


async def add_automod_words_bulk(
    db: Database, guild_id: int, words: list[str], added_by: int
) -> int:
    """
    Birden fazla yasaklı kelime ekler.

    Returns:
        Eklenen kelime sayısı.
    """
    added = 0
    for word in words:
        if await add_automod_word(db, guild_id, word, added_by):
            added += 1
    return added


# ══════════════════════════════════════════════
#  AUTOMOD MUAF ROLLER Sorguları
# ══════════════════════════════════════════════

async def add_whitelist_role(
    db: Database, guild_id: int, role_id: int, filter_type: str = "all"
) -> bool:
    """
    Automod muaf rolü ekler.

    Args:
        filter_type: "all", "profanity", "link", "caps"

    Returns:
        Başarılıysa True.
    """
    try:
        await db.execute(
            "INSERT INTO automod_whitelist_roles (guild_id, role_id, filter_type) VALUES ($1, $2, $3) ON CONFLICT (guild_id, role_id, filter_type) DO NOTHING",
            guild_id, role_id, filter_type,
        )
        return True
    except Exception:
        return False


async def remove_whitelist_role(
    db: Database, guild_id: int, role_id: int, filter_type: str = "all"
) -> bool:
    """Automod muaf rolünü siler."""
    res = await db.execute(
        "DELETE FROM automod_whitelist_roles WHERE guild_id = $1 AND role_id = $2 AND filter_type = $3",
        guild_id, role_id, filter_type,
    )
    if res and res.startswith("DELETE"):
        try:
            return int(res.split()[1]) > 0
        except (IndexError, ValueError):
            pass
    return False


async def get_whitelist_roles(
    db: Database, guild_id: int, filter_type: str | None = None
) -> list[dict[str, Any]]:
    """
    Muaf rolleri döndürür.

    Args:
        filter_type: Belirli bir filtre için muaf roller. None ise tümünü döndürür.
    """
    if filter_type:
        rows = await db.fetch_all(
            "SELECT role_id, filter_type FROM automod_whitelist_roles WHERE guild_id = $1 AND filter_type IN ($2, 'all')",
            guild_id, filter_type,
        )
    else:
        rows = await db.fetch_all(
            "SELECT role_id, filter_type FROM automod_whitelist_roles WHERE guild_id = $1",
            guild_id,
        )
    return [{"role_id": row["role_id"], "filter_type": row["filter_type"]} for row in rows]


async def is_role_whitelisted(
    db: Database, guild_id: int, role_ids: list[int], filter_type: str
) -> bool:
    """
    Kullanıcının rollerinden herhangi birinin belirli filtre için muaf olup olmadığını kontrol eder.

    Args:
        role_ids: Kullanıcının rol ID listesi.
        filter_type: Kontrol edilecek filtre türü.
    """
    if not role_ids:
        return False

    # PostgreSQL IN operatörü ile binding yapmak için:
    # `role_id = ANY($2::bigint[])` veya dinamik $2, $3... oluşturulabilir.
    # EN kolayı ve temiz olanı = ANY($2) kullanmaktır.
    row = await db.fetch_one(
        """
        SELECT COUNT(*) FROM automod_whitelist_roles
        WHERE guild_id = $1 AND role_id = ANY($2::bigint[])
        AND filter_type IN ($3, 'all')
        """,
        guild_id, role_ids, filter_type,
    )
    return (row[0] if row else 0) > 0


# ══════════════════════════════════════════════
#  KANAL YÖNETİMİ YAPILANDIRMA Sorguları
# ══════════════════════════════════════════════

# channel_config tablosundaki geçerli sütunlar (güvenlik için doğrulamada kullanılır)
_CHANNEL_CONFIG_DEFAULTS: dict[str, Any] = {
    "guild_id": 0,
    "purge_enabled": True,
    "purge_max_messages": 1000,
    "slowmode_enabled": True,
    "slowmode_max_seconds": 21600,
    "lock_enabled": True,
    "lock_save_permissions": True,
    "nuke_enabled": True,
    "nuke_require_confirm": True,
}


async def get_channel_config(db: Database, guild_id: int) -> dict[str, Any]:
    """
    Kanal yönetimi yapılandırmasını döndürür.
    Kayıt yoksa varsayılan değerlerle oluşturur.

    Returns:
        Yapılandırma sözlüğü.
    """
    row = await db.fetch_one(
        "SELECT * FROM channel_config WHERE guild_id = $1",
        guild_id,
    )

    if row is None:
        await db.execute(
            "INSERT INTO channel_config (guild_id) VALUES ($1) ON CONFLICT (guild_id) DO NOTHING",
            guild_id,
        )
        return dict(_CHANNEL_CONFIG_DEFAULTS, guild_id=guild_id)

    result: dict[str, Any] = {}
    for key, default_val in _CHANNEL_CONFIG_DEFAULTS.items():
        val = row[key]
        if val is None:
            result[key] = default_val
        else:
            if isinstance(default_val, bool):
                result[key] = bool(val)
            else:
                result[key] = val
    return result


async def update_channel_config(
    db: Database, guild_id: int, **kwargs: Any
) -> None:
    """
    Kanal yönetimi yapılandırmasını günceller.

    Kullanım:
        await update_channel_config(db, guild_id, purge_enabled=False, purge_max_messages=500)
    """
    # Önce kayıt var mı kontrol et (yoksa oluşturur)
    await get_channel_config(db, guild_id)

    valid_columns = set(_CHANNEL_CONFIG_DEFAULTS.keys()) - {"guild_id"}
    updates = {k: v for k, v in kwargs.items() if k in valid_columns}
    if not updates:
        return

    set_clauses = []
    values = []
    for idx, (col, val) in enumerate(updates.items(), start=1):
        set_clauses.append(f"{col} = ${idx}")
        values.append(val)
    
    guild_param_idx = len(updates) + 1
    values.append(guild_id)
    
    set_clause = ", ".join(set_clauses)

    await db.execute(
        f"UPDATE channel_config SET {set_clause} WHERE guild_id = ${guild_param_idx}",
        *values,
    )


# ══════════════════════════════════════════════
#  KANAL İZNİ KAYDETME Sorguları (lock/unlock)
# ══════════════════════════════════════════════

async def save_channel_permissions(
    db: Database, guild_id: int, channel_id: int, permission_data: dict[str, Any]
) -> None:
    """
    Kanalın izinlerini JSON olarak kaydeder (UPSERT).
    Lock sırasında çağrılır, unlock sırasında geri yüklenir.

    Args:
        permission_data: İzin sözlüğü (örn: {"send_messages": True, "view_channel": None}).
    """
    data = json.dumps(permission_data)
    await db.execute(
        """
        INSERT INTO saved_permissions (guild_id, channel_id, permission_data)
        VALUES ($1, $2, $3)
        ON CONFLICT(guild_id, channel_id) DO UPDATE SET permission_data = EXCLUDED.permission_data
        """,
        guild_id, channel_id, data,
    )


async def get_saved_permissions(
    db: Database, guild_id: int, channel_id: int
) -> dict[str, Any] | None:
    """
    Kaydedilmiş izinleri döndürür.

    Returns:
        İzin sözlüğü veya kayıt yoksa None.
    """
    row = await db.fetch_one(
        "SELECT permission_data FROM saved_permissions WHERE guild_id = $1 AND channel_id = $2",
        guild_id, channel_id,
    )
    if row is None:
        return None
    try:
        return json.loads(row["permission_data"])
    except (json.JSONDecodeError, TypeError):
        return None


async def delete_saved_permissions(
    db: Database, guild_id: int, channel_id: int
) -> None:
    """Kaydedilmiş izinleri siler (geri yükleme sonrası temizlik)."""
    await db.execute(
        "DELETE FROM saved_permissions WHERE guild_id = $1 AND channel_id = $2",
        guild_id, channel_id,
    )
