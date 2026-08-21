"""Demo audio validation and transcoding (spec 3.2, 7, 8).

Pure subprocess work: nothing here touches the database or object storage, so
every rule below is testable against real files. The split between `inspect`
and `transcode` is the split between the two halves of the pipeline --
inspection runs inside the request (ffprobe only reads headers, so it costs
well under a second even on a 50 MB file) and transcoding runs in the
background, because it costs 20-40s on a full-length demo.
"""

import json
import os
import subprocess
import tempfile
from contextlib import contextmanager

from django.conf import settings

PROBE_TIMEOUT_SECONDS = 30
TRANSCODE_TIMEOUT_SECONDS = 600

STREAM_BITRATE = "128k"
STREAM_SAMPLE_RATE = "44100"

MIN_DURATION_SECONDS = 1


class DemoValidationError(Exception):
    """The upload was rejected. The message is written for the uploader."""


class TranscodeError(Exception):
    """ffmpeg could not produce a streaming copy."""


@contextmanager
def uploaded_to_tempfile(uploaded_file, suffix=".mp3"):
    """Django keeps small uploads in memory; ffprobe needs a real path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as handle:
            for chunk in uploaded_file.chunks():
                handle.write(chunk)
        yield path
    finally:
        if os.path.exists(path):
            os.unlink(path)


def probe(path):
    """Return ffprobe's JSON for `path`, or raise DemoValidationError."""
    try:
        result = subprocess.run(
            [
                settings.FFPROBE_BIN,
                "-v", "error",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            capture_output=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:  # pragma: no cover - deployment fault, not user input
        raise RuntimeError(f"ffprobe is not installed ({settings.FFPROBE_BIN})") from exc
    except subprocess.TimeoutExpired as exc:
        raise DemoValidationError("We couldn't read that file — it may be damaged.") from exc

    if result.returncode != 0:
        raise DemoValidationError("That doesn't look like an audio file we can read.")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - ffprobe emitting non-JSON
        raise DemoValidationError("We couldn't read that file — it may be damaged.") from exc


def inspect_demo(path, max_duration_sec):
    """Validate that `path` really is an MP3 of an acceptable length.

    Extension is never consulted (spec 8) -- a .wav renamed to .mp3 fails the
    container check, and an .mp4 carrying an mp3 track fails it too. Returns the
    duration in whole seconds.
    """
    data = probe(path)

    container = data.get("format", {}).get("format_name", "")
    if "mp3" not in container.split(","):
        raise DemoValidationError(
            "That file isn't an MP3. Whatever the filename says, the contents are "
            "something else — please export it as an MP3 and try again."
        )

    streams = data.get("streams", [])
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if len(audio) != 1 or audio[0].get("codec_name") != "mp3":
        raise DemoValidationError(
            "That MP3 has an audio track we can't work with. Please export a "
            "standard single-track MP3 and try again."
        )
    # Embedded cover art is a normal attached-picture stream and is fine on the
    # way in; the transcode drops it. Anything else video-shaped is not.
    for stream in streams:
        if stream.get("codec_type") == "video" and not stream.get("disposition", {}).get("attached_pic"):
            raise DemoValidationError("That file contains video. Demos are audio only.")

    duration = _duration_of(data)
    if duration is None:
        raise DemoValidationError("We couldn't work out how long that recording is.")
    if duration < MIN_DURATION_SECONDS:
        raise DemoValidationError("That file has no audio in it.")
    if duration > max_duration_sec:
        raise DemoValidationError(
            f"That demo runs {_minutes(duration)}, and the limit is "
            f"{_minutes(max_duration_sec)}. Trim it to your strongest stretch and send it over."
        )
    return duration


def _duration_of(data):
    raw = data.get("format", {}).get("duration")
    if raw is None:
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio" and stream.get("duration"):
                raw = stream["duration"]
                break
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return None


def _minutes(seconds):
    minutes = seconds / 60
    if minutes >= 1:
        rounded = round(minutes, 1)
        whole = int(rounded)
        return f"{whole if rounded == whole else rounded} minutes"
    return f"{int(seconds)} seconds"


def transcode_to_stream(src_path, dst_path):
    """Write a 128 kbps streaming copy of `src_path`, stripped of metadata.

    `-map_metadata -1` is the ID3 strip spec 3.2 asks for; `-vn` drops embedded
    artwork, which is both bandwidth nobody asked for and a convenient place to
    hide a payload.
    """
    try:
        result = subprocess.run(
            [
                settings.FFMPEG_BIN,
                "-nostdin",
                "-y",
                "-i", src_path,
                "-vn",
                "-map", "0:a:0",
                "-map_metadata", "-1",
                "-codec:a", "libmp3lame",
                "-b:a", STREAM_BITRATE,
                "-ar", STREAM_SAMPLE_RATE,
                dst_path,
            ],
            capture_output=True,
            timeout=TRANSCODE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:  # pragma: no cover - deployment fault
        raise TranscodeError(f"ffmpeg is not installed ({settings.FFMPEG_BIN})") from exc
    except subprocess.TimeoutExpired as exc:
        raise TranscodeError("transcode timed out") from exc

    if result.returncode != 0:
        tail = result.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]
        raise TranscodeError("ffmpeg failed: " + " / ".join(tail))
    if not os.path.exists(dst_path) or os.path.getsize(dst_path) == 0:
        raise TranscodeError("ffmpeg produced an empty file")
