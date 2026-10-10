"""
Groq (ücretsiz katman) ortak yardımcıları — AI sohbet, !ciz prompt çevirisi ve çeviri köprüsü aynı kodu kullanır.
- Tek paylaşılan istemci (GROQ_API_KEY boşsa None → özellik kapalı, çökme yok).
- Model yedekleme: Groq bir modeli kaldırırsa (404) ya da boş cevap verirse sıradaki model denenir.
- Senkron: çağıran taraf thread'de çalıştırır (run_in_executor / asyncio.to_thread).
"""
import logging
import os
import re

from groq import Groq

logger = logging.getLogger('MezarBot.Groq')

# Sırayla denenir. (2026-09: llama-3.3-70b-versatile kaldırıldı → "bi hata oldu ya, kusura bakma" hatasının sebebi.)
# Düşünen modellerde düşünme metni cevap kotasından yer; bu yüzden düşünme düşük/gizli tutulur.
AI_MODELLERI = (
    ("openai/gpt-oss-120b", {"reasoning_effort": "low"}),
    ("qwen/qwen3.8-27b", {"reasoning_format": "hidden"}),
    ("openai/gpt-oss-20b", {"reasoning_effort": "low"}),
)
# Kısa/basit işler (çeviri): önce hızlı model
HIZLI_MODELLER = (AI_MODELLERI[2], AI_MODELLERI[1], AI_MODELLERI[0])

_DUSUNME = re.compile(r"<think>.*?</think>", re.S)
_istemci = None


def groq_istemci():
    """Paylaşılan Groq istemcisi; GROQ_API_KEY yoksa ya da başlatılamazsa None."""
    global _istemci
    if _istemci is None:
        anahtar = (os.getenv("GROQ_API_KEY") or "").strip()
        if not anahtar:
            return None
        try:
            _istemci = Groq(api_key=anahtar)
        except Exception as e:
            logger.error(f"Groq başlatma hatası: {e}")
            return None
    return _istemci


def groq_tamamla(client, mesajlar, temperature, max_tokens, modeller=AI_MODELLERI):
    """Modelleri sırayla dener; ilk dolu cevabı döner. Hepsi başarısızsa None (hata loglanır). Senkron."""
    if client is None:
        return None
    son_hata = None
    for model, ek in modeller:
        try:
            yanit = client.chat.completions.create(messages=mesajlar, model=model, temperature=temperature,
                                                   max_tokens=max_tokens, **ek)
            metin = (yanit.choices[0].message.content or "") if yanit.choices else ""
            metin = _DUSUNME.sub("", metin).strip()
            if metin:
                return metin
            son_hata = f"{model}: boş cevap"
        except Exception as e:
            son_hata = f"{model}: {e}"
            logger.warning(f"AI modeli başarısız, sıradaki deneniyor — {son_hata[:200]}")
    logger.error(f"AI: tüm modeller başarısız — {str(son_hata)[:300]}")
    return None
