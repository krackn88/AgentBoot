from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from gadgetforge.checker.models import CheckOutcome, CheckerRecipe
from gadgetforge.checker.replay import parse_combo, run_recipe_check


@dataclass
class CheckerJobStats:
    total: int = 0
    checked: int = 0
    hits: int = 0
    bad: int = 0
    retries: int = 0
    errors: int = 0
    running: bool = False
    stop_requested: bool = False
    current: str = ""
    logs: list[str] = field(default_factory=list)
    hits_lines: list[str] = field(default_factory=list)


class CheckerJobWorker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.stats = CheckerJobStats()
        self._recipe: CheckerRecipe | None = None

    def is_running(self) -> bool:
        with self._lock:
            return self.stats.running

    def start(
        self,
        recipe: CheckerRecipe,
        combos: list[str],
        *,
        threads: int = 5,
        proxies: list[str] | None = None,
        delay_ms: int = 0,
    ) -> dict[str, Any]:
        with self._lock:
            if self.stats.running:
                return {"ok": False, "error": "already_running"}
            if not recipe.steps:
                return {"ok": False, "error": "recipe_has_no_steps"}
            parsed = [c for line in combos if (c := parse_combo(line))]
            if not parsed:
                return {"ok": False, "error": "no_valid_combos"}

            self._recipe = recipe
            self.stats = CheckerJobStats(total=len(parsed), running=True)
            proxy_cycle = itertools.cycle(proxies or [None])

            def run() -> None:
                from concurrent.futures import ThreadPoolExecutor, as_completed

                def work(combo: tuple[str, str]) -> None:
                    if self.stats.stop_requested:
                        return
                    email, password = combo
                    with self._lock:
                        self.stats.current = f"{email}:***"
                    proxy = next(proxy_cycle)
                    result = run_recipe_check(recipe, email, password, proxy=proxy)
                    with self._lock:
                        self.stats.checked += 1
                        line = result.line()
                        self.stats.logs.append(line)
                        if len(self.stats.logs) > 500:
                            self.stats.logs = self.stats.logs[-500:]
                        if result.outcome == CheckOutcome.HIT:
                            self.stats.hits += 1
                            self.stats.hits_lines.append(line)
                        elif result.outcome == CheckOutcome.BAD:
                            self.stats.bad += 1
                        elif result.outcome == CheckOutcome.RETRY:
                            self.stats.retries += 1
                        elif result.outcome == CheckOutcome.ERROR:
                            self.stats.errors += 1
                    if delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)

                try:
                    with ThreadPoolExecutor(max_workers=max(1, threads)) as pool:
                        futures = [pool.submit(work, c) for c in parsed]
                        for f in as_completed(futures):
                            if self.stats.stop_requested:
                                break
                            f.result()
                finally:
                    with self._lock:
                        self.stats.running = False
                        self.stats.current = ""

            self._thread = threading.Thread(target=run, daemon=True)
            self._thread.start()
            return {"ok": True, "queued": len(parsed)}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self.stats.stop_requested = True
        return {"ok": True}

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.stats.running,
                "total": self.stats.total,
                "checked": self.stats.checked,
                "hits": self.stats.hits,
                "bad": self.stats.bad,
                "retries": self.stats.retries,
                "errors": self.stats.errors,
                "current": self.stats.current,
                "logs": list(self.stats.logs[-100:]),
                "hits_lines": list(self.stats.hits_lines[-50:]),
            }


checker_worker = CheckerJobWorker()
