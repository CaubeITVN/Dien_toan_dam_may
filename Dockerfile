FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    CLOUD_STATELESS_ENV=1 \
    LLM_PROVIDER=openrouter \
    OPENROUTER_MODEL=google/gemini-2.0-flash-001 \
    PORT=7860

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-vie \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user

WORKDIR /app

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

RUN mkdir -p /app/.cache/huggingface /app/data/uploads /app/data/processed /app/data/raw /app/data/ocr /app/models/dense /app/cloud_volume \
    && python -c "from huggingface_hub import snapshot_download; snapshot_download('intfloat/multilingual-e5-small')"

COPY . .

RUN chown -R user:user /app

USER user

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import os, urllib.request; p = os.environ.get('PORT', '7860'); urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz', timeout=4)"

CMD ["sh", "-c", "uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
