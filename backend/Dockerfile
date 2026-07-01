# Central Intelligence backend image — serves the API, and (with a different
# command) the Celery worker and beat. One image, three roles; see
# docker-compose.yml at the project root.
#
# Python 3.12: stack targets >=3.11; the audioop-lts backport in requirements
# only installs on 3.13+, so on 3.12 the stdlib audioop is used.
FROM python:3.12-slim

# System deps:
#   - ffmpeg     : pydub / faster-whisper (call transcription) need it at runtime
#   - build-essential + libpq-dev : building psycopg2 / native wheels
#   - curl       : container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install deps first so the layer caches when only app code changes.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code.
COPY . .

EXPOSE 8000

# Default command runs the API. The worker and beat services in
# docker-compose.yml override this with their own celery commands.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
