"""Demo transcoding queue (spec 7: "process asynchronously so uploads don't block").

The queue is the `Demo.processing_state` column; the thread is only an
optimization on top of it. A deploy or crash mid-transcode leaves a row stuck in
`processing`, and `reclaim_stale()` puts it back on the queue -- so the
durability story is the table, and `manage.py process_demos` is a backstop that
needs no scheduler to be correct.

Claiming is a conditional UPDATE checked by row count, so a thread and the
command can never both transcode the same demo.
"""

import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.utils import timezone

from . import storage
from .audio import TranscodeError, transcode_to_stream
from .models import Demo

logger = logging.getLogger(__name__)

# One transcode at a time per process. A burst of uploads should queue, not fork
# N ffmpeg processes on a 512 MB instance.
_TRANSCODE_SLOT = threading.Semaphore(1)


def dispatch(demo):
    """Start transcoding in the background, if background work is enabled."""
    if not settings.DEMO_PROCESS_IN_BACKGROUND:
        return None
    thread = threading.Thread(target=_run_in_thread, args=(demo.pk,), daemon=True)
    thread.start()
    return thread


def _run_in_thread(demo_id):
    with _TRANSCODE_SLOT:
        try:
            process_demo(demo_id)
        except Exception:  # never let a worker thread die silently
            logger.exception("demo processing thread failed for demo %s", demo_id)
        finally:
            # Threads get their own connection; leaving it open leaks a Postgres
            # backend per upload.
            connection.close()


def claim(demo_id):
    """Move a queued demo to `processing`. True if this caller won the claim."""
    claimed = Demo.objects.filter(
        pk=demo_id, processing_state=Demo.ProcessingState.QUEUED
    ).update(
        processing_state=Demo.ProcessingState.PROCESSING,
        processing_started_at=timezone.now(),
        processing_error="",
    )
    return claimed == 1


def process_demo(demo_id):
    """Transcode one demo. Returns the Demo row, or None if it wasn't ours."""
    if not claim(demo_id):
        return None

    demo = Demo.objects.get(pk=demo_id)
    key = storage.new_key()
    try:
        with storage.local_copy(demo.original_path) as source, storage.temp_output() as target:
            transcode_to_stream(source, target)
            stream_path = storage.save_local_file(storage.demo_stream_path(key), target)
    except (TranscodeError, OSError) as exc:
        demo.processing_state = Demo.ProcessingState.FAILED
        demo.processing_error = str(exc)[:2000]
        demo.save(update_fields=["processing_state", "processing_error", "updated_at"])
        logger.error("demo %s failed to transcode: %s", demo_id, exc)
        return demo

    demo.stream_path = stream_path
    demo.processing_state = Demo.ProcessingState.READY
    demo.processed_at = timezone.now()
    demo.processing_error = ""
    demo.save(
        update_fields=["stream_path", "processing_state", "processed_at", "processing_error", "updated_at"]
    )
    logger.info("demo %s transcoded to %s", demo_id, stream_path)
    return demo


def reclaim_stale():
    """Requeue demos whose worker died mid-transcode. Returns how many."""
    cutoff = timezone.now() - timedelta(minutes=settings.DEMO_STALE_PROCESSING_MINUTES)
    stale = Demo.objects.filter(
        processing_state=Demo.ProcessingState.PROCESSING, processing_started_at__lt=cutoff
    )
    count = stale.update(processing_state=Demo.ProcessingState.QUEUED, processing_started_at=None)
    if count:
        logger.warning("requeued %d demo(s) abandoned mid-transcode", count)
    return count


def drain_queue():
    """Process everything queued, oldest first. Returns (processed, failed)."""
    reclaim_stale()
    processed = failed = 0
    queued = list(
        Demo.objects.filter(processing_state=Demo.ProcessingState.QUEUED)
        .order_by("created_at")
        .values_list("pk", flat=True)
    )
    for demo_id in queued:
        demo = process_demo(demo_id)
        if demo is None:
            continue
        if demo.processing_state == Demo.ProcessingState.FAILED:
            failed += 1
        else:
            processed += 1
    return processed, failed
