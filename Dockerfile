FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .


FROM python:3.12-slim

RUN useradd --create-home app
WORKDIR /home/app
USER app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --chown=app web/ web/

ENV WEB_DIR=/home/app/web

EXPOSE 8080

# Cloud Run tells the container which port to listen on via $PORT (8080 unless it says otherwise).
CMD ["sh", "-c", "exec uvicorn traininglogs.api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
