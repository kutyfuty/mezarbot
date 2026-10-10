"""
Elektronik Lab & Komponent Asistanı
- %100 Ücretsiz: Hesaplamalar ve pinout referansları tamamen yerel Python ile çalışır.
- AI Devre Danışmanı: Groq ücretsiz katmanı üzerinden elektronik hata ayıklama desteği sunar.
- Komut Grubu (/lab): Discord 100 global slash komut sınırını aşmamak için /lab grubu altında toplanmıştır.
"""
import logging
import math
import re
import os
import discord
from discord.ext import commands
from discord import app_commands
from groq import Groq

logger = logging.getLogger('MezarBot.Elektronik')

# ══════════════════════════════════════════════
#  PINOUT REFERANS VERİLERİ (100% Yerel / 0 Maliyet)
# ══════════════════════════════════════════════

PINOUT_VERILERI = {
    "esp32": {
        "baslik": "⚡ ESP32 (WROOM-32 / DevKit V1)",
        "voltaj": "3.3V Mantık Seviyesi (5V Toleranslı DEĞİLDİR!)",
        "aciklama": (
            "**Kritik Dikkat Noktaları:**\n"
            "• **Wi-Fi + ADC2 Çakışması:** Wi-Fi açıkken GPIO 0, 2, 4, 12-15, 25-27 pinlerindeki analog okumalar (ADC2) ÇALIŞMAZ! Analog sensörler için sadece ADC1 (GPIO 32-39) kullanın.\n"
            "• **Strapping Pinleri (Boot):** GPIO 0, 2, 5, 12, 15 boot modunu etkiler. Bu pinlere pull-up/down bağlarken dikkat edin (GPIO 0 pull-down olursa kart flash modunda kalır).\n"
            "• **Sadece Giriş Pinleri (Input Only):** GPIO 34, 35, 36 (VP), 39 (VN) dahili pull-up içermez ve ÇIKIŞ olarak kullanılamaz."
        ),
        "harita": (
            "```text\n"
            "           ┌──────────┐\n"
            "       EN ─┤ 1     30 ├─ GPIO 23 (MOSI)\n"
            "(ADC1) 36 ─┤ 2     29 ├─ GPIO 22 (SCL)\n"
            "(ADC1) 39 ─┤ 3     28 ├─ GPIO 1  (TX0)\n"
            "(ADC1) 34 ─┤ 4     27 ├─ GPIO 3  (RX0)\n"
            "(ADC1) 35 ─┤ 5     26 ├─ GPIO 21 (SDA)\n"
            "(ADC1) 32 ─┤ 6     25 ├─ GPIO 19 (MISO)\n"
            "(ADC1) 33 ─┤ 7     24 ├─ GPIO 18 (SCK)\n"
            "  DAC1 25 ─┤ 8     23 ├─ GPIO 5  (CS)\n"
            "  DAC2 26 ─┤ 9     22 ├─ GPIO 17 (TX2)\n"
            "       27 ─┤ 10    21 ├─ GPIO 16 (RX2)\n"
            "       14 ─┤ 11    20 ├─ GPIO 4\n"
            "       12 ─┤ 12    19 ├─ GPIO 0  (Boot)\n"
            "       13 ─┤ 13    18 ├─ GPIO 2  (LED)\n"
            "      GND ─┤ 14    17 ├─ GPIO 15\n"
            "      VIN ─┤ 15    16 ├─ 3V3\n"
            "           └──────────┘\n"
            "```"
        ),
        "protokoller": "• **I2C:** SDA=GPIO 21, SCL=GPIO 22\n• **SPI:** MOSI=23, MISO=19, SCK=18, CS=5\n• **Serial2:** TX2=17, RX2=16"
    },
    "esp8266": {
        "baslik": "⚡ ESP8266 (NodeMCU v2/v3 / D1 Mini)",
        "voltaj": "3.3V Mantık Seviyesi (5V Toleranslı DEĞİLDİR)",
        "aciklama": (
            "**Kritik Dikkat Noktaları:**\n"
            "• **Analog Giriş (A0):** NodeMCU dahili voltaj bölücüyle 0-3.3V destekler (Çıplak ESP-12 modülü ise sadece 0-1.0V destekler!).\n"
            "• **Boot Pinleri:** D3 (GPIO 0) HIGH olmalı, D4 (GPIO 2) HIGH olmalı, D8 (GPIO 15) LOW olmalı. Aksi halde kart açılmaz!\n"
            "• **D0 (GPIO 16):** Deep sleep uyandırma pinidir (RST'ye bağlanır)."
        ),
        "harita": (
            "```text\n"
            "NodeMCU Pin Eşleşmesi:\n"
            "D0 -> GPIO 16 (Wake)    D5 -> GPIO 14 (SCK)\n"
            "D1 -> GPIO 5  (SCL)     D6 -> GPIO 12 (MISO)\n"
            "D2 -> GPIO 4  (SDA)     D7 -> GPIO 13 (MOSI)\n"
            "D3 -> GPIO 0  (Flash)   D8 -> GPIO 15 (CS/SS)\n"
            "D4 -> GPIO 2  (LED)     A0 -> ADC0    (0-3.3V)\n"
            "```"
        ),
        "protokoller": "• **I2C (Varsayılan):** D1 (SCL), D2 (SDA)\n• **SPI:** D5 (SCK), D6 (MISO), D7 (MOSI), D8 (CS)"
    },
    "arduino_nano": {
        "baslik": "⚡ Arduino Nano (ATmega328P)",
        "voltaj": "5V Mantık Seviyesi (16 MHz)",
        "aciklama": (
            "**Kritik Özellikler:**\n"
            "• **Analog Pinler:** A0-A7 (A6 ve A7 sadece analog giriş olarak çalışır, dijital I/O yapılamaz!).\n"
            "• **PWM Pinleri:** D3, D5, D6, D9, D10, D11 (~ işareti olanlar).\n"
            "• **Donanımsal Kesmeler (Interrupt):** D2 (INT0) ve D3 (INT1)."
        ),
        "harita": (
            "```text\n"
            "          ┌──────────┐\n"
            "    TXD1 ─┤ D1   VIN ├─ VIN (7-12V)\n"
            "    RXD0 ─┤ D0   GND ├─ GND\n"
            "   RESET ─┤ RST  RST ├─ RESET\n"
            "     GND ─┤ GND  +5V ├─ +5V Out\n"
            "(INT0) D2 ─┤ D2    A7 ├─ Analog In Only\n"
            "(PWM)  D3 ─┤ D3    A6 ├─ Analog In Only\n"
            "       D4 ─┤ D4    A5 ├─ A5 (SCL)\n"
            "(PWM)  D5 ─┤ D5    A4 ├─ A4 (SDA)\n"
            "(PWM)  D6 ─┤ D6    A3 ├─ A3\n"
            "       D7 ─┤ D7    A2 ├─ A2\n"
            "       D8 ─┤ D8    A1 ├─ A1\n"
            "(PWM)  D9 ─┤ D9    A0 ├─ A0\n"
            "(PWM) D10 ─┤ D10  REF ├─ AREF\n"
            "(PWM) D11 ─┤ D11  3V3 ├─ 3.3V Out\n"
            "      D12 ─┤ D12  D13 ├─ D13 (SCK/LED)\n"
            "          └──────────┘\n"
            "```"
        ),
        "protokoller": "• **I2C:** A4 (SDA), A5 (SCL)\n• **SPI:** D11 (MOSI), D12 (MISO), D13 (SCK), D10 (SS)"
    },
    "raspberry_pico": {
        "baslik": "⚡ Raspberry Pi Pico / Pico W (RP2040)",
        "voltaj": "3.3V Mantık Seviyesi (Çift Çekirdek Cortex-M0+ 133MHz)",
        "aciklama": (
            "**Kritik Özellikler:**\n"
            "• **PIO (Programmable I/O):** 8 adet bağımsız donanım durum makinesi ile özel protokoller oluşturulabilir.\n"
            "• **ADC Kanalları:** GP26 (ADC0), GP27 (ADC1), GP28 (ADC2), dahili sıcaklık sensörü (ADC4).\n"
            "• **Tüm GPIO:** Neredeyse tüm pinlerde PWM ve interrupt desteği bulunur."
        ),
        "harita": (
            "```text\n"
            "I2C0: GP0 (SDA), GP1 (SCL)  │  SPI0: GP16 (RX), GP19 (TX), GP18 (SCK)\n"
            "I2C1: GP2 (SDA), GP3 (SCL)  │  UART0: GP0 (TX), GP1 (RX)\n"
            "ADC0: GP26 (Pin 31)         │  ADC1: GP27 (Pin 32)\n"
            "ADC2: GP28 (Pin 34)         │  VBUS: Pin 40 (5V USB)\n"
            "```"
        ),
        "protokoller": "MicroPython, C/C++ SDK ve Arduino IDE ile tam uyumludur."
    },
    "ne555": {
        "baslik": "⏱️ NE555 Timer Entegresi",
        "voltaj": "4.5V - 16V Besleme Gerilimi",
        "aciklama": (
            "**Çalışma Modları:**\n"
            "• **Astable (Karasız):** Kare dalga / osilatör üretimi.\n"
            "  Formül: f = 1.44 / ((R1 + 2*R2) * C)\n"
            "• **Monostable (Tek Kararlı):** Zamanlayıcı / darbe üretici.\n"
            "  Formül: T = 1.1 * R * C"
        ),
        "harita": (
            "```text\n"
            "       ┌───∪───┐\n"
            " GND ─┤ 1   8 ├─ VCC (+4.5V .. +16V)\n"
            "TRIG ─┤ 2   7 ├─ DISCH (Boşalma)\n"
            " OUT ─┤ 3   6 ├─ THRESH (Eşik)\n"
            "RSET ─┤ 4   5 ├─ CTRL (Kontrol Voltajı / 10nF)\n"
            "       └───────┘\n"
            "```"
        ),
        "protokoller": "Çıkış pini (Pin 3) 200mA akım sürebilir veya çekebilir (doğrudan LED/röle sürebilir)."
    },
    "lm7805": {
        "baslik": "🔌 LM7805 (5V Lineer Voltaj Regülatörü)",
        "voltaj": "Giriş: 7V - 25V │ Çıkış: Sabit 5V (Maks 1.5A Soğutucu ile)",
        "aciklama": (
            "**Önemli Bilgiler:**\n"
            "• **Isı Hesabı:** Lineer olduğu için fazla voltaj ısıya dönüşür: P = (Vin - 5V) * Iout.\n"
            "  Örn: 12V girişten 500mA çekerseniz: (12-5) * 0.5 = 3.5 Watt ısı üretir (Soğutucu ŞART!).\n"
            "• **Kapasitörler:** Salınımı önlemek için Girişe 0.33µF, Çıkışa 0.1µF seramik kondansatör bağlanmalıdır."
        ),
        "harita": (
            "```text\n"
            "  TO-220 Ön Yüzü (Yazılar Karşıda):\n"
            "   ┌─────────┐\n"
            "   │  LM7805 │\n"
            "   └─┬───┬───┬─┘\n"
            "     1   2   3\n"
            "     │   │   │\n"
            "  GİRİŞ GND ÇIKIŞ\n"
            " (7-25V)    (+5V)\n"
            "```"
        ),
        "protokoller": "Yüksek verim gerektiren pilli devrelerde bunun yerine DC-DC Step-Down (LM2596 / Buck) önerilir."
    }
}


# ══════════════════════════════════════════════
#  DİRENÇ RENK KODU HESAPLAYICI (Yerel)
# ══════════════════════════════════════════════

RENK_EMOJI = {
    0: ("Siyah", "⬛"),
    1: ("Kahverengi", "🟫"),
    2: ("Kırmızı", "🟥"),
    3: ("Turuncu", "🟧"),
    4: ("Sarı", "🟨"),
    5: ("Yeşil", "🟩"),
    6: ("Mavi", "🟦"),
    7: ("Mor", "🟪"),
    8: ("Gri", "⬜"),
    9: ("Beyaz", "⚪")
}

def direnc_coz(deger_str: str):
    """'220', '10k', '4.7k', '1M' gibi metinleri ohm değerine ve 4 renk bandına çevirir."""
    s = deger_str.lower().strip().replace(',', '.')
    s = re.sub(r'(ohm|[\sΩ])', '', s)
    carpan = 1.0
    if s.endswith('k'):
        s = s[:-1]
        carpan = 1000.0
    elif 'k' in s:
        s = s.replace('k', '.')
        carpan = 1000.0
    elif s.endswith('m'):
        s = s[:-1]
        carpan = 1000000.0
    elif 'm' in s:
        s = s.replace('m', '.')
        carpan = 1000000.0
    elif s.endswith('r'):
        s = s[:-1]
    elif 'r' in s:
        s = s.replace('r', '.')

    try:
        ohm = float(s) * carpan
    except ValueError:
        return None, "Geçerli bir direnç değeri girin (Örn: `220`, `10k`, `4.7k`, `1M`)."

    if ohm < 1 or ohm > 99000000:
        return None, "Direnç değeri 1 Ω ile 99 MΩ arasında olmalıdır."

    log_v = math.floor(math.log10(ohm))
    carpan_ussu = log_v - 1
    carpan_val = 10 ** carpan_ussu
    anlamli = round(ohm / carpan_val)

    if anlamli >= 100:
        anlamli //= 10
        carpan_ussu += 1

    b1 = anlamli // 10
    b2 = anlamli % 10

    if b1 not in RENK_EMOJI or b2 not in RENK_EMOJI or carpan_ussu < 0 or carpan_ussu > 7:
        return None, "Bu değer standart 4 bant renk koduyla gösterilemiyor."

    b1_ad, b1_em = RENK_EMOJI[b1]
    b2_ad, b2_em = RENK_EMOJI[b2]
    c_ad, c_em = RENK_EMOJI[carpan_ussu]

    if ohm >= 1000000:
        gosterim = f"{ohm / 1000000:.2f}".rstrip('0').rstrip('.') + " MΩ"
    elif ohm >= 1000:
        gosterim = f"{ohm / 1000:.2f}".rstrip('0').rstrip('.') + " kΩ"
    else:
        gosterim = f"{int(ohm)} Ω"

    return {
        "ohm": ohm,
        "gosterim": gosterim,
        "b1": f"{b1_em} {b1_ad}",
        "b2": f"{b2_em} {b2_ad}",
        "carpan": f"{c_em} {c_ad} (10^{carpan_ussu})",
        "tolerans": "🪙 Altın (±%5)"
    }, None


# ══════════════════════════════════════════════
#  COG & SLASH GROUP (/lab)
# ══════════════════════════════════════════════

class Elektronik(commands.Cog):
    """Maker & Elektronik Atölye Araçları (%100 Ücretsiz)"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    lab_grup = app_commands.Group(name="lab", description="Elektronik ve maker atölye araçları")

    # ── 1. Pinout Komutu ───────────────────────────

    @lab_grup.command(name="pinout", description="Popüler geliştirme kartlarının ve entegrelerin bacak bağlantılarını gösterir")
    @app_commands.describe(kart="Görüntülenecek kart veya entegre")
    @app_commands.choices(kart=[
        app_commands.Choice(name="ESP32 (WROOM-32 / DevKit)", value="esp32"),
        app_commands.Choice(name="ESP8266 (NodeMCU / D1 Mini)", value="esp8266"),
        app_commands.Choice(name="Arduino Nano (ATmega328P)", value="arduino_nano"),
        app_commands.Choice(name="Raspberry Pi Pico (RP2040)", value="raspberry_pico"),
        app_commands.Choice(name="NE555 Timer Entegresi", value="ne555"),
        app_commands.Choice(name="LM7805 Voltaj Regülatörü", value="lm7805"),
    ])
    async def slash_pinout(self, interaction: discord.Interaction, kart: str):
        veri = PINOUT_VERILERI.get(kart)
        if not veri:
            return await interaction.response.send_message("❌ Kart bilgisi bulunamadı.", ephemeral=True)

        embed = discord.Embed(
            title=veri["baslik"],
            color=discord.Color.from_rgb(46, 204, 113)
        )
        embed.add_field(name="🔋 Gerilim & Mantık", value=veri["voltaj"], inline=False)
        embed.add_field(name="📌 Pin Haritası", value=veri["harita"], inline=False)
        embed.add_field(name="⚠️ Kritik Notlar", value=veri["aciklama"], inline=False)
        if "protokoller" in veri:
            embed.add_field(name="🔌 Protokol Pinleri", value=veri["protokoller"], inline=False)
        embed.set_footer(text="MezarBot • Maker Atölyesi (Yerel Veri)")

        await interaction.response.send_message(embed=embed)

    # ── 2. Direnç Renk Kodu ────────────────────────

    @lab_grup.command(name="direnc", description="Direnç değerinin 4 bant renk kodunu hesaplar")
    @app_commands.describe(deger="Direnç değeri (Örn: 220, 10k, 4.7k, 1M)")
    async def slash_direnc(self, interaction: discord.Interaction, deger: str):
        res, err = direnc_coz(deger)
        if err:
            return await interaction.response.send_message(f"❌ {err}", ephemeral=True)

        embed = discord.Embed(
            title=f"🎨 Direnç Renk Kodu: {res['gosterim']}",
            color=discord.Color.from_rgb(241, 196, 15)
        )
        embed.add_field(name="1. Bant (1. Basamak)", value=res["b1"], inline=True)
        embed.add_field(name="2. Bant (2. Basamak)", value=res["b2"], inline=True)
        embed.add_field(name="3. Bant (Çarpan)", value=res["carpan"], inline=True)
        embed.add_field(name="4. Bant (Tolerans)", value=res["tolerans"], inline=True)
        embed.add_field(name="Tam Değer", value=f"`{res['ohm']:,.0f} Ω`", inline=True)
        embed.set_footer(text="MezarBot • Direnç Renk Hesaplayıcı")

        await interaction.response.send_message(embed=embed)

    # ── 3. Gerilim Bölücü Hesaplayıcı ───────────────

    @lab_grup.command(name="voltaj", description="Gerilim bölücü (Voltage Divider) çıkışını ve akımını hesaplar")
    @app_commands.describe(vin="Giriş voltajı (Volt, örn: 5 veya 12)", r1="Üst direnç (Ohm, örn: 10000 veya 10k)", r2="Alt direnç (Ohm, örn: 10000 veya 10k)")
    async def slash_voltaj(self, interaction: discord.Interaction, vin: float, r1: str, r2: str):
        res1, err1 = direnc_coz(r1)
        res2, err2 = direnc_coz(r2)
        if err1 or err2:
            return await interaction.response.send_message("❌ Direnç değerlerini kontrol edin (Örn: `10k`, `220`).", ephemeral=True)

        r1_val = res1["ohm"]
        r2_val = res2["ohm"]

        vout = vin * (r2_val / (r1_val + r2_val))
        akim_ma = (vin / (r1_val + r2_val)) * 1000.0
        p_r1 = ((vin - vout) ** 2) / r1_val
        p_r2 = (vout ** 2) / r2_val

        embed = discord.Embed(
            title="⚡ Gerilim Bölücü Hesabı",
            color=discord.Color.from_rgb(52, 152, 219)
        )
        embed.add_field(name="Giriş Gerilimi (Vin)", value=f"`{vin:.2f} V`", inline=True)
        embed.add_field(name="Çıkış Gerilimi (Vout)", value=f"**`{vout:.3f} V`**", inline=True)
        embed.add_field(name="Toplam Akım", value=f"`{akim_ma:.3f} mA`", inline=True)
        embed.add_field(name="R1 Direnci & Güç", value=f"`{res1['gosterim']}` ({p_r1*1000:.1f} mW)", inline=True)
        embed.add_field(name="R2 Direnci & Güç", value=f"`{res2['gosterim']}` ({p_r2*1000:.1f} mW)", inline=True)

        if vin >= 4.5 and 3.0 <= vout <= 3.6:
            embed.description = "💡 **İpucu:** Bu oran 5V sinyali 3.3V mikrodenetleyici pinine güvenle düşürmek için uygundur."

        embed.set_footer(text="MezarBot • Vout = Vin * (R2 / (R1 + R2))")
        await interaction.response.send_message(embed=embed)

    # ── 4. LED Ön Direnç Hesaplayıcı ────────────────

    @lab_grup.command(name="led", description="LED için gereken seri ön direnç değerini hesaplar")
    @app_commands.describe(vin="Giriş voltajı (Volt, örn: 5 veya 12)", vled="LED iletim voltajı (Kırmızı: 2.0, Mavi/Beyaz: 3.2)", iled_ma="Hedef LED akımı (mA cinsinden, örn: 15 veya 20)")
    async def slash_led(self, interaction: discord.Interaction, vin: float, vled: float = 2.0, iled_ma: float = 15.0):
        if vin <= vled:
            return await interaction.response.send_message("❌ Giriş voltajı LED voltajından büyük olmalıdır!", ephemeral=True)

        fark_v = vin - vled
        r_ohm = fark_v / (iled_ma / 1000.0)
        p_watt = fark_v * (iled_ma / 1000.0)

        embed = discord.Embed(
            title="💡 LED Seri Ön Direnç Hesabı",
            color=discord.Color.from_rgb(230, 126, 34)
        )
        embed.add_field(name="Hesaplanan Değer", value=f"**`{r_ohm:.1f} Ω`**", inline=True)
        embed.add_field(name="Direnç Üzerindeki Güç", value=f"`{p_watt*1000:.1f} mW` (1/4W uygundur)", inline=True)
        embed.add_field(name="Giriş / LED Voltajı", value=f"`{vin:.1f}V` giriş / `{vled:.1f}V` LED", inline=True)
        embed.description = f"📌 Standart **`{round(r_ohm):d} Ω`** veya bir üst standart değeri kullanabilirsiniz."
        embed.set_footer(text="MezarBot • R = (Vin - Vled) / Iled")

        await interaction.response.send_message(embed=embed)

    # ── 5. AI Devre Danışmanı (Groq Ücretsiz) ───────

    @lab_grup.command(name="soru", description="Yapay zekâya elektronik, devre, gömülü sistem ve kod hatası sor")
    @app_commands.describe(soru="Devre veya kod ile ilgili sorunuz")
    async def slash_devre(self, interaction: discord.Interaction, soru: str):
        await interaction.response.defer()

        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            return await interaction.followup.send("❌ AI servisi yapılandırılmamış.")

        prompt_sistem = (
            "Sen uzman bir elektronik mühendisi, gömülü sistemler uzmanı ve maker asistanısın. "
            "Kullanıcılar sana devre şemaları, mikrodenetleyiciler (ESP32, Arduino, STM32, PIC, Raspberry Pi), "
            "sensörler, lehimleme, gürültü filtreleme, flyback diyotları, pull-up dirençleri ve C++/MicroPython kodları sorar. "
            "Cevapların pratik, mühendislik açısından doğru, net ve doğrudan çözüme odaklı olsun. "
            "Mümkünse komponent önerisi (örn: 100nF dekuplaj kondansatörü, 1N4007 diyot) yap."
        )

        def ai_cagrisi():
            client = Groq(api_key=groq_key)
            modeller = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
            for m in modeller:
                try:
                    resp = client.chat.completions.create(
                        model=m,
                        messages=[
                            {"role": "system", "content": prompt_sistem},
                            {"role": "user", "content": soru}
                        ],
                        max_tokens=600,
                        temperature=0.4
                    )
                    txt = resp.choices[0].message.content or ""
                    txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()
                    if txt:
                        return txt
                except Exception as e:
                    logger.debug(f"Devre AI model denemesi hatası ({m}): {e}")
            return None

        cevap = await self.bot.loop.run_in_executor(None, ai_cagrisi)
        if not cevap:
            return await interaction.followup.send("⚠️ Yanıt alınamadı, lütfen sorunuzu tekrar deneyin.")

        if len(cevap) > 4000:
            cevap = cevap[:3990] + "..."

        embed = discord.Embed(
            title="🔬 AI Devre & Donanım Danışmanı",
            color=discord.Color.from_rgb(155, 89, 182),
            description=cevap
        )
        embed.set_footer(text=f"Soran: {interaction.user.name} • Groq AI (Ücretsiz Katman)")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Elektronik(bot))
