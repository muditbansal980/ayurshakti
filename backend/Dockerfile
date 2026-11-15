FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY requirements.lock ./
COPY src ./src
RUN pip install --constraint requirements.lock '.[embeddings]'

RUN useradd --create-home --uid 10001 sakti \
    && mkdir -p /app/data/reports /app/data/processed /app/model-cache \
    && chown -R sakti:sakti /app
USER sakti
EXPOSE 8000
CMD ["uvicorn", "ip_sakti.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

