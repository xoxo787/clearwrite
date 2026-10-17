"""Bounded in-memory model jobs with cancellation and expiry."""
from __future__ import annotations
import secrets
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

class Jobs:
    def __init__(self, semaphore: threading.BoundedSemaphore | None = None):
        self.semaphore = semaphore or threading.BoundedSemaphore(2)
        self.lock = threading.Lock()
        self.items: dict[str, Job] = {}
        self.threads: set[threading.Thread] = set()

    def start(self, task: Callable[[threading.Event], dict]) -> dict:
        if not self.semaphore.acquire(blocking=False):
            raise BusyError('다른 작업이 진행 중입니다. 잠시 후 다시 실행하세요.')
        with self.lock:
            now = time.monotonic()
            for key in [key for key, job in self.items.items() if job.state != 'running' and now - job.created > 900]:
                del self.items[key]
            finished = sorted((job for job in self.items.values() if job.state != 'running'), key=lambda j: j.created)
            while len(self.items) >= 24 and finished:
                del self.items[finished.pop(0).id]
            job = Job(secrets.token_urlsafe(18), now)
            self.items[job.id] = job
        def execute() -> None:
            try:
                result = task(job.cancel)
                with self.lock:
                    if job.cancel.is_set():
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
                self.semaphore.release()
                with self.lock:
                    self.threads.discard(threading.current_thread())
        thread = threading.Thread(target=execute, name='clearwrite-job', daemon=True)
        with self.lock:
            self.threads.add(thread)
        thread.start()
        return {'job_id': job.id, 'state': 'running'}

    def get(self, identifier: str) -> dict | None:
        with self.lock:
            job = self.items.get(identifier)
            return None if job is None else {'job_id': job.id, 'state': job.state, 'result': job.result, 'error': job.error}

    def cancel(self, identifier: str) -> dict | None:
        with self.lock:
            job = self.items.get(identifier)
            if job is None:
                return None
            if job.state == 'running':
                job.cancel.set()
            return {'job_id': job.id, 'state': job.state, 'cancel_requested': job.cancel.is_set()}

    def close(self) -> None:
        with self.lock:
            for job in self.items.values():
                if job.state == 'running':
                    job.cancel.set()
            threads = list(self.threads)
        deadline = time.monotonic() + 10
        for thread in threads:
            if thread is not threading.current_thread():
                thread.join(max(0, deadline - time.monotonic()))
