FROM node:24-slim AS frontend

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml requirements.lock ./
COPY src/ src/

# Exactly the versions in the lock file, so every build runs what was tested.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.lock \
    && pip install --no-cache-dir --no-deps .


FROM python:3.12-slim

RUN useradd --create-home app
WORKDIR /home/app
USER app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --chown=app --from=frontend /frontend/dist frontend/

ENV APP_DIR=/home/app/frontend

EXPOSE 8080

# Cloud Run tells the container which port to listen on via $PORT (8080 unless it says otherwise).
CMD ["sh", "-c", "exec uvicorn traininglogs.api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
