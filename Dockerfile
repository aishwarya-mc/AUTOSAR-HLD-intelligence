FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# tesseract enables the OCR fallback for scanned pages
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY frontend ./frontend
COPY data/sample ./data/sample
COPY scripts/start_single.sh ./scripts/start_single.sh

RUN useradd -m appuser && mkdir -p data/uploads data/db && chown -R appuser /srv
USER appuser

EXPOSE 8000 8501
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
