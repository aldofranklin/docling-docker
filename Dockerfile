FROM python:3.10.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/huggingface \
    TRANSFORMERS_CACHE=/models/huggingface \
    TORCH_HOME=/models/torch

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libmagic1 \
    tesseract-ocr \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt /app/requirements-docker.txt

RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /app/requirements-docker.txt

COPY docling_worker.py /app/docling_worker.py

RUN mkdir -p /data/input /data/output /models/huggingface /models/torch

CMD ["python", "/app/docling_worker.py"]
