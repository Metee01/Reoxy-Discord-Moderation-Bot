<div align="center">

# Reoxy Bot

**Profesyonel Discord Moderasyon Botu**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![discord.py](https://img.shields.io/badge/discord.py-2.3+-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-MIT-yellow?logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Code Style](https://img.shields.io/badge/Code%20Style-Ruff-000000)](https://github.com/astral-sh/ruff)
[![Lisans](https://img.shields.io/badge/Lisans-MIT-yellow?logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Kod Stili](https://img.shields.io/badge/Kod%20Stili-Agents.md-8B5CF6)](AGENTS.md)
[![Deploy](https://img.shields.io/badge/Deploy-Render.com-46E3B7?logo=render&logoColor=white)](https://render.com)
<br>
discord.py · PostgreSQL · Hibrit Komutlar · AutoMod
<br>

Türkçe | [English](README.md)

<br>

</div>

## Özellikler

- **Hibrit Komutlar** — Tüm komutlar hem prefix (`!`) hem de slash (`/`) olarak çalışır
- **AutoMod** — Küfür, link, caps lock, emoji, mention ve spam filtreleri
- **Moderasyon** — Kick, Ban, Softban, Forceban, Timeout, Unban
- **Uyarı Sistemi** — Eşik tabanlı otomatik ceza (timeout / ban)
- **Kanal Yönetimi** — Purge, Slowmode, Lock/Unlock, Nuke
- **Mod-Log** — Tüm işlemler özel log kanalına embed olarak gönderilir
- **SQL Injection Koruması** — Tüm sorgular parametreli, raw SQL cog'larda yasak
- **Yetki Hiyerarşisi** — Kendine işlem, bot'a işlem, rol sırası kontrolleri
- **Guild Bazlı Ac/Kapat** — Her özellik sunucu bazında yönetici tarafından açılıp kapatılabilir

<br>

## Gereksinimler

| Bileşen | Versiyon |
|---|---|
| Python | 3.10+ |
| discord.py | 2.3+ |
| PostgreSQL | 14+ (Supabase, Neon, Render) |
| asyncpg | 0.29+ |

## Hızlı Kurulum

```bash
# 1. Projeyi klonla
git clone https://github.com/Metee01/Reoxy-Discord-Moderation-Bot.git
cd Reoxy-Discord-Moderation-Bot

# 2. Bağımlılıkları yükle
pip install -r requirements.txt

# 3. .env dosyası oluştur (örnek .env.example'dan kopyala)
copy .env.example .env
# Linux/Mac: cp .env.example .env

# 4. .env içini doldur
#    DISCORD_TOKEN=bot_tokenin
#    DATABASE_URL=postgresql://kullanici:sifre@host:5432/veritabanı

# 5. Çalıştır
python bot.py
```

> Supabase kullanıyorsanız **Connection Pooler** adresini (port 5432/6543) kullanmanız önerilir. Session veya Transaction modu her ikisi de çalışır.

<br>

## Render.com'a Deployment

Proje, `render.yaml` dosyası ile Render.com'a tek tıkla deployment için hazırdır.

### Manuel Kurulum

1. Render Dashboard'da **New +** → **Web Service**
2. GitHub reponu bağla
3. Aşağıdaki ayarları kullan:

| Ayar | Değer |
|---|---|
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python bot.py` |
| Health Check Path | `/health` |
| Plan | Free (veya uygun plan) |

4. Environment değişkenlerini ekle:

| Değişken | Değer |
|---|---|
| `DISCORD_TOKEN` | Bot tokenin |
| `DATABASE_URL` | PostgreSQL bağlantı adresi |

### render.yaml ile (Opsiyonel)

Repodaki `render.yaml` otomatik olarak algılanır. Sadece GitHub bağlantısı ve secret environment değişkenlerini girmeniz yeterlidir.

<br>

## Komutlar

### Moderasyon

| Komut | Açıklama | Yetki |
|---|---|---|
| `kick` | Kullanıcıyı sunucudan atar | Kick Members |
| `ban` | Kullanıcıyı yasaklar | Ban Members |
| `softban` | Yasaklayıp mesajları siler, ardından yasağı kaldırır | Ban Members |
| `forceban` | Sunucuda olmayan kullanıcıyı ID ile yasaklar | Ban Members |
| `timeout` | Kullanıcıyı geçici olarak susturur | Moderate Members |
| `untimeout` | Susturmayı kaldırır | Moderate Members |
| `unban` | Yasağı kaldırır | Ban Members |
| `warn` | Uyarı verir | Moderate Members |
| `warnings` | Uyarıları listeler | Moderate Members |
| `delwarn` | Belirli bir uyarıyı siler | Moderate Members |
| `clearwarns` | Kullaniçinin tüm uyarılarını temizler | Moderate Members |
| `modlog` | Mod-log kanalını ayarlar | Administrator |

### Kanal Yönetimi

| Komut | Açıklama | Yetki |
|---|---|---|
| `purge` | Toplu mesaj siler (kullanıcı/tür filtresi ile) | Manage Messages |
| `slowmode` | Yavaş modu ayarlar | Manage Channels |
| `lock` | Kanalı yazıya kapatır | Manage Channels |
| `unlock` | Kanalı açar (kaydedilmiş izinleri geri yükler) | Manage Channels |
| `nuke` | Kanalı mesajlarıyla birlikte yeniler | Administrator |

### AutoMod Ayarları (`/automod`)

| Komut | Açıklama |
|---|---|
| `durum` | Tüm filtre ayarlarını gösterir |
| `küfür-ac` / `küfür-kapat` | Küfür filtresini acar/kapatir |
| `küfür-ekle` / `küfür-sil` | Yasaklı kelime ekler/siler |
| `küfür-liste` | Yasaklı kelimeleri listeler |
| `link-aç` / `link-kapat` | Link filtresini acar/kapatir |
| `caps-aç` / `caps-kapat` | Caps lock filtresini acar/kapatir |
| `spam-aç` / `spam-kapat` | Spam korumasını acar/kapatir |
| `spam-ayar` | Spam parametrelerini günceller |
| `muaf-ekle` / `muaf-sil` | Muaf rol ekler/siler |

### Kanal Ayarları (`/kanal`)

| Komut | Açıklama |
|---|---|
| `durum` | Komut durumlarını gösterir |
| `purge-ac/kapat/limit` | Purge ayarları |
| `slowmode-ac/kapat/limit` | Slowmode ayarları |
| `lock-ac/kapat/kaydet` | Lock/Unlock ayarları |
| `nuke-ac/kapat/onay` | Nuke ayarları |

<br>

## Proje Yapısı

```
reoxy-bot/
├── bot.py                  # Giriş noktası
├── config.yaml             # Statik yapılandırma (renkler, emojiler)
├── render.yaml             # Render.com deployment ayarları
├── requirements.txt        # Bağımlılıklar
├── core/
│   ├── bot.py              # ReoxyBot sınıfı (commands.Bot alt sınıfı)
│   ├── config.py           # YAML yükleyici
│   ├── database.py         # asyncpg pool yöneticisi
│   └── logger.py           # Loguru yapılandırmasi
├── cogs/
│   ├── moderation.py       # Kick/Ban/Timeout/Warn
│   ├── automod.py          # Küfür/Link/Spam filtreleri
│   ├── channel.py          # Purge/Slowmode/Lock/Nuke
│   └── general.py          # Yardim menusu
├── database/
│   ├── models.py           # Tablo şemaları + migration'lar
│   └── queries.py          # Async sorgu fonksiyonları
├── utils/
│   ├── constants.py        # ActionType, Colors, Emojis
│   ├── embeds.py           # Merkezi embed oluşturucular
│   ├── permissions.py      # Yetki & hiyerarsi kontrolleri
│   └── time_parser.py      # Süre çözümleyici
├── web/
│   └── server.py           # Health check (Render.com için)
└── data/                   # SQLite dosyaları (.gitignore)
```

<br>

## Mimari Kararlar

- **Hibrit Komutlar**: Tüm komutlar hem `!prefix` hem de `/slash` olarak çalışır (`hybrid_command`)
- **Async/await**: Discord API ve veritabanı işlemleri tamamen asenkrondur
- **Parametreli SQL**: SQL injection'a karşı %100 koruma
- **Guild Bazlı Config**: Her özellik sunucu bazında açılıp kapatılabilir (automod/channel deseni)
- **Zero Trust Yetki**: Her komutta hiyerarsi kontrolu, sunucu sahibi/bot/kendine-işlem kontrolleri
- **Veritabanı Agnostik**: asyncpg ile PostgreSQL, opsiyonel olarak SQLite (aiosqlite)

<br>

## Teknoloji Yığının

| Teknoloji | Kullanım Amacı |
|---|---|
| discord.py 2.3+ | Discord API arayüzü |
| asyncpg | Async PostgreSQL sürücüsü |
| PyYAML | Yapilandirma dosyası |
| Loguru | Log yönetimi |
| python-dotenv | .env yükleyici |

<br>

## Geliştirme

### Kod Standartları

- Python 3.10+ type hints (`str | None`, `list[int]`)
- `from __future__ import annotations` her modülün başında
- Docstring'ler Türkçe
- Loguru placeholder'lari (`{}`), f-string log yok
- Embed'ler `utils/embeds.py` üzerinden
- SQL sadece `database/queries.py` içinde

### Ortam Değişkenleri

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `DISCORD_TOKEN` | Evet | Discord bot tokeni |
| `DATABASE_URL` | Evet | PostgreSQL bağlantı adresi |
| `PORT` | Hayır | Render.com health check portu (varsayılan: 10000) |

<br>

## Lisans

MIT License — detaylar için [LICENSE](LICENSE) dosyasına bakın.