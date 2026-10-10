# MezarBot — Docker imajı
FROM denoland/deno:bin AS deno

FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    MEZARBOT_DB=/app/data/mezarbot.db \
    HOME=/app/data XDG_CACHE_HOME=/app/data/.cache TMPDIR=/app/data/tmp
# FFmpeg (ses), Deno (yt-dlp'nin YouTube JS çözümü)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=deno /deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# uid 1000 = çoğu Linux masaüstündeki ilk kullanıcı → ./data birimine yazabilir (farklıysa: sudo chown -R 1000 data)
RUN useradd --uid 1000 --home /app/data mezarbot \
    && mkdir -p /app/data/tmp && chown -R mezarbot /app
USER mezarbot
CMD ["python", "main.py"]
