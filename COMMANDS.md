# MezarBot commands

Most commands work with both `/` (slash) and `!` (prefix); grouped commands (e.g. `/oda`, `/sesstat`) are slash-only. Command names are Turkish (prefix commands also have English aliases like `!play`, `!skip`). Generated from the bot's command tree.

## 🎵 Music

| Command | Description |
|---|---|
| `/atla` | Skips the song (votes if voting is on) · give a number to jump to that track |
| `/calmalistesi cikar` | Remove a track from your playlist |
| `/calmalistesi ekle` | Add a song to your playlist (empty: the current song) |
| `/calmalistesi goster` | Playlists (personal and shared) |
| `/calmalistesi kaydet` | Saves the current song + queue to your personal playlist (overwrites one with the same name) |
| `/calmalistesi oynat` | Adds a playlist to the queue |
| `/calmalistesi sil` | Deletes your personal playlist entirely |
| `/cik` | Disconnects the bot from voice (the queue is cleared) |
| `/devam` | Resumes paused music |
| `/dongu` | Loop mode: off / song / queue |
| `/duraklat` | Pauses the music |
| `/durdur` | Stops playback and clears the queue (leaves the channel if 24/7 is off) |
| `/geri` | Rewinds the song (default 10 s) |
| `/ileri` | Fast-forwards the song (default 10 s) |
| `/kaldir` | Removes a track from the queue |
| `/karistir` | Shuffles the queue |
| `/katil` | Calls the bot to your voice channel |
| `/kuyruk` | Shows the queue page by page |
| `/muzikayar dj` | Sets the DJ role (empty: turns it off). DJs use the control commands. |
| `/muzikayar goster` | This server's music settings |
| `/muzikayar istekkanali` | Song request channel: every message in this channel is searched and added to the queue |
| `/muzikayar normalizasyon` | Default state of volume normalization |
| `/muzikayar otomatik` | Default state of autoplay |
| `/muzikayar oylama` | Vote skip: on / off or the required ratio (e.g. 60) |
| `/muzikayar surekli` | 24/7 mode: don't leave the channel when idle/alone |
| `/muzikayar varsayilanses` | Starting volume for new sessions (0-150) |
| `/muzikayar zamanasimi` | How many minutes to wait before leaving when idle or alone |
| `/muzikgecmis` | Songs played recently on this server |
| `/normalizasyon` | Volume normalization (evens out loudness between songs) on/off |
| `/onceki` | Goes back to the previous song |
| `/otomatik` | Autoplay: keeps going with similar songs when the queue ends |
| `/oygec` | Turns vote skip on/off or sets the required ratio |
| `/oylaatla` | Votes to skip the song |
| `/oynat` | Plays a song / playlist (YouTube, YT Music, Spotify, SoundCloud, link) |
| `/sar` | Seeks to a specific point in the song (1:30, +30, -10) |
| `/ses` | Volume level (0-150, remembered per server) |
| `/simdi` | Shows what's playing and the control panel (moves the panel to this channel) |
| `/siradaki` | Adds a song to the front of the queue (plays next) |
| `/tasi` | Moves a track to another position in the queue |
| `/temizle` | Clears the queue (if you're not a DJ, only the tracks you added) |
| `/ytdlpguncelle` | [Bot Owner] Updates yt-dlp in the venv |

## 🔊 Private voice rooms

| Command | Description |
|---|---|
| `/oda ac` | Unlocks the room: everyone can join |
| `/oda ad` | Renames the room (at most 50 characters) |
| `/oda at` | Kicks a member from the room and stops them rejoining |
| `/oda bilgi` | Your private voice room's info and management |
| `/oda davet` | Invites a member to your room (they can join even if it's locked/hidden) |
| `/oda devret` | Gives room ownership to another member |
| `/oda gizle` | Hides the room: only invited people can see it |
| `/oda goster` | Makes the room visible to everyone again |
| `/oda kilitle` | Locks the room: only people you invite can join |
| `/oda limit` | Sets the people limit (0 = unlimited, at most 99) |
| `/oda panel` | Re-sends the control panel to the room's chat |
| `/oda sahiplen` | Take over the room if its owner isn't in it (you must be in the room) |
| `/oda yasak-kaldir` | Lifts a member's room ban |
| `/oda yasakla` | Kicks a member from the room; they can't see or join it |
| `/ozeloda ayar` | Changes the private room defaults (empty: shows them) |
| `/ozeloda durum` | Private room system status and settings (admin) |
| `/ozelodaaktif` | Turns on the private voice room system on this server and sets up/repairs its channels |
| `/ozelodakapat` | Turns off the private voice room system and removes its channels |

## 📊 Voice stats

| Command | Description |
|---|---|
| `/sesstat ay` | Members who spent the most time in voice this month |
| `/sesstat ben` | Your voice channel stats |
| `/sesstat hafta` | Members who spent the most time in voice this week |
| `/sesstat kanal` | Set the channel to track (leave empty to track ALL channels) |
| `/sesstat sifirla` | Deletes all voice activity data (CAN'T BE UNDONE) |
| `/sesstat top` | Members who spent the most time in voice on this server (all time) |

## 🛡️ Moderation & server settings

| Command | Description |
|---|---|
| `/afk` | Go AFK (your reason is shown when someone mentions you) |
| `/at` | Kick a member from the server |
| `/ayarlar` | Show and change the bot's settings for this server |
| `/dil` | Changes the bot's language for this server (tr / en) |
| `/durumayarla` | [Bot Owner] Sets the bot's status permanently |
| `/gorusuruzayarla` | Set or turn off the goodbye (leave) channel and message |
| `/hosgeldinayarla` | Set the welcome channel and message |
| `/logayarla` | Set the moderation log channel |
| `/otomod` | Turn auto-moderation on/off |
| `/otorolayarla` | Set the role automatically given to new members |
| `/settings` | View and change bot settings and language for this server |
| `/sil` | Delete messages from the channel (default 5) |
| `/sustur` | Time out a member (e.g. 10m, 1h) |
| `/susturmakald` | Remove a member's timeout |
| `/sync` | [Bot Owner] Syncs slash commands globally |
| `/takimkur` | Split the people in your voice channel into random teams |
| `/uyar` | Warn a member |
| `/uyarayarla` | Set the warning log channel |
| `/uyarilar` | Show a member's warnings |
| `/uyarisil` | Clear a member's warnings |
| `/yamanotu` | [Bot Owner] Announces a patch note to all servers |
| `/yamanotukanal` | Set or turn off the patch notes channel |
| `/yasak` | Ban a member from the server |
| `/yaz` | Post a message in a channel through the bot |

## 🤖 AI

| Command | Description |
|---|---|
| `/ciz` | Draw an image with AI |
| `/draw` | Draw an image with AI |
| `/kisilik` | Pick the AI's personality |
| `/sifirla` | Reset your AI chat history |

## 🗣️ Text to speech

| Command | Description |
|---|---|
| `/ayril` | Disconnect the text-to-speech bot from the channel |
| `/konus` | Read text aloud in a voice channel |

## 🌐 Translation

| Command | Description |
|---|---|
| `/cevir` | Translates text to Turkish or English |

## ❓ Help

| Command | Description |
|---|---|
| `/help` | View MezarBot command guide and help menu |
| `/yardim` | View the MezarBot command guide |

## 🚪 Member approval gate (optional, enabled in config)

| Command | Description |
|---|---|
| `/dilpaneli` | Re-sends the language picker panel in the 🚪・giris channel |
| `/onayla` | Approves a pending member and opens the channels |
| `/reddet` | Rejects a pending member and kicks them from the server |

## Message reactions

- React with 🇬🇧 / 🇺🇸 to translate a message to English, 🇹🇷 to Turkish (Groq).
- Mention the bot to chat with the AI.
