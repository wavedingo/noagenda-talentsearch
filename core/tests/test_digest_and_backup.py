from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from core.management.commands.backup_database import _pg_dump
from core.management.commands.send_admin_digest import build_digest


class DigestTests(TestCase):
    def test_digest_mentions_empty_queue_and_no_spikes(self):
        body = build_digest()
        self.assertIn("Signups in the last 24 hours:", body)
        self.assertIn("Vote-velocity spikes: none", body)

    def test_command_sends_mail(self):
        call_command("send_admin_digest", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("daily digest", mail.outbox[0].subject)


class BackupTests(TestCase):
    def test_sqlite_backup_writes_a_private_key(self):
        out = StringIO()
        call_command("backup_database", stdout=out)
        self.assertIn("private/backups/", out.getvalue())

    @patch.dict("os.environ", {"DATABASE_URL": "postgres://x", "PG_DUMP_BIN": "/usr/lib/postgresql/18/bin/pg_dump"})
    @patch("core.management.commands.backup_database.subprocess.run")
    def test_pg_dump_uses_the_versioned_binary(self, run):
        run.return_value.stdout = b"DUMP"
        self.assertEqual(_pg_dump(), b"DUMP")
        self.assertEqual(run.call_args.args[0][0], "/usr/lib/postgresql/18/bin/pg_dump")
