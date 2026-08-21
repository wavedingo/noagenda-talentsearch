"""Shared test scaffolding.

Media files are generated with the real ffmpeg rather than mocked, because the
thing under test *is* container inspection — a fake probe would happily agree
that a renamed .wav is an MP3, which is exactly the bug spec 8 is worried about.
"""

import io
import os
import subprocess
import tempfile

from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import User
from candidates.models import Candidate
from core.models import Settings


def _ffmpeg(*args):
    subprocess.run(
        [settings.FFMPEG_BIN, "-nostdin", "-y", "-v", "error", *args],
        check=True,
        capture_output=True,
    )


def make_mp3(path, seconds=2, bitrate="64k", title=None, cover=None):
    args = ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    if cover:
        args += ["-i", cover, "-map", "0:a", "-map", "1:v", "-disposition:v:0", "attached_pic"]
    args += ["-codec:a", "libmp3lame", "-b:a", bitrate]
    if title:
        args += ["-metadata", f"title={title}", "-metadata", "artist=Real Name Here"]
    _ffmpeg(*args, path)
    return path


def make_wav(path, seconds=1):
    _ffmpeg("-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", path)
    return path


def make_m4a(path, seconds=1):
    _ffmpeg("-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-codec:a", "aac", path)
    return path


def make_png(path, size="64x64"):
    _ffmpeg("-f", "lavfi", "-i", f"color=c=red:s={size}:d=1", "-frames:v", "1", path)
    return path


def upload_from(path, name="demo.mp3", content_type="audio/mpeg"):
    with open(path, "rb") as handle:
        return SimpleUploadedFile(name, handle.read(), content_type=content_type)


def photo_upload(name="photo.jpg", size=(800, 600), image_format="JPEG"):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, (120, 60, 30)).save(buffer, format=image_format)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def set_runtime_setting(key, value):
    Settings.objects.update_or_create(key=key, defaults={"value_json": value})
    cache.clear()


def make_user(email="producer@example.com", **extra):
    return User.objects.create_user(email=email, **extra)


def make_candidate(email="candidate@example.com", stage_name="The Contender", **extra):
    user = make_user(email=email)
    defaults = {"slug": stage_name.lower().replace(" ", "-"), "stage_name": stage_name}
    defaults.update(extra)
    return Candidate.objects.create(user=user, **defaults)


class MediaTestCase(TestCase):
    """Isolates uploads in a temp directory and clears the settings cache.

    `get_setting()` caches for 60s in a process-wide locmem cache that outlives
    a test's transaction rollback, so a test that changes a runtime setting
    would otherwise leak into whichever test runs next.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._media_dir = tempfile.TemporaryDirectory()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir.name)
        cls._media_override.enable()
        cls.workdir = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        cls._media_dir.cleanup()
        cls.workdir.cleanup()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def work_path(self, name):
        return os.path.join(self.workdir.name, name)
