"""
Reoxy Bot — Veritabanı Şema Tanımları

PostgreSQL tablo oluşturma ifadeleri (DDL).
"""

# ── Uyarılar Tablosu ──
CREATE_WARNINGS_TABLE = """
CREATE TABLE IF NOT EXISTS warnings (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    moderator_id    BIGINT NOT NULL,
    reason          TEXT    NOT NULL DEFAULT 'Sebep belirtilmedi',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active          BOOLEAN NOT NULL DEFAULT TRUE
);
"""

CREATE_WARNINGS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_warnings_guild_user
ON warnings (guild_id, user_id, active);
"""

# ── Moderasyon Logları Tablosu ──
CREATE_MOD_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS mod_logs (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    action          TEXT    NOT NULL,
    user_id         BIGINT NOT NULL,
    moderator_id    BIGINT NOT NULL,
    reason          TEXT    DEFAULT 'Sebep belirtilmedi',
    duration        TEXT    DEFAULT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_MOD_LOGS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_mod_logs_guild
ON mod_logs (guild_id, created_at DESC);
"""

# ── Sunucu Yapılandırma Tablosu ──
CREATE_GUILD_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id            BIGINT PRIMARY KEY,
    mod_log_channel     BIGINT DEFAULT NULL,
    warn_threshold      INTEGER DEFAULT 3,
    warn_action         TEXT    DEFAULT 'timeout',
    mute_duration       INTEGER DEFAULT 3600
);
"""

# ══════════════════════════════════════════════
#  AUTOMOD TABLOLARI
# ══════════════════════════════════════════════

# ── Automod Yapılandırma Tablosu ──
CREATE_AUTOMOD_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS automod_config (
    guild_id                BIGINT PRIMARY KEY,
    profanity_enabled       BOOLEAN DEFAULT FALSE,
    profanity_action        TEXT    DEFAULT 'warn',
    link_filter_enabled     BOOLEAN DEFAULT FALSE,
    link_filter_action      TEXT    DEFAULT 'delete',
    link_block_invites      BOOLEAN DEFAULT TRUE,
    link_block_all_urls     BOOLEAN DEFAULT FALSE,
    caps_filter_enabled     BOOLEAN DEFAULT FALSE,
    caps_threshold          INTEGER DEFAULT 70,
    caps_min_length         INTEGER DEFAULT 10,
    caps_action             TEXT    DEFAULT 'delete',
    log_channel             BIGINT DEFAULT NULL,
    spam_enabled            BOOLEAN DEFAULT FALSE,
    spam_max_messages       INTEGER DEFAULT 5,
    spam_window_seconds     INTEGER DEFAULT 5,
    spam_action             TEXT    DEFAULT 'timeout',
    emoji_filter_enabled    BOOLEAN DEFAULT FALSE,
    emoji_max_count         INTEGER DEFAULT 15,
    emoji_action            TEXT    DEFAULT 'delete',
    mention_filter_enabled  BOOLEAN DEFAULT FALSE,
    mention_max_count       INTEGER DEFAULT 5,
    mention_action          TEXT    DEFAULT 'delete'
);
"""

# ── Yasaklı Kelimeler Tablosu ──
CREATE_AUTOMOD_WORDS_TABLE = """
CREATE TABLE IF NOT EXISTS automod_words (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    word        TEXT    NOT NULL,
    added_by    BIGINT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guild_id, word)
);
"""

CREATE_AUTOMOD_WORDS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_automod_words_guild
ON automod_words (guild_id);
"""

# ── Muaf Roller Tablosu (Automod filtrelerinden muaf roller) ──
CREATE_AUTOMOD_WHITELIST_TABLE = """
CREATE TABLE IF NOT EXISTS automod_whitelist_roles (
    id          SERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    role_id     BIGINT NOT NULL,
    filter_type TEXT    NOT NULL DEFAULT 'all',
    UNIQUE(guild_id, role_id, filter_type)
);
"""

CREATE_AUTOMOD_WHITELIST_INDEX = """
CREATE INDEX IF NOT EXISTS idx_automod_whitelist_guild
ON automod_whitelist_roles (guild_id);
"""

# ══════════════════════════════════════════════
#  KANAL YÖNETİMİ TABLOLARI
# ══════════════════════════════════════════════

# ── Kanal Yönetimi Yapılandırma Tablosu ──
CREATE_CHANNEL_CONFIG_TABLE = """
CREATE TABLE IF NOT EXISTS channel_config (
    guild_id                BIGINT PRIMARY KEY,
    purge_enabled           BOOLEAN DEFAULT TRUE,
    purge_max_messages      INTEGER DEFAULT 1000,
    slowmode_enabled        BOOLEAN DEFAULT TRUE,
    slowmode_max_seconds    INTEGER DEFAULT 21600,
    lock_enabled            BOOLEAN DEFAULT TRUE,
    lock_save_permissions   BOOLEAN DEFAULT TRUE,
    nuke_enabled            BOOLEAN DEFAULT TRUE,
    nuke_require_confirm    BOOLEAN DEFAULT TRUE
);
"""

# ── Kaydedilmiş Kanal İzinleri Tablosu (lock/unlock geri yükleme) ──
CREATE_SAVED_PERMISSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS saved_permissions (
    id              SERIAL PRIMARY KEY,
    guild_id        BIGINT NOT NULL,
    channel_id      BIGINT NOT NULL,
    permission_data TEXT    NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(guild_id, channel_id)
);
"""

CREATE_SAVED_PERMISSIONS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_saved_permissions_guild
ON saved_permissions (guild_id);
"""

# Tüm tablo oluşturma ifadeleri — sıralı çalıştırılacak
ALL_TABLES = [
    CREATE_WARNINGS_TABLE,
    CREATE_WARNINGS_INDEX,
    CREATE_MOD_LOGS_TABLE,
    CREATE_MOD_LOGS_INDEX,
    CREATE_GUILD_CONFIG_TABLE,
    CREATE_AUTOMOD_CONFIG_TABLE,
    CREATE_AUTOMOD_WORDS_TABLE,
    CREATE_AUTOMOD_WORDS_INDEX,
    CREATE_AUTOMOD_WHITELIST_TABLE,
    CREATE_AUTOMOD_WHITELIST_INDEX,
    CREATE_CHANNEL_CONFIG_TABLE,
    CREATE_SAVED_PERMISSIONS_TABLE,
    CREATE_SAVED_PERMISSIONS_INDEX,
]

# PostgreSQL'de migrations ihtiyacı varsa ALTER TABLE formatında:
MIGRATIONS = []
