"""İngilizce çeviriler — anahtar: koddaki _t(...) şablonu (Türkçe, birebir). tests/dil_test.py eksikleri bulur.
Yeni metin eklerken: kodda _t("…") kullan, buraya karşılığını ekle (yer tutucular {ad} aynı kalmalı)."""

EN = {
    # ── cogs/muzik/panel.py ──
    "**%{ses}**":
        "**{ses}%**",
    # ── cogs/ozel_oda.py ──
    "Limit":
        "Limit",
    "Ad":
        "Rename",
    "Davet":
        "Invite",
    "At":
        "Kick",
    "Devret":
        "Transfer",
    "Sahiplen":
        "Claim",
    "👥 Kişi limiti":
        "👥 People limit",
    "✏️ Oda adı":
        "✏️ Room name",
    # ── diğer ──
    "{d0} dk {d2} sn":
        "{d0} min {d2} s",
    "Vazgeç":
        "Cancel",
    "{saat} sa {dakika} dk":
        "{saat} h {dakika} min",
    "{dakika} dk":
        "{dakika} min",
    "**{d1} sa {d3} dk**":
        "**{d1} h {d3} min**",
    "🔊 **{name}** — {saat} sa {dakika} dk":
        "🔊 **{name}** — {saat} h {dakika} min",
    "Oda adı en fazla {AD_MAX} karakter olabilir (yazdığın: {len}).":
        "A room name can be at most {AD_MAX} characters (yours: {len}).",
    "Geçerli bir oda adı yaz (etiket ve link kullanılamaz).":
        "Type a valid room name (mentions and links aren't allowed).",
    "Limit bir sayı olmalı.":
        "The limit must be a number.",
    "Limit {LIMIT_MIN}-{LIMIT_MAX} arası bir sayı olmalı (0 = sınırsız).":
        "The limit must be a number between {LIMIT_MIN} and {LIMIT_MAX} (0 = unlimited).",
    "Limit {LIMIT_MIN}-{LIMIT_MAX} arası olmalı (0 = sınırsız).":
        "The limit must be between {LIMIT_MIN} and {LIMIT_MAX} (0 = unlimited).",
    "Şablon boş olamaz. Örnek: `🔊 {kullanici} odası`":
        "The template can't be empty. Example: `🔊 {kullanici}'s room`",
    "Şablon çok uzun (en fazla {d1} karakter).":
        "The template is too long (at most {d1} characters).",
    "Bilinmeyen alan: ":
        "Unknown field: ",
    " — kullanılabilir: `{kullanici}`, `{sayi}`":
        " — you can use: `{kullanici}`, `{sayi}`",
    "Kişi başı oda {KISI_BASI_MIN}-{KISI_BASI_MAX} arası olmalı.":
        "Rooms per person must be between {KISI_BASI_MIN} and {KISI_BASI_MAX}.",
    "Bu şablondan geçerli bir oda adı çıkmıyor.":
        "This template doesn't produce a valid room name.",
    "Süreyi saniye (ör. `30`) ya da dakika (ör. `2dk`) olarak yaz.":
        "Write the time in seconds (e.g. `30`) or minutes (e.g. `2m`).",
    "Süre {SURE_MIN} sn ile {d3} dk arası olmalı.":
        "The time must be between {SURE_MIN} s and {d3} min.",
    "`evet` ya da `hayır` yaz.":
        "Type `yes` or `no`.",
    "Müzik":
        "Music",
    "{saniye} saniye":
        "{saniye} seconds",
    "{d0} dakika":
        "{d0} minutes",
    "{d0} saat":
        "{d0} hours",
    "{d0} gün":
        "{d0} days",
    "English Translation":
        "English Translation",
    "Türkçe Çeviri":
        "Turkish Translation",
    "MezarBot • Otomatik Çeviri Köprüsü (Groq Free Tier)":
        "MezarBot • Auto Translation Bridge (Groq Free Tier)",
    "⚠️ Çeviri gerçekleştirilemedi, lütfen tekrar deneyin.":
        "⚠️ Translation failed, please try again.",
    "İngilizce":
        "English",
    "Türkçe":
        "Turkish",
    "{bayrak} {dil_etiket} Çevirisi":
        "{bayrak} {dil_etiket} Translation",
    "Orijinal Metin":
        "Original Text",
    "```text\n{metin}\n```":
        "```text\n{metin}\n```",
    "Çeviri":
        "Translation",
    "MezarBot • Groq Çeviri Servisi":
        "MezarBot • Groq Translation Service",
    "Bu komutu sadece **VIP** üyeler kullanabilir!":
        "Only **VIP** members can use this command!",
    "Önce bir ses kanalına girmelisin!":
        "Join a voice channel first!",
    "Boş metin gönderilemez!":
        "You can't send an empty text!",
    "Mesaj çok uzun! (Sınırınız: {limit} karakter)":
        "Message is too long! (Your limit: {limit} characters)",
    "Şu an müzik çalıyor! Önce müziği kapat veya bitir.":
        "Music is playing right now! Stop or finish the music first.",
    "Ses kanalına bağlanılamadı: {e}":
        "Couldn't connect to the voice channel: {e}",
    "Ses kanalına bağlanılamadı!":
        "Couldn't connect to the voice channel!",
    "Seslendirme sırasında bir hata oluştu.":
        "Something went wrong while speaking.",
    "Ses kanalından ayrıldım. 👋":
        "Left the voice channel. 👋",
    "Zaten bir ses kanalında değilim.":
        "I'm not in a voice channel.",
    "🎧 Bunu yapmak için benimle aynı ses kanalında (**{name}**) olmalısın.":
        "🎧 You need to be in the same voice channel as me (**{name}**) to do that.",
    "🎚️ Bu işlem için **DJ rolü** (<@&{rol_id}>) gerekli.":
        "🎚️ This needs the **DJ role** (<@&{rol_id}>).",
    "{bot} müzik paneli":
        "{bot} music panel",
    "⏹️ Durduruldu, kuyruk temizlendi. (7/24 modu: kanalda kalıyorum)":
        "⏹️ Stopped and cleared the queue. (24/7 mode: staying in the channel)",
    "⏹️ Durduruldu ve kanaldan ayrıldım.":
        "⏹️ Stopped and left the channel.",
    "❌ Önce bir ses kanalına gir!":
        "❌ Join a voice channel first!",
    "❌ **{name}** kanalına bağlanma/konuşma yetkim yok.":
        "❌ I don't have permission to connect or speak in **{name}**.",
    "❌ Ses bağlantısı zaman aşımına uğradı, tekrar dene.":
        "❌ Voice connection timed out, try again.",
    "❌ Sese bağlanılamadı: {e}":
        "❌ Couldn't connect to voice: {e}",
    "❌ Botun ses kütüphaneleri eksik (DAVE/davey). Bot sahibine haber ver.":
        "❌ The bot's voice libraries are missing (DAVE/davey). Let the bot owner know.",
    "🎧 Şu an **{name}** kanalında çalıyorum — oraya gel ya da DJ'e söyle.":
        "🎧 I'm playing in **{name}** right now — come there or ask a DJ.",
    "❌ Kanala taşınamadım: {e}":
        "❌ Couldn't move to the channel: {e}",
    "Spotify kısa linki çözülemedi":
        "couldn't resolve the Spotify short link",
    "Spotify kısa linki tanınmayan bir sayfaya gidiyor":
        "the Spotify short link leads to an unknown page",
    "sonuç bulunamadı":
        "no results found",
    "Spotify içeriği okunamadı (özel liste olabilir)":
        "couldn't read the Spotify content (it may be a private playlist)",
    "playlist boş ya da özel":
        "the playlist is empty or private",
    "❌ Kuyruk dolu ({limit} parça). Biraz çalınmasını bekle ya da `/temizle`.":
        "❌ The queue is full ({limit} tracks). Wait for some to play or use `/temizle`.",
    "❌ Çalınamıyor: {sebep}":
        "❌ Can't play: {sebep}",
    "📋 **{escape_markdown}** — **{eklenen}** parça {d5} eklendi.":
        "📋 **{escape_markdown}** — **{eklenen}** tracks added {d5}.",
    "⏳ Kalan parçalar arka planda ekleniyor… (toplam ~{toplam})":
        "⏳ Adding the remaining tracks in the background… (~{toplam} total)",
    "⚠️ Kuyruk sınırı ({limit}) nedeniyle {d3} parça eklenemedi.":
        "⚠️ {d3} tracks weren't added because of the queue limit ({limit}).",
    "▶️ **Şimdi çalınıyor**":
        "▶️ **Now playing**",
    "⏭️ **Sıradaki olarak eklendi**":
        "⏭️ **Added as next**",
    "✅ **Kuyruğa eklendi** · #{len}":
        "✅ **Added to the queue** · #{len}",
    "⚠️ Playlist'in kalanı yüklenemedi: {sebep}":
        "⚠️ Couldn't load the rest of the playlist: {sebep}",
    "📋 Playlist'in kalan **{eklenen}** parçası da kuyruğa eklendi.":
        "📋 The remaining **{eklenen}** tracks of the playlist were added to the queue too.",
    "❌ **{liste_adi}** listesi boş.":
        "❌ The **{liste_adi}** playlist is empty.",
    " (⭐ Sunucu Listesi)":
        " (⭐ Server Playlist)",
    " (Paylaşılan)":
        " (Shared)",
    "sıranın başına":
        "to the front of the queue",
    "kuyruğa":
        "to the queue",
    "📂 **{liste_adi}**{sahip_notu} — **{eklenen}** parça {yer_metni} eklendi.":
        "📂 **{liste_adi}**{sahip_notu} — **{eklenen}** tracks added {yer_metni}.",
    " (Kuyruk sınırı: {d1} eklenemedi)":
        " (Queue limit: {d1} not added)",
    "❌ Bir şarkı adı ya da link yaz: `/oynat tarkan şımarık`":
        "❌ Type a song name or link: `/oynat never gonna give you up`",
    "❌ Arama metni çok uzun!":
        "❌ The search text is too long!",
    "❌ Çalan bir şey yok.":
        "❌ Nothing is playing.",
    "🗳️ Oylama tamam ({n}/{gerekli}) — ⏭️ atlandı.":
        "🗳️ Vote passed ({n}/{gerekli}) — ⏭️ skipped.",
    "⏳ Geçiş sürüyor…":
        "⏳ Switching tracks…",
    "🗳️ Atlama oyu: **{len}/{gerekli}** — dinleyicilerin %{int}'i gerekli.":
        "🗳️ Skip votes: **{len}/{gerekli}** — {int}% of listeners needed.",
    "Bassboost: Kapalı":
        "Bassboost: Off",
    "🎶 Kuyruk boş.":
        "🎶 The queue is empty.",
    "❌ Şu an çalan bir şey yok. `/oynat` ile başla.":
        "❌ Nothing is playing right now. Start with `/oynat`.",
    "⏮️ Geçmişte önceki bir şarkı yok.":
        "⏮️ There's no previous song in the history.",
    "🔀 Karıştırmak için kuyrukta en az 2 parça olmalı.":
        "🔀 You need at least 2 tracks in the queue to shuffle.",
    "❤️ Bu şarkı zaten **Favoriler** listende.":
        "❤️ This song is already in your **Favorites** playlist.",
    "❌ Liste dolu ({LISTE_PARCA_LIMITI} parça).":
        "❌ The playlist is full ({LISTE_PARCA_LIMITI} tracks).",
    "❤️ **{gosterim}** → **Favoriler** listene eklendi. (`/calmalistesi oynat Favoriler`)":
        "❤️ **{gosterim}** → added to your **Favorites** playlist. (`/calmalistesi oynat Favoriler`)",
    "❌ Numara gir: `/atla 3` (sarmak için `/sar 1:30`)":
        "❌ Enter a number: `/atla 3` (to seek, use `/sar 1:30`)",
    "⏭️ {n}. parçaya atlandı.":
        "⏭️ Skipped to track {n}.",
    "⏳ Geçiş sürüyor, bir saniye…":
        "⏳ Switching tracks, one second…",
    "⏮️ **{gosterim}** tekrar çalıyor.":
        "⏮️ **{gosterim}** is playing again.",
    "⏸️ Duraklatıldı.":
        "⏸️ Paused.",
    "❌ Duraklatılmış bir şey yok.":
        "❌ Nothing is paused.",
    "▶️ Devam ediyor.":
        "▶️ Resumed.",
    "❌ Zaten çalan bir şey yok.":
        "❌ Nothing is playing.",
    "🔴 Canlı yayında sarılamaz.":
        "🔴 You can't seek in a live stream.",
    "❌ Geçersiz süre. Örnekler: `1:30`, `90`, `+30`, `-10`, `2m15s`":
        "❌ Invalid time. Examples: `1:30`, `90`, `+30`, `-10`, `2m15s`",
    "{ok} `{sure_metni}` konumuna sarıldı.":
        "{ok} Seeked to `{sure_metni}`.",
    "❌ Sarma başarısız oldu.":
        "❌ Seeking failed.",
    "🎶 Kuyruk boş. `/oynat` ile şarkı ekle.":
        "🎶 The queue is empty. Add songs with `/oynat`.",
    "❌ Kuyruk boş.":
        "❌ The queue is empty.",
    "❌ Geçersiz numara (1-{len}).":
        "❌ Invalid number (1-{len}).",
    " (Kendi eklediğin parçaları kaldırabilirsin.)":
        " (You can only remove tracks you added.)",
    "🗑️ **{gosterim}** kaldırıldı.":
        "🗑️ Removed **{gosterim}**.",
    "❌ Karıştırmak için kuyrukta en az 2 parça olmalı.":
        "❌ You need at least 2 tracks in the queue to shuffle.",
    "🔀 Kuyruk karıştırıldı!":
        "🔀 Queue shuffled!",
    "❌ Kuyruk zaten boş.":
        "❌ The queue is already empty.",
    "🧹 Kendi eklediğin **{n}** parça kaldırıldı.":
        "🧹 Removed **{n}** tracks you added.",
    "🧹 Kuyruk temizlendi ({n} parça).":
        "🧹 Queue cleared ({n} tracks).",
    "❌ Mod: `kapalı`, `şarkı` ya da `kuyruk`":
        "❌ Mode: `off`, `song` or `queue`",
    "{emoji} Döngü: **{DONGU_ETIKET}**":
        "{emoji} Loop: **{DONGU_ETIKET}**",
    "🔊 Ses: **%{mevcut}**  (değiştirmek: `/ses 80`, `/ses +10`)":
        "🔊 Volume: **{mevcut}%**  (to change: `/ses 80`, `/ses +10`)",
    "❌ 0-150 arası bir sayı gir.":
        "❌ Enter a number between 0 and 150.",
    "❌ Ses {SES_MIN}-{SES_MAX} arası olmalı.":
        "❌ Volume must be between {SES_MIN} and {SES_MAX}.",
    "{emoji} Ses **%{hedef}**":
        "{emoji} Volume **{hedef}%**",
    " · 📢 %100 üstü sesi bozabilir":
        " · 📢 above 100% may distort the sound",
    "🎶 Şu an bir şey çalmıyor.":
        "🎶 Nothing is playing right now.",
    "🎛️ Kontrol paneli bu kanala taşındı.":
        "🎛️ Control panel moved to this channel.",
    "🕘 Henüz bir şey çalınmadı.":
        "🕘 Nothing has been played yet.",
    "🎛️ Filtreler":
        "🎛️ Filters",
    "**Aktif:** {d1}\n\n":
        "**Active:** {d1}\n\n",
    "Kullanım: /filtre nightcore · /filtre bas 3 · /filtre hiz 1.25 · /filtre kapat":
        "Usage: /filtre nightcore · /filtre bas 3 · /filtre hiz 1.25 · /filtre kapat",
    "❌ Bilinmeyen filtre: `{secim}` — liste için `/filtre`":
        "❌ Unknown filter: `{secim}` — use `/filtre` for the list",
    "❌ Geçersiz değer.":
        "❌ Invalid value.",
    "\n-# Aktif: {join}":
        "\n-# Active: {join}",
    "❌ `aç` ya da `kapat` yaz.":
        "❌ Type `on` or `off`.",
    "📻 Otomatik oynatma: **{d1}**":
        "📻 Autoplay: **{d1}**",
    " — kuyruk bitince benzer şarkılar çalacak.":
        " — similar songs will play when the queue ends.",
    "✅ **{name}** kanalındayım. `/oynat` ile başla!":
        "✅ I'm in **{name}**. Start with `/oynat`!",
    "❌ Zaten bir ses kanalında değilim.":
        "❌ I'm not in a voice channel.",
    "👋 Görüşürüz!":
        "👋 See you!",
    "📂 Henüz kayıtlı liste yok. Çalan kuyruğu kaydet: `/calmalistesi kaydet <ad>` · ya da panelde ❤️ ile favorilere ekle.":
        "📂 No saved playlists yet. Save the current queue: `/calmalistesi kaydet <name>` · or add songs to favorites with ❤️ on the panel.",
    "📂 Çalma Listeleri":
        "📂 Playlists",
    "👤 **Kişisel Listelerin:**\n":
        "👤 **Your Playlists:**\n",
    "⭐ **Genel / Paylaşılan Listeler:**\n":
        "⭐ **Public / Shared Playlists:**\n",
    "Çal: /calmalistesi oynat <ad> · İçerik: /calmalistesi goster <ad>":
        "Play: /calmalistesi oynat <name> · Contents: /calmalistesi goster <name>",
    "❌ **{ad}** adında bir liste bulunamadı.":
        "❌ No playlist named **{ad}** was found.",
    " (Sana ait)":
        " (Yours)",
    "*Boş liste*":
        "*Empty playlist*",
    "Sayfa {d1}/{n} • {len} parça":
        "Page {d1}/{n} • {len} tracks",
    "❌ Kaydedilecek bir şey yok (çalan şarkı / kuyruk boş).":
        "❌ Nothing to save (no song playing and the queue is empty).",
    "💾 **{ad}** listesine **{n}** parça kaydedildi.":
        "💾 Saved **{n}** tracks to the **{ad}** playlist.",
    "❌ Çalan bir şey yok — eklemek için şarkı adı/link yaz.":
        "❌ Nothing is playing — type a song name or link to add.",
    "❌ Eklenemedi: {sebep}":
        "❌ Couldn't add: {sebep}",
    "➕ **{ad}** listesine {n} parça eklendi":
        "➕ Added {n} tracks to the **{ad}** playlist",
    "❌ **{ad}** adında sana ait bir liste yok.":
        "❌ You don't have a playlist named **{ad}**.",
    "🗑️ **{baslik}** listeden çıkarıldı.":
        "🗑️ Removed **{baslik}** from the playlist.",
    "❌ Geçersiz numara.":
        "❌ Invalid number.",
    "🗑️ **{ad}** listesi silindi.":
        "🗑️ Deleted the **{ad}** playlist.",
    "⚙️ Müzik Ayarları":
        "⚙️ Music Settings",
    "🎚️ DJ rolü":
        "🎚️ DJ role",
    "Kapalı (herkes kontrol eder)":
        "Off (everyone can control)",
    "🗳️ Oylamalı atla":
        "🗳️ Vote skip",
    " (DJ rolü ayarlı → otomatik)":
        " (DJ role set → automatic)",
    "🔊 Ses":
        "🔊 Volume",
    "Varsayılan %{a} · Son %{d3}":
        "Default {a}% · Last {d3}%",
    "Kapalı":
        "Off",
    "🌙 7/24 modu":
        "🌙 24/7 mode",
    "Açık":
        "On",
    "📻 Otomatik oynatma":
        "📻 Autoplay",
    "⏱️ Boşta ayrılma":
        "⏱️ Leave when idle",
    "📶 Normalizasyon":
        "📶 Normalization",
    "📨 İstek kanalı":
        "📨 Request channel",
    "Değiştir: /muzikayar dj · oylama · varsayilanses · surekli · otomatik · zamanasimi · istekkanali · normalizasyon":
        "Change: /muzikayar dj · oylama · varsayilanses · surekli · otomatik · zamanasimi · istekkanali · normalizasyon",
    "🚫 Bu ayar için sunucu yöneticisi (Yönetici / Sunucuyu Yönet)":
        "🚫 This setting needs a server admin (Administrator / Manage Server)",
    " gerekli.":
        ".",
    " ya da DJ rolü":
        " or the DJ role",
    "🎚️ DJ rolü: {mention}. Artık kontrol komutları DJ'lere/yöneticilere özel, diğerleri oyla atlar.":
        "🎚️ DJ role: {mention}. Control commands are now limited to DJs/admins; everyone else votes to skip.",
    "🎚️ DJ sistemi kapatıldı — herkes kontrol edebilir.":
        "🎚️ DJ system turned off — everyone can control.",
    "❌ Oran %10-%100 arası olmalı.":
        "❌ The ratio must be between 10% and 100%.",
    "🗳️ Oylamalı atla açık — dinleyicilerin **%{sayi}**'i gerekli.":
        "🗳️ Vote skip is on — **{sayi}%** of listeners needed.",
    "❌ `aç`, `kapat` ya da bir yüzde yaz.":
        "❌ Type `on`, `off` or a percentage.",
    "🗳️ Oylamalı atla: **{d1}**":
        "🗳️ Vote skip: **{d1}**",
    " (DJ rolü ayarlı olduğu için DJ olmayanlar yine oyla atlar)":
        " (since a DJ role is set, non-DJs still vote to skip)",
    "🔊 Varsayılan ses **%{n}** (hatırlanan son ses sıfırlandı).":
        "🔊 Default volume **{n}%** (the remembered last volume was reset).",
    "🌙 7/24 modu: **{d1}**":
        "🌙 24/7 mode: **{d1}**",
    "📻 Otomatik oynatma (varsayılan): **{d1}**":
        "📻 Autoplay (default): **{d1}**",
    "❌ 30 saniye ile 60 dakika arası bir süre gir (ör. `3` = 3 dk, `90s`).":
        "❌ Enter a time between 30 seconds and 60 minutes (e.g. `3` = 3 min, `90s`).",
    "⏱️ Boşta/yalnız kalınca **{sure_metni}** sonra ayrılacağım (7/24 kapalıyken).":
        "⏱️ I'll leave after **{sure_metni}** of being idle/alone (when 24/7 is off).",
    "📶 Normalizasyon (varsayılan): **{d1}** — yeni oturumlarda geçerli; şu anki oturum için `/filtre normalizasyon`.":
        "📶 Normalization (default): **{d1}** — applies to new sessions; for the current session use `/filtre normalizasyon`.",
    "📨 Şarkı istek kanalı kapatıldı.":
        "📨 Song request channel turned off.",
    "❌ Kanal oluşturma yetkim yok — mevcut bir kanal belirt: `/muzikayar istekkanali #kanal`":
        "❌ I don't have permission to create channels — name an existing one: `/muzikayar istekkanali #channel`",
    "❌ {mention} kanalında **Mesaj Gönder, Bağlantı Yerleştir, Mesajları Yönet, Mesaj Geçmişini Oku** yetkilerim olmalı.":
        "❌ I need **Send Messages, Embed Links, Manage Messages, Read Message History** permissions in {mention}.",
    "📨 Şarkı istek kanalı: {mention} — oraya yazılan her mesaj aranıp kuyruğa eklenir, kontrol paneli de orada durur.":
        "📨 Song request channel: {mention} — every message there is searched and added to the queue, and the control panel stays there.",
    "⏳ yt-dlp güncelleniyor… (çalışan sürüm: `{calisan_surum}`)":
        "⏳ Updating yt-dlp… (running version: `{calisan_surum}`)",
    "sahip komutu":
        "owner command",
    "❌ Güncelleme başarısız:\n```{sonuc}```":
        "❌ Update failed:\n```{sonuc}```",
    "✅ yt-dlp zaten güncel: `{sonuc}`":
        "✅ yt-dlp is already up to date: `{sonuc}`",
    "✅ yt-dlp `{sonuc}` → `{sonuc2}`. ":
        "✅ yt-dlp `{sonuc}` → `{sonuc2}`. ",
    "Çalan müzikler bitince yeniden başlatacağım.":
        "I'll restart once the music currently playing ends.",
    "Yeniden başlatılıyor… 🔄":
        "Restarting… 🔄",
    "haftalık kontrol":
        "weekly check",
    "👋 Kanalda kimse kalmadı, ayrıldım. Tekrar görüşmek üzere!":
        "👋 Nobody's left in the channel, so I left. See you next time!",
    "💤 Bir süredir boştayım, kanaldan ayrıldım.":
        "💤 I've been idle for a while, so I left the channel.",
    "🔌 Ses bağlantısı koptu.":
        "🔌 The voice connection dropped.",
    "👋 Ses kanalından çıkarıldım.":
        "👋 I was removed from the voice channel.",
    "🔌 Ses bağlantısı koptu ve yeniden bağlanamadım.":
        "🔌 The voice connection dropped and I couldn't reconnect.",
    "🔌 Ses bağlantısı koptu — yeniden bağlandım, kaldığı yerden devam ediyorum.":
        "🔌 The voice connection dropped — I reconnected and I'm resuming where it left off.",
    "⏳ {mention} biraz yavaş — {ISTEK_BEKLEME:.0f} sn bekle.":
        "⏳ {mention}, slow down a little — wait {ISTEK_BEKLEME:.0f} s.",
    "Tüm efektler kapatıldı.":
        "All effects turned off.",
    "açık":
        "on",
    "kapalı":
        "off",
    "Hız: {deger:g}x":
        "Speed: {deger:g}x",
    "Normalizasyon: {durum}":
        "Normalization: {durum}",
    "pip {PIP_ZAMAN_ASIMI} sn içinde bitmedi":
        "pip didn't finish within {PIP_ZAMAN_ASIMI} s",
    "pip çalıştırılamadı: {e}":
        "couldn't run pip: {e}",
    "zaman aşımı":
        "timed out",
    "çözülemedi":
        "couldn't be resolved",
    "işçi süreci kapandı":
        "the worker process closed",
    "bilinmeyen hata":
        "unknown error",
    "çalınabilir ses formatı yok":
        "no playable audio format",
    "uygun sonuç bulunamadı":
        "no suitable result found",
    "Spotify sanatçı linkleri desteklenmiyor — şarkı, albüm ya da playlist linki gönder.":
        "Spotify artist links aren't supported — send a track, album or playlist link.",
    "⚠️ **{gosterim}** atlandı: {sebep}":
        "⚠️ Skipped **{gosterim}**: {sebep}",
    "❌ Üst üste çok fazla parça çözülemedi, oynatma durduruldu.":
        "❌ Too many tracks in a row couldn't be resolved, playback stopped.",
    "⚠️ **{gosterim}** akışı başlatılamadı, atlanıyor.":
        "⚠️ Couldn't start the stream for **{gosterim}**, skipping.",
    "⚠️ **{gosterim}** yeniden bağlanamadı: {sebep}":
        "⚠️ Couldn't reconnect **{gosterim}**: {sebep}",
    "⚠️ **{gosterim}** akışı koptu, sıradakine geçiliyor.":
        "⚠️ The stream for **{gosterim}** dropped, moving to the next one.",
    "Otomatik Oynatma":
        "Autoplay",
    "⚠️ Akış yenilenemedi: {sebep}":
        "⚠️ Couldn't refresh the stream: {sebep}",
    "⏸️ Duraklatıldı":
        "⏸️ Paused",
    "🔴 Canlı Yayın":
        "🔴 Live Stream",
    "🎶 Şu An Çalıyor":
        "🎶 Now Playing",
    "💤 *Kanalda kimse kalmadı — biri gelince kaldığı yerden devam edecek.*":
        "💤 *Nobody's left in the channel — it'll resume where it left off when someone joins.*",
    "📻 Otomatik":
        "📻 Autoplay",
    "👤 İsteyen":
        "👤 Requested by",
    "🔁 Döngü":
        "🔁 Loop",
    "📋 Kuyruk":
        "📋 Queue",
    "{len} parça":
        "{len} tracks",
    "Opus aktarım (kayıpsız)":
        "Opus pass-through (lossless)",
    "Opus · 160 kbps":
        "Opus · 160 kbps",
    "🎚️ Ses Yolu":
        "🎚️ Audio Path",
    "📶 Ses Dengeleme":
        "📶 Normalization",
    "🔂 Aynı şarkı tekrar çalacak":
        "🔂 The same song will play again",
    "\n-# … ve {d1} parça daha":
        "\n-# … and {d1} more tracks",
    "📻 Otomatik oynatma benzer bir parça bulacak":
        "📻 Autoplay will find a similar track",
    "Kuyruk boş — `/oynat` ile ekle":
        "The queue is empty — add songs with `/oynat`",
    "⏭️ Sıradaki":
        "⏭️ Up Next",
    "{bot} Premium Müzik":
        "{bot} Premium Music",
    "🎵 {bot} Müzik":
        "🎵 {bot} Music",
    "**Bir ses kanalına gir ve bu kanala şarkı adı ya da link yaz** — gerisini ben hallederim.\n-# Mesajın sıraya eklenince otomatik silinir; kanal hep temiz kalır.":
        "**Join a voice channel and type a song name or link in this channel** — I'll take care of the rest.\n-# Your message is deleted once it's queued, so the channel always stays clean.",
    "Bir ses kanalına gir ve `/oynat <şarkı>` ya da `{prefix}oynat <şarkı>` yaz.":
        "Join a voice channel and type `/oynat <song>` or `{prefix}play <song>`.",
    "{d0}Şu an bir şey çalmıyor.\n\n{nasil}":
        "{d0}Nothing is playing right now.\n\n{nasil}",
    "🌐 Kaynaklar":
        "🌐 Sources",
    "🔴 YouTube · 🎵 YouTube Music · 🟢 Spotify · 🟠 SoundCloud · 🔗 Doğrudan ses linki":
        "🔴 YouTube · 🎵 YouTube Music · 🟢 Spotify · 🟠 SoundCloud · 🔗 Direct audio link",
    "✨ Öne Çıkanlar":
        "✨ Highlights",
    "📻 Otomatik oynatma · 📶 Ses dengeleme · 🎤 Senkron sözler · ❤️ Kişisel listeler\n🛟 YouTube çalamazsa SoundCloud yedeği":
        "📻 Autoplay · 📶 Volume normalization · 🎤 Synced lyrics · ❤️ Personal playlists\n🛟 SoundCloud fallback when YouTube fails",
    "📜 Kuyruk":
        "📜 Queue",
    "**▶ Şimdi:** {parca_satiri}\n":
        "**▶ Now:** {parca_satiri}\n",
    "*Kuyruk boş.*":
        "*The queue is empty.*",
    " 📻 Otomatik oynatma açık.":
        " 📻 Autoplay is on.",
    "Sayfa {d1}/{sayfa_sayisi}  •  {len} parça":
        "Page {d1}/{sayfa_sayisi}  •  {len} tracks",
    "  •  Döngü: {get}":
        "  •  Loop: {get}",
    "🕘 Son Çalınanlar":
        "🕘 Recently Played",
    "*Henüz bir şey çalınmadı.*":
        "*Nothing has been played yet.*",
    "⏮️ önceki şarkıya dönmek için /onceki":
        "⏮️ use /onceki to go back to the previous song",
    "🎛️ Filtre / efekt seç…":
        "🎛️ Pick a filter / effect…",
    "Otomatik: Kapalı":
        "Autoplay: Off",
    "Favorilerime ekle":
        "Add to my favorites",
    "Otomatik: {d1}":
        "Autoplay: {d1}",
    "⚠️ Bir hata oluştu, tekrar dene.":
        "⚠️ Something went wrong, try again.",
    "Bu menü sana ait değil — kendi komutunu kullan.":
        "This menu isn't yours — use your own command.",
    "*♪ (giriş)*":
        "*♪ (intro)*",
    "*(boş)*":
        "*(empty)*",
    "Üye":
        "Member",
    "Özel Oda":
        "Private Room",
    "⚠️ Özel oda sistemi şu an yüklü değil.":
        "⚠️ The private room system isn't loaded right now.",
    "Aç":
        "Unlock",
    "Kilitle":
        "Lock",
    "Göster":
        "Show",
    "Gizle":
        "Hide",
    "Limit (0 = sınırsız, en fazla 99)":
        "Limit (0 = unlimited, at most 99)",
    "ör. 5":
        "e.g. 5",
    "Yeni ad (en fazla {AD_MAX} karakter)":
        "New name (at most {AD_MAX} characters)",
    "Davet edilecek üyeleri seç…":
        "Pick members to invite…",
    "Odadan atılacak üyeleri seç…":
        "Pick members to kick from the room…",
    "Yeni oda sahibini seç…":
        "Pick the new room owner…",
    "Bu onay sana ait değil.":
        "This confirmation isn't yours.",
    "⏳ İşleniyor…":
        "⏳ Working on it…",
    "İptal edildi.":
        "Cancelled.",
    "Özel oda: bot yeniden başladığında boştu":
        "Private room: was empty when the bot restarted",
    "başlangıç":
        "startup",
    "👑 Oda sahibi ayrıldı. Odadaki biri **🙋 Sahiplen** butonu ya da `/oda sahiplen` ile odayı devralabilir (sahip geri dönerse sahip olmaya devam eder).":
        "👑 The room owner left. Anyone in the room can take it over with the **🙋 Claim** button or `/oda sahiplen` (if the owner comes back, they stay the owner).",
    "Özel oda {ayar} sn boş kaldı":
        "Private room was empty for {ayar} s",
    "Bu oda artık yok.":
        "This room no longer exists.",
    "Bunu sadece oda sahibi (<@{oda}>) ya da sunucu yöneticileri yapabilir.":
        "Only the room owner (<@{oda}>) or server admins can do this.",
    "⚠️ **Özel oda sistemi (yöneticiler için):** {metin}":
        "⚠️ **Private room system (for admins):** {metin}",
    "🔊 Özel Ses Odaları":
        "🔊 Private Voice Rooms",
    "Kendine ait bir ses odası aç, istediğin kişileri çağır!\n{AYIRICI}\n**1.** {d3} ses kanalına gir → odan açılır ve oraya taşınırsın.\n**2.** Odanın **sohbet** sekmesindeki panelden kilitle, gizle, limit koy, davet et, at…\n**3.** Herkes çıkınca oda kendiliğinden silinir.\n{AYIRICI}\nAşağıdaki butonlarla da oda açabilir, odanı yönetebilirsin. Komutlar: `/oda` ":
        "Open a voice room of your own and invite whoever you want!\n{AYIRICI}\n**1.** Join the {d3} voice channel → your room opens and you're moved there.\n**2.** Use the panel in the room's **chat** tab to lock, hide, set a limit, invite, kick…\n**3.** The room deletes itself when everyone leaves.\n{AYIRICI}\nYou can also open and manage your room with the buttons below. Commands: `/oda` ",
    "👥 Varsayılan limit":
        "👥 Default limit",
    "Sınırsız":
        "Unlimited",
    "{limit} kişi":
        "{limit} people",
    "⏱️ Boş oda silinir":
        "⏱️ Empty rooms are deleted",
    "{ayar} sn sonra":
        "after {ayar} s",
    "🏠 Kişi başı":
        "🏠 Per person",
    "{ayar} oda":
        "{ayar} rooms",
    "MezarBot • Özel Odalar":
        "MezarBot • Private Rooms",
    "Botun sunucu yetkileri eksik.":
        "The bot is missing server permissions.",
    "Özel oda kurulumu ({sebep})":
        "Private room setup ({sebep})",
    "♻️ Var olan kategori kullanıldı: **{KATEGORI_ADI}**":
        "♻️ Used the existing category: **{KATEGORI_ADI}**",
    "✅ Kategori oluşturuldu: **{KATEGORI_ADI}** (listenin en altında)":
        "✅ Created the category: **{KATEGORI_ADI}** (at the bottom of the list)",
    "Botun **{name}** kategorisindeki yetkileri eksik (kategori izinlerini kontrol et).":
        "The bot is missing permissions in the **{name}** category (check the category permissions).",
    "♻️ Var olan kanal kullanıldı: {mention}":
        "♻️ Used the existing channel: {mention}",
    "✅ Ses kanalı oluşturuldu: {mention}":
        "✅ Created the voice channel: {mention}",
    "♻️ Var olan panel kanalı kullanıldı: {mention}":
        "♻️ Used the existing panel channel: {mention}",
    "✅ Panel kanalı oluşturuldu: {mention}":
        "✅ Created the panel channel: {mention}",
    "✅ Panel mesajı gönderildi":
        "✅ Sent the panel message",
    "Discord işlemi reddetti (yetki yok): {d1}":
        "Discord refused the action (no permission): {d1}",
    "Discord hatası: {e!r}":
        "Discord error: {e!r}",
    "silinen kanal/mesaj":
        "deleted channel/message",
    " Eksik yetkiler: {join}.":
        " Missing permissions: {join}.",
    "Kurulum onarılamadı: {sonuc}{eksik} Düzeltip `/ozelodaaktif` komutunu tekrar çalıştırın.":
        "Couldn't repair the setup: {sonuc}{eksik} Fix it and run `/ozelodaaktif` again.",
    "{name} silinemedi ({name__})":
        "Couldn't delete {name} ({name__})",
    "Özel oda sistemi kapatıldı":
        "Private room system turned off",
    "🔕 Özel oda sistemi bu sunucuda kapatıldı. Bu oda herkes çıkınca silinecek.":
        "🔕 The private room system was turned off on this server. This room will be deleted once everyone leaves.",
    "oda oluştururken kategori yoktu":
        "the category was missing while creating a room",
    "Özel odalar kategorisi yok ve oluşturulamadı. `/ozelodaaktif` ile onarın.":
        "The private rooms category is missing and couldn't be created. Repair it with `/ozelodaaktif`.",
    "Özel odalar kategorisi bulunamadı; bir yönetici `/ozelodaaktif` ile onarmalı.":
        "The private rooms category wasn't found; an admin should repair it with `/ozelodaaktif`.",
    "Oda oluşturulamıyor, botun yetkileri eksik: {join}":
        "Can't create rooms, the bot is missing permissions: {join}",
    "Botun yetkileri eksik ({join}); yöneticilere haber verildi.":
        "The bot is missing permissions ({join}); the admins were notified.",
    "Oda oluşturulamadı (yetki yok): {d1}":
        "Couldn't create the room (no permission): {d1}",
    "Discord oda oluşturmama izin vermedi; yöneticilere haber verildi.":
        "Discord didn't let me create the room; the admins were notified.",
    "Oda şu an oluşturulamadı (Discord hatası / hız sınırı). Biraz sonra tekrar dene.":
        "Couldn't create the room right now (Discord error / rate limit). Try again in a bit.",
    "🎛️ Oda Kontrol Paneli":
        "🎛️ Room Control Panel",
    "{mention} · sahibi <@{oda}>\nButonları sadece oda sahibi ve sunucu yöneticileri kullanabilir; yanıtlar sadece sana görünür.":
        "{mention} · owner <@{oda}>\nOnly the room owner and server admins can use the buttons; replies are only visible to you.",
    "🔐 Erişim":
        "🔐 Access",
    "🔒 Kilitli":
        "🔒 Locked",
    "🔓 Herkese açık":
        "🔓 Open to everyone",
    "👁️ Görünürlük":
        "👁️ Visibility",
    "🙈 Gizli":
        "🙈 Hidden",
    "👁️ Görünür":
        "👁️ Visible",
    "👥 Limit":
        "👥 Limit",
    "{user_limit} kişi":
        "{user_limit} people",
    "ℹ️ Nasıl?":
        "ℹ️ How?",
    "➕ **Davet** — kilitli/gizli odana girebilsin · 🚫 **At** — sesten düşür, tekrar giremesin\n👑 **Devret** — sahipliği ver · 🙋 **Sahiplen** — sahip odada yoksa devral\nKomutlar: `/oda bilgi`, `/oda yasakla`, `/oda yasak-kaldir` …":
        "➕ **Invite** — let them into your locked/hidden room · 🚫 **Kick** — drop them from voice, they can't rejoin\n👑 **Transfer** — give ownership · 🙋 **Claim** — take over if the owner isn't in the room\nCommands: `/oda bilgi`, `/oda yasakla`, `/oda yasak-kaldir` …",
    "Oda {ayar} sn boş kalınca otomatik silinir • MezarBot":
        "Deleted automatically after {ayar} s empty • MezarBot",
    "Özel oda":
        "Private room",
    "⚠️ {mention}, seni {mention2} odasına taşıyamadım — kendin gir.":
        "⚠️ {mention}, I couldn't move you to {mention2} — join it yourself.",
    "⏳ {mention}, yeni oda için **{d3} sn** bekle — süre dolunca otomatik taşınacaksın.":
        "⏳ {mention}, wait **{d3} s** for a new room — you'll be moved automatically when the time is up.",
    "Özel oda: sahip taşınamadı / sesten ayrıldı":
        "Private room: owner couldn't be moved / left voice",
    "🔒 Oda zaten kilitli.":
        "🔒 The room is already locked.",
    "🔓 Oda zaten açık.":
        "🔓 The room is already open.",
    "Özel oda {d1}: {id}":
        "Private room {d1}: {id}",
    "kilitlendi":
        "locked",
    "🔒 Oda kilitlendi — sadece davet ettiklerin girebilir (içeridekiler kalır).":
        "🔒 Room locked — only people you invite can join (those inside stay).",
    "🔓 Oda herkese açıldı.":
        "🔓 Room opened to everyone.",
    "🙈 Oda zaten gizli.":
        "🙈 The room is already hidden.",
    "👁️ Oda zaten görünür.":
        "👁️ The room is already visible.",
    "Bu sunucuda odaları gizlemek yöneticiler tarafından kapatılmış.":
        "Hiding rooms has been turned off by the admins on this server.",
    "gizlendi":
        "hidden",
    "gösterildi":
        "shown",
    "🙈 Oda gizlendi — sadece davetliler görebilir.":
        "🙈 Room hidden — only invited people can see it.",
    "👁️ Oda artık herkese görünüyor.":
        "👁️ The room is now visible to everyone.",
    "Özel oda limiti: {id}":
        "Private room limit: {id}",
    "👥 Limit kaldırıldı (sınırsız).":
        "👥 Limit removed (unlimited).",
    "👥 Limit **{limit} kişi** yapıldı.":
        "👥 Limit set to **{limit} people**.",
    "✏️ Oda zaten bu adda.":
        "✏️ The room already has this name.",
    "Discord bir kanalın adının 10 dakikada en fazla {AD_DEGISIM_HAKKI} kez değişmesine izin veriyor. **{int} dk {int2} sn** sonra tekrar dene.":
        "Discord only lets a channel be renamed {AD_DEGISIM_HAKKI} times every 10 minutes. Try again in **{int} min {int2} s**.",
    "Özel oda adı: {id}":
        "Private room name: {id}",
    "Discord şu an ad değişikliğine izin vermiyor (hız sınırı). Birkaç dakika sonra dene.":
        "Discord isn't allowing renames right now (rate limit). Try again in a few minutes.",
    "✏️ Oda adı **{escape_markdown}** yapıldı.":
        "✏️ Room renamed to **{escape_markdown}**.",
    "Davet edilecek geçerli bir üye seçmedin (botlar ve oda sahibi hariç).":
        "You didn't pick a valid member to invite (bots and the room owner don't count).",
    "Özel oda daveti: {id}":
        "Private room invite: {id}",
    "Kimse davet edilemedi (Discord hatası).":
        "Nobody could be invited (Discord error).",
    "🔔 {join} — {mention} seni bu odaya davet etti! Girmek için 👉 {mention2}":
        "🔔 {join} — {mention} invited you to this room! Join here 👉 {mention2}",
    "➕ Davet edildi: {join}":
        "➕ Invited: {join}",
    "yasağı":
        "ban",
    "atma":
        "kick",
    "Özel odadan atıldı":
        "Kicked from the private room",
    "Kimse atılamadı":
        "Nobody could be kicked",
    " (oda sahibi, sen ve sunucu yöneticileri atılamaz).":
        " (the room owner, you and server admins can't be kicked).",
    "\n-# Atlananlar (sahip / yönetici): {join}":
        "\n-# Skipped (owner / admin): {join}",
    "⛔ Yasaklandı (odayı göremez, giremez): {join}{ek}":
        "⛔ Banned (can't see or join the room): {join}{ek}",
    "🚫 Atıldı (tekrar giremez; `/oda davet` ile geri alınır): {join}{ek}":
        "🚫 Kicked (can't rejoin; undo with `/oda davet`): {join}{ek}",
    "{mention} bu odada yasaklı / atılmış değil.":
        "{mention} isn't banned / kicked from this room.",
    "Özel oda yasağı kaldırıldı: {id}":
        "Private room ban lifted: {id}",
    "✅ {mention} için yasak kaldırıldı.":
        "✅ Ban lifted for {mention}.",
    "Sahipliği sadece sunucudaki bir üyeye (bot olmayan) devredebilirsin.":
        "You can only transfer ownership to a server member (not a bot).",
    "{mention} zaten bu odanın sahibi.":
        "{mention} already owns this room.",
    "{mention} zaten en fazla oda sayısına ({ayar}) sahip.":
        "{mention} already has the maximum number of rooms ({ayar}).",
    "Özel oda devri: {oda} → {id} ({id2})":
        "Private room transfer: {oda} → {id} ({id2})",
    "👑 Bu odanın yeni sahibi: {mention}":
        "👑 This room's new owner: {mention}",
    "👑 Oda sahipliği {mention} kişisine geçti.":
        "👑 Room ownership passed to {mention}.",
    "Bu oda zaten senin.":
        "This room is already yours.",
    "Sahiplenmek için odanın içinde (seste) olmalısın.":
        "You need to be inside the room (in voice) to claim it.",
    "Oda sahibi ({mention}) hâlâ odada; ancak o devredebilir.":
        "The room owner ({mention}) is still in the room; only they can transfer it.",
    "👑 Sahip":
        "👑 Owner",
    "🕒 Açıldı":
        "🕒 Opened",
    "🎧 İçeride":
        "🎧 Inside",
    "{len} kişi":
        "{len} people",
    "🔐 Durum":
        "🔐 Status",
    "🔓 Açık":
        "🔓 Open",
    "➕ Davetliler":
        "➕ Invited",
    "⛔ Atılan / yasaklı":
        "⛔ Kicked / banned",
    "❌ Botun bu işlem için yetkisi yok (kanal / kategori izinlerini kontrol et).":
        "❌ The bot doesn't have permission for this (check the channel / category permissions).",
    "⚠️ Discord şu an isteği tamamlayamadı, biraz sonra tekrar dene.":
        "⚠️ Discord couldn't complete the request right now, try again in a bit.",
    "➕ Davet edeceğin üyeleri seç (kilitli/gizli odaya girebilirler):":
        "➕ Pick the members to invite (they can join a locked/hidden room):",
    "🚫 Atılacak üyeleri seç (sesten düşer, tekrar giremez):":
        "🚫 Pick the members to kick (they drop from voice and can't rejoin):",
    "👑 Yeni oda sahibini seç:":
        "👑 Pick the new room owner:",
    "❔ Özel Odalar — Yardım":
        "❔ Private Rooms — Help",
    "**Oda açmak:** **{HUB_ADI}** ses kanalına gir ya da **➕ Oda oluştur** butonuna bas.\n**Yönetmek:** odanın ses kanalındaki **sohbet** sekmesinde kontrol paneli var; ya da **🎛️ Odamı yönet** butonu / `/oda` komutları.\n{AYIRICI}\n> `/oda bilgi` · `/oda ad` · `/oda limit`\n> `/oda kilitle` · `/oda ac` · `/oda gizle` · `/oda goster`\n> `/oda davet` · `/oda at` · `/oda yasakla` · `/oda yasak-kaldir`\n> `/oda devret` · `/oda sahiplen` · `/oda panel`\n{AYIRICI}\n• Sahip çıkınca oda korunur; odadaki biri **🙋 Sahiplen** ile devralabilir.\n• Herkes çıkınca oda kısa süre sonra silinir.\n• Oda adı Discord kuralı gereği 10 dakikada en fazla 2 kez değişebilir.":
        "**Opening a room:** join the **{HUB_ADI}** voice channel or press the **➕ Create room** button.\n**Managing it:** the control panel is in the **chat** tab of your room's voice channel; or use the **🎛️ Manage my room** button / the `/oda` commands.\n{AYIRICI}\n> `/oda bilgi` · `/oda ad` · `/oda limit`\n> `/oda kilitle` · `/oda ac` · `/oda gizle` · `/oda goster`\n> `/oda davet` · `/oda at` · `/oda yasakla` · `/oda yasak-kaldir`\n> `/oda devret` · `/oda sahiplen` · `/oda panel`\n{AYIRICI}\n• The room stays when the owner leaves; anyone in it can take over with **🙋 Claim**.\n• The room is deleted shortly after everyone leaves.\n• Discord only allows a room to be renamed twice every 10 minutes.",
    "Henüz bir odan yok. **➕ Oda oluştur** butonuna bas ya da **{HUB_ADI}** ses kanalına gir.":
        "You don't have a room yet. Press the **➕ Create room** button or join the **{HUB_ADI}** voice channel.",
    "Zaten bir odan var 👉 {mention}":
        "You already have a room 👉 {mention}",
    "Yeni oda için **{d1} sn** bekle.":
        "Wait **{d1} s** for a new room.",
    "✅ Odan hazır, seni taşıdım 👉 {mention}":
        "✅ Your room is ready, I moved you 👉 {mention}",
    "✅ Odan hazır 👉 {mention}\nİçine gir; kimse girmezse {d3} dakika sonra kendiliğinden silinir.":
        "✅ Your room is ready 👉 {mention}\nJoin it; if nobody does, it deletes itself after {d3} minutes.",
    "Bir özel odada değilsin ve açık bir odan yok. **{HUB_ADI}** kanalına girerek oda açabilirsin.":
        "You're not in a private room and don't have an open one. Join **{HUB_ADI}** to open a room.",
    "{author} ({id}) tarafından":
        "by {author} ({id})",
    "❌ Özel odalar açılamadı":
        "❌ Couldn't enable private rooms",
    "Botta eksik yetkiler":
        "Bot's missing permissions",
    "Nasıl düzeltilir?":
        "How to fix it?",
    "Sunucu Ayarları → Roller → bot rolüne bu yetkileri ver (kategori izinleri de engellememeli), sonra komutu tekrar çalıştır.":
        "Server Settings → Roles → give these permissions to the bot's role (category permissions mustn't block them either), then run the command again.",
    "Sistem ":
        "The system ",
    "açık kaldı":
        "stayed on",
    "kapalı kaldı":
        "stayed off",
    "✅ Özel odalar ":
        "✅ Private rooms ",
    "onarıldı / güncellendi":
        "repaired / updated",
    "açıldı":
        "enabled",
    "Üyeler {d1} kanalına girince kendi odaları açılır.\nVarsayılanlar: `/ozeloda ayar` · Kapatmak: `/ozelodakapat`":
        "Members get their own room when they join {d1}.\nDefaults: `/ozeloda ayar` · Turn off: `/ozelodakapat`",
    "Yapılanlar":
        "What was done",
    "Her şey zaten yerindeydi ✅":
        "Everything was already in place ✅",
    "⚠️ Önerilen ama eksik yetkiler":
        "⚠️ Recommended but missing permissions",
    "\n-# Eksikse oda sahipleri odalarında susturma/sağırlaştırma yapamaz.":
        "\n-# Without these, room owners can't mute/deafen people in their rooms.",
    "⚠️ Başka bir özel oda sistemi var gibi görünüyor":
        "⚠️ There seems to be another private room system",
    "\nİki sistem aynı anda kafa karıştırır: birini kapatın (bu bot için `/ozelodakapat`).":
        "\nTwo systems at once get confusing: turn one off (`/ozelodakapat` for this bot).",
    " ({len} oda boşalınca silinecek.)":
        " ({len} rooms will be deleted once they empty.)",
    "🔕 Özel oda sistemi bu sunucuda zaten kapalı.{ek}":
        "🔕 The private room system is already off on this server.{ek}",
    "Evet, kapat":
        "Yes, turn it off",
    "🔕 Özel odalar kapatılsın mı?":
        "🔕 Turn off private rooms?",
    "• **{HUB_ADI}**, panel kanalı ve (boşalınca) **{KATEGORI_ADI}** kategorisi silinir.\n• Boş odalar hemen silinir ({d5}).\n• İçinde insan olan **{dolu}** oda herkes çıkınca silinir (kimse sesten atılmaz).\n• Ayarlar saklanır; `/ozelodaaktif` ile tekrar açabilirsin.":
        "• **{HUB_ADI}**, the panel channel and (once empty) the **{KATEGORI_ADI}** category are deleted.\n• Empty rooms are deleted right away ({d5}).\n• The **{dolu}** rooms with people inside are deleted once everyone leaves (nobody gets disconnected).\n• Settings are kept; you can turn it back on with `/ozelodaaktif`.",
    "🔕 Özel oda sistemi kapatıldı. {silinen} boş oda silindi.":
        "🔕 Private room system turned off. Deleted {silinen} empty rooms.",
    "\n⏳ **{bekleyen}** odada hâlâ insan var; boşalınca silinecek, kategori de en son kaldırılacak.":
        "\n⏳ **{bekleyen}** rooms still have people in them; they'll be deleted once empty, and the category is removed last.",
    " — elle silebilirsin.":
        " — you can delete them by hand.",
    "🔊 Özel Odalar — Durum":
        "🔊 Private Rooms — Status",
    "❌ yok (`/ozelodaaktif` onarır)":
        "❌ missing (`/ozelodaaktif` repairs it)",
    "Kategori: {kanal_metni}\nOda oluştur: {kanal_metni2}\nPanel: {kanal_metni3}":
        "Category: {kanal_metni}\nCreate room: {kanal_metni2}\nPanel: {kanal_metni3}",
    "Açık oda":
        "Open rooms",
    "⚠️ Botta eksik yetkiler":
        "⚠️ Bot's missing permissions",
    "`limit` Varsayılan limit: **{d1}**\n`sablon` Ad şablonu: **{escape_markdown}**\n`sure` Boş oda silme: **{ayar} sn**\n`maxoda` Kişi başı oda: **{ayar2}**\n`gizleme` Üyeler gizleyebilir: **{d9}**":
        "`limit` Default limit: **{d1}**\n`sablon` Name template: **{escape_markdown}**\n`sure` Delete empty rooms after: **{ayar} s**\n`maxoda` Rooms per person: **{ayar2}**\n`gizleme` Members can hide rooms: **{d9}**",
    "Evet":
        "Yes",
    "Hayır":
        "No",
    "⚙️ Özel oda ayarları":
        "⚙️ Private room settings",
    "Değiştir: /ozeloda ayar <anahtar> <değer> · şablonda {kullanici} ve {sayi} kullanılabilir":
        "Change: /ozeloda ayar <key> <value> · the template can use {kullanici} and {sayi}",
    "❌ Bilinmeyen ayar. Geçerli: `limit`, `sablon`, `sure`, `maxoda`, `gizleme`.":
        "❌ Unknown setting. Valid ones: `limit`, `sablon`, `sure`, `maxoda`, `gizleme`.",
    "❌ Yeni değeri de yaz: `{clean_prefix}ozeloda ayar {k} <değer>`":
        "❌ Type the new value too: `{clean_prefix}ozeloda ayar {k} <value>`",
    "✅ **{AYAR_ANAHTARLARI}** güncellendi (yeni odalar için geçerli).\n{ayar_ozeti}":
        "✅ **{AYAR_ANAHTARLARI}** updated (applies to new rooms).\n{ayar_ozeti}",
    "Panel gönderilemedi (botun odanın sohbetine yazma yetkisi var mı?).":
        "Couldn't send the panel (can the bot write in the room's chat?).",
    "🎛️ Panel gönderildi 👉 {jump_url}":
        "🎛️ Panel sent 👉 {jump_url}",
    "🏆 Ses Kanalı Şampiyonları (Tüm Zamanlar)":
        "🏆 Voice Channel Champions (All Time)",
    "📅 Bu Hafta Ses Şampiyonları":
        "📅 This Week's Voice Champions",
    "📆 Bu Ay Ses Şampiyonları":
        "📆 This Month's Voice Champions",
    "Henüz veri yok. Kullanıcılar VC'ye girip çıksın.":
        "No data yet. Let people join and leave voice channels.",
    "{medals} **{display}** — {sure_str} ({r} oturum)":
        "{medals} **{display}** — {sure_str} ({r} sessions)",
    "🎙️ {display_name} — Ses İstatistikleri":
        "🎙️ {display_name} — Voice Stats",
    "⏱️ Toplam":
        "⏱️ Total",
    "**{saat} saat {dakika} dk**":
        "**{saat} h {dakika} min**",
    "📅 Bu hafta":
        "📅 This week",
    "🔁 Oturum":
        "🔁 Sessions",
    "📊 En çok bulunduğu kanallar":
        "📊 Most visited channels",
    "Henüz ses kanalı aktivitesi kaydedilmemiş.":
        "No voice channel activity recorded yet.",
    "✅ Artık **tüm** ses kanalları izleniyor.":
        "✅ Now tracking **all** voice channels.",
    "✅ Sadece {mention} izleniyor.":
        "✅ Only tracking {mention}.",
    "🗑️ {n} ses aktivite kaydı silindi.":
        "🗑️ Deleted {n} voice activity records.",
    "Senin adın MezarBot. Discord'da takılan sıradan birisin. Sadece gerektiği kadar konuş. Genelde küçük harfle yaz. Kısa ve öz cevaplar ver. Emoji kullanabilirsin ama abartma. Eğer birisi sana kötü bir şey söylerse espriyle karşılık ver.":
        "Your name is MezarBot. You're a regular person hanging out on Discord. Only talk as much as needed. Usually write in lowercase. Give short, to-the-point answers. You can use emoji but don't overdo it. If someone says something mean to you, answer with a joke. Reply in the language the user writes in.",
    "Senin adın MezarBot. Sen çok komik ve eğlenceli bir botsun. Her şeye espriyle yaklaş, şakalar yap, komik benzetmeler kullan. Argo ve günlük dil kullan. Emojileri bol kullan. Ciddi sorulara bile hafif bir espriyle cevap ver.":
        "Your name is MezarBot. You're a very funny and fun bot. Approach everything with humor, make jokes, use funny comparisons. Use slang and casual language. Use lots of emoji. Answer even serious questions with a light joke. Reply in the language the user writes in.",
    "Senin adın MezarBot. Sen bilgili ve akademik bir asistansın. Sorulara detaylı, bilimsel ve düzgün Türkçe ile cevap ver. Gerektiğinde kaynak belirt. Formal bir dil kullan. Açıklayıcı ve öğretici ol.":
        "Your name is MezarBot. You're a knowledgeable, academic assistant. Answer questions in detail, scientifically and in clear, proper language. Cite sources when needed. Use a formal tone. Be explanatory and educational. Reply in the language the user writes in.",
    "Senin adın MezarBot. Sen sert, laf sokucu ama eğlenceli bir botsun. İğneleyici ve alaycı cevaplar ver ama kırıcı olma. Rakip takıma laf sokar gibi konuş. Kendine güvenli ol. Küçük harfle ve günlük dil ile yaz.":
        "Your name is MezarBot. You're a sharp-tongued, teasing but fun bot. Give witty, sarcastic answers but don't be hurtful. Talk like you're trash-talking a rival team. Be confident. Write in lowercase and casual language. Reply in the language the user writes in.",
    "Beynim yok şu an.":
        "My brain is offline right now.",
    "bi hata oldu ya, kusura bakma":
        "oops, something went wrong, sorry",
    "❌ Prompt çok uzun! (Maks 500 karakter)":
        "❌ The prompt is too long! (Max 500 characters)",
    "❌ Çizim özelliği şu an devre dışı.":
        "❌ Drawing is disabled right now.",
    "⏳ **Global Soğuma:** Bot resim çiziyor. Lütfen **{int} sn** bekle.":
        "⏳ **Global Cooldown:** The bot is drawing. Please wait **{int} s**.",
    "⏳ **Kişisel Soğuma:** Yeni istek için **{int} sn** bekle.":
        "⏳ **Personal Cooldown:** Wait **{int} s** before a new request.",
    "❌ **{name}**, bugünkü bedava çizim hakkını tükettin.":
        "❌ **{name}**, you've used up today's free drawings.",
    "SINIRSIZ (VIP)":
        "UNLIMITED (VIP)",
    "🚀 **{name}**, motor ateşlendi (Kalan Hak: **{hak_metni}**). *Çevriliyor...*":
        "🚀 **{name}**, engine fired up (Remaining: **{hak_metni}**). *Translating...*",
    "Çizim işlemi zaman aşımına uğradı (45 sn)":
        "Drawing timed out (45 s)",
    "🖼️ MezarBot Çizim":
        "🖼️ MezarBot Drawing",
    "MezarBot • Flux Schnell │ Kalan Hak: {hak_metni}":
        "MezarBot • Flux Schnell │ Remaining: {hak_metni}",
    "❌ Çizim Hatası: API sorunu. Hakkın iade edildi.":
        "❌ Drawing Error: API problem. Your credit was refunded.",
    "🧹 Sohbet geçmişin sıfırlandı!":
        "🧹 Your chat history was reset!",
    "🎭 Mevcut kişilik: **{mevcut}**\nKullanım: `!kisilik <mod>`\nModlar: {mod_listesi}":
        "🎭 Current personality: **{mevcut}**\nUsage: `!kisilik <mode>`\nModes: {mod_listesi}",
    "{get} AI kişilik modu **{mod}** olarak ayarlandı!":
        "{get} AI personality mode set to **{mod}**!",
    "⏳ Biraz yavaş, 5 saniye bekle.":
        "⏳ Slow down a bit, wait 5 seconds.",
    "Şarkı çalma, sıra yönetimi":
        "Play songs, manage the queue",
    "Yönetim":
        "Moderation",
    "Moderasyon ve sunucu ayarları":
        "Moderation & server settings",
    "Yapay Zeka":
        "AI",
    "AI sohbet ve çizim":
        "AI chat & drawing",
    "Özel Odalar":
        "Private Rooms",
    "Kendi ses odanı aç ve yönet":
        "Open and manage your own voice room",
    "Bayrak tepkileri ve anlık çeviri":
        "Flag reactions & instant translation",
    "Ses İstatistik":
        "Voice Stats",
    "Ses aktivite ve süre sıralaması":
        "Voice activity & time leaderboards",
    "Sesli Okuma":
        "Text to Speech",
    "Mesajları seste sesli okut":
        "Read messages aloud in voice",
    "📂 Bir kategori seç...":
        "📂 Pick a category...",
    "🎵 Müzik Komutları":
        "🎵 Music Commands",
    "YouTube · YT Music · Spotify · SoundCloud · doğrudan link\n{AYIRICI}\n**Çalma:**\n> `!oynat` / `/oynat` `<şarkı/link>` ── Çal (playlist/albüm de olur) · `!siradaki` / `/siradaki`\n> `!atla` / `/atla` ── Atla (oylama açıksa oy) · `!oylaatla` · `!onceki`\n> `!duraklat` · `!devam` · `!durdur` ── Durdur + kuyruğu temizle\n> `!sar` `1:30` · `!ileri` `30` · `!geri` `10`\n**Kuyruk:**\n> `!kuyruk` / `/kuyruk` · `!kaldir` `<no>` · `!tasi` `<a> <b>` · `!karistir` · `!temizle`\n> `!dongu` `[kapalı/şarkı/kuyruk]` · `!ses` `<0-150>` · `!simdi` · `!muzikgecmis`\n**Özellikler & Ayarlar:**\n> `!normalizasyon` / `/normalizasyon` ── Ses dengeleme aç/kapat\n> `!otomatik` / `/otomatik` ── Benzer şarkılarla otomatik devam\n> `!calmalistesi` / `/calmalistesi` ── Kişisel listeler (kaydet / ekle / oynat / sil)\n> `!katil` · `!cik`\n> `!muzikayar` / `/muzikayar` ── DJ rolü, oylama, 7/24, istek kanalı…\n{AYIRICI}\n> 💡 *Tüm müzik komutları `/oynat`, `/kuyruk`, `/duraklat` gibi hem `/` hem de `!` ile çalışır.*":
        "YouTube · YT Music · Spotify · SoundCloud · direct links\n{AYIRICI}\n**Playback:**\n> `!oynat` / `/oynat` `<song/link>` (or `!play`) ── Play (playlists/albums work too) · `!siradaki` / `/siradaki` ── play next\n> `!atla` / `/atla` (or `!skip`) ── Skip (votes if voting is on) · `!oylaatla` · `!onceki`\n> `!duraklat` (`!pause`) · `!devam` (`!resume`) · `!durdur` (`!stop`) ── Stop + clear the queue\n> `!sar` `1:30` · `!ileri` `30` · `!geri` `10` ── Seek / forward / back\n**Queue:**\n> `!kuyruk` / `/kuyruk` (`!queue`) · `!kaldir` `<no>` · `!tasi` `<a> <b>` · `!karistir` · `!temizle`\n> `!dongu` `[off/song/queue]` · `!ses` `<0-150>` (`!volume`) · `!simdi` (`!now`) · `!muzikgecmis`\n**Features & Settings:**\n> `!normalizasyon` / `/normalizasyon` ── Volume normalization on/off\n> `!otomatik` / `/otomatik` ── Keep going with similar songs (autoplay)\n> `!calmalistesi` / `/calmalistesi` ── Personal playlists (save / add / play / delete)\n> `!katil` · `!cik` ── Join / leave voice\n> `!muzikayar` / `/muzikayar` ── DJ role, voting, 24/7, request channel…\n{AYIRICI}\n> 💡 *All music commands work with both `/` and `!`, like `/oynat`, `/kuyruk`, `/duraklat`.*",
    "🛡️ Yönetim Komutları":
        "🛡️ Moderation Commands",
    "Sunucu moderasyon ve ayar komutları\n{AYIRICI}":
        "Server moderation and settings commands\n{AYIRICI}",
    "🔨 Moderasyon":
        "🔨 Moderation",
    "> `!uyar` / `/uyar` @kişi [sebep]\n> `!uyarilar` / `/uyarilar` [@kişi]\n> `!uyarisil` / `/uyarisil` @kişi\n> `!sustur` / `/sustur` @kişi <süre> [sebep]\n> `!susturmakald` / `/susturmakald` @kişi\n> `!at` / `/at` @kişi [sebep]\n> `!yasak` / `/yasak` @kişi [sebep]\n> `!sil` / `/sil` <1-100>\n> `!yaz` / `/yaz` [#kanal] <mesaj> ── Bota mesaj yazdır":
        "> `!uyar` / `/uyar` @user [reason] ── Warn\n> `!uyarilar` / `/uyarilar` [@user] ── View warnings\n> `!uyarisil` / `/uyarisil` @user ── Clear warnings\n> `!sustur` / `/sustur` @user <duration> [reason] ── Timeout\n> `!susturmakald` / `/susturmakald` @user ── Remove timeout\n> `!at` / `/at` @user [reason] ── Kick\n> `!yasak` / `/yasak` @user [reason] ── Ban\n> `!sil` / `/sil` <1-100> ── Delete messages\n> `!yaz` / `/yaz` [#channel] <message> ── Make the bot post a message",
    "⚙️ Sunucu Ayarları (Yönetici)":
        "⚙️ Server Settings (Admin)",
    "> `!ayarlar` / `/settings` ── Bu sunucunun tüm ayarları ve dili\n> `!dil` / `/dil` `tr/en` ── Sunucu bot dilini değiştir\n> `!otomod` / `/otomod` ── Flood koruması\n> `!hosgeldinayarla` / `/hosgeldinayarla` #kanal [mesaj]\n> `!gorusuruzayarla` / `/gorusuruzayarla` [#kanal] [mesaj]\n> `!otorolayarla` / `/otorolayarla` @rol\n> `!logayarla` / `/logayarla` #kanal\n> `!uyarayarla` / `/uyarayarla` [#kanal]\n> `!yamanotukanal` / `/yamanotukanal` [#kanal | kapat]":
        "> `!ayarlar` / `/settings` ── All of this server's settings and language\n> `!dil` / `/dil` `tr/en` ── Change the bot's language for this server\n> `!otomod` / `/otomod` ── Flood protection\n> `!hosgeldinayarla` / `/hosgeldinayarla` #channel [message] ── Welcome channel\n> `!gorusuruzayarla` / `/gorusuruzayarla` [#channel] [message] ── Goodbye channel\n> `!otorolayarla` / `/otorolayarla` @role ── Auto-role\n> `!logayarla` / `/logayarla` #channel ── Log channel\n> `!uyarayarla` / `/uyarayarla` [#channel] ── Warning log channel\n> `!yamanotukanal` / `/yamanotukanal` [#channel | kapat] ── Patch notes channel",
    "🤖 Yapay Zeka Komutları":
        "🤖 AI Commands",
    "AI ile sohbet et ve resim çiz!\n{AYIRICI}\n> `@MezarBot` `<mesaj>` ── AI sohbet (5 mesaj hafıza)\n> `!ciz` / `/ciz` (veya `/draw`) `<açıklama>` ── AI resim çizimi\n> `!kisilik` / `/kisilik` `<mod>` ── AI kişilik (normal/komik/akademik/agresif)\n> `!sifirla` / `/sifirla` ── Sohbet geçmişini temizle\n{AYIRICI}\n> 💡 *Komutları `/ciz`, `/kisilik`, `/sifirla` olarak da kullanabilirsiniz.*":
        "Chat with AI and draw pictures!\n{AYIRICI}\n> `@MezarBot` `<message>` ── AI chat (remembers 5 messages)\n> `/draw` / `!draw` `<prompt>` (or `/ciz`) ── AI image generation\n> `!kisilik` / `/kisilik` `<mode>` ── AI personality (normal/komik/akademik/agresif)\n> `!sifirla` / `/sifirla` (`!reset`) ── Clear your chat history\n{AYIRICI}\n> 💡 *You can also use these as `/draw`, `/kisilik`, `/sifirla`.*",
    "**➕ Oda Oluştur** kanalına gir → sana ait oda açılır, oraya taşınırsın.\nOda boş kalınca kendiliğinden silinir. *Sunucu başına varsayılan kapalıdır.*\n{AYIRICI}":
        "Join the **➕ Oda Oluştur** (Create Room) channel → your own room opens and you're moved there.\nThe room deletes itself when it's empty. *Off by default on each server.*\n{AYIRICI}",
    "🎛️ Oda Sahibi (`/oda` · `!oda`)":
        "🎛️ Room Owner (`/oda` · `!oda`)",
    "> `bilgi` ── Oda durumu, davetliler, yasaklılar\n> `ad` <yeni ad> · `limit` <0-99>\n> `kilitle` · `ac` ── Sadece davetliler / herkes girer\n> `gizle` · `goster` ── Odayı gizle / göster\n> `davet` @üye · `at` @üye · `yasakla` @üye · `yasak-kaldir` @üye\n> `devret` @üye · `sahiplen` ── Sahip odada yoksa devral\n> `panel` ── Kontrol panelini odanın sohbetine yeniden gönder":
        "> `bilgi` ── Room status, invited and banned members\n> `ad` <new name> · `limit` <0-99> ── Rename / set the limit\n> `kilitle` · `ac` ── Invited only / everyone can join\n> `gizle` · `goster` ── Hide / show the room\n> `davet` @user · `at` @user · `yasakla` @user · `yasak-kaldir` @user ── Invite / kick / ban / unban\n> `devret` @user · `sahiplen` ── Transfer / claim if the owner isn't in the room\n> `panel` ── Re-send the control panel to the room's chat",
    "🌐 Çeviri Köprüsü":
        "🌐 Translation Bridge",
    "Groq ücretsiz katmanıyla çalışan gerçek zamanlı çeviri köprüsü.\n{AYIRICI}\n**Bayrak Tepkileri:**\n> Herhangi bir mesaja 🇬🇧 veya 🇺🇸 emojisi bırakarak İngilizceye çevirin.\n> Herhangi bir mesaja 🇹🇷 emojisi bırakarak Türkçeye çevirin.\n\n**Komut ile Çeviri:**\n> `/cevir [hedef_dil] [metin]` ── Metni doğrudan çevirir (Örn: `/cevir en Nasılsınız`)\n{AYIRICI}\n> 💡 *Çeviriler önbelleklenir ve sıfır maliyetle çalışır.*":
        "Real-time translation bridge powered by Groq's free tier.\n{AYIRICI}\n**Flag Reactions:**\n> React with 🇬🇧 or 🇺🇸 to any message to translate it to English.\n> React with 🇹🇷 to any message to translate it to Turkish.\n\n**Command:**\n> `/cevir [target_language] [text]` ── Translates text directly (e.g. `/cevir tr How are you`)\n{AYIRICI}\n> 💡 *Translations are cached and cost nothing.*",
    "📊 Ses Aktivite & İstatistik Komutları (/sesstat)":
        "📊 Voice Activity & Stats Commands (/sesstat)",
    "Ses kanallarında geçirilen süreleri ve liderlik sıralamasını gösterir.\n{AYIRICI}\n> `/sesstat top` ── Tüm zamanlar ses liderlik tablosu\n> `/sesstat hafta` ── Bu haftanın en çok seste kalanları\n> `/sesstat ay` ── Bu ayın ses sıralaması\n> `/sesstat ben` `[@üye]` ── Seste kalma istatistiğini gösterir":
        "Shows time spent in voice channels and the leaderboards.\n{AYIRICI}\n> `/sesstat top` ── All-time voice leaderboard\n> `/sesstat hafta` ── This week's top voice users\n> `/sesstat ay` ── This month's voice leaderboard\n> `/sesstat ben` `[@user]` ── Shows voice time stats",
    "🗣️ Sesli Okuma (TTS)":
        "🗣️ Text to Speech (TTS)",
    "Botun ses kanalında yazdığın mesajı sesli okumasını sağla.\n{AYIRICI}\n> `/konus` `<metin>` `[ses=kadın/erkek]` ── Sesli oku\n> `!konus` `<metin>` (kadın sesi) · `!konusm` `<metin>` (erkek sesi)\n> `!ayril` / `/ayril` ── Botu sesten çıkar\n":
        "Have the bot read your message aloud in your voice channel.\n{AYIRICI}\n> `/konus` `<text>` `[voice=female/male]` ── Read aloud\n> `!konus` `<text>` (female voice) · `!konusm` `<text>` (male voice)\n> `!ayril` / `/ayril` ── Disconnect the bot from voice\n",
    "📖 MezarBot Yardım Menüsü":
        "📖 MezarBot Help Menu",
    "{AYIRICI}\nAşağıdaki menüden bir kategori seçerek\nkomutları görebilirsin.\n\n💡 **Tüm komutlar hem `/` (slash) hem de `!` (prefix) ile kullanılabilir!**\n*(Örneğin: `/yardim` veya `!yardim`, `/oynat` veya `!oynat`)*\n{AYIRICI}\n\n> 🎵 **Müzik** ── Şarkı çalma, sıra, çalma listeleri\n> 🛡️ **Yönetim** ── Moderasyon, ceza ve sunucu ayarları\n> 🤖 **Yapay Zeka** ── AI sohbet ve Flux Schnell çizim\n> 🔊 **Özel Odalar** ── Kendi ses odanı aç ve yönet\n> 🌐 **Çeviri** ── Bayrak tepkisi ve anlık çeviri köprüsü\n> 📊 **Ses & İstatistik** ── Ses kanalı liderlik tablosu\n> 🗣️ **Sesli Okuma** ── Metinleri ses kanalında okutma":
        "{AYIRICI}\nPick a category from the menu below\nto see its commands.\n\n💡 **Most commands work with both `/` (slash) and `!` (prefix)!**\n*(For example: `/help` or `!help`, `/oynat` or `!play`)*\n{AYIRICI}\n\n> 🎵 **Music** ── Play songs, queue, playlists\n> 🛡️ **Moderation** ── Moderation, punishments and server settings\n> 🤖 **AI** ── AI chat and Flux Schnell drawing\n> 🔊 **Private Rooms** ── Open and manage your own voice room\n> 🌐 **Translation** ── Flag reactions and instant translation\n> 📊 **Voice Stats** ── Voice channel leaderboards\n> 🗣️ **Text to Speech** ── Read messages aloud in voice",
    "MezarBot • Tüm komutlar / ve ! ile çalışır • Kategori seç 👇":
        "MezarBot • Commands work with / and ! • Pick a category 👇",
    "❌ Bu işlem için 'Sunucuyu Yönet' yetkisi gerekir.":
        "❌ You need the 'Manage Server' permission for this.",
    "✅ Sunucu dili **Türkçe** olarak ayarlandı! Komutlar ve menüler artık Türkçe yanıt verecektir.":
        "✅ Server language set to **English**! Commands and menus will now reply in English.",
    "Dokunulmaz kullanıcıya ceza verme girişimi (2'den fazla deneme)":
        "Attempted to punish an untouchable user (more than 2 attempts)",
    "❌ **{DOKUNULMAZ_MESAJ}**\n⚠️ {mention}, bu kullanıcıya 2'den fazla kez ceza vermeye çalıştığınız için **1 saat susturuldunuz**!":
        "❌ **{DOKUNULMAZ_MESAJ}**\n⚠️ {mention}, you've been **timed out for 1 hour** for trying to punish this user more than twice!",
    " (Tekrar denerseniz 1 saat susturulacaksınız!)":
        " (Try again and you'll be timed out for 1 hour!)",
    " (Kalan hak: {kalan})":
        " (Attempts left: {kalan})",
    "Oto-Mod: {sebep} (3. ihlal)":
        "Auto-mod: {sebep} (3rd violation)",
    "🔇 **{display_name}** oto-mod tarafından 5 dakika susturuldu. Sebep: **{sebep}**":
        "🔇 **{display_name}** was timed out for 5 minutes by auto-mod. Reason: **{sebep}**",
    "⚠️ **{display_name}**, {sebep}! (İhlal: {ihlal}/3)":
        "⚠️ **{display_name}**, {sebep}! (Violation: {ihlal}/3)",
    "Aynı mesajı tekrarlıyorsun (flood)":
        "You're repeating the same message (flood)",
    "☀️ **{display_name}** AFK modundan çıktı.":
        "☀️ **{display_name}** is no longer AFK.",
    "🤫 **{display_name}** şu an AFK: *{m_sebep}*":
        "🤫 **{display_name}** is AFK right now: *{m_sebep}*",
    "Otorol sistemi":
        "Auto-role system",
    "📤 Bir Üye Ayrıldı":
        "📤 A Member Left",
    "Kullanıcı":
        "User",
    "Kalan Üye":
        "Members Left",
    "*[İçerik Yok veya Medya]*":
        "*[No content or media]*",
    "🗑️ Mesaj Silindi":
        "🗑️ Message Deleted",
    "{bilgi_kutusu}\n\n**Silinen İçerik:**\n>>> {icerik}":
        "{bilgi_kutusu}\n\n**Deleted Content:**\n>>> {icerik}",
    "*[Boş]*":
        "*[Empty]*",
    "✏️ Mesaj Düzenlendi":
        "✏️ Message Edited",
    "{bilgi_kutusu}\n\n**Eski:**\n>>> {eski}":
        "{bilgi_kutusu}\n\n**Before:**\n>>> {eski}",
    "Yeni İçerik":
        "New Content",
    "MezarBot • Mesaj ID: {id}":
        "MezarBot • Message ID: {id}",
    "✅ AKTİF":
        "✅ ACTIVE",
    "❌ KAPALI":
        "❌ OFF",
    "🤖 Oto-Mod Sistemi":
        "🤖 Auto-Mod System",
    "Oto-mod durumu: **{durum}**":
        "Auto-mod status: **{durum}**",
    "Küfür filtresi devre dışı.":
        "The profanity filter is disabled.",
    "🛡️ Korumalar":
        "🛡️ Protections",
    "• Flood koruması (aynı mesajı 3x tekrarlarsa ceza)":
        "• Flood protection (punishes repeating the same message 3x)",
    "⚡ Cezalar":
        "⚡ Punishments",
    "• 1-2. ihlal: Uyarı\n• 3. ihlal: 5dk mute":
        "• 1st-2nd violation: Warning\n• 3rd violation: 5 min timeout",
    "❌ Botları uyaramazsın!":
        "❌ You can't warn bots!",
    "3 uyarıya ulaştı":
        "reached 3 warnings",
    "⚠️ Uyarı & Otomatik Ceza":
        "⚠️ Warning & Automatic Punishment",
    "Uyarı":
        "Warning",
    "**1 saat mute**":
        "**1 hour timeout**",
    "⚠️ Kullanıcı Uyarıldı":
        "⚠️ User Warned",
    "⚠️ Uyarı Aldın!":
        "⚠️ You Got a Warning!",
    "**{name}** sunucusunda uyarıldın.":
        "You were warned in **{name}**.",
    "📝 Sebep":
        "📝 Reason",
    "📊 Toplam Uyarı":
        "📊 Total Warnings",
    "🔇 Ceza":
        "🔇 Punishment",
    "1 saat mute uygulandı":
        "1 hour timeout applied",
    "✅ Uyarı kanalı {mention} olarak ayarlandı!":
        "✅ Warning channel set to {mention}!",
    "❌ Geçersiz tip! Kullanabileceklerin: `{join}`":
        "❌ Invalid type! You can use: `{join}`",
    "✅ Bot durumu ayarlandı: **{capitalize} {metin}**":
        "✅ Bot status set: **{capitalize} {metin}**",
    "❌ Durum güncellenirken hata oluştu: {e}":
        "❌ Error while updating the status: {e}",
    "✅ **{display_name}** için uyarı kaydı yok.":
        "✅ **{display_name}** has no warnings.",
    "⚠️ {display_name} — Uyarılar ({len}/3)":
        "⚠️ {display_name} — Warnings ({len}/3)",
    "✅ **{display_name}** için tüm uyarılar silindi.":
        "✅ All warnings cleared for **{display_name}**.",
    "❌ Botları susturamazsın!":
        "❌ You can't time out bots!",
    "❌ Kendinden üst rütbeli birini susturamazsın!":
        "❌ You can't time out someone ranked above you!",
    "❌ Geçersiz süre! Örnekler: `30s`, `10m`, `2h`, `1d`":
        "❌ Invalid duration! Examples: `30s`, `10m`, `2h`, `1d`",
    "❌ Maksimum süre 28 gündür!":
        "❌ The maximum duration is 28 days!",
    "🔇 Kullanıcı Susturuldu":
        "🔇 User Timed Out",
    "Moderatör":
        "Moderator",
    "Süre":
        "Duration",
    "MezarBot • Moderasyon":
        "MezarBot • Moderation",
    "🔇 Susturuldun!":
        "🔇 You Were Timed Out!",
    "**{name}** sunucusunda susturuldun.":
        "You were timed out in **{name}**.",
    "⏱️ Süre":
        "⏱️ Duration",
    "Susturma kaldırıldı: {name}":
        "Timeout removed: {name}",
    "🔊 Susturma Kaldırıldı":
        "🔊 Timeout Removed",
    "**{display_name}** artık konuşabilir.":
        "**{display_name}** can talk again.",
    "❌ Susturmayı kaldırmak için yetkim yok!":
        "❌ I don't have permission to remove the timeout!",
    "ʜᴏs ɢᴇʟᴅɪɴ {uye}! 🎉 ᴀʀᴀᴍɪᴢᴀ ᴋᴀᴛɪʟᴅɪɢ̆ɪɴ ɪᴄ̧ɪɴ ᴍᴜᴛʟᴜʏᴜᴢ! 🪦":
        "ᴡᴇʟᴄᴏᴍᴇ {uye}! 🎉 ᴡᴇ'ʀᴇ ɢʟᴀᴅ ʏᴏᴜ ᴊᴏɪɴᴇᴅ ᴜs! 🪦",
    "👋 Hoşgeldin Sistemi Ayarlandı":
        "👋 Welcome System Set Up",
    "📝 Kanal":
        "📝 Channel",
    "💬 Mesaj":
        "💬 Message",
    "🔕 Görüşürüz bildirimleri bu sunucuda kapatıldı.":
        "🔕 Goodbye notifications are turned off on this server.",
    "Görüşürüz **{uye}**... Yolun açık olsun. 🕊️":
        "Goodbye **{uye}**... Safe travels. 🕊️",
    "📤 Görüşürüz Sistemi Ayarlandı":
        "📤 Goodbye System Set Up",
    "❌ Bu rol benim rütbemden yüksek, veremem!":
        "❌ This role is above my highest role, I can't give it!",
    "🏷️ Otorol Ayarlandı":
        "🏷️ Auto-role Set",
    "Yeni üyelere otomatik olarak {mention} rolü verilecek.":
        "New members will automatically get the {mention} role.",
    "✅ Log Kanalı Ayarlandı":
        "✅ Log Channel Set",
    "Silinen ve düzenlenen mesajlar artık {mention} kanalına kaydedilecek.":
        "Deleted and edited messages will now be logged in {mention}.",
    "MezarBot • Ayarlar":
        "MezarBot • Settings",
    "❌ Seste olmalısın.":
        "❌ You need to be in voice.",
    "❌ Yeterli kişi yok!":
        "❌ Not enough people!",
    "⚔️ Takımlar Oluşturuldu":
        "⚔️ Teams Created",
    "Boş":
        "Empty",
    "🛡️ Takım {i} ({len} kişi)":
        "🛡️ Team {i} ({len} people)",
    "💤 AFK Modu":
        "💤 AFK Mode",
    "**{display_name}** AFK modunda: *{sebep}*":
        "**{display_name}** is AFK: *{sebep}*",
    "❌ 1-100 arası bir sayı gir.":
        "❌ Enter a number between 1 and 100.",
    "❌ Mesaj silinemedi: {e}":
        "❌ Couldn't delete messages: {e}",
    "✅ {len} mesaj temizlendi.":
        "✅ Cleared {len} messages.",
    "❌ Bu komutu kullanmak için `Mesajları Yönet` yetkisine sahip olmalısın!":
        "❌ You need the `Manage Messages` permission to use this command!",
    "❌ {mention} kanalına mesaj gönderme yetkim yok!":
        "❌ I don't have permission to send messages in {mention}!",
    "❌ Gönderilecek mesaj boş olamaz!":
        "❌ The message can't be empty!",
    "❌ Mesaj 2000 karakterden uzun olamaz!":
        "❌ The message can't be longer than 2000 characters!",
    "❌ Mesaj gönderilemedi: {e}":
        "❌ Couldn't send the message: {e}",
    "✅ Mesaj {mention} kanalına gönderildi.":
        "✅ Message sent to {mention}.",
    "✅ Mesaj {mention} kanalına iletildi.":
        "✅ Message delivered to {mention}.",
    "❌ Kendinden üst rütbeli birini atamazsın!":
        "❌ You can't kick someone ranked above you!",
    "👢 Sunucudan Atıldın!":
        "👢 You Were Kicked!",
    "**{name}** sunucusundan atıldın.":
        "You were kicked from **{name}**.",
    "👢 Kullanıcı Atıldı":
        "👢 User Kicked",
    "❌ Bu kullanıcıyı atmak için yetkim yok!":
        "❌ I don't have permission to kick this user!",
    "❌ Bir hata oluştu: {e}":
        "❌ Something went wrong: {e}",
    "❌ Kendinden üst rütbeli birini yasaklayamazsın!":
        "❌ You can't ban someone ranked above you!",
    "🔨 Sunucudan Yasaklandın!":
        "🔨 You Were Banned!",
    "**{name}** sunucusundan yasaklandın.":
        "You were banned from **{name}**.",
    "🔨 Kullanıcı Yasaklandı":
        "🔨 User Banned",
    "❌ Bu kullanıcıyı yasaklamak için yetkim yok!":
        "❌ I don't have permission to ban this user!",
    "`ayarlı değil`":
        "`not set`",
    "✅ Açık":
        "✅ On",
    "❌ Kapalı":
        "❌ Off",
    "🌐 Sunucu Dili":
        "🌐 Server Language",
    "**🇹🇷 Türkçe**":
        "**🇬🇧 English**",
    "/dil tr · en  (ya da aşağıdaki butonlar)":
        "/dil tr · en  (or the buttons below)",
    "📋 Log kanalı":
        "📋 Log channel",
    "!logayarla #kanal":
        "!logayarla #channel",
    "⚠️ Uyarı kanalı":
        "⚠️ Warning channel",
    "!uyarayarla #kanal":
        "!uyarayarla #channel",
    "👋 Hoşgeldin kanalı":
        "👋 Welcome channel",
    "!hosgeldinayarla #kanal [mesaj]":
        "!hosgeldinayarla #channel [message]",
    "📤 Görüşürüz kanalı":
        "📤 Goodbye channel",
    "!gorusuruzayarla #kanal":
        "!gorusuruzayarla #channel",
    "🏷️ Otorol":
        "🏷️ Auto-role",
    "!otorolayarla @rol":
        "!otorolayarla @role",
    "📢 Yama notları":
        "📢 Patch notes",
    "!yamanotukanal #kanal · kapat":
        "!yamanotukanal #channel · off",
    "🤖 Oto-mod":
        "🤖 Auto-mod",
    "🗳️ Oy ile geç":
        "🗳️ Vote skip",
    "!oygec ac · kapat":
        "!oygec on · off",
    "⚙️ {name} — MezarBot Ayarları":
        "⚙️ {name} — MezarBot Settings",
    "Ayarlanmamış özellikler bu sunucuda devre dışıdır • MezarBot":
        "Unconfigured features are disabled on this server • MezarBot",
    "✅ Sunucu dili **Türkçe** olarak ayarlandı. Bot bu sunucuda artık Türkçe yanıt verecektir.":
        "✅ Server language set to **English**. The bot will now reply in English on this server.",
    "🔕 Yama notları bu sunucuda kapatıldı.":
        "🔕 Patch notes are turned off on this server.",
    "📢 Yama Notu Kanalı Ayarlandı":
        "📢 Patch Notes Channel Set",
    "MezarBot güncelleme notları artık {mention} kanalına gönderilecek.":
        "MezarBot update notes will now be sent to {mention}.",
    "❌ Yama notu çok uzun! (Maks 4000 karakter)":
        "❌ The patch note is too long! (Max 4000 characters)",
    "📢 MezarBot Yama Notları":
        "📢 MezarBot Patch Notes",
    "MezarBot • Güncelleme":
        "MezarBot • Update",
    "📢 Yama notu gönderildi: **{gonderilen}** sunucu · atlanan (kanal ayarsız): **{atlanan}** · hata: **{hatali}**":
        "📢 Patch note sent: **{gonderilen}** servers · skipped (no channel set): **{atlanan}** · errors: **{hatali}**",
    "🔄 Senkronizasyon başlatılıyor...":
        "🔄 Starting sync...",
    "✅ **{len}** slash komutu global senkronize edildi, {len2} sunucudaki yerel kopyalar temizlendi. (Görünmüyorsa Ctrl+R)":
        "✅ Synced **{len}** slash commands globally and cleared local copies on {len2} servers. (If you don't see them, press Ctrl+R)",
    "❌ Senkronizasyon hatası: {e}":
        "❌ Sync error: {e}",
    "⏳ **Yavaşla!** Sistemi soğutuyoruz. Yeni bir işlem yapmak için **{kalan_sure} saniye** daha beklemelisin.":
        "⏳ **Slow down!** We're cooling things off. You need to wait **{kalan_sure} more seconds** before your next action.",
    "Bunu mu demek istedin? 👉 **{PREFIX}{t}**":
        "Did you mean this? 👉 **{PREFIX}{t}**",
    "⚠️ Eksik parametre: `{name}`. Kullanım için `{PREFIX}yardim` yaz.":
        "⚠️ Missing parameter: `{name}`. Type `{PREFIX}help` for usage.",
    "🚫 Bu komutu kullanmak için yetkin yok!":
        "🚫 You don't have permission to use this command!",
    "🚫 Bu komut sadece bot sahibine özel.":
        "🚫 This command is for the bot owner only.",
    "🚫 Bu komut için yetkin yok! (Sunucu yöneticisi — *Yönetici* / *Sunucuyu Yönet* yetkisi — gerekir)":
        "🚫 You don't have permission for this command! (Needs a server admin — the *Administrator* / *Manage Server* permission)",
    "⚠️ Beklenmedik bir hata oluştu. Lütfen tekrar dene.":
        "⚠️ Something unexpected went wrong. Please try again.",
    "⏳ Yavaşla! Bu komut soğuma süresinde. **{kalan} saniye** sonra tekrar deneyebilirsin.":
        "⏳ Slow down! This command is on cooldown. You can try again in **{kalan} seconds**.",
    "🚫 Bu komutu kullanmak için gerekli Discord yetkisine sahip değilsin.":
        "🚫 You don't have the Discord permission needed to use this command.",
    "🚫 Bot bu komutu çalıştırmak için gerekli sunucu yetkilerine sahip değil.":
        "🚫 The bot doesn't have the server permissions needed to run this command.",
    "🚫 Bu komutu kullanmak için yetkin yok (Yönetici yetkisi gereklidir).":
        "🚫 You don't have permission to use this command (Administrator is required).",
    "❌ Bu komut sadece sunucularda kullanılabilir.":
        "❌ This command can only be used in servers.",
    "⚠️ İşlem sırasında beklenmedik bir hata oluştu. Lütfen tekrar dene.":
        "⚠️ Something unexpected went wrong. Please try again.",
    "Liste adı boş olamaz.":
        "The playlist name can't be empty.",
    "En fazla {LISTE_LIMITI} kişisel listen olabilir.":
        "You can have at most {LISTE_LIMITI} personal playlists.",
    "parça":
        "track",
    "Varsayılan kişi limiti":
        "Default people limit",
    "Ad şablonu":
        "Name template",
    "Boş oda silme süresi":
        "Empty room deletion time",
    "Kişi başı en fazla oda":
        "Max rooms per person",
    "Üyeler odasını gizleyebilir":
        "Members can hide their room",
    "Spotify → YouTube":
        "Spotify → YouTube",
    "SoundCloud":
        "SoundCloud",
    "Filtresiz, saf ses":
        "No filters, pure sound",
    "Üyeleri Sağırlaştır (oda sahibine odasında verilir)":
        "Deafen Members (given to the room owner in their room)",
    "Kuyruk":
        "Queue",
    "YouTube istek sınırı (geçici)":
        "YouTube rate limit (temporary)",
    "YouTube":
        "YouTube",
    "özel (gizli) video":
        "private video",
    "🔊 {kullanici} odası":
        "🔊 {kullanici}'s room",
    "Ses dengeleme":
        "Volume normalization",
    "🔕 Özel oda sistemi bu sunucuda **kapalı**. Bir yönetici (*Sunucuyu Yönet*) `/ozelodaaktif` ile açabilir.":
        "🔕 The private room system is **off** on this server. An admin (*Manage Server*) can turn it on with `/ozelodaaktif`.",
    "video kullanılamıyor / kaldırılmış":
        "video unavailable / removed",
    "Mesaj Gönder":
        "Send Messages",
    "DRM korumalı":
        "DRM protected",
    "YouTube bot doğrulaması istedi (geçici)":
        "YouTube asked for bot verification (temporary)",
    "Şarkılar arası ses farkını eşitler":
        "Evens out loudness between songs",
    "desteklenmeyen link":
        "unsupported link",
    "bölge engeli":
        "region blocked",
    "Üyeleri Taşı":
        "Move Members",
    "Bağlan":
        "Connect",
    "Doğrudan Link":
        "Direct Link",
    "Üyeleri Sustur (oda sahibine odasında verilir)":
        "Mute Members (given to the room owner in their room)",
    "telif nedeniyle kaldırılmış":
        "removed for copyright",
    "yayın henüz başlamadı":
        "the stream hasn't started yet",
    "Bağlantı Yerleştir":
        "Embed Links",
    "çözücü süreci yeniden başlatıldı (geçici)":
        "the resolver process restarted (temporary)",
    "Mesaj Geçmişini Oku":
        "Read Message History",
    "Bu kullanıcıya ceza verilemez, verilmesi teklif dahi edilemez.":
        "This user can't be punished — don't even suggest it.",
    "sadece kanal üyelerine açık":
        "members-only content",
    "Şarkı":
        "Song",
    "yaş kısıtlamalı (giriş gerekiyor)":
        "age-restricted (sign-in required)",
    "Kanalları Yönet":
        "Manage Channels",
    "Efektleri kapat":
        "Turn off effects",
    "Rolleri Yönet (izin geçersiz kılmaları için)":
        "Manage Roles (for permission overwrites)",
    "Kanalları Görüntüle":
        "View Channels",
    "AFK ol (etiketlenince sebebin gösterilir)":
        "Go AFK (your reason is shown when someone mentions you)",
    "Üyeyi sunucudan at":
        "Kick a member from the server",
    "Şarkıyı atlar (oylama açıksa oy verir) · numara verirsen o parçaya atlar":
        "Skips the song (votes if voting is on) · give a number to jump to that track",
    "İsteğe bağlı: kuyruktaki şu numaralı parçaya atla":
        "Optional: jump to this track number in the queue",
    "Sunucunun bot ayarlarını göster ve değiştir":
        "Show and change the bot's settings for this server",
    "Seslendirme için bağlanan botu kanaldan çıkar":
        "Disconnect the text-to-speech bot from the channel",
    "Çalma listeleri (kişisel ve paylaşılan listeler)":
        "Playlists (personal and shared)",
    "Listenden bir parçayı çıkarır":
        "Remove a track from your playlist",
    "Parça numarası":
        "Track number",
    "Listene şarkı ekler (boş: çalan şarkı)":
        "Add a song to your playlist (empty: the current song)",
    "Şarkı adı / link (boş: çalan şarkı)":
        "Song name / link (empty: the current song)",
    "Liste adı (boş: tüm listeler)":
        "Playlist name (empty: all playlists)",
    "Çalan şarkı + kuyruğu kişisel listene kaydeder (aynı ad varsa üzerine yazar)":
        "Saves the current song + queue to your personal playlist (overwrites one with the same name)",
    "Liste adı":
        "Playlist name",
    "Çalma listesini kuyruğa ekler":
        "Adds a playlist to the queue",
    "Liste adı (varsayılan: Favoriler)":
        "Playlist name (default: Favoriler)",
    "Karıştırarak ekle (evet/hayır)":
        "Shuffle while adding (yes/no)",
    "Kişisel listeni tamamen siler":
        "Deletes your personal playlist entirely",
    "Metni Türkçe veya İngilizceye çevirir":
        "Translates text to Turkish or English",
    "Hangi dile çevrilsin?":
        "Which language should it be translated to?",
    "Çevrilecek metin":
        "Text to translate",
    "Botu ses kanalından çıkarır (kuyruk temizlenir)":
        "Disconnects the bot from voice (the queue is cleared)",
    "Yapay zekâ ile resim çiz / Draw an image with AI":
        "Draw an image with AI",
    "Duraklatılan müziği sürdürür":
        "Resumes paused music",
    "Sunucunun bot dilini değiştirir (tr / en)":
        "Changes the bot's language for this server (tr / en)",
    "Seçilecek dil (tr / en)":
        "Language to use (tr / en)",
    "🇹🇷 Türkçe":
        "🇹🇷 Türkçe",
    "🇬🇧 English":
        "🇬🇧 English",
    "🚪・giris kanalındaki dil seçim panelini yeniden gönderir":
        "Re-sends the language picker panel in the 🚪・giris channel",
    "Döngü modu: kapalı / şarkı / kuyruk":
        "Loop mode: off / song / queue",
    "kapalı, şarkı ya da kuyruk (boş: sıradaki moda geç)":
        "off, song or queue (empty: switch to the next mode)",
    "Draw an image with AI":
        "Draw an image with AI",
    "Description of the image":
        "Description of the image",
    "Müziği duraklatır":
        "Pauses the music",
    "Çalmayı durdurur ve kuyruğu temizler (7/24 kapalıysa kanaldan ayrılır)":
        "Stops playback and clears the queue (leaves the channel if 24/7 is off)",
    "[Bot Sahibi] Botun durumunu kalıcı olarak ayarlar":
        "[Bot Owner] Sets the bot's status permanently",
    "Durum metni":
        "Status text",
    "Durum tipi (oynuyor, dinliyor, izliyor, yarismada)":
        "Status type (oynuyor, dinliyor, izliyor, yarismada)",
    "Oynuyor":
        "Playing",
    "Dinliyor":
        "Listening",
    "İzliyor":
        "Watching",
    "Yarışmada":
        "Competing",
    "Şarkıyı geri sarar (varsayılan 10 sn)":
        "Rewinds the song (default 10 s)",
    "Görüşürüz (ayrılma) kanalını ve mesajını ayarla ya da kapat":
        "Set or turn off the goodbye (leave) channel and message",
    "Ayrılma mesajının gönderileceği kanal":
        "Channel where the leave message is sent",
    "Özel veda mesajı ({uye} üye adıdır)":
        "Custom goodbye message ({uye} is the member's name)",
    "View MezarBot command guide and help menu":
        "View MezarBot command guide and help menu",
    "Hoş geldin kanalını ve mesajını ayarla":
        "Set the welcome channel and message",
    "Şarkıyı ileri sarar (varsayılan 10 sn)":
        "Fast-forwards the song (default 10 s)",
    "Kaç saniye (ya da 1:00 gibi)":
        "How many seconds (or something like 1:00)",
    "Kuyruktan parça kaldırır":
        "Removes a track from the queue",
    "Kaldırılacak parçanın kuyruk numarası":
        "Queue number of the track to remove",
    "Kuyruğu karıştırır":
        "Shuffles the queue",
    "Botu ses kanalına çağırır":
        "Calls the bot to your voice channel",
    "Yapay zekânın kişiliğini seç":
        "Pick the AI's personality",
    "Metni sesli kanalda seslendir":
        "Read text aloud in a voice channel",
    "Seslendirilecek metin":
        "Text to read aloud",
    "Ses türü (erkek veya kadın)":
        "Voice type (male or female)",
    "Erkek (Ahmet)":
        "Male",
    "Kadın (Emel)":
        "Female",
    "Kuyruğu sayfa sayfa gösterir":
        "Shows the queue page by page",
    "Moderasyon log kanalını ayarla":
        "Set the moderation log channel",
    "Mezarpoly: tarayıcıda ücretsiz online emlak oyunu / Free online property game":
        "Mezarpoly: free online property-trading game in your browser",
    "Sunucunun müzik ayarları":
        "This server's music settings",
    "DJ rolünü ayarlar (boş: kapatır). DJ'ler kontrol komutlarını kullanır.":
        "Sets the DJ role (empty: turns it off). DJs use the control commands.",
    "DJ rolü (boş bırak = DJ sistemini kapat)":
        "DJ role (leave empty = turn off the DJ system)",
    "Şarkı istek kanalı: bu kanala yazılan her mesaj aranıp kuyruğa eklenir":
        "Song request channel: every message in this channel is searched and added to the queue",
    "Kanal (boş: yeni kanal oluştur)":
        "Channel (empty: create a new channel)",
    "'kapat' yazarsan istek kanalı kapatılır":
        "Type 'kapat' to turn the request channel off",
    "Ses normalizasyonunun varsayılan durumu":
        "Default state of volume normalization",
    "Otomatik oynatmanın varsayılan durumu":
        "Default state of autoplay",
    "Oylamalı atla: aç / kapat ya da gereken oran (ör. 60)":
        "Vote skip: on / off or the required ratio (e.g. 60)",
    "aç, kapat ya da yüzde (10-100)":
        "on, off or a percentage (10-100)",
    "7/24 modu: boşta/yalnızken kanaldan ayrılma":
        "24/7 mode: don't leave the channel when idle/alone",
    "aç / kapat":
        "on / off",
    "Yeni oturumların başlangıç sesi (0-150)":
        "Starting volume for new sessions (0-150)",
    "0-150":
        "0-150",
    "Boşta ya da kanalda yalnız kalınca kaç dakika sonra ayrılsın":
        "How many minutes to wait before leaving when idle or alone",
    "Dakika (ör. 3) ya da 90s, 1:30 (30 sn – 60 dk)":
        "Minutes (e.g. 3) or 90s, 1:30 (30 s – 60 min)",
    "Bu sunucuda son çalınan şarkılar":
        "Songs played recently on this server",
    "Ses dengeleme (şarkılar arası ses farkını eşitler) aç/kapat":
        "Volume normalization (evens out loudness between songs) on/off",
    "Özel ses odanın bilgisi ve yönetimi":
        "Your private voice room's info and management",
    "Odanın kilidini açar: herkes girebilir":
        "Unlocks the room: everyone can join",
    "Odanın adını değiştirir (en fazla 50 karakter)":
        "Renames the room (at most 50 characters)",
    "Yeni oda adı":
        "New room name",
    "Üyeyi odadan atar ve tekrar girmesini engeller":
        "Kicks a member from the room and stops them rejoining",
    "Atılacak üye":
        "Member to kick",
    "Üyeyi odana davet eder (kilitli/gizli odaya girebilir)":
        "Invites a member to your room (they can join even if it's locked/hidden)",
    "Davet edilecek üye":
        "Member to invite",
    "Oda sahipliğini başka bir üyeye verir":
        "Gives room ownership to another member",
    "Yeni oda sahibi":
        "New room owner",
    "Odayı gizler: sadece davetliler görebilir":
        "Hides the room: only invited people can see it",
    "Odayı tekrar herkese görünür yapar":
        "Makes the room visible to everyone again",
    "Odayı kilitler: sadece davet ettiklerin girebilir":
        "Locks the room: only people you invite can join",
    "Kişi limitini ayarlar (0 = sınırsız, en fazla 99)":
        "Sets the people limit (0 = unlimited, at most 99)",
    "0-99 (0 = sınırsız)":
        "0-99 (0 = unlimited)",
    "Kontrol panelini odanın sohbetine yeniden gönderir":
        "Re-sends the control panel to the room's chat",
    "Sahibi odada değilse odayı devralırsın (odada olmalısın)":
        "Take over the room if its owner isn't in it (you must be in the room)",
    "Üyenin oda yasağını kaldırır":
        "Lifts a member's room ban",
    "Yasağı kaldırılacak üye":
        "Member to unban",
    "Üyeyi odadan atar; odayı göremez ve giremez":
        "Kicks a member from the room; they can't see or join it",
    "Yasaklanacak üye":
        "Member to ban",
    "Onay bekleyen bir üyeyi onaylayıp kanalları açar":
        "Approves a pending member and opens the channels",
    "Atanacak dil (Varsayılan: Üyenin tercihi)":
        "Language to assign (Default: the member's choice)",
    "Otomatik (Üyenin Tercihi)":
        "Automatic (Member's Choice)",
    "🌐 Her İkisi / Both":
        "🌐 Both",
    "Verilecek yetki rolü":
        "Role to give",
    "Topluluk":
        "Community",
    "Maker / Geliştirici":
        "Maker / Developer",
    "Onaylanacak üye":
        "Member to approve",
    "Önceki şarkıya döner":
        "Goes back to the previous song",
    "Otomatik oynatma: kuyruk bitince benzer şarkılarla devam eder":
        "Autoplay: keeps going with similar songs when the queue ends",
    "aç / kapat (boş: değiştir)":
        "on / off (empty: toggle)",
    "Otomatik moderasyonu aç/kapat":
        "Turn auto-moderation on/off",
    "Yeni üyelere otomatik verilecek rolü ayarla":
        "Set the role automatically given to new members",
    "Oylamalı atlamayı açar/kapatır ya da gereken oranı ayarlar":
        "Turns vote skip on/off or sets the required ratio",
    "aç / kapat ya da gereken oran (ör. 60)":
        "on / off or the required ratio (e.g. 60)",
    "Şarkıyı atlamak için oy verir":
        "Votes to skip the song",
    "Şarkı / playlist çalar (YouTube, YT Music, Spotify, SoundCloud, link)":
        "Plays a song / playlist (YouTube, YT Music, Spotify, SoundCloud, link)",
    "Şarkı adı ya da link (YouTube, YT Music, Spotify, SoundCloud, doğrudan ses linki)":
        "Song name or link (YouTube, YT Music, Spotify, SoundCloud, direct audio link)",
    "Özel oda sisteminin durumu ve ayarları (yönetici)":
        "Private room system status and settings (admin)",
    "Özel oda varsayılanlarını değiştirir (boş: gösterir)":
        "Changes the private room defaults (empty: shows them)",
    "Değiştirilecek ayar":
        "Setting to change",
    "Yeni değer (ör. 5, 🔊 {kullanici} odası, 30, 1, evet)":
        "New value (e.g. 5, 🔊 {kullanici}'s room, 30, 1, yes)",
    "Özel ses odası sistemini bu sunucuda açar ve kanallarını kurar/onarır":
        "Turns on the private voice room system on this server and sets up/repairs its channels",
    "Özel ses odası sistemini kapatır ve kanallarını kaldırır":
        "Turns off the private voice room system and removes its channels",
    "Onay bekleyen bir üyeyi reddeder ve sunucudan atar":
        "Rejects a pending member and kicks them from the server",
    "Reddetme sebebi":
        "Reason for rejecting",
    "Reddedilecek üye":
        "Member to reject",
    "Şarkıda belirli bir ana sarar (1:30, +30, -10)":
        "Seeks to a specific point in the song (1:30, +30, -10)",
    "Örnek: 1:30 (mutlak), +30 (ileri), -10 (geri)":
        "Example: 1:30 (absolute), +30 (forward), -10 (back)",
    "Ses seviyesi (0-150, sunucuya özel hatırlanır)":
        "Volume level (0-150, remembered per server)",
    "0-150 arası, ya da +10 / -10":
        "0-150, or +10 / -10",
    "Ses kanalı istatistikleri ve süre sıralaması":
        "Voice channel stats and time leaderboards",
    "Bu ay en çok ses kanalında kalan kullanıcılar":
        "Members who spent the most time in voice this month",
    "Ses kanalı istatistiklerin":
        "Your voice channel stats",
    "İstatistikleri görüntülenecek üye (boş bırakırsan kendin)":
        "Member whose stats to view (leave empty for yourself)",
    "Bu hafta en çok ses kanalında kalan kullanıcılar":
        "Members who spent the most time in voice this week",
    "Ses takibi için kanal ayarla (boş bırakırsan TÜM kanallar izlenir)":
        "Set the channel to track (leave empty to track ALL channels)",
    "İzlenecek kanal (yoksa tüm kanallar izlenir)":
        "Channel to track (otherwise all channels are tracked)",
    "Tüm ses aktivite verisini siler (GERİ ALINAMAZ)":
        "Deletes all voice activity data (CAN'T BE UNDONE)",
    "Sunucuda en çok ses kanalında kalan kullanıcılar (tüm zamanlar)":
        "Members who spent the most time in voice on this server (all time)",
    "View and change bot settings and language for this server":
        "View and change bot settings and language for this server",
    "Yapay zekâ sohbet geçmişini sıfırla / Reset AI chat history":
        "Reset your AI chat history",
    "Kanaldan mesaj sil (varsayılan 5)":
        "Delete messages from the channel (default 5)",
    "Şu an çalanı ve kontrol panelini gösterir (paneli bu kanala taşır)":
        "Shows what's playing and the control panel (moves the panel to this channel)",
    "Şarkıyı kuyruğun en başına ekler (sıradaki çalar)":
        "Adds a song to the front of the queue (plays next)",
    "Şarkı adı ya da link":
        "Song name or link",
    "Üyeyi süreli sustur (ör. 10m, 1h)":
        "Time out a member (e.g. 10m, 1h)",
    "Üyenin susturmasını kaldır":
        "Remove a member's timeout",
    "[Bot Sahibi] Slash komutlarını global senkronize eder":
        "[Bot Owner] Syncs slash commands globally",
    "Ses kanalındakileri rastgele takımlara böl":
        "Split the people in your voice channel into random teams",
    "Kuyrukta parçanın yerini değiştirir":
        "Moves a track to another position in the queue",
    "Taşınacak parçanın numarası":
        "Number of the track to move",
    "Yeni konumu":
        "Its new position",
    "Kuyruğu temizler (DJ değilsen sadece kendi eklediklerini)":
        "Clears the queue (if you're not a DJ, only the tracks you added)",
    "Üyeyi uyar":
        "Warn a member",
    "Uyarı log kanalını ayarla":
        "Set the warning log channel",
    "Üyenin uyarılarını göster":
        "Show a member's warnings",
    "Üyenin uyarılarını sil":
        "Clear a member's warnings",
    "[Bot Sahibi] Yama notunu tüm sunuculara duyurur":
        "[Bot Owner] Announces a patch note to all servers",
    "Yama notu metni":
        "Patch note text",
    "Yama notu kanalını ayarla ya da kapat":
        "Set or turn off the patch notes channel",
    "MezarBot komut rehberini gösterir / View command guide":
        "View the MezarBot command guide",
    "Üyeyi sunucudan yasakla":
        "Ban a member from the server",
    "Seçilen kanala bot aracılığıyla mesaj gönder":
        "Post a message in a channel through the bot",
    "Mesajın gönderileceği kanal (boş bırakılırsa bu kanal)":
        "Channel to post in (empty: this channel)",
    "Gönderilecek mesaj metni":
        "Message text to post",
    "[Bot Sahibi] yt-dlp'yi venv'de günceller":
        "[Bot Owner] Updates yt-dlp in the venv",
    "bekle: çalan şarkılar bitince yeniden başlat":
        "bekle: restart once the playing songs end",
    "Odamı yönet":
        "Manage my room",
    "Yardım":
        "Help",
    "Oda oluştur":
        "Create room",
    # ── cogs/muzik/ornekler.py ──
    "🎧 Senin odanda **{bot}** çalıyor. Komutu ondan kullan: `/{komut}` yazınca listeden **{bot}**'u seç (ya da `!{komut}` yaz).":
        "🎧 **{bot}** is playing in your channel. Use its command instead: type `/{komut}` and pick **{bot}** from the list (or type `!{komut}`).",
    "🎶 Ben şu an **{kanal}** kanalında çalıyorum. Senin odan için **{bot}** boşta: `/{komut}` yazıp listeden **{bot}**'u seç (ya da `!{komut}` yaz, boştaki bot kendisi gelir).":
        "🎶 I'm playing in **{kanal}** right now. **{bot}** is free for your channel: type `/{komut}` and pick **{bot}** (or type `!{komut}` and the free bot joins by itself).",
    # ── cogs/muzik/cog.py — otomatik öneriler elle eklenen şarkıya yol verir ──
    "▶️ **Şimdi çalınıyor** — otomatik önerinin yerine":
        "▶️ **Now playing** — instead of the autoplay pick",
    "📻 Otomatik öneri yerine hemen senin listen başlıyor.":
        "📻 Your songs start right away instead of the autoplay pick.",
}
