"""Shared job runner (ARCHITECTURE.md §8): every job takes a Postgres advisory lock before doing
anything, so a second backend instance (or an overlapping run) never duplicates work, and logs its
outcome to job_runs. The scheduler itself is a single in-process APScheduler — cheap, and correct
as long as every job goes through run_locked() rather than assuming it's the only instance running.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

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

_scheduler: BackgroundScheduler | None = None


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
    from app.jobs.file_cleanup import run as run_file_cleanup

    scheduler = _get_scheduler()
    if not scheduler.running:
        scheduler.add_job(lambda: run_locked("file_cleanup", run_file_cleanup), "interval", minutes=5, id="file_cleanup", next_run_time=datetime.now(timezone.utc))
        scheduler.start()


def stop() -> None:
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
