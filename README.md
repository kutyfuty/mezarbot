# 🪦 MezarBot

[![test](https://github.com/kutyfuty/mezarbot/actions/workflows/test.yml/badge.svg)](https://github.com/kutyfuty/mezarbot/actions/workflows/test.yml) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![Lisans](https://img.shields.io/badge/lisans-MIT-green)

Kendi sunucunda çalıştırabileceğin, **Türkçe** ve çok sunuculu bir Discord botu: takılmayan müzik, özel ses odaları,
moderasyon, ses istatistikleri, yapay zekâ sohbeti/çizimi, seslendirme ve anlık çeviri. Sunucu başına TR / EN dil seçeneği.

> *English summary below.*

## Özellikler

**🎵 Müzik**
- YouTube, YouTube Music, Spotify (şarkı / albüm / playlist), SoundCloud ve doğrudan ses linkleri; aramayla çalma
- **YouTube çalamazsa SoundCloud yedeği:** bot doğrulaması, yaş/bölge kısıtı ya da kaldırılmış videoda aynı şarkıyı
  SoundCloud'da bulur; 30 sn'lik önizlemeleri ve yanlış şarkıları (cover, remix, başka şarkı) eler
- Kalıcı kontrol paneli (butonlar), kuyruk, döngü, karıştırma, ileri/geri sarma, önceki şarkı, oylamalı atlama, DJ rolü
- Otomatik oynatma (kuyruk bitince benzer şarkılar), ses dengeleme, 7/24 modu, şarkı istek kanalı
- Kişisel ve paylaşılan çalma listeleri, çalma geçmişi, şarkı sözleri (LRCLIB)
- **Takılmayan ses:** yt-dlp ve Spotify çözümleme ayrı süreçlerde çalışır, Opus kaynaklar yeniden kodlanmadan aktarılır;
  Discord'un uçtan uca ses şifrelemesi (DAVE) destekli

**🔊 Özel ses odaları** — "Oda oluştur" kanalına giren herkese kendi odası: kilitle, gizle, davet et, at/yasakla,
limit, devret, sahiplen; kalıcı butonlu panel. Sunucu başına `/ozelodaaktif` ile açılır.

**🛡️ Moderasyon** — oto-mod (tekrarlanan mesaj / flood), uyarı sistemi, susturma/atma/yasaklama, mesaj ve moderasyon logları,
hoş geldin / görüşürüz mesajları, otomatik rol, AFK, takım kurma.

**📊 Ses istatistikleri** — haftalık / aylık / tüm zamanlar ses süresi sıralaması.

**🤖 Yapay zekâ** — botu etiketleyerek sohbet (Groq, ücretsiz katman, kişilik seçimi), `/ciz` ile resim (Replicate Flux).

**🗣️ Seslendirme** — `/konus` ile metni ses kanalında okur (Microsoft Edge TTS, ücretsiz).

**🌐 Çeviri** — mesaja 🇬🇧 / 🇹🇷 tepkisi koy, çevirisi gelsin; `/cevir` komutu.

Tüm komutlar: **[KOMUTLAR.md](KOMUTLAR.md)**

## Kurulum

### 1. Discord uygulaması
1. [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → **Bot** → token'ı kopyala.
2. **Privileged Gateway Intents** altında **Server Members** ve **Message Content** açık olmalı.
3. **OAuth2 → URL Generator**: `bot` + `applications.commands` kapsamları, **Administrator** (ya da ihtiyaç duyulan
   izinler) → oluşan linkle botu sunucuna ekle.

### 2. Ayarlar
```bash
git clone https://github.com/kutyfuty/mezarbot.git
cd mezarbot
cp .env.example .env                 # DISCORD_TOKEN zorunlu, diğerleri opsiyonel
cp config.example.json config.json   # sahip_id = kendi Discord kullanıcı ID'n
```

| `.env` değişkeni | Gerekli mi | Ne için |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Bot token'ı |
| `GROQ_API_KEY` | – | Yapay zekâ sohbeti ve çeviri ([ücretsiz](https://console.groq.com)) |
| `REPLICATE_API_TOKEN` | – | `/ciz` resim çizimi |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | – | Spotify API (boşsa herkese açık embed sayfası kullanılır) |

Anahtarı boş olan özellik kapanır; bot çökmez.

### 3a. Docker ile (önerilen)
```bash
docker compose up -d --build
docker compose logs -f
```
Veritabanı ve önbellek `./data` klasöründe kalır.

### 3b. Elle
Gerekenler: **Python 3.11+** (3.14 ile test edildi), **FFmpeg**, YouTube için **Deno ≥ 2.3** ya da **Node ≥ 22**.
```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python main.py
```
Linux'ta servis olarak çalıştırmak için örnek: [`deploy/mezarbot.service.example`](deploy/mezarbot.service.example).

### İlk adımlar (sunucuda)
- `/dil` → botun dili (tr / en), `/ayarlar` → log, hoş geldin, otorol vb.
- `/ozelodaaktif` → özel ses odalarını kur, `/muzikayar` → DJ rolü, istek kanalı, 7/24 modu.

## Testler
```bash
venv/bin/python tests/smoke_test.py            # veritabanı, migrasyonlar, çok sunuculu davranış
venv/bin/python tests/ozel_oda_test.py         # özel ses odaları
venv/bin/python tests/muzik_test.py --agsiz    # müzik (ağsız; parametresiz çalıştırınca gerçek akış testleri de)
```
Testler Discord'a bağlanmaz ve gerçek veritabanına dokunmaz.

## Notlar
- Kod, değişken adları ve mesajlar Türkçedir. Mimari ve kurallar: [AGENTS.md](AGENTS.md).
- `cogs_devre_disi/` içindeki modüller (ekonomi, itiraf, kelime oyunu …) varsayılan olarak yüklenmez.
- YouTube, veri merkezi IP'lerinden gelen isteklere sık sık bot doğrulaması sorar. VPS'te çalıştırıyorsan
  `data/cookies.txt` (Netscape biçiminde tarayıcı çerezi) eklemek işe yarar; SoundCloud yedeği de bu durumda devreye girer.
- Müzik özellikleri yt-dlp üzerinden çalışır; kullandığın platformların kullanım koşullarına uymak senin sorumluluğundadır.

## English

**MezarBot** is a self-hosted, multi-guild Discord bot (Turkish-first, per-server TR/EN language):
stutter-free music (YouTube, YT Music, Spotify, SoundCloud; persistent button panel, autoplay, playlists, lyrics,
DAVE voice encryption, **automatic SoundCloud fallback when YouTube fails**), temporary private voice rooms, moderation
and auto-mod, voice activity leaderboards, AI chat (Groq) and image generation (Replicate), text-to-speech and
flag-reaction translation.

Quick start: copy `.env.example` → `.env` (set `DISCORD_TOKEN`) and `config.example.json` → `config.json`
(set `sahip_id` to your Discord user ID), then `docker compose up -d --build`. Enable the **Server Members** and
**Message Content** intents in the Developer Portal. The codebase and docs are in Turkish.

## Lisans
[MIT](LICENSE)
