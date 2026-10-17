"""Bounded in-memory model jobs with cancellation and expiry."""
from __future__ import annotations
import secrets
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Callable
from .core import InputError
from .model_cli import ModelCancelled
from .providers import ProviderError

class BusyError(RuntimeError):
    pass

@dataclass
class Job:
    id: str
    created: float
    cancel: threading.Event = field(default_factory=threading.Event)
    state: str = 'running'
    result: dict | None = None
    error: str | None = None
    finished: float | None = None

class Jobs:
    def __init__(self, semaphore: threading.BoundedSemaphore | None = None, *,
                 retention_seconds: float = 900, cleanup_interval: float = 1):
        if (not math.isfinite(retention_seconds) or retention_seconds <= 0 or
                not math.isfinite(cleanup_interval) or cleanup_interval <= 0):
            raise ValueError('작업 기록 보관 시간은 양수여야 합니다.')
        self.semaphore = semaphore or threading.BoundedSemaphore(2)
        self.lock = threading.Lock()
        self.items: dict[str, Job] = {}
        self.threads: set[threading.Thread] = set()
        self.retention_seconds = retention_seconds
        self.cleanup_interval = cleanup_interval
        self.stopped = threading.Event()
        self.cleaner: threading.Thread | None = None

    def _forget_locked(self, identifier: str) -> None:
        job = self.items.pop(identifier)
        job.result = job.error = None

    def _expire_locked(self) -> None:
        now = time.monotonic()
        for key, job in list(self.items.items()):
            if job.finished is not None and now - job.finished >= self.retention_seconds:
                self._forget_locked(key)

    def _clean(self) -> None:
        while not self.stopped.wait(self.cleanup_interval):
            with self.lock:
                self._expire_locked()

    def start(self, task: Callable[[threading.Event], dict]) -> dict:
        if not self.semaphore.acquire(blocking=False):
            raise BusyError('다른 작업이 진행 중입니다. 잠시 후 다시 실행하세요.')
        with self.lock:
            if self.stopped.is_set():
                self.semaphore.release()
                raise BusyError('앱이 종료 중입니다. 새 요청을 시작할 수 없습니다.')
            now = time.monotonic()
            self._expire_locked()
            finished = sorted((job for job in self.items.values() if job.finished is not None), key=lambda j: j.finished)
            while len(self.items) >= 24 and finished:
                self._forget_locked(finished.pop(0).id)
            job = Job(secrets.token_urlsafe(18), now)
            self.items[job.id] = job
            if self.cleaner is None:
                self.cleaner = threading.Thread(target=self._clean, name='clearwrite-expiry', daemon=True)
                self.cleaner.start()
        def execute() -> None:
            try:
                result = task(job.cancel)
                with self.lock:
                    if self.stopped.is_set():
                        job.result, job.error, job.state = None, None, 'cancelled'
                    elif job.cancel.is_set():
                        job.state, job.error = 'cancelled', '요청을 취소했습니다.'
                    else:
                        job.result, job.state = result, 'completed'
            except ModelCancelled as exc:
                with self.lock:
                    job.state, job.error = 'cancelled', str(exc)
            except (InputError, ProviderError) as exc:
                with self.lock:
                    job.state, job.error = 'failed', str(exc)
            except Exception:
                with self.lock:
                    job.state, job.error = 'failed', '처리 중 오류가 발생했습니다. 원문을 보관하고 다시 실행하세요.'
            finally:
                with self.lock:
                    job.finished = time.monotonic()
                    if self.stopped.is_set():
                        job.result = job.error = None
                    self.threads.discard(threading.current_thread())
                self.semaphore.release()
        thread = threading.Thread(target=execute, name='clearwrite-job', daemon=True)
        with self.lock:
            if self.stopped.is_set():
                self.semaphore.release()
                raise BusyError('앱이 종료 중입니다. 새 요청을 시작할 수 없습니다.')
            self.threads.add(thread)
            try:
                thread.start()
            except RuntimeError:
                self.threads.discard(thread)
                self._forget_locked(job.id)
                self.semaphore.release()
                raise BusyError('작업을 시작하지 못했습니다. 잠시 후 다시 실행하세요.') from None
        return {'job_id': job.id, 'state': 'running'}

    def get(self, identifier: str) -> dict | None:
        with self.lock:
            self._expire_locked()
            job = self.items.get(identifier)
            return None if job is None else {'job_id': job.id, 'state': job.state, 'result': job.result, 'error': job.error}

    def cancel(self, identifier: str) -> dict | None:
        with self.lock:
            self._expire_locked()
            job = self.items.get(identifier)
            if job is None:
                return None
            if job.state == 'running':
                job.cancel.set()
            return {'job_id': job.id, 'state': job.state, 'cancel_requested': job.cancel.is_set()}

    def close(self) -> None:
        with self.lock:
            self.stopped.set()
            for job in self.items.values():
                if job.state == 'running':
                    job.cancel.set()
                job.result = job.error = None
            self.items.clear()
            threads = list(self.threads)
        deadline = time.monotonic() + 10
        for thread in threads:
            if thread is not threading.current_thread():
                thread.join(max(0, deadline - time.monotonic()))
        if self.cleaner is not None and self.cleaner is not threading.current_thread():
            self.cleaner.join(timeout=2)
