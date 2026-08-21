"""Upload validation and transcoding.

Spec 9 names upload validation as one of the four places a silent bug would hurt
most, so every case here runs against a file ffmpeg actually produced.
"""

from candidates.audio import (
    DemoValidationError,
    inspect_demo,
    probe,
    transcode_to_stream,
)
from candidates.tests.helpers import MediaTestCase, make_m4a, make_mp3, make_png, make_wav


class InspectDemoTests(MediaTestCase):
    def test_accepts_a_real_mp3(self):
        path = make_mp3(self.work_path("good.mp3"), seconds=3)
        self.assertAlmostEqual(inspect_demo(path, max_duration_sec=900), 3, delta=1)

    def test_rejects_a_wav_renamed_to_mp3(self):
        """The A.7 smoke test in person: content inspection, not extension."""
        path = make_wav(self.work_path("real.wav"))
        renamed = self.work_path("disguised.mp3")
        with open(path, "rb") as source, open(renamed, "wb") as target:
            target.write(source.read())

        with self.assertRaises(DemoValidationError) as caught:
            inspect_demo(renamed, max_duration_sec=900)
        self.assertIn("isn't an MP3", str(caught.exception))

    def test_rejects_an_m4a_renamed_to_mp3(self):
        path = make_m4a(self.work_path("real.m4a"))
        renamed = self.work_path("disguised2.mp3")
        with open(path, "rb") as source, open(renamed, "wb") as target:
            target.write(source.read())

        with self.assertRaises(DemoValidationError):
            inspect_demo(renamed, max_duration_sec=900)

    def test_rejects_a_text_file_with_an_mp3_extension(self):
        path = self.work_path("notes.mp3")
        with open(path, "w") as handle:
            handle.write("this is not audio, it is a shopping list\n" * 50)

        with self.assertRaises(DemoValidationError):
            inspect_demo(path, max_duration_sec=900)

    def test_rejects_an_over_length_demo_with_a_friendly_message(self):
        path = make_mp3(self.work_path("long.mp3"), seconds=8)
        with self.assertRaises(DemoValidationError) as caught:
            inspect_demo(path, max_duration_sec=5)
        message = str(caught.exception)
        self.assertIn("Trim it", message)
        self.assertNotIn("Traceback", message)

    def test_accepts_a_demo_exactly_at_the_limit(self):
        """The boundary is inclusive: a demo bang on the limit is fine."""
        path = make_mp3(self.work_path("boundary.mp3"), seconds=4)
        duration = inspect_demo(path, max_duration_sec=900)
        self.assertEqual(inspect_demo(path, max_duration_sec=duration), duration)
        with self.assertRaises(DemoValidationError):
            inspect_demo(path, max_duration_sec=duration - 1)

    def test_rejects_a_file_with_no_audio(self):
        path = self.work_path("empty.mp3")
        open(path, "wb").close()
        with self.assertRaises(DemoValidationError):
            inspect_demo(path, max_duration_sec=900)

    def test_tolerates_embedded_cover_art(self):
        """Cover art is a normal attached-picture stream on the way in. The
        transcode drops it; validation shouldn't reject it."""
        cover = make_png(self.work_path("cover.png"))
        path = make_mp3(self.work_path("with-art.mp3"), seconds=2, cover=cover)
        self.assertGreaterEqual(inspect_demo(path, max_duration_sec=900), 1)


class TranscodeTests(MediaTestCase):
    def test_produces_a_playable_mp3_of_the_same_length(self):
        source = make_mp3(self.work_path("source.mp3"), seconds=4, bitrate="320k")
        target = self.work_path("stream.mp3")

        transcode_to_stream(source, target)

        data = probe(target)
        self.assertIn("mp3", data["format"]["format_name"].split(","))
        self.assertAlmostEqual(float(data["format"]["duration"]), 4, delta=1)

    def test_normalizes_to_128kbps(self):
        source = make_mp3(self.work_path("fat.mp3"), seconds=4, bitrate="320k")
        target = self.work_path("thin.mp3")

        transcode_to_stream(source, target)

        bitrate = int(probe(target)["format"]["bit_rate"])
        self.assertAlmostEqual(bitrate, 128_000, delta=8_000)

    def test_strips_id3_tags_from_the_streaming_copy(self):
        """Spec 3.2. The uploader's tags can carry their real name."""
        source = make_mp3(self.work_path("tagged.mp3"), seconds=2, title="My Audition")
        self.assertIn("title", _tags(source))

        target = self.work_path("untagged.mp3")
        transcode_to_stream(source, target)

        tags = _tags(target)
        self.assertNotIn("title", tags)
        self.assertNotIn("artist", tags)

    def test_drops_embedded_cover_art(self):
        cover = make_png(self.work_path("art.png"))
        source = make_mp3(self.work_path("arty.mp3"), seconds=2, cover=cover)
        self.assertTrue(_has_video_stream(source))

        target = self.work_path("artless.mp3")
        transcode_to_stream(source, target)

        self.assertFalse(_has_video_stream(target))


def _tags(path):
    return {key.lower() for key in probe(path).get("format", {}).get("tags", {})}


def _has_video_stream(path):
    return any(s.get("codec_type") == "video" for s in probe(path).get("streams", []))
