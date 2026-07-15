# syntax=docker/dockerfile:1

# ---- Stage 1: build the React frontend into static files ----
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend

# No committed lockfile: resolve fresh from the public registry. --include=dev
# is required because tsc/vite (needed by `npm run build`) are devDependencies.
COPY frontend/package.json ./
RUN npm install --include=dev

# Compile the SPA -> /app/frontend/dist (tsc -b && vite build).
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py

WORKDIR /app

# Python dependencies (all ship manylinux wheels — no build toolchain needed).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source.
COPY app.py config.py entrypoint.sh ./
COPY identityhub/ ./identityhub/
COPY migrations/ ./migrations/
# The OpenAPI spec is served at /api/docs (Swagger UI) and /api/openapi.yaml.
COPY docs/openapi.yaml ./docs/openapi.yaml
# Strip CRLF before making it executable: Git on Windows may check the script
# out with \r line endings, which would break the shebang inside the container
# (exec would look for an interpreter named "/bin/sh\r").
RUN sed -i 's/\r$//' ./entrypoint.sh && chmod +x ./entrypoint.sh

# Built frontend from stage 1 — Flask serves this via the serve_spa route,
# which resolves the SPA at <repo>/frontend/dist (i.e. /app/frontend/dist).
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Run as an unprivileged user with a writable /data dir for the SQLite volume.
# Creating and chowning /data here means the named volume inherits appuser
# ownership the first time it is mounted.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
