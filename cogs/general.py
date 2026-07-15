"""
Reoxy Bot — Genel Komutlar Cog'u

Bot yardım menüsü ve genel komutlar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import error_embed, info_embed
from utils.constants import Emojis

if TYPE_CHECKING:
    from core.bot import ReoxyBot


class HelpSelect(discord.ui.Select):
    """Yardım menüsü kategori seçim dropdown'ı."""

    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label="Ana Sayfa",
                description="Yardım menüsünün ana sayfası",
                emoji="🏡",
                value="home",
            ),
            discord.SelectOption(
                label="Moderasyon Komutları",
                description="Ban, Kick, Timeout vb. komutlar",
                emoji="🛡️",
                value="moderation",
            ),
            discord.SelectOption(
                label="Otomatik Moderasyon (AutoMod)",
                description="Küfür, Link, Spam filtreleri",
                emoji="🤖",
                value="automod",
            ),
            discord.SelectOption(
                label="Kanal Yönetimi",
                description="Purge, Lock, Slowmode vb. komutlar",
                emoji="⚙️",
                value="channel",
            ),
        ]
        super().__init__(
            placeholder="İncelemek istediğiniz kategoriyi seçin...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Kategori seçildiğinde çalışır."""
        self.view: HelpView
        value = self.values[0]
        embed = None

        if value == "home":
            embed = self.view.get_home_embed()
        elif value == "moderation":
            embed = self.view.get_moderation_embed()
        elif value == "automod":
            embed = self.view.get_automod_embed()
        elif value == "channel":
            embed = self.view.get_channel_embed()

        if embed:
            await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    """Yardım menüsü etkileşim görünümü."""

    def __init__(self, author_id: int) -> None:
        super().__init__(timeout=120)
        self.author_id = author_id
        self.add_item(HelpSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Sadece komutu tetikleyen kullanıcının etkileşime geçmesine izin verir."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=error_embed(
                    "Bu Menüyü Kullanamazsınız",
                    "Bu yardım menüsü sadece komutu çağıran kullanıcı tarafından kontrol edilebilir.",
                ),
                ephemeral=True,
            )
            return False
        return True

    def get_home_embed(self) -> discord.Embed:
        """Ana sayfa embed'ini döndürür."""
        description = (
            f"**Reoxy Bot** sunucunuzu korumak ve yönetmek amacıyla tasarlanmış profesyonel bir Discord botudur.\n\n"
            f"Aşağıdaki menüyü kullanarak botun komutları hakkında detaylı bilgi alabilirsiniz:\n\n"
            f"🛡️ **Moderasyon Komutları** — Ban, kick, susturma, uyarı sistemleri.\n"
            f"🤖 **Otomatik Moderasyon** — Küfür, reklam, spam engelleyici filtreler.\n"
            f"⚙️ **Kanal Yönetimi** — Mesaj silme, yavaş mod, kanal kilitleme, nuke.\n\n"
            f"{Emojis.INFO} *İstediğiniz kategoriye menüden erişebilirsiniz.*"
        )
        return info_embed("Reoxy Bot — Yardım Menüsü", description)

    def get_moderation_embed(self) -> discord.Embed:
        """Moderasyon komutları listesini döndürür."""
        description = (
            f"### 🛡️ Moderasyon Komutları\n"
            f"Sunucunuzdaki düzeni sağlamak için kullanabileceğiniz tüm moderasyon komutları:\n\n"
            f"**`/kick` `[kullanıcı] [sebep]`**\n"
            f"{Emojis.ARROW_RIGHT} Kullanıcıyı sunucudan atar.\n\n"
            f"**`/ban` `[kullanıcı] [sebep]`**\n"
            f"{Emojis.ARROW_RIGHT} Kullanıcıyı sunucudan kalıcı olarak yasaklar.\n\n"
            f"**`/softban` `[kullanıcı] [sebep]`**\n"
            f"{Emojis.ARROW_RIGHT} Kullanıcıyı yasaklar ve hemen banını açarak son mesajlarını temizler.\n\n"
            f"**`/forceban` `[id] [sebep]`**\n"
            f"{Emojis.ARROW_RIGHT} Sunucuda bulunmayan bir kullanıcıyı ID kullanarak yasaklar.\n\n"
            f"**`/timeout` `[kullanıcı] [süre] [sebep]`**\n"
            f"{Emojis.ARROW_RIGHT} Kullanıcıyı belirtilen süre kadar susturur (Örn: `10m`, `1h30m`, `3d`).\n\n"
            f"**`/untimeout` `[kullanıcı] [sebep]`**\n"
            f"{Emojis.ARROW_RIGHT} Kullanıcının susturmasını kaldırır.\n\n"
            f"**`/unban` `[id] [sebep]`**\n"
            f"{Emojis.ARROW_RIGHT} Belirtilen kullanıcının yasaklamasını kaldırır.\n\n"
            f"**`/warn` `[kullanıcı] [sebep]`**\n"
            f"{Emojis.ARROW_RIGHT} Kullanıcıya bir uyarı verir. Uyarı limiti aşılırsa otomatik ceza uygulanır.\n\n"
            f"**`/warnings` `[kullanıcı]`**\n"
            f"{Emojis.ARROW_RIGHT} Kullanıcının aktif uyarı listesini görüntüler.\n\n"
            f"**`/delwarn` `[uyarı_id]`**\n"
            f"{Emojis.ARROW_RIGHT} Belirtilen ID'li uyarıyı pasif hale getirir.\n\n"
            f"**`/clearwarns` `[kullanıcı]`**\n"
            f"{Emojis.ARROW_RIGHT} Kullanıcının tüm uyarılarını temizler.\n\n"
            f"**`/modlog` `[kullanıcı]`**\n"
            f"{Emojis.ARROW_RIGHT} Sunucudaki veya belirli bir kullanıcının moderasyon geçmişini gösterir."
        )
        return info_embed("Moderasyon Komutları", description)

    def get_automod_embed(self) -> discord.Embed:
        """Automod komutları listesini döndürür."""
        description = (
            f"### 🤖 Otomatik Moderasyon (AutoMod) Komutları\n"
            f"Sunucudaki otomatik filtreleri yönetmek için kullanabileceğiniz slash komut grupları:\n\n"
            f"**`/automod durum`**\n"
            f"{Emojis.ARROW_RIGHT} Mevcut filtrelerin açık/kapalı durumlarını ve limitlerini gösterir.\n\n"
            f"**`/automod <filtre>-aç` / `<filtre>-kapat`**\n"
            f"{Emojis.ARROW_RIGHT} Filtreleri aktif/deaktif eder. (profanity, link, caps, spam, emoji, mention)\n\n"
            f"**`/automod profanity-kelime-ekle` / `sil` / `liste`**\n"
            f"{Emojis.ARROW_RIGHT} Küfür filtresine özel yasaklı kelime ekler, siler veya listeler.\n\n"
            f"**`/automod <filtre>-ayarlar`**\n"
            f"{Emojis.ARROW_RIGHT} Filtrenin limitlerini/ayarlarını özelleştirir (Örn: spam_max_messages, caps_threshold).\n\n"
            f"**`/automod whitelist-ekle` / `sil`**\n"
            f"{Emojis.ARROW_RIGHT} Belirtilen filtrelerden muaf tutulacak rolleri yönetir.\n\n"
            f"**`/automod log-kanalı` `[kanal]`**\n"
            f"{Emojis.ARROW_RIGHT} AutoMod ihlal günlüklerinin loglanacağı kanalı ayarlar."
        )
        return info_embed("Otomatik Moderasyon Komutları", description)

    def get_channel_embed(self) -> discord.Embed:
        """Kanal yönetimi komutları listesini döndürür."""
        description = (
            f"### ⚙️ Kanal Yönetimi Komutları\n"
            f"Kanalları ve sohbet akışını düzenlemek için kullanabileceğiniz komutlar:\n\n"
            f"**`/purge` `[miktar]`**\n"
            f"{Emojis.ARROW_RIGHT} Belirtilen miktarda mesajı kanaldan siler (Maks: 1000).\n\n"
            f"**`/slowmode` `[süre] [kanal]`**\n"
            f"{Emojis.ARROW_RIGHT} Belirtilen kanalın yavaş mod süresini ayarlar (Örn: `5s`, `1m`, `0` kapatmak için).\n\n"
            f"**`/lock` `[kanal] [sebep]`**\n"
            f"{Emojis.ARROW_RIGHT} Belirtilen kanalı normal üyelerin yazımına kapatır.\n\n"
            f"**`/unlock` `[kanal] [sebep]`**\n"
            f"{Emojis.ARROW_RIGHT} Kilitli olan kanalın kilidini açar ve eski izinleri geri yükler.\n\n"
            f"**`/nuke`**\n"
            f"{Emojis.ARROW_RIGHT} Kanalı silip tamamen aynı ayarlarla yeniden oluşturur (tüm mesaj geçmişini temizler).\n\n"
            f"**`/kanal durum`**\n"
            f"{Emojis.ARROW_RIGHT} Kanal yönetimi ayarlarını ve komut durumlarını gösterir.\n\n"
            f"**`/kanal <ayar>-aç` / `kapat`**\n"
            f"{Emojis.ARROW_RIGHT} purge, slowmode, lock, nuke komutlarını genel olarak açar/kapatır.\n\n"
            f"**`/kanal <ayar>-limit` / `onay-istensin`**\n"
            f"{Emojis.ARROW_RIGHT} Kanal komutlarının limitlerini veya onay ayarlarını düzenler."
        )
        return info_embed("Kanal Yönetimi Komutları", description)


class General(commands.Cog):
    """General — Yardım menüsü ve genel bot komutları."""

    def __init__(self, bot: ReoxyBot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="yardım", description="Bot komutları hakkında detaylı yardım menüsü açar.")
    async def yardım(self, ctx: commands.Context[ReoxyBot]) -> None:
        """Kullanıcılara botun yardım menüsünü sunar."""
        view = HelpView(ctx.author.id)
        embed = view.get_home_embed()
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="dbtest", description="Veritabanı bağlantısının durumunu test eder.")
    @commands.has_permissions(administrator=True)
    async def dbtest(self, ctx: commands.Context[ReoxyBot]) -> None:
        """Veritabanı bağlantı havuzu ve gecikme süresini test eder."""
        from datetime import datetime
        
        # Kullanıcıyı bilgilendir
        await ctx.defer(ephemeral=True)
        
        start_time = datetime.now()
        try:
            # PostgreSQL ping sorgusu çalıştır
            await self.bot.db.execute("SELECT 1")
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            embed = success_embed(
                "Veritabanı Bağlantısı Başarılı",
                f"🛡️ **Supabase/PostgreSQL** veritabanına bağlantı aktif ve sorunsuz.\n"
                f"⏱️ **Gecikme Süresi (Latency):** `{duration:.2f} ms`"
            )
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = error_embed(
                "Veritabanı Bağlantı Hatası",
                f"❌ Veritabanı bağlantısı başarısız oldu!\n"
                f"📝 **Hata Mesajı:** `{str(e)}`"
            )
            await ctx.send(embed=embed, ephemeral=True)


async def setup(bot: ReoxyBot) -> None:
    """Cog'u bota yükler."""
    await bot.add_cog(General(bot))
