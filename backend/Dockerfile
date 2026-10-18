FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# The API runs as an unprivileged user. It only reads /app and talks to the database over the
# network, so it needs no write access to anything.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .
USER app

EXPOSE 8000

# Render sets PORT; local Docker uses 8000. app.healthcheck asks GET /health on that same port.
# start-period leaves room for the database wait and migrations that run before the API listens.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-m", "app.healthcheck"]

# app.serve waits for the database, runs migrations, seeds an EMPTY database if SEED_ON_START is
# true (never resets), then runs uvicorn in the same process. See backend/app/serve.py.
CMD ["python", "-m", "app.serve"]
