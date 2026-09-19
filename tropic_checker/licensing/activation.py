"""Activation window shown when no valid license is present."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from .. import theme as T
from .hwid import format_hwid, get_hardware_id
from .license_core import validate_license_key
from .online import activate_online, validate_online
from .store import load_saved_license, save_license


class ActivationApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Tropic Time Checker — Activation")
        self.geometry("680x620")
        self.minsize(640, 560)
        self.configure(fg_color=T.PANEL)
        self.activated = False
        self.license_key = ""

        self.hwid = format_hwid(get_hardware_id())
        self._build()

    def _build(self) -> None:
        frame = ctk.CTkFrame(self, fg_color=T.PANEL_LIGHT, corner_radius=16)
        frame.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(
            frame,
            text="🌴 Activate Tropic Time Checker",
            font=T.FONT_TITLE,
            text_color=T.PINK,
        ).pack(anchor="w", padx=20, pady=(20, 6))
        ctk.CTkLabel(
            frame,
            text="Step 1: Copy your Hardware ID below and send it to your vendor.\n"
            "Step 2: After they create your license, enter the activation code they send you.",
            font=T.FONT_BODY,
            text_color=T.TEXT_DIM,
            wraplength=580,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            frame,
            text="Your Hardware ID (send this to your vendor)",
            font=T.FONT_HEADING,
            text_color=T.TEXT,
        ).pack(anchor="w", padx=20)
        hw_row = ctk.CTkFrame(frame, fg_color="transparent")
        hw_row.pack(fill="x", padx=20, pady=(6, 12))
        self.hwid_var = tk.StringVar(value=self.hwid)
        ctk.CTkEntry(hw_row, textvariable=self.hwid_var, font=T.FONT_MONO, state="readonly").pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        ctk.CTkButton(
            hw_row,
            text="Copy",
            width=80,
            fg_color=T.MINT,
            hover_color=T.LIME,
            text_color="#111",
            command=self._copy_hwid,
        ).pack(side="right")

        tabs = ctk.CTkTabview(frame, fg_color=T.CARD)
        tabs.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        online_tab = tabs.add("Online")
        offline_tab = tabs.add("Offline Key")

        ctk.CTkLabel(
            online_tab,
            text="Enter the activation code from your vendor (e.g. TROPIC-AB12-CD34).\n"
            "Your license only works on this PC.",
            font=T.FONT_SMALL,
            text_color=T.TEXT_DIM,
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(8, 6))
        self.code_entry = ctk.CTkEntry(online_tab, font=T.FONT_MONO, placeholder_text="TROPIC-XXXX-XXXX")
        self.code_entry.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(
            online_tab,
            text="Activate Online",
            height=38,
            fg_color=T.MINT,
            hover_color=T.LIME,
            text_color="#111",
            command=self._activate_online,
        ).pack(fill="x")

        ctk.CTkLabel(
            offline_tab,
            text="Paste a license key if your vendor sent one directly.",
            font=T.FONT_SMALL,
            text_color=T.TEXT_DIM,
        ).pack(anchor="w", pady=(8, 6))
        self.key_box = ctk.CTkTextbox(offline_tab, height=100, font=T.FONT_MONO)
        self.key_box.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(
            offline_tab,
            text="Activate Offline Key",
            height=38,
            fg_color=T.PINK,
            hover_color=T.PINK_HOVER,
            command=self._activate_offline,
        ).pack(fill="x")

    def _copy_hwid(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.hwid)
        messagebox.showinfo("Copied", "Hardware ID copied to clipboard.")

    def _finish(self, key: str) -> None:
        self.license_key = key
        self.activated = True
        messagebox.showinfo("Activated", "License accepted. Starting Tropic Time Checker...")
        self.destroy()

    def _activate_online(self) -> None:
        code = self.code_entry.get().strip()
        if not code:
            messagebox.showwarning("Activation", "Enter your activation code.")
            return
        try:
            key = activate_online(code)
            self._finish(key)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Activation Failed", str(exc))

    def _activate_offline(self) -> None:
        key = self.key_box.get("1.0", "end").strip()
        if not key:
            messagebox.showwarning("Activation", "Paste your license key first.")
            return
        try:
            validate_license_key(key)
            save_license(key)
            self._finish(key)
        except ValueError as exc:
            messagebox.showerror("Activation Failed", str(exc))


def ensure_activated() -> None:
    """Exit unless a valid license is present or user activates."""
    saved = load_saved_license()
    if saved:
        try:
            info = validate_license_key(saved)
            if not validate_online(saved):
                raise ValueError("License revoked or expired on server")
            return
        except ValueError:
            pass

    app = ActivationApp()
    app.mainloop()
    if not app.activated:
        raise SystemExit("Activation required")
