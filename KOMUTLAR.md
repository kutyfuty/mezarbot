# MezarBot komutları

Komutların çoğu hem `/` (slash) hem de `!` (önek) ile kullanılabilir; alt komutlu gruplar (ör. `/oda`, `/sesstat`) sadece slash ile çalışır. Liste botun komut ağacından üretildi.

## 🎵 Müzik

| Komut | Açıklama |
|---|---|
| `/atla` | Şarkıyı atlar (oylama açıksa oy verir) · numara verirsen o parçaya atlar |
| `/calmalistesi cikar` | Listenden bir parçayı çıkarır |
| `/calmalistesi ekle` | Listene şarkı ekler (boş: çalan şarkı) |
| `/calmalistesi goster` | Çalma listeleri (kişisel ve paylaşılan listeler) |
| `/calmalistesi kaydet` | Çalan şarkı + kuyruğu kişisel listene kaydeder (aynı ad varsa üzerine yazar) |
| `/calmalistesi oynat` | Çalma listesini kuyruğa ekler |
| `/calmalistesi sil` | Kişisel listeni tamamen siler |
| `/cik` | Botu ses kanalından çıkarır (kuyruk temizlenir) |
| `/devam` | Duraklatılan müziği sürdürür |
| `/dongu` | Döngü modu: kapalı / şarkı / kuyruk |
| `/duraklat` | Müziği duraklatır |
| `/durdur` | Çalmayı durdurur ve kuyruğu temizler (7/24 kapalıysa kanaldan ayrılır) |
| `/geri` | Şarkıyı geri sarar (varsayılan 10 sn) |
| `/ileri` | Şarkıyı ileri sarar (varsayılan 10 sn) |
| `/kaldir` | Kuyruktan parça kaldırır |
| `/karistir` | Kuyruğu karıştırır |
| `/katil` | Botu ses kanalına çağırır |
| `/kuyruk` | Kuyruğu sayfa sayfa gösterir |
| `/muzikayar dj` | DJ rolünü ayarlar (boş: kapatır). DJ'ler kontrol komutlarını kullanır. |
| `/muzikayar goster` | Sunucunun müzik ayarları |
| `/muzikayar istekkanali` | Şarkı istek kanalı: bu kanala yazılan her mesaj aranıp kuyruğa eklenir |
| `/muzikayar normalizasyon` | Ses normalizasyonunun varsayılan durumu |
| `/muzikayar otomatik` | Otomatik oynatmanın varsayılan durumu |
| `/muzikayar oylama` | Oylamalı atla: aç / kapat ya da gereken oran (ör. 60) |
| `/muzikayar surekli` | 7/24 modu: boşta/yalnızken kanaldan ayrılma |
| `/muzikayar varsayilanses` | Yeni oturumların başlangıç sesi (0-150) |
| `/muzikayar zamanasimi` | Boşta ya da kanalda yalnız kalınca kaç dakika sonra ayrılsın |
| `/muzikgecmis` | Bu sunucuda son çalınan şarkılar |
| `/normalizasyon` | Ses dengeleme (şarkılar arası ses farkını eşitler) aç/kapat |
| `/onceki` | Önceki şarkıya döner |
| `/otomatik` | Otomatik oynatma: kuyruk bitince benzer şarkılarla devam eder |
| `/oygec` | Oylamalı atlamayı açar/kapatır ya da gereken oranı ayarlar |
| `/oylaatla` | Şarkıyı atlamak için oy verir |
| `/oynat` | Şarkı / playlist çalar (YouTube, YT Music, Spotify, SoundCloud, link) |
| `/sar` | Şarkıda belirli bir ana sarar (1:30, +30, -10) |
| `/ses` | Ses seviyesi (0-150, sunucuya özel hatırlanır) |
| `/simdi` | Şu an çalanı ve kontrol panelini gösterir (paneli bu kanala taşır) |
| `/siradaki` | Şarkıyı kuyruğun en başına ekler (sıradaki çalar) |
| `/tasi` | Kuyrukta parçanın yerini değiştirir |
| `/temizle` | Kuyruğu temizler (DJ değilsen sadece kendi eklediklerini) |
| `/ytdlpguncelle` | [Bot Sahibi] yt-dlp'yi venv'de günceller |

## 🔊 Özel ses odaları

| Komut | Açıklama |
|---|---|
| `/oda ac` | Odanın kilidini açar: herkes girebilir |
| `/oda ad` | Odanın adını değiştirir (en fazla 50 karakter) |
| `/oda at` | Üyeyi odadan atar ve tekrar girmesini engeller |
| `/oda bilgi` | Özel ses odanın bilgisi ve yönetimi |
| `/oda davet` | Üyeyi odana davet eder (kilitli/gizli odaya girebilir) |
| `/oda devret` | Oda sahipliğini başka bir üyeye verir |
| `/oda gizle` | Odayı gizler: sadece davetliler görebilir |
| `/oda goster` | Odayı tekrar herkese görünür yapar |
| `/oda kilitle` | Odayı kilitler: sadece davet ettiklerin girebilir |
| `/oda limit` | Kişi limitini ayarlar (0 = sınırsız, en fazla 99) |
| `/oda panel` | Kontrol panelini odanın sohbetine yeniden gönderir |
| `/oda sahiplen` | Sahibi odada değilse odayı devralırsın (odada olmalısın) |
| `/oda yasak-kaldir` | Üyenin oda yasağını kaldırır |
| `/oda yasakla` | Üyeyi odadan atar; odayı göremez ve giremez |
| `/ozeloda ayar` | Özel oda varsayılanlarını değiştirir (boş: gösterir) |
| `/ozeloda durum` | Özel oda sisteminin durumu ve ayarları (yönetici) |
| `/ozelodaaktif` | Özel ses odası sistemini bu sunucuda açar ve kanallarını kurar/onarır |
| `/ozelodakapat` | Özel ses odası sistemini kapatır ve kanallarını kaldırır |

## 📊 Ses istatistikleri

| Komut | Açıklama |
|---|---|
| `/sesstat ay` | Bu ay en çok ses kanalında kalan kullanıcılar |
| `/sesstat ben` | Ses kanalı istatistiklerin |
| `/sesstat hafta` | Bu hafta en çok ses kanalında kalan kullanıcılar |
| `/sesstat kanal` | Ses takibi için kanal ayarla (boş bırakırsan TÜM kanallar izlenir) |
| `/sesstat sifirla` | Tüm ses aktivite verisini siler (GERİ ALINAMAZ) |
| `/sesstat top` | Sunucuda en çok ses kanalında kalan kullanıcılar (tüm zamanlar) |

## 🛡️ Moderasyon ve sunucu ayarları

| Komut | Açıklama |
|---|---|
| `/afk` | AFK ol (etiketlenince sebebin gösterilir) |
| `/at` | Üyeyi sunucudan at |
| `/ayarlar` | Sunucunun bot ayarlarını göster ve değiştir |
| `/dil` | Sunucunun bot dilini değiştirir (tr / en) |
| `/durumayarla` | [Bot Sahibi] Botun durumunu kalıcı olarak ayarlar |
| `/gorusuruzayarla` | Görüşürüz (ayrılma) kanalını ve mesajını ayarla ya da kapat |
| `/hosgeldinayarla` | Hoş geldin kanalını ve mesajını ayarla |
| `/logayarla` | Moderasyon log kanalını ayarla |
| `/otomod` | Otomatik moderasyonu aç/kapat |
| `/otorolayarla` | Yeni üyelere otomatik verilecek rolü ayarla |
| `/settings` | View and change bot settings and language for this server |
| `/sil` | Kanaldan mesaj sil (varsayılan 5) |
| `/sustur` | Üyeyi süreli sustur (ör. 10m, 1h) |
| `/susturmakald` | Üyenin susturmasını kaldır |
| `/sync` | [Bot Sahibi] Slash komutlarını global senkronize eder |
| `/takimkur` | Ses kanalındakileri rastgele takımlara böl |
| `/uyar` | Üyeyi uyar |
| `/uyarayarla` | Uyarı log kanalını ayarla |
| `/uyarilar` | Üyenin uyarılarını göster |
| `/uyarisil` | Üyenin uyarılarını sil |
| `/yamanotu` | [Bot Sahibi] Yama notunu tüm sunuculara duyurur |
| `/yamanotukanal` | Yama notu kanalını ayarla ya da kapat |
| `/yasak` | Üyeyi sunucudan yasakla |
| `/yaz` | Seçilen kanala bot aracılığıyla mesaj gönder |

## 🤖 Yapay zekâ

| Komut | Açıklama |
|---|---|
| `/ciz` | Yapay zekâ ile resim çiz / Draw an image with AI |
| `/draw` | Draw an image with AI |
| `/kisilik` | Yapay zekânın kişiliğini seç |
| `/sifirla` | Yapay zekâ sohbet geçmişini sıfırla / Reset AI chat history |

## 🗣️ Seslendirme (TTS)

| Komut | Açıklama |
|---|---|
| `/ayril` | Seslendirme için bağlanan botu kanaldan çıkar |
| `/konus` | Metni sesli kanalda seslendir |

## 🌐 Çeviri

| Komut | Açıklama |
|---|---|
| `/cevir` | Metni Türkçe veya İngilizceye çevirir |

## ❓ Yardım

| Komut | Açıklama |
|---|---|
| `/help` | View MezarBot command guide and help menu |
| `/yardim` | MezarBot komut rehberini gösterir / View command guide |

## 🚪 Üye onay kapısı (opsiyonel, config ile açılır)

| Komut | Açıklama |
|---|---|
| `/dilpaneli` | 🚪・giris kanalındaki dil seçim panelini yeniden gönderir |
| `/onayla` | Onay bekleyen bir üyeyi onaylayıp kanalları açar |
| `/reddet` | Onay bekleyen bir üyeyi reddeder ve sunucudan atar |

## Mesaj tepkileri

- Bir mesaja 🇬🇧 / 🇺🇸 tepkisi → İngilizce çeviri, 🇹🇷 → Türkçe çeviri (Groq).
- Botu etiketleyerek yapay zekâyla sohbet edilir.
