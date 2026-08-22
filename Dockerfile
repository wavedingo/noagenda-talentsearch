FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Render Postgres is 18. Debian's postgresql-client is 17 and pg_dump
    # refuses to dump a newer server. The 18 binary lives here after the
    # PGDG install below; the backup command reads this so PATH cannot
    # silently pick the distro 17 again.
    PG_DUMP_BIN=/usr/lib/postgresql/18/bin/pg_dump

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        curl \
        gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exists so WhiteNoise doesn't warn about a missing STATIC_ROOT in dev/test,
# where collectstatic is never run (only production's preDeployCommand runs it).
RUN mkdir -p staticfiles

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
