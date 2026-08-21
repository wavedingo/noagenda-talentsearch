"""Profile photo handling (spec 3.2: jpg/png/webp, max 5 MB, server-side resized).

Every accepted image is re-encoded, never passed through. Re-encoding is what
strips EXIF -- including the GPS tag a phone camera writes -- so it happens even
when the upload is already small enough, and it means the bytes we serve were
produced by Pillow rather than by whatever wrote the original file.
"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

PHOTO_MAX_BYTES = 5 * 1024 * 1024
PHOTO_BOX = (600, 600)
PHOTO_QUALITY = 85
# Well under Pillow's own decompression-bomb ceiling: a headshot has no business
# being 50 megapixels, and decoding one costs ~200 MB of RAM on a small dyno.
PHOTO_MAX_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class PhotoValidationError(Exception):
    """The photo was rejected. The message is written for the uploader."""


def process_photo(uploaded_file):
    """Return JPEG bytes for `uploaded_file`, resized and stripped of metadata."""
    if uploaded_file.size > PHOTO_MAX_BYTES:
        raise PhotoValidationError(
            f"That photo is larger than {PHOTO_MAX_BYTES // (1024 * 1024)} MB. "
            "Most phones can export a smaller copy."
        )

    data = uploaded_file.read()
    try:
        probe = Image.open(io.BytesIO(data))
        image_format = probe.format
        width, height = probe.size
    except (UnidentifiedImageError, OSError) as exc:
        raise PhotoValidationError("That doesn't look like an image file.") from exc

    if image_format not in ALLOWED_FORMATS:
        raise PhotoValidationError("Photos need to be a JPG, PNG, or WebP.")
    if width * height > PHOTO_MAX_PIXELS:
        raise PhotoValidationError("That image is too large to process. Please send a smaller copy.")

    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
        image.thumbnail(PHOTO_BOX, Image.LANCZOS)
    except OSError as exc:
        raise PhotoValidationError("We couldn't read that image — it may be damaged.") from exc

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=PHOTO_QUALITY, optimize=True)
    return out.getvalue()
