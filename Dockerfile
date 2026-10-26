# Backend: data pipeline scripts + FastAPI service.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APEXLENS_DATA_DIR=/app/data \
    APEXLENS_REPORTS_DIR=/app/reports

# libgomp1: LightGBM runtime; git: F1DB checkout during ingestion
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .
COPY scripts ./scripts
COPY docs ./docs

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
CMD ["uvicorn", "apexlens.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
