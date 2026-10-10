# AGENTS.md

## Must-follow constraints

- **NEVER** commit `.env`, `*.db`, `*.log`, `bot.lock` or `.cache` — `.gitignore` is configured for this
- **NEVER** open the real `mezarbot.db` from tests/scripts — set `MEZARBOT_DB=/tmp/...` **before** importing `database` (it connects at import time)
- All SQL queries MUST use parameterized values (`?`). Column names in dynamic queries MUST be validated against a whitelist — `SUNUCU_AYAR_KOLONLARI` / `KELIME_OYUNU_KOLONLARI` in `database.py` (`sunucu_ayar_guncelle`, `kelime_oyunu_guncelle` raise `ValueError` otherwise)
- Owner ID lives ONLY in `config.json` → `sahip_id` (exposed as `yapilandirma.SAHIP_ID`, also `bot.owner_id`); trusted users → `guvenilir_idler`, approval gate → `onay_sistemi`. Never hardcode user/guild/role/channel IDs (the repo is public)
- The bot is **multi-guild**: server-specific settings go in the `sunucu_ayarlar` table (add a migration + whitelist entry), are set by guild admins via commands, and features MUST skip cleanly when a guild hasn't configured them
- Permission checks: settings commands → `@commands.check(yonetici_kontrol)` (owner, or Administrator / Manage Guild in that guild); moderation → `commands.has_guild_permissions(...)` (real Discord permission); VIP perks → `vip_kontrol(member)`. VIP ≠ admin
- All gambling/random outcomes (blackjack, yazitura, duello) MUST use `_secure_random` (`random.SystemRandom()`), never `random`
- Balance mutations MUST be atomic SQL (`bakiye = bakiye + ?`, deductions `... WHERE bakiye >= ?` + `rowcount` check), never read-then-write. Bets are escrowed up front (`_bakiye_rezerve_et`), then paid/refunded (`_bakiye_ekle`, `_duello_iade`, `_duello_ode`)
- Cache (`_sunucu_cache`, `_afk_cache`, `_kelime_oyunu_cache`, `_vip_kisiler`, `_vip_roller`) MUST be updated alongside every DB write that affects cached data
- DB migrations MUST be additive and idempotent (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN` in try/except). Never drop or rewrite existing data. The only exception is a key change (SQLite cannot alter a PK): follow the `_ekonomi_sunucu_bazli_migrasyon()` pattern — schema-check guard, verified backup first, single transaction, old table renamed (not dropped), row-by-row verification

## Validation before finishing

- `venv/bin/python -m py_compile $(git ls-files '*.py')`
- `venv/bin/python tests/smoke_test.py` — offline (no Discord), temp DB; add `--gercek-db-kopyasi` to run migrations on a /tmp copy of the real DB
- All default cogs load (`vagonlar` in `main.py`: yonetim, yapayzeka, muzik, yardim, konusma, ses_aktivite, durum_rotator, ozel_oda, sunucu_onay, ceviri) + `config.json → ek_coglar`
- `venv/bin/python tests/ozel_oda_test.py` — private voice rooms, offline
- No bare `except:` — always catch specific exceptions or `except Exception:`
- Bot starts: `venv/bin/python main.py` (needs `DISCORD_TOKEN` in `.env`); as a service see `deploy/mezarbot.service.example` (or `docker compose up -d`)

## Repo-specific conventions

- All code, variable names, comments, and user-facing strings are in **Turkish**
- Cog-based architecture: each feature is a separate file in `cogs/`; retired cogs live in `cogs_devre_disi/` (not loaded)
- Paths/config live in `yapilandirma.py` (`BOT_DIZINI`, `DB_DOSYA`, `VERI_DIZINI`, `GECICI_DIZIN`, `YTDL_CACHE_DIZINI`, `SAHIP_ID`, `PREFIX`, `ESKI_EKONOMI_SUNUCU_ID`, `GUVENILIR_IDLER`, `EK_COGLAR`, `DURUM_MESAJLARI`, `ONAY_*`). Every path is resolved relative to the bot directory, never the CWD. `.env` is loaded from the bot directory
- Shared UI constants and helpers live in `arayuz.py` (`FFMPEG_YOLU`, `DURUM_TIPLERI`, `Renkler`, embed builders)
- Groq (AI chat, !ciz prompt translation, /cevir + flag translation) goes through `groq_yardimci.py` (`groq_istemci()` shared client, `groq_tamamla()` model fallback) — do not create Groq clients or model loops in cogs
- Database functions live in `database.py` — cogs import `db` for direct cursor use, plus cache wrapper functions
- Optional API keys (GROQ / REPLICATE / SPOTIFY) may be empty: the feature is disabled with a log line, never a crash
- XP updates are **batched in memory** (`_xp_buffer` in ekonomi.py) and flushed every 30 seconds and on shutdown — if adding new balance reads, call `_flush_xp_to_db()` first
- Music cleanup logic is centralized in `Muzik._cleanup_guild()` — do not duplicate cleanup code
- Private voice rooms (`cogs/ozel_oda.py` + `ozel_oda_veritabani.py`, own tables on the shared `db`, whitelists `OZEL_ODA_AYAR_KOLONLARI` / `ODA_KOLONLARI`): **OFF by default per guild** (`ozel_oda_ayarlar.aktif`), toggled only by `/ozelodaaktif` / `/ozelodakapat` (Manage Server). While off the cog does nothing in that guild except deleting leftover rooms once empty. Owner powers are channel-level overwrites only; panel buttons are `DynamicItem`s (`ozeloda:<eylem>:<kanal_id>`); empty-room cleanup is the single `temizlik_dongusu` (decision in `temizlik_karari`)

## Data scope (global vs per-guild)

- Global (per user): `cizim_haklari`, `vip_kisiler`, `vip_roller`; bot-wide: `bot_ayarlar` (presence), `gonderilen_firsatlar`, `turkce_sozluk`, `dukkan_urunler` (product catalog)
- **Economy is per guild** — keyed by `(sunucu_id, kullanici_id)`: `ekonomi` (bakiye, xp, seviye, son_gunluk, streak, son_gunluk_tarih, gunluk_kayip, kumar_kazanma, transfer_sayisi; PK `(sunucu_id, kullanici_id)`), `islem_gecmisi` (+`sunucu_id`), `basarimlar` (PK `(sunucu_id, kullanici_id, basarim_id)`), `envanter` (UNIQUE `(sunucu_id, kullanici_id, urun_id)`). Schemas live in `EKONOMI_TABLOLARI` (`database.py`). Every economy query/helper MUST filter by both keys (`bakiye_al`, `ekonomi_kaydi_olustur`, `islem_kaydet`, `basarim_ver`, … take `sunucu_id` first and raise `TypeError` on non-int keys); money only moves within one guild; escrow views carry `sunucu_id`; in-memory `_xp_buffer`, `xp_cooldown`, `aktif_oyuncular` are keyed `(sunucu_id, kullanici_id)`; `Ekonomi.cog_check` rejects DMs (`NoPrivateMessage`)
- Per guild: `sunucu_ayarlar`, `kelime_oyunu`, `kullanilan_kelimeler`, `kelime_puanlari`, `uyarilar`, `moderasyon_log.sunucu_id`, `itiraflar.guild_id`, `starboard(_ayarlar)`, `ses_aktivite`, `ses_kanal_ayar`, `afk_durumlari`, `ozel_oda_ayarlar`, `ozel_odalar`; in memory: music state, flood counters, AI chat history `(guild, user)`
- Legacy, unused: `afk_listesi` (kept untouched); `eski_global_ekonomi` / `eski_global_islem_gecmisi` / `eski_global_basarimlar` / `eski_global_envanter` = the pre-migration global tables, renamed and kept read-only as a safety copy (never read by code)

## Global → per-guild economy migration

- `_ekonomi_sunucu_bazli_migrasyon()` runs inside `veritabanini_kur()` on every start; it only acts on economy tables that still lack `sunucu_id` (idempotent)
- Legacy rows go to `config.json` → `eski_ekonomi_sunucu_id` (`yapilandirma.ESKI_EKONOMI_SUNUCU_ID`); if legacy rows exist and it is empty, startup aborts (exit 78) without touching the DB
- Procedure: sqlite backup API → `<db>.bak-ekonomi-<YYYYmmdd-HHMMSS>` (0600, verified) → one `BEGIN IMMEDIATE` transaction: rename old table to `eski_global_<t>`, create the new table, `INSERT … SELECT`, verify row-by-row (`EXCEPT`) + totals, copy the AUTOINCREMENT counter → commit. Any error → rollback + `EkonomiMigrasyonHatasi` → `main.baslat()` exits 78

## Important locations

- `yapilandirma.py` — paths, `.env` loading, `config.json` parsing, yt-dlp JS runtime detection
- `config.json` — non-secret, bot-wide settings (`sahip_id`, `prefix`, `guvenilir_idler`, `onay_sistemi`, `ek_coglar`, `durum_mesajlari`, `eski_ekonomi_sunucu_id` (migration target for legacy global economy data), `node_yolu`/`deno_yolu`)
- `.env` — `DISCORD_TOKEN` (required), `GROQ_API_KEY`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `REPLICATE_API_TOKEN`, `HUGGINGFACE_TOKEN` (currently unused)
- `database.py` — DB connection, cache globals, VIP/AFK/settings/permission helpers, schema + migrations (`veritabanini_kur()`)
- `deploy/mezarbot.service.example` — hardened systemd unit example; `Dockerfile` / `docker-compose.yml` — container setup
- `tests/smoke_test.py` — offline smoke test

## Change safety rules

- Adding new DB columns requires a migration entry in `veritabanini_kur()` (`ALTER TABLE ADD COLUMN` with `try/except`); new `sunucu_ayarlar` columns also go into `SUNUCU_AYAR_KOLONLARI`
- Adding new cached data requires updating both `cache_yukle()` and any write functions to keep cache consistent
- Music module: `kalici_durumu_yukle()` is imported by `main.py` — do not move or rename without updating the import
- `main.py` must stay import-safe (lock/log/token handling only inside `baslat()`), the smoke test imports it

## Known gotchas

- SQLite runs synchronously on the asyncio event loop — avoid adding new DB queries in hot paths (e.g., `on_message` listeners). Use cache instead (full `aiosqlite` migration not done yet)
- `check_same_thread=False` is intentional — the bot runs single-threaded via asyncio, but some slash commands use `asyncio.to_thread` on the shared connection
- `kelime_oyunu_sayac_artir()` does its own `db.commit()` — calling code must not re-commit for the counter, but may commit for other operations in the same block
- `FFMPEG_YOLU` = `shutil.which("ffmpeg")` or `/usr/bin/ffmpeg`
- Single instance: `bot.lock` is held with `fcntl.flock` for the process lifetime (kernel releases it on crash). Exit code `3` = already running, `78` = config error (systemd does not restart on these)
- yt-dlp needs a supported JS runtime for YouTube challenges: Node ≥ 22 or Deno ≥ 2.3 (`/opt/node20` is too old — a warning is logged at startup)
- Slash commands sync ONLY globally on first `on_ready`; guild-level copies are cleared there. Never `copy_global_to(guild)` — global + guild copies make Discord list every command twice

## Music (`cogs/muzik/` package)

- Layout: `kuyruk` (pure queue/seek/vote math), `filtreler` (FFmpeg `-af`), `kaynaklar` (yt-dlp/Spotify via worker processes; any YouTube failure — bot check, age/region block, removed — falls back to SoundCloud via `_soundcloud_yedek`, which skips Go+ 30 s previews and rejects wrong songs with `baslik_uyar_mi` + duration/variant score. Spotify is metadata only: its audio is DRM, never a playback source), `isci.py` (standalone worker script — NEVER import it from the package), `oynatici` (per-guild player), `panel` (persistent view), `sozler` (LRCLIB), `guncelleyici` (yt-dlp updater), `cog` (commands/listeners)
- DB: `muzik_veritabani.py` owns its own tables (`muzik_ayarlar`, `muzik_calma_listeleri`, `muzik_calma_listesi_parcalari`, `muzik_bot_durum`) on the shared `db` connection; `muzik_veritabanini_kur()` runs in the cog's `cog_load`. Column whitelist: `MUZIK_AYAR_KOLONLARI`; cache `_muzik_ayar_cache` is refreshed from the DB row on every write
- Audio path MUST stay: `discord.FFmpegOpusAudio` (copy when source is Opus + no filter + volume 100, else libopus with `-af` incl. `volume=`) wrapped in `OnbellekliKaynak`. No `PCMVolumeTransformer`/`audioop` or other per-frame Python work in the audio thread (causes stutter under GIL contention)
- yt-dlp / Spotify parsing MUST run in the worker processes (`Cozucu` → `IsciHavuzu`), never in a thread of the bot process
- Cleanup is centralized in `Muzik._cleanup_guild()` (player FFmpeg + tasks, panel, voice). Player transitions use the `nesil` counter — bump it before `vc.stop()` when the old stream's end must be ignored
- DAVE: discord.py ≥ 2.7 requires `davey` for any voice connection (RuntimeError otherwise); Discord rejects non-E2EE voice since 2026-03-02 (close code 4017)
- yt-dlp auto-update exits with code `75` (`bot.cikis_kodu`, handled at the end of `main.baslat()`) → systemd `Restart=on-failure` restarts with the new version
- Tests: `venv/bin/python tests/muzik_test.py` (network) or `--agsiz` (offline only)
