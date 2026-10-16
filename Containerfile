# --- Frontend build ---
FROM docker.io/library/node:24-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Runtime ---
FROM docker.io/library/python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PENDEL_DATA_DIR=/data PENDEL_STATIC_DIR=/app/static
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/pendel ./pendel
RUN pip install --no-cache-dir --root-user-action=ignore . && useradd --uid 1000 --no-create-home pendel && mkdir /data && chown pendel /data
COPY --from=frontend /src/build ./static
USER pendel
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "pendel.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
