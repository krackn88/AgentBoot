"""Multi-threaded checking engine."""

from __future__ import annotations

import itertools
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field

from .api import AccountResult, check_account


@dataclass
class CheckerStats:
    total: int = 0
    checked: int = 0
    hits: int = 0
    fails: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def cpm(self) -> float:
        elapsed = max(time.time() - self.start_time, 0.001)
        return (self.checked / elapsed) * 60

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time


class CheckerEngine:
    def __init__(
        self,
        combos: list[tuple[str, str]],
        proxies: list[str],
        threads: int = 5,
        on_hit: Callable[[AccountResult], None] | None = None,
        on_fail: Callable[[AccountResult], None] | None = None,
        on_progress: Callable[[CheckerStats], None] | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self.combos = list(combos)
        self.proxies = list(proxies)
        self.threads = max(1, min(threads, 100))
        self.on_hit = on_hit
        self.on_fail = on_fail
        self.on_progress = on_progress
        self.on_log = on_log
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.stats = CheckerStats(total=len(combos))

    def stop(self) -> None:
        self._stop.set()

    def is_stopped(self) -> bool:
        return self._stop.is_set()

    def _proxy_cycle(self) -> Iterator[str | None]:
        if not self.proxies:
            return itertools.repeat(None)
        return itertools.cycle(self.proxies)

    def _log(self, message: str) -> None:
        if self.on_log:
            self.on_log(message)

    def _emit_progress(self) -> None:
        if self.on_progress:
            self.on_progress(self.stats)

    def _submit_next(
        self,
        pool: ThreadPoolExecutor,
        combo_iter: Iterator[tuple[str, str]],
        proxy_iter: Iterator[str | None],
        futures: dict[Future[AccountResult], tuple[str, str]],
    ) -> None:
        while len(futures) < self.threads and not self.is_stopped():
            try:
                email, password = next(combo_iter)
            except StopIteration:
                return
            proxy = next(proxy_iter)
            fut = pool.submit(check_account, email, password, proxy)
            futures[fut] = (email, password)

    def _handle_result(
        self,
        fut: Future[AccountResult],
        email: str,
        password: str,
        hits: list[AccountResult],
    ) -> None:
        try:
            result = fut.result()
        except Exception as exc:
            result = AccountResult(
                email=email,
                password=password,
                success=False,
                message=str(exc),
            )

        with self._lock:
            self.stats.checked += 1
            if result.success:
                self.stats.hits += 1
                hits.append(result)
            else:
                self.stats.fails += 1

        if result.success:
            self._log(f"HIT  {result.summary_line()}")
            if self.on_hit:
                self.on_hit(result)
        else:
            short = result.message[:80] if result.message else "failed"
            self._log(f"FAIL {email} | {short}")
            if self.on_fail:
                self.on_fail(result)

        self._emit_progress()

    def _shutdown_pool(self, pool: ThreadPoolExecutor, *, cancel_pending: bool) -> None:
        try:
            pool.shutdown(wait=not cancel_pending, cancel_futures=cancel_pending)
        except TypeError:
            pool.shutdown(wait=not cancel_pending)

    def run(self) -> list[AccountResult]:
        hits: list[AccountResult] = []
        combo_iter = iter(self.combos)
        proxy_iter = self._proxy_cycle()

        self.stats.start_time = time.time()
        self._log(f"Starting {self.stats.total} combos with {self.threads} threads")

        pool = ThreadPoolExecutor(max_workers=self.threads)
        futures: dict[Future[AccountResult], tuple[str, str]] = {}
        stopped = False

        try:
            self._submit_next(pool, combo_iter, proxy_iter, futures)

            while futures:
                if self.is_stopped():
                    stopped = True
                    for pending in futures:
                        pending.cancel()
                    break

                done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED, timeout=0.5)
                if not done:
                    continue

                for fut in done:
                    email, password = futures.pop(fut)
                    if fut.cancelled():
                        continue
                    self._handle_result(fut, email, password, hits)
                    if not self.is_stopped():
                        self._submit_next(pool, combo_iter, proxy_iter, futures)
        finally:
            self._shutdown_pool(pool, cancel_pending=stopped)

        self._log("Stopped" if stopped else "Finished")
        return hits
