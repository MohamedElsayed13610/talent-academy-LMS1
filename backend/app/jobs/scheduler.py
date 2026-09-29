"""Shared job runner (ARCHITECTURE.md §8): every job takes a Postgres advisory lock before doing
anything, so a second backend instance (or an overlapping run) never duplicates work, and logs its
outcome to job_runs. The scheduler itself is a single in-process APScheduler — cheap, and correct
as long as every job goes through run_locked() rather than assuming it's the only instance running.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.base import STATE_STOPPED
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.audit import JobRun

logger = logging.getLogger("app.jobs")

# Arbitrary but stable advisory-lock keys, one per job (Postgres advisory locks are a single
# global namespace keyed by a bigint, not the job name).
LOCK_KEYS: dict[str, int] = {
    "auto_submit": 1001,
    "file_cleanup": 1002,
    "orphan_sweep": 1003,
    "backup": 1004,
    "session_prune": 1005,
}

# Africa/Cairo has used a fixed UTC+2 offset year-round (no DST) since 2016, so "03:00 Cairo" is
# simply "01:00 UTC" with no seasonal correction ever needed.
_CAIRO_UTC_OFFSET_HOURS = 2
_BACKUP_HOUR_UTC = 3 - _CAIRO_UTC_OFFSET_HOURS

_scheduler: BackgroundScheduler | None = None


def _next_backup_run(now: datetime) -> datetime:
    """The next 01:00 UTC (03:00 Africa/Cairo) at or after `now` -- the anchor for the every-3-days
    interval below, so the job always lands on that same wall-clock time regardless of when the
    process happens to start."""
    candidate = now.replace(hour=_BACKUP_HOUR_UTC, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def _get_scheduler() -> BackgroundScheduler:
    global _scheduler
    # APScheduler's BackgroundScheduler can't be restarted once shut down (its internal executor
    # thread pool is gone for good) — build a fresh one rather than reusing a dead instance. In
    # production this function runs once per process; the guard mainly protects test suites and
    # dev-reload cycles that start/stop the app's lifespan repeatedly in one process.
    if _scheduler is None or _scheduler.state == STATE_STOPPED:
        _scheduler = BackgroundScheduler(timezone="UTC")
    return _scheduler


def run_locked(job_name: str, fn: Callable[[], str]) -> None:
    lock_key = LOCK_KEYS[job_name]
    started_at = datetime.now(timezone.utc)
    with SessionLocal() as db:
        got_lock = db.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_key})
        if not got_lock:
            return  # another instance/run already holds it — skip silently, this is normal
        try:
            detail = fn()
            db.add(JobRun(job_name=job_name, started_at=started_at, finished_at=datetime.now(timezone.utc), status="ok", detail=detail[:500]))
            db.commit()
        except Exception as exc:  # noqa: BLE001 — a job failure must never crash the scheduler thread
            logger.exception("job %s failed", job_name)
            db.rollback()
            db.add(JobRun(job_name=job_name, started_at=started_at, finished_at=datetime.now(timezone.utc), status="failed", detail=str(exc)[:500]))
            db.commit()
        finally:
            db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_key})
            db.commit()


def start() -> None:
    from app.jobs.auto_submit import run as run_auto_submit
    from app.jobs.backup import run as run_backup
    from app.jobs.file_cleanup import run as run_file_cleanup

    scheduler = _get_scheduler()
    if not scheduler.running:
        # misfire_grace_time=None: APScheduler's default (1 second) silently drops a scheduled run
        # if the executor gets to it even slightly late -- easy to hit under normal jitter (a busy
        # event loop, a slow DB round-trip, the dev reloader's file-watcher), and observed in
        # practice to make auto_submit tick "missed" indefinitely instead of running. None means a
        # late run still fires (coalesced with any other pending runs) rather than being skipped --
        # correctness here matters more than exact timing.
        scheduler.add_job(lambda: run_locked("file_cleanup", run_file_cleanup), "interval", minutes=5, id="file_cleanup", next_run_time=datetime.now(timezone.utc), misfire_grace_time=None)
        # Every 30s per ARCHITECTURE.md §8 -- expired in-progress attempts must resolve promptly
        # even if the student never comes back to the tab.
        scheduler.add_job(lambda: run_locked("auto_submit", run_auto_submit), "interval", seconds=30, id="auto_submit", next_run_time=datetime.now(timezone.utc), misfire_grace_time=None)
        # Every 3 days at 03:00 Africa/Cairo (01:00 UTC) -- Scope E. start_date anchors the first
        # run to that wall-clock time (not "3 days after process start"), and every run after it
        # lands on the same hour since the interval is a whole number of days.
        scheduler.add_job(
            lambda: run_locked("backup", run_backup), "interval", days=3,
            start_date=_next_backup_run(datetime.now(timezone.utc)), id="backup", misfire_grace_time=3600,
        )
        scheduler.start()


def stop() -> None:
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
