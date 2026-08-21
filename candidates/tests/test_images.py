import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from candidates.images import PHOTO_BOX, PhotoValidationError, process_photo
from candidates.tests.helpers import photo_upload

EXIF_MAKE = 0x010F
EXIF_DATETIME = 0x0132
EXIF_ORIENTATION = 0x0112


class ProcessPhotoTests(SimpleTestCase):
    def test_resizes_within_the_box_and_keeps_aspect_ratio(self):
        result = Image.open(io.BytesIO(process_photo(photo_upload(size=(1600, 900)))))
        self.assertLessEqual(result.width, PHOTO_BOX[0])
        self.assertLessEqual(result.height, PHOTO_BOX[1])
        self.assertAlmostEqual(result.width / result.height, 16 / 9, places=1)

    def test_always_re_encodes_as_jpeg(self):
        result = Image.open(io.BytesIO(process_photo(photo_upload(size=(200, 200), image_format="PNG"))))
        self.assertEqual(result.format, "JPEG")

    def test_strips_exif(self):
        """Re-encoding is the point: a phone photo carries the camera, the
        timestamp, and often GPS coordinates."""
        upload = _photo_with_exif()
        self.assertIn(EXIF_MAKE, Image.open(io.BytesIO(upload.read())).getexif())
        upload.seek(0)

        result = Image.open(io.BytesIO(process_photo(upload)))
        self.assertEqual(dict(result.getexif()), {})

    def test_applies_the_orientation_tag_before_discarding_it(self):
        """Orientation 6 means "rotate 90°". Dropping EXIF without applying it
        first would leave every phone portrait shot on its side."""
        upload = _photo_with_exif(size=(400, 300), orientation=6)
        result = Image.open(io.BytesIO(process_photo(upload)))
        self.assertGreater(result.height, result.width)

    def test_rejects_a_non_image(self):
        upload = SimpleUploadedFile("photo.jpg", b"definitely not an image", content_type="image/jpeg")
        with self.assertRaises(PhotoValidationError):
            process_photo(upload)

    def test_rejects_an_oversize_file(self):
        upload = SimpleUploadedFile("big.jpg", b"\xff\xd8" + b"\x00" * (6 * 1024 * 1024))
        with self.assertRaises(PhotoValidationError) as caught:
            process_photo(upload)
        self.assertIn("MB", str(caught.exception))


def _photo_with_exif(size=(400, 300), orientation=1):
    exif = Image.Exif()
    exif[EXIF_MAKE] = "TestCam"
    exif[EXIF_DATETIME] = "2026:08:20 10:00:00"
    exif[EXIF_ORIENTATION] = orientation

    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 20, 30)).save(buffer, format="JPEG", exif=exif)
    return SimpleUploadedFile("exif.jpg", buffer.getvalue(), content_type="image/jpeg")
