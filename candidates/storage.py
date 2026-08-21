"""Object-storage key layout and helpers (spec 7, A.4).

Everything goes through `default_storage`, which is R2 when the credentials are
configured and local disk otherwise (see `config/settings.py`). Nothing outside
this module builds a key by hand.

The `private/` and `public/` split is load-bearing. Only the transcoded stream
copy is stripped of metadata, so the original -- which still carries whatever
ID3 tags, cover art and authoring software the uploader's machine wrote into it
-- lives under `private/` and is never rendered in any template. R2's public
custom domain serves the whole bucket, so blocking `/private/*` at Cloudflare is
part of the deployment checklist rather than something the app can enforce.
"""

import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

DEMO_ORIGINAL_TEMPLATE = "private/demos/{key}/original.mp3"
DEMO_STREAM_TEMPLATE = "public/demos/{key}/stream.mp3"
PHOTO_TEMPLATE = "public/photos/{key}.jpg"


def new_key():
    """An unguessable path component, so a pending submission can't be found by
    walking predictable URLs."""
    return uuid.uuid4().hex


def demo_original_path(key):
    return DEMO_ORIGINAL_TEMPLATE.format(key=key)


def demo_stream_path(key):
    return DEMO_STREAM_TEMPLATE.format(key=key)


def photo_path(key):
    return PHOTO_TEMPLATE.format(key=key)


def save_bytes(path, data):
    return default_storage.save(path, ContentFile(data))


def save_local_file(path, local_path):
    with open(local_path, "rb") as handle:
        return default_storage.save(path, ContentFile(handle.read()))


def delete(path):
    if path and default_storage.exists(path):
        default_storage.delete(path)


@contextmanager
def local_copy(path, suffix=".mp3"):
    """Materialise a stored object on local disk so ffmpeg can read it."""
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        with default_storage.open(path, "rb") as source, open(tmp_path, "wb") as target:
            shutil.copyfileobj(source, target)
        yield tmp_path
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@contextmanager
def temp_output(suffix=".mp3"):
    """A path ffmpeg can write to, cleaned up afterwards."""
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        yield tmp_path
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
