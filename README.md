# 🪦 MezarBot

[![test](https://github.com/kutyfuty/mezarbot/actions/workflows/test.yml/badge.svg)](https://github.com/kutyfuty/mezarbot/actions/workflows/test.yml) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

**English** · [Türkçe](#türkçe)

A self-hosted, multi-server Discord bot with stutter-free music, private voice rooms, moderation,
voice activity leaderboards, AI chat and image generation, text-to-speech and instant translation.
Each server can pick its language (Turkish / English).

<p align="center">
  <img src="docs/ekran/muzik-paneli.png" width="49%" alt="Music control panel">
  <img src="docs/ekran/ozel-oda.png" width="49%" alt="Private voice room panel">
</p>
<p align="center">
  <img src="docs/ekran/yardim-en.png" width="49%" alt="Help menu (English)">
  <img src="docs/ekran/ayarlar-en.png" width="49%" alt="Server settings (English)">
</p>
<p align="center">
  <img src="docs/ekran/kuyruk.png" width="49%" alt="Queue">
  <img src="docs/ekran/sesstat.png" width="49%" alt="Voice activity leaderboard">
</p>

> Screenshots are rendered from the bot's real embed and button output (`docs/ekran/`), with sample users.
> The help menu and settings follow the server language; music and voice room panels are Turkish for now.

## Features

**🎵 Music**
- YouTube, YouTube Music, Spotify (tracks, albums, playlists), SoundCloud and direct audio links, or just search
- **SoundCloud fallback:** if YouTube refuses a song (bot check, age/region lock, removed video), the bot finds the
  same song on SoundCloud and skips 30-second previews and wrong matches (covers, remixes, other songs)
- Persistent control panel with buttons, queue, loop, shuffle, seek, previous track, vote skip, DJ role
- Autoplay (similar songs when the queue ends), volume normalization, 24/7 mode, song request channel
- Personal and shared playlists, play history, synced lyrics (LRCLIB)
- **No stutter:** yt-dlp and Spotify resolving run in separate processes, Opus sources are passed through without
  re-encoding, and Discord's end-to-end voice encryption (DAVE) is supported

**🔊 Private voice rooms**: everyone who uses the "create room" button gets their own room. They can lock, hide,
invite, kick, ban, set a limit, transfer or claim it from a persistent button panel. Turn it on per server with
`/ozelodaaktif`.

**🛡️ Moderation**: auto-mod against repeated messages (flood), warnings, timeout / kick / ban, message and moderation
logs, welcome and goodbye messages, auto-role, AFK, random team builder.

**📊 Voice stats**: weekly, monthly and all-time voice channel leaderboards.

**🤖 AI**: chat by mentioning the bot (Groq free tier, selectable personality), image generation with `/draw`
(Replicate Flux).

**🗣️ Text-to-speech**: `/konus` reads text aloud in a voice channel (Microsoft Edge TTS, free).

**🌐 Translation**: react to a message with 🇬🇧 or 🇹🇷 to get a translation, or use `/cevir`.

Full command list (Turkish): **[KOMUTLAR.md](KOMUTLAR.md)**

## Setup

### 1. Discord application
1. [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → **Bot** → copy the token.
2. Under **Privileged Gateway Intents**, turn on **Server Members** and **Message Content**.
3. **OAuth2 → URL Generator**: scopes `bot` + `applications.commands`, permission **Administrator** (or the ones you
   need), then invite the bot with the generated link.

### 2. Configuration
```bash
git clone https://github.com/kutyfuty/mezarbot.git
cd mezarbot
cp .env.example .env                 # DISCORD_TOKEN is required, the rest is optional
cp config.example.json config.json   # set sahip_id to your own Discord user ID
```

| `.env` variable | Required | Used for |
|---|---|---|
| `DISCORD_TOKEN` | ✅ | Bot token |
| `GROQ_API_KEY` | – | AI chat and translation ([free](https://console.groq.com)) |
| `REPLICATE_API_TOKEN` | – | `/ciz` / `/draw` image generation |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | – | Spotify API (without it, the public embed page is used) |

A feature whose key is empty is simply turned off; the bot does not crash.

### 3a. Docker (recommended)
```bash
docker compose up -d --build
docker compose logs -f
```
The database and caches live in `./data`.

### 3b. Manual
Requirements: **Python 3.11+** (tested on 3.14), **FFmpeg**, and **Deno ≥ 2.3** or **Node ≥ 22** for YouTube.
```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python main.py
```
To run it as a Linux service, see [`deploy/mezarbot.service.example`](deploy/mezarbot.service.example).

### First steps on your server
- `/dil en` (or `!language en`) sets the bot language, `/settings` (or `/ayarlar`) shows logs, welcome, auto-role and more.
- `/ozelodaaktif` sets up private voice rooms, `/muzikayar` sets the DJ role, request channel and 24/7 mode.

## Tests
```bash
venv/bin/python tests/smoke_test.py            # database, migrations, multi-server behavior
venv/bin/python tests/ozel_oda_test.py         # private voice rooms
venv/bin/python tests/muzik_test.py --agsiz    # music, offline (without the flag it also tests real streams)
```
Tests never connect to Discord and never touch the real database. They run on every push via GitHub Actions.

## Notes
- The code, variable names and bot messages are in Turkish. Architecture and rules: [AGENTS.md](AGENTS.md).
- Modules in `cogs_devre_disi/` (economy, confessions, word game, …) are not loaded by default.
- YouTube often asks datacenter IPs to prove they are not a bot. On a VPS, adding `data/cookies.txt` (browser cookies in
  Netscape format) helps, and the SoundCloud fallback kicks in when it doesn't.
- Music works through yt-dlp. You are responsible for following the terms of the platforms you use.
- Screenshots are regenerated with `venv/bin/python docs/ekran/sahneler.py && node docs/ekran/cizici.js`.

---

## Türkçe

[English](#-mezarbot) · **Türkçe**

Kendi sunucunda çalıştırabileceğin, çok sunuculu bir Discord botu: takılmayan müzik, özel ses odaları, moderasyon,
ses istatistikleri, yapay zekâ sohbeti ve çizimi, seslendirme ve anlık çeviri. Her sunucu kendi dilini seçebilir
(Türkçe / İngilizce).

<p align="center">
  <img src="docs/ekran/muzik-paneli.png" width="49%" alt="Müzik kontrol paneli">
  <img src="docs/ekran/ozel-oda.png" width="49%" alt="Özel ses odası paneli">
</p>
<p align="center">
  <img src="docs/ekran/yardim-tr.png" width="49%" alt="Yardım menüsü">
  <img src="docs/ekran/ayarlar-tr.png" width="49%" alt="Sunucu ayarları">
</p>
<p align="center">
  <img src="docs/ekran/kuyruk.png" width="49%" alt="Kuyruk">
  <img src="docs/ekran/sesstat.png" width="49%" alt="Ses sıralaması">
</p>

> Görseller botun gerçek embed ve buton çıktısından, örnek kullanıcılarla üretildi (`docs/ekran/`).

### Özellikler

**🎵 Müzik**
- YouTube, YouTube Music, Spotify (şarkı / albüm / playlist), SoundCloud ve doğrudan ses linkleri; aramayla çalma
- **YouTube çalamazsa SoundCloud yedeği:** bot doğrulaması, yaş/bölge kısıtı ya da kaldırılmış videoda aynı şarkıyı
  SoundCloud'da bulur; 30 sn'lik önizlemeleri ve yanlış şarkıları (cover, remix, başka şarkı) eler
- Kalıcı kontrol paneli (butonlar), kuyruk, döngü, karıştırma, ileri/geri sarma, önceki şarkı, oylamalı atlama, DJ rolü
- Otomatik oynatma (kuyruk bitince benzer şarkılar), ses dengeleme, 7/24 modu, şarkı istek kanalı
- Kişisel ve paylaşılan çalma listeleri, çalma geçmişi, şarkı sözleri (LRCLIB)
- **Takılmayan ses:** yt-dlp ve Spotify çözümleme ayrı süreçlerde çalışır, Opus kaynaklar yeniden kodlanmadan aktarılır;
  Discord'un uçtan uca ses şifrelemesi (DAVE) desteklenir

**🔊 Özel ses odaları**: "Oda oluştur" butonuna basan herkese kendi odası. Kilitle, gizle, davet et, at/yasakla,
limit koy, devret, sahiplen; hepsi kalıcı butonlu panelden. Sunucu başına `/ozelodaaktif` ile açılır.

**🛡️ Moderasyon**: oto-mod (tekrarlanan mesaj / flood), uyarı sistemi, susturma/atma/yasaklama, mesaj ve moderasyon
logları, hoş geldin / görüşürüz mesajları, otomatik rol, AFK, takım kurma.

**📊 Ses istatistikleri**: haftalık / aylık / tüm zamanlar ses süresi sıralaması.

**🤖 Yapay zekâ**: botu etiketleyerek sohbet (Groq ücretsiz katman, kişilik seçimi), `/ciz` ile resim (Replicate Flux).

**🗣️ Seslendirme**: `/konus` metni ses kanalında okur (Microsoft Edge TTS, ücretsiz).

**🌐 Çeviri**: mesaja 🇬🇧 / 🇹🇷 tepkisi koy, çevirisi gelsin; ya da `/cevir`.

Tüm komutlar: **[KOMUTLAR.md](KOMUTLAR.md)**

### Kurulum

**1. Discord uygulaması**
1. [Discord Developer Portal](https://discord.com/developers/applications) → **New Application** → **Bot** → token'ı kopyala.
2. **Privileged Gateway Intents** altında **Server Members** ve **Message Content** açık olmalı.
3. **OAuth2 → URL Generator**: `bot` + `applications.commands` kapsamları, **Administrator** (ya da ihtiyaç duyulan
   izinler) → oluşan linkle botu sunucuna ekle.

**2. Ayarlar**
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

**3a. Docker ile (önerilen)**
```bash
docker compose up -d --build
docker compose logs -f
```
Veritabanı ve önbellek `./data` klasöründe kalır.

**3b. Elle**
Gerekenler: **Python 3.11+** (3.14 ile test edildi), **FFmpeg**, YouTube için **Deno ≥ 2.3** ya da **Node ≥ 22**.
```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python main.py
```
Linux'ta servis olarak çalıştırmak için örnek: [`deploy/mezarbot.service.example`](deploy/mezarbot.service.example).

**İlk adımlar (sunucuda)**
- `/dil` → botun dili (tr / en), `/ayarlar` → log, hoş geldin, otorol vb.
- `/ozelodaaktif` → özel ses odalarını kur, `/muzikayar` → DJ rolü, istek kanalı, 7/24 modu.

### Testler
```bash
venv/bin/python tests/smoke_test.py            # veritabanı, migrasyonlar, çok sunuculu davranış
venv/bin/python tests/ozel_oda_test.py         # özel ses odaları
venv/bin/python tests/muzik_test.py --agsiz    # müzik (ağsız; parametresiz çalıştırınca gerçek akış testleri de)
```
Testler Discord'a bağlanmaz, gerçek veritabanına dokunmaz; her push'ta GitHub Actions'ta çalışır.

### Notlar
- Kod, değişken adları ve mesajlar Türkçedir. Mimari ve kurallar: [AGENTS.md](AGENTS.md).
- `cogs_devre_disi/` içindeki modüller (ekonomi, itiraf, kelime oyunu …) varsayılan olarak yüklenmez.
- YouTube, veri merkezi IP'lerinden gelen isteklere sık sık bot doğrulaması sorar. VPS'te `data/cookies.txt`
  (Netscape biçiminde tarayıcı çerezi) eklemek işe yarar; olmazsa SoundCloud yedeği devreye girer.
- Müzik özellikleri yt-dlp üzerinden çalışır; kullandığın platformların kullanım koşullarına uymak senin sorumluluğundadır.
- Görselleri yeniden üretmek için: `venv/bin/python docs/ekran/sahneler.py && node docs/ekran/cizici.js`.

## License / Lisans
[MIT](LICENSE)
