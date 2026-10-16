# Pendel – single image: SvelteKit SPA built in a Node stage, served by the FastAPI backend.
# Build: docker build -f Containerfile -t pendel .

# --- Frontend build ---
FROM docker.io/library/node:25-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Runtime ---
FROM docker.io/library/python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PENDEL_DATA_DIR=/data PENDEL_STATIC_DIR=/app/static PENDEL_PORT=8000 \
    TZ=Europe/Berlin
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/pendel ./pendel
RUN pip install --no-cache-dir --root-user-action=ignore . && mkdir /data
COPY --from=frontend /src/build ./static
COPY deploy/container-entrypoint.sh /usr/local/bin/pendel-entrypoint
RUN chmod 0755 /usr/local/bin/pendel-entrypoint
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PENDEL_PORT', '8000')}/api/health\", timeout=4)"]
ENTRYPOINT ["/usr/local/bin/pendel-entrypoint"]
