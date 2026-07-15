# Reoxy Bot — Geliştirme Kuralları

> Bu dosya, Reoxy Bot projesinde çalışan tüm AI asistanlarına ve geliştiricilere rehberlik eder.
> Aşağıdaki kurallara **kesinlikle** uyulmalıdır. Mevcut kod tabanındaki kalıplar bozulmamalıdır.

---

## 📋 Proje Özeti

**Reoxy Bot**, discord.py tabanlı profesyonel bir Discord moderasyon botudur.
- **Dil:** Python 3.14+
- **Framework:** discord.py 2.3+ (async/await)
- **Veritabanı:** SQLite (aiosqlite, async)
- **Loglama:** Loguru
- **Yapılandırma:** YAML (config.yaml) + .env
- **Komut sistemi:** Hybrid (hem slash hem prefix)

---

## 🗂️ Proje Mimarisi

```
reoxy-bot/
├── bot.py                 # Ana giriş noktası
├── config.yaml            # Statik yapılandırma (renkler, emojiler, ayarlar)
├── .env                   # Gizli değişkenler (DISCORD_TOKEN) — ASLA commit etme
├── requirements.txt       # Bağımlılıklar
├── core/                  # Çekirdek sistemler
│   ├── bot.py             # ReoxyBot (commands.Bot alt sınıfı)
│   ├── config.py          # Config — YAML yükleyici (sınıf metotları)
│   ├── database.py        # Database — async SQLite yöneticisi
│   └── logger.py          # Loguru yapılandırması
├── cogs/                  # Discord komut grupları (Cog'lar)
│   ├── moderation.py      # Kick/Ban/Timeout/Warn vb.
│   ├── automod.py         # Otomatik filtreler (küfür, link, spam...)
│   └── channel.py         # Kanal yönetimi (purge, slowmode, lock, nuke)
├── database/              # Veritabanı katmanı
│   ├── models.py          # Tablo şemaları (ALL_TABLES, MIGRATIONS)
│   └── queries.py         # Yüksek seviyeli async sorgu fonksiyonları
├── utils/                 # Yardımcı modüller
│   ├── constants.py       # Colors, Emojis, ActionType sabitleri
│   ├── embeds.py          # Merkezi embed oluşturucular
│   ├── permissions.py     # Yetki & hiyerarşi kontrolleri
│   └── time_parser.py     # Süre çözümleyici ("10m", "1h30m" → timedelta)
├── data/                  # SQLite veritabanı dosyaları (.gitignore'da)
└── logs/                  # Log dosyaları (.gitignore'da)
```

### Yeni bir özellik eklerken nereye yazılır?

| İhtiyaç | Nereye |
|---|---|
| Yeni Discord komutu/lListener | `cogs/` altına yeni `.py` veya mevcut cog'a ekle |
| SQL sorgusu | `database/queries.py`'e async fonksiyon ekle |
| Yeni tablo/sütun | `database/models.py`'e `ALL_TABLES` veya `MIGRATIONS` listesine ekle |
| Embed şablonu | `utils/embeds.py`'e fonksiyon ekle |
| Sabit değer (renk, emoji, action type) | `utils/constants.py`'a ekle |
| Yardımcı fonksiyon | `utils/` altına ilgili modüle veya yeni modül |

---

## 🐍 Python & Kod Stili

### Zorunlu İçe Aktarmalar
Her modülün başında şu yapı kullanılır:
```python
"""
Reoxy Bot — Modül Adı

Kısa açıklama.
"""

from __future__ import annotations
```
`from __future__ import annotations` **her zaman** eklenir (geç tip çözümleme için).

### Tip İpuçları (Type Hints)
- **Tüm** fonksiyon parametreleri ve dönüş tipleri tip ipucu içermelidir.
- Modern sentaks kullan: `str | None` (Optional[str] değil), `list[int]` (List[int] değil), `dict[str, Any]`.
```python
async def get_active_warnings(
    db: Database, guild_id: int, user_id: int,
) -> list[dict[str, Any]]:
```

### Circular Import Önleme
`core.bot.ReoxyBot` tipini cog'lar içinde kullanırken yalnızca tip ipucu için `TYPE_CHECKING` bloğu kullan:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.bot import ReoxyBot
```

### Docstring'ler
- **Türkçe** yazılır.
- Her modülün başında modül docstring'i (başlık + açıklama) bulunur.
- Her fonksiyon/metot docstring içerir: kısa açıklama + `Args:` + `Returns:` (gerekirse `Raises:`).
```python
async def add_warning(db: Database, guild_id: int, user_id: int, ...) -> int:
    """
    Yeni uyarı ekler.

    Returns:
        Eklenen uyarının ID'si.
    """
```

### Yorumlar & Bölüm Ayırıcılar
- Kod bölümlerini şu ayırıcılarla grupla:
```python
# ══════════════════════════════════════════════
#  BÖLÜM ADI
# ══════════════════════════════════════════════
```
- Yorumlar **Türkçe** ve "neden"i açıklamalıdır (ne yaptığını kod zaten söyler).

### Asenkron Kurallar
- Tüm I/O (DB, Discord API, dosya) işlemleri `async`/`await` ile yapılır.
- **Asla** `asyncio.run()` kullanma — discord.py event loop'u yönetir.
- Uzun süren senkron işlemleri `asyncio.to_thread()` ile sarmala.

---

## 💬 Discord Komut Kuralları

### Hybrid Komutlar
Moderasyon ve kullanıcı komutları **hybrid** olarak yazılır (hem slash hem prefix destekler):
```python
@commands.hybrid_command(name="kick", description="Kullanıcıyı sunucudan atar.")
@commands.has_permissions(kick_members=True)
@commands.bot_has_permissions(kick_members=True)
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
```

### Komut Yazım Deseni
Bir moderasyon komutu şu adımları sırasıyla izler:
1. **Parametre doğrulama** (geçersizse erken `return await ctx.send(embed=error_embed(...))`)
2. **Yetki hiyerarşi kontrolü** — `check_hierarchy()` kullan
3. **DM bildirimi** — kullanıcıya eylem bildir (`_send_dm` + `dm_notification_embed`)
4. **İşlemi uygula** (kick/ban/timeout)
5. **Logla** — `logger.info("...", arg1, arg2)` (f-string DEĞİL, loguru placeholder)
6. **Kanal yanıtı** — `mod_action_embed` ile
7. **Veritabanına kayıt** — `_log_action` → `queries.add_mod_log`
8. **Mod-log kanalına** — `_log_to_channel` + `mod_log_embed`

### Yetki Kontrolleri
- `@commands.has_permissions(...)` decorator'ı + `@commands.bot_has_permissions(...)` birlikte kullan.
- Hiyerarşi için **her zaman** `utils.permissions.check_hierarchy()` çağrılır — self-action, bot'a işlem, sunucu sahibi, rol sırası kontrolleri yapar.

### Komut & Parametre İsimlendirmesi
- Komut isimları ve parametreler **Türkçe** ve snake-case: `kullanıcı`, `sebep`, `mesaj_silme_günü`.
- Slash komut açıklamaları (`description`) Türkçe ve kullanıcı dostu olmalı.

---

## 🎨 Embed & Görsel Tutarsızlığı

**Kesin kural:** Discord mesajları **her zaman** `utils/embeds.py` fonksiyonlarıyla oluşturulur.
Raw `discord.Embed()` constructor'ı **doğrudan cog'ların içinde kullanılmaz**.

### Mevcut Embed Fonksiyonları
- `success_embed(title, description)` — yeşil, ✅
- `error_embed(title, description)` — kırmızı, ❌
- `warning_embed(title, description)` — kehribar, ⚠️
- `info_embed(title, description)` — indigo, ℹ️
- `mod_action_embed(...)` — moderasyon işlemi yanıtı
- `mod_log_embed(...)` — mod-log kanalı için (case_id içerir)
- `dm_notification_embed(...)` — kullanıcı DM bildirimi
- `warn_list_embed(...)` — uyarı listesi

### Renkler & Emojiler
- Renkler ve emojiler `utils/constants.py`'daki `Colors` ve `Emojis` sınıflarından alınır.
- **Magic değer kullanma** — hex kodları veya emoji karakterleri doğrudan cog'lara gömülmez.
- Tema: Koyu arka plan, pembe-mor (#8B5CF6 / #D946EF) vurgular.

---

## 🗄️ Veritabanı Kuralları

### Erişim
- Tüm DB erişimi `database/queries.py`'deki async fonksiyonlardan yapılır.
- `self.bot.db` (Database örneği) cog'lar içinde kullanılır.
- **Doğrudan SQL yazma** cog'larda — her zaman `queries.py`'e fonksiyon ekle.

### Güvenlik
- **Daima** parametreli sorgular kullan (`?` placeholder):
```python
await db.fetch_all(
    "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ?",
    (guild_id, user_id),
)
```
- **Asla** f-string veya `.format()` ile SQL oluşturma (SQL injection). Tek istisna: `IN (...)` için `",".join("?" * len(items))` deseni.

### Şema Değişiklikleri
- Yeni tablo → `database/models.py` → `ALL_TABLES` listesine `CREATE TABLE IF NOT EXISTS` ekle.
- Yeni sütun → `MIGRATIONS` listesine `ALTER TABLE ... ADD COLUMN` ekle (zaten varsa sessizce atlanır).
- Migration'lar geriye dönük uyumlu olmalı — mevcut verileri silmemeli.

### Cache Kullanımı (Automod deseni)
Sık erişilen veriler (kelime listesi, config) cog içinde cache'lenir:
```python
self._config_cache: dict[int, dict] = {}
```
Ayar değiştiğinde cache `_invalidate_*` metoduyla temizlenir.

### Guild Bazlı "Aç/Kapat/Özelleştir" Deseni
**Kural:** Kullanıcı tarafından kapatılabilen komut içeren her cog, guild bazlı bir `<isim>_config` tablosu ve `/ayar-grubu` slash grubu içermelidir. Desen (automod ve channel cog'ları referans):

1. **Tablo** (`database/models.py`): `<feature>_config` — her komut için `<komut>_enabled` (BOOLEAN default 1) + özelleştirilebilir limitler (`<komut>_max_*`). `ALL_TABLES`'a eklenir.
2. **Sorgular** (`database/queries.py`):
   - `get_<feature>_config(db, guild_id)` — yoksa varsayılanlarla oluşturur, `_DEFAULTS` sözlüğü ile sütun-doğrulamalı eşler.
   - `update_<feature>_config(db, guild_id, **kwargs)` — geçerli sütunlar dışında değer reddeder (SQL injection önlemi).
3. **Cog** (`cogs/<feature>.py`):
   - Her komutun başında `config = await self._get_config(guild_id)` ile açık/kapalı + limit kontrolü yapılır. Kapalıysa `ephemeral` hata embed'i.
   - Config cache: `_get_config` / `_invalidate_config` (automod deseni).
   - `app_commands.Group` ile `/<feature> durum`, `/<feature> <komut>-aç`, `/<feature> <komut>-kapat`, `/<feature> <komut>-limit` komutları (administrator yetkisi).

### İzin Kaydetme Deseni (Lock/Unlock)
Lock sırasında @everyone izinleri JSON olarak `saved_permissions` tablosuna kaydedilir, unlock'ta geri yüklenir. `lock_save_permissions` config'i ile açılıp kapatılabilir. Bu desen "yıkıcı ama geri alınabilir" işlemler için referans alınır.

---

## 📝 Loglama Kuralları

**Sadece** Loguru kullanılır (`from loguru import logger`). Standart `logging` modülü **kullanılmaz**.

### Log Seviyeleri
| Seviye | Kullanım |
|---|---|
| `logger.debug()` | Detaylı akış (cache temizleme vb.) |
| `logger.info()` | Önemli işlemler (komut çalıştırma, kullanıcı yasaklama) |
| `logger.warning()` | Beklenen hatalar (DM gönderilemedi, yetki eksik) |
| `logger.error()` | Beklenmeyen hatalar (`exc_info` ile) |
| `logger.critical()` | Bot çalışamaz (token eksik vb.) |

### Loguru Placeholder Sözdizimi
f-string **kullanma**, loguru'nun lazy placeholder'larını kullan (performans + doğru escaping):
```python
# ✅ DOĞRU
logger.info("Kullanıcı yasaklandı: {} (ID: {})", kullanıcı, kullanıcı.id)

# ❌ YANLIŞ
logger.info(f"Kullanıcı yasaklandı: {kullanıcı} (ID: {kullanıcı.id})")
```

---

## ⚙️ Yapılandırma (Config) Kuralları

- Statik ayarlar `config.yaml`'da, gizli değerler `.env`'de.
- `config.yaml` erişimi **her zaman** `Config.get("bölüm", "anahtar", default=...)` ile:
```python
prefix = Config.get("bot", "prefix", default="!")
```
- `.env` erişimi `os.getenv("DEĞİŞKEN")` ile.
- **Asla** token, şifre veya gizli değeri koda gömme.
- `.env` ve `data/*.db` `.gitignore`'da kalır — commit etme.

---

## 🧩 Yeni Cog Ekleme

Yeni bir cog oluştururken bu iskeleti kullan:
```python
"""
Reoxy Bot — Cog Adı

Açıklama.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from utils.embeds import success_embed, error_embed

if TYPE_CHECKING:
    from core.bot import ReoxyBot


class YeniCog(commands.Cog):
    """Cog Adı — Kısa açıklama."""

    def __init__(self, bot: ReoxyBot) -> None:
        self.bot = bot

    # Komutlar...


async def setup(bot: ReoxyBot) -> None:
    """Cog'u bota yükler."""
    await bot.add_cog(YeniCog(bot))
```

**Önemli:** Yeni cog eklendiğinde mutlaka `core/bot.py` → `setup_hook` → `cog_extensions` listesine ekle. Yoksa yüklenmez.

---

## ✅ Commit Öncesi Kontrol Listesi

Kod yazdıktan sonra şu kurallara uyulduğunu doğrula:

- [ ] `from __future__ import annotations` ekli mi?
- [ ] Tüm fonksiyonlarda dönüş tipi ve parametre tip ipuçları var mı?
- [ ] Docstring'ler Türkçe ve güncel mi?
- [ ] Embed'ler `utils/embeds.py`'den mi geliyor (raw `discord.Embed()` yok)?
- [ ] Renk/emoji `utils/constants.py`'dan mı (magic değer yok)?
- [ ] SQL sorguları parametreli mi (f-string SQL yok)?
- [ ] Loglar loguru placeholder'larıyla mı (`{}`), f-string değil?
- [ ] Yetki gerektiren komutlarda `check_hierarchy()` çağrıldı mı?
- [ ] Yeni cog `core/bot.py` → `cog_extensions`'a eklendi mi?
- [ ] Kapatılabilen komutlar için `<feature>_config` tablosu + `/ayar` slash grubu eklendi mi (guild bazlı aç/kapat deseni)?
- [ ] Yeni ActionType eklendiyse `utils/constants.py` → `ActionType`, `ACTION_LABELS`, `ACTION_EMOJIS` üçlüsü güncellendi mi?
- [ ] `.env`, `data/*.db`, `logs/` commit dışında mı?

---

---
trigger: always_on
description: Consult the graphify knowledge graph at graphify-out/ for codebase and architecture questions.
---

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- For codebase or architecture questions, when `graphify-out/graph.json` exists, first run `graphify query "<question>"` (CLI) or `query_graph` (MCP). Use `graphify path "<A>" "<B>"` / `shortest_path` for relationships and `graphify explain "<concept>"` / `get_node` for focused concepts. These return a scoped subgraph, usually much smaller than `GRAPH_REPORT.md` or raw grep output.
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)


## 🚫 Yapılmaması Gerekenler

- Discord mesajlarını raw string/`discord.Embed()` ile göndermek (embed şablonlarını kullan).
- Cog'lar içinde doğrudan SQL yazmak (`queries.py` kullan).
- f-string ile log veya SQL oluşturmak.
- `print()` kullanmak (loguru kullan).
- Türkçe dışında dilde docstring/kullanıcı mesajı yazmak.
- `Optional[...]` / `List[...]` eski tip ipuçleri (modern `|` sentaksı kullan).
- `data/reoxy.db` veya `.env` dosyasını commit etmek.
-discord.py'nin intent'lerini `core/bot.py` dışında değiştirmek.
- Moderasyon komutlarında hiyerarşi kontrolünü atlamak.
