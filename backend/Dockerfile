FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin \
    && rm -rf /var/lib/apt/lists/*

# Dependencies get their own layer so editing source never reinstalls torch.
# Model weights are deliberately not downloaded here; they live in the model_cache volume.
COPY pyproject.toml requirements.lock ./
RUN python -c "import tomllib; p=tomllib.load(open('pyproject.toml','rb'))['project']; open('/tmp/requirements.txt','w').write('\n'.join(p['dependencies']+p['optional-dependencies']['embeddings']))" \
    && pip install --constraint requirements.lock -r /tmp/requirements.txt

COPY src ./src
RUN pip install --no-deps --no-build-isolation .

RUN useradd --create-home --uid 10001 sakti \
    && mkdir -p /app/data/reports /app/data/processed /app/model-cache \
    && chown -R sakti:sakti /app
USER sakti
EXPOSE 8000
CMD ["uvicorn", "ip_sakti.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
