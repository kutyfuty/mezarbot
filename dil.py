"""
Çok dillilik (TR / EN) — kaynak dil Türkçe, çeviriler dil_en.py → EN sözlüğünde.

Kullanım (cog'larda):
    from dil import _t
    await ctx.send(_t("Kuyruk boş."))
    _t("{n} parça eklendi", n=len(parcalar))     # anahtar = Türkçe ŞABLON, değerler format ile

Hangi dil? Etkin sunucunun dili (`/dil`, sunucu_ayarlar.dil) — bir contextvar'da tutulur ve her girişte
OTOMATİK ayarlanır: slash komutları (DilAgaci.interaction_check), buton/menü/modal tıklamaları
(View/Modal/DynamicItem görevleri), olay dinleyicileri (Client._run_event: mesaj, üye, ses olayı …).
Arka plan döngülerinde (ör. müzik oynatıcısı, temizlik) `dil_ayarla(guild)` elle çağrılır.

Slash komutu açıklamaları/seçenekleri ayrıca DilCevirmeni ile Discord'u İngilizce kullanan herkese
İngilizce görünür (sunucu dilinden bağımsız).

Kurallar: anahtar birebir aynı Türkçe metindir; EN'de yoksa Türkçe döner (test eksikleri yakalar:
tests/dil_test.py). Değişken kısımlar {ad} yer tutucusu olur, f-string ile anahtar üretilmez.
"""
import contextvars
import logging

import discord
from discord import app_commands

from dil_en import EN

logger = logging.getLogger('MezarBot.Dil')

DILLER = ("tr", "en")
_aktif = contextvars.ContextVar("mezarbot_dil", default="tr")


def _sunucu_dili(guild_id):
    from database import sunucu_dil_al   # döngüsel import olmasın diye geç
    try:
        return sunucu_dil_al(guild_id) if guild_id else "tr"
    except Exception:   # cache henüz yüklenmemiş vb. — varsayılan Türkçe
        return "tr"


def _guild_id(nesne):
    """Guild / Interaction / Context / Message / Member / VoiceState / payload / int → guild id (yoksa None)."""
    if nesne is None:
        return None
    if isinstance(nesne, int):
        return nesne
    if isinstance(nesne, discord.Guild):
        return nesne.id
    gid = getattr(nesne, "guild_id", None)
    if isinstance(gid, int):
        return gid
    guild = getattr(nesne, "guild", None)
    return getattr(guild, "id", None)


def dil_ayarla(nesne):
    """Etkin dili nesnenin sunucusuna göre ayarlar ve döner. Sunucu yoksa (DM) Türkçe."""
    dil = _sunucu_dili(_guild_id(nesne))
    _aktif.set(dil if dil in DILLER else "tr")
    return _aktif.get()


def dilli_gorev(coro, guild, name=None):
    """asyncio görevi — `guild`'in dilinde çalışır (arka plan görevleri çağıranın dilini miras almasın diye)."""
    import asyncio
    baglam = contextvars.copy_context()
    baglam.run(dil_ayarla, guild)
    return asyncio.create_task(coro, name=name, context=baglam)


def dil_zorla(dil):
    """Etkin dili doğrudan ayarlar (testler ve dil seçimi önizlemesi için)."""
    _aktif.set(dil if dil in DILLER else "tr")


def aktif_dil():
    return _aktif.get()


def _t(metin, **degerler):
    """Etkin dile çevirir ve yer tutucuları doldurur."""
    if _aktif.get() == "en":
        metin = EN.get(metin, metin)
    return metin.format(**degerler) if degerler else metin


def ceviri(metin, dil):
    """Belirli bir dile çeviri (yer tutucusuz) — etkin dilden bağımsız."""
    return EN.get(metin, metin) if dil == "en" else metin


# ══════════════════════════════════════════════
#  OTOMATİK DİL AYARI — discord.py giriş noktaları
# ══════════════════════════════════════════════

class DilAgaci(app_commands.CommandTree):
    """Slash komutları (hibritler dahil) çalışmadan önce sunucunun dilini etkinleştirir."""

    async def interaction_check(self, interaction):
        dil_ayarla(interaction)
        return True


class DilCevirmeni(app_commands.Translator):
    """Slash komut/grup/parametre açıklamaları ve seçenek adları → Discord'u İngilizce kullananlara İngilizce.
    Komut ve parametre ADLARI çevrilmez (Türkçe kalır; prefix komutlarda İngilizce takma adlar var)."""

    _YERLER = {app_commands.TranslationContextLocation.command_description,
               app_commands.TranslationContextLocation.group_description,
               app_commands.TranslationContextLocation.parameter_description,
               app_commands.TranslationContextLocation.choice_name}

    async def translate(self, string, locale, context):
        if context.location not in self._YERLER or not str(locale).startswith("en"):
            return None
        return EN.get(string.message)


_KURULDU = False


def kancalari_kur():
    """Buton/menü/modal görevleri ve olay dinleyicileri başlarken dili ayarlayan sarmalayıcılar (bir kez)."""
    global _KURULDU
    if _KURULDU:
        return
    _KURULDU = True
    from discord.ui import modal as _modal, view as _view

    eski_view = _view.View._scheduled_task

    async def view_gorevi(self, item, interaction):
        dil_ayarla(interaction)
        return await eski_view(self, item, interaction)
    _view.View._scheduled_task = view_gorevi

    eski_modal = _modal.Modal._scheduled_task

    async def modal_gorevi(self, interaction, *args, **kwargs):
        dil_ayarla(interaction)
        return await eski_modal(self, interaction, *args, **kwargs)
    _modal.Modal._scheduled_task = modal_gorevi

    eski_dinamik = _view.ViewStore.schedule_dynamic_item_call

    async def dinamik_gorev(self, component_type, factory, interaction, *args, **kwargs):
        dil_ayarla(interaction)
        return await eski_dinamik(self, component_type, factory, interaction, *args, **kwargs)
    _view.ViewStore.schedule_dynamic_item_call = dinamik_gorev

    eski_olay = discord.Client._run_event

    async def olay(self, coro, event_name, *args, **kwargs):
        for arg in args:
            if _guild_id(arg) is not None or isinstance(arg, discord.Guild):
                dil_ayarla(arg)
                break
        else:
            _aktif.set("tr")
        return await eski_olay(self, coro, event_name, *args, **kwargs)
    discord.Client._run_event = olay
