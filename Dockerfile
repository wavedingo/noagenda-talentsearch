FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exists so WhiteNoise doesn't warn about a missing STATIC_ROOT in dev/test,
# where collectstatic is never run (only production's preDeployCommand runs it).
RUN mkdir -p staticfiles

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
