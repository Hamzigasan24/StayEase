# StayEase API — production-oriented image (Step 14).
# No --reload here; no .env is ever copied in (see .dockerignore).
# Runtime config comes from environment variables / compose file.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps kept minimal (psycopg-binary needs libpq at runtime).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Run as non-root.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# App reads APP_ENV/DEBUG/DATABASE_URL/... from the environment.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
