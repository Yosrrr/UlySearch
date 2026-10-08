FROM node:22-trixie-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PORT=10000 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       poppler-utils tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.txt \
    && python -m playwright install --with-deps chromium

COPY backend/ /app/backend/
COPY --from=frontend-build /build/frontend/dist/ /app/frontend/dist/

RUN mkdir -p /app/backend/data /app/backend/debug_detail /app/data /app/debug_detail /tmp \
    && chown -R pwuser:pwuser /app /tmp

USER pwuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "10000", \
     "--proxy-headers", "--forwarded-allow-ips", "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"]