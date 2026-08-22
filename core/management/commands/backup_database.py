"""Write a database dump to private/backups/ via default_storage (R2 in prod)."""

import os
import subprocess
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Dump the database to private/backups/YYYY-MM-DD.dump"

    def handle(self, *args, **options):
        stamp = datetime.now(dt_timezone.utc).strftime("%Y-%m-%d")
        key = f"private/backups/{stamp}.dump"
        vendor = connection.vendor
        if vendor == "postgresql":
            data = _pg_dump()
        elif vendor == "sqlite":
            data = _sqlite_copy()
        else:
            raise CommandError(f"No backup path for {vendor}")
        default_storage.save(key, ContentFile(data))
        self.stdout.write(self.style.SUCCESS(f"Wrote {key} ({len(data)} bytes)"))


def _pg_dump():
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise CommandError("DATABASE_URL is not set")
    pg_dump = os.environ.get("PG_DUMP_BIN", "pg_dump")
    try:
        result = subprocess.run(
            [pg_dump, "--no-owner", "--no-acl", "--dbname", database_url],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise CommandError(f"{pg_dump} is not installed in this image") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace")
        if "server version mismatch" in stderr:
            raise CommandError(
                stderr
                + "The image needs a pg_dump at least as new as the Render "
                "Postgres major version. See PG_DUMP_BIN in the Dockerfile."
            ) from exc
        raise CommandError(stderr) from exc
    return result.stdout


def _sqlite_copy():
    """File-backed SQLite is a copy; the in-memory test DB is an SQL dump."""
    name = settings.DATABASES["default"].get("NAME")
    if isinstance(name, str) and not str(name).startswith("file:"):
        try:
            with open(name, "rb") as handle:
                return handle.read()
        except FileNotFoundError:
            pass
    buf = []
    for line in connection.connection.iterdump():
        buf.append(line)
    return ("\n".join(buf) + "\n").encode("utf-8")
