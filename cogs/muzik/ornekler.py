"""
Çoklu müzik botu (Jockey tarzı "multi-instance"): aynı kodu çalıştıran birden çok bot hesabı
(MezarBot + MüzikBaba ...) aynı sunucuda farklı ses kanallarında aynı anda çalabilir.

Bir bot hesabı bir sunucuda aynı anda yalnızca BİR ses kanalında olabilir (Discord kuralı); bu yüzden
ikinci oda için ikinci hesap gerekir. Botlar birbirleriyle konuşmaz — her biri Discord'un ses durumlarından
(kim hangi kanalda) AYNI kararı kendisi verir:

  Önekli komut (!oynat ...) → hepsi mesajı görür, yalnızca "sorumlu" olan çalıştırır, diğerleri sessiz kalır:
    1. Komutu yazanın ses kanalında bir müzik botu varsa → o bot.
    2. Yoksa → sunucuda hiçbir ses kanalına bağlı olmayan ilk bot (config sırasıyla).
    3. Hepsi meşgulse ya da yazan seste değilse → listedeki ilk bot (kendi hata/uyarı mesajını verir).
  Slash komutu → kullanıcı botu kendisi seçmiştir; yanlış botu seçtiyse doğru botu söyleyen kısa bir uyarı.

config.json → "muzik_ornekleri": [ana_bot_id, ikinci_bot_id, ...] (sıra = öncelik). Boşsa sistem kapalıdır.
"""
import time

import discord
from discord import app_commands
from discord.ext import commands

from dil import _t
from yapilandirma import MUZIK_ORNEKLERI

# Bu komutlar kullanıcıyı bir ses kanalına bağlar / orada çalar → boştaki bota yönlendirilebilir
BAGLANAN_KOMUTLAR = {"oynat", "siradaki", "katil", "calmalistesi oynat", "calmalistesi"}
# Yönlendirme dışı: sahip ve ayar komutları her botta doğrudan çalışır (her bot kendi ayarını tutar)
YONLENDIRILMEYEN = {"ytdlpguncelle"}


class BaskaOrnekte(commands.CheckFailure):
    """Önekli komutu başka bir müzik botu üstlendi → bu bot sessizce yok sayar (on_command_error)."""


class OrnekYonlendirme(app_commands.CheckFailure):
    """Slash komutu yanlış bota yazıldı → mesajı kullanıcıya gizli olarak gösterilir (on_tree_error)."""


_uyelik = {}   # (sunucu_id, bot_id) → (var_mı, zaman) — diğer botlar bu sunucuda mı? (10 dk önbellek)


def aktif_mi():
    return len(MUZIK_ORNEKLERI) > 1


def _baglandigi_kanal(guild, bot_id):
    """bot_id'nin bu sunucuda bağlı olduğu ses kanalı (ses durumlarından; üye önbelleği gerekmez)."""
    for kanal in list(guild.voice_channels) + list(guild.stage_channels):
        if bot_id in kanal.voice_states:
            return kanal
    return None


async def _sunucuda_mi(bot, guild, bot_id):
    if bot_id == bot.user.id:
        return True
    if guild.get_member(bot_id) is not None:
        return True
    anahtar = (guild.id, bot_id)
    kayit = _uyelik.get(anahtar)
    if kayit and time.monotonic() - kayit[1] < 600:
        return kayit[0]
    try:
        await guild.fetch_member(bot_id)
        var = True
    except discord.NotFound:
        var = False
    except discord.HTTPException:
        var = bool(kayit and kayit[0])   # geçici hata → son bilinen durum
    _uyelik[anahtar] = (var, time.monotonic())
    return var


def uyelik_degisti(guild_id, bot_id):
    _uyelik.pop((guild_id, bot_id), None)


async def sunucudaki_ornekler(bot, guild):
    return [i for i in MUZIK_ORNEKLERI if await _sunucuda_mi(bot, guild, i)]


async def sorumlu(bot, guild, uye):
    """Bu üyenin komutunu hangi bot üstlenmeli? → bot id."""
    ornekler = await sunucudaki_ornekler(bot, guild)
    if not ornekler:
        return bot.user.id
    kanal = uye.voice.channel if (uye.voice and uye.voice.channel) else None
    if kanal is not None:
        for i in ornekler:
            if i in kanal.voice_states:
                return i
        for i in ornekler:
            if _baglandigi_kanal(guild, i) is None:
                return i
    return ornekler[0]


def _ad(guild, bot_id):
    uye = guild.get_member(bot_id)
    return uye.display_name if uye else f"<@{bot_id}>"


async def denetle(cog, ctx):
    """cog_check'ten çağrılır. Bu bot komutu çalıştırmalı mı? Gerekirse BaskaOrnekte / OrnekYonlendirme fırlatır."""
    if not aktif_mi() or ctx.guild is None or ctx.command is None:
        return True
    ad = ctx.command.qualified_name
    if ad in YONLENDIRILMEYEN:
        return True
    bot, guild, uye = cog.bot, ctx.guild, ctx.author
    benim = bot.user.id

    if ctx.interaction is None:          # önekli komut: tek bot cevap versin
        if await sorumlu(bot, guild, uye) != benim:
            raise BaskaOrnekte()
        return True

    # Slash: kullanıcı beni seçti. Odasında başka bir müzik botu varsa ona yönlendir.
    kanal = uye.voice.channel if (uye.voice and uye.voice.channel) else None
    if kanal is None or benim in kanal.voice_states:
        return True
    ornekler = await sunucudaki_ornekler(bot, guild)
    for i in ornekler:
        if i != benim and i in kanal.voice_states:
            raise OrnekYonlendirme(_t("🎧 Senin odanda **{bot}** çalıyor. Komutu ondan kullan: `/{komut}` yazınca listeden **{bot}**'u seç (ya da `!{komut}` yaz).",
                                      bot=_ad(guild, i), komut=ad))
    # Ben başka bir odada meşgulsem ve boşta bir bot varsa, bu oda için onu öner
    benim_kanal = _baglandigi_kanal(guild, benim)
    if ad.split()[0] in {k.split()[0] for k in BAGLANAN_KOMUTLAR} and benim_kanal is not None and benim_kanal != kanal \
            and any(not m.bot for m in benim_kanal.members):
        bos = [i for i in ornekler if i != benim and _baglandigi_kanal(guild, i) is None]
        if bos:
            raise OrnekYonlendirme(_t("🎶 Ben şu an **{kanal}** kanalında çalıyorum. Senin odan için **{bot}** boşta: `/{komut}` yazıp listeden **{bot}**'u seç (ya da `!{komut}` yaz, boştaki bot kendisi gelir).",
                                      kanal=benim_kanal.name, bot=_ad(guild, bos[0]), komut=ad))
    return True
