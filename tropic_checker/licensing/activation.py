"""Activation window shown when no valid license is present."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from .. import theme as T
from .hwid import format_hwid, get_hardware_id
from .license_core import validate_license_key
from .store import load_saved_license, save_license


class ActivationApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Tropic Time Checker — Activation")
        self.geometry("640x520")
        self.minsize(600, 480)
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
            text="Send your Hardware ID to receive a license key. This app is locked to one PC.",
            font=T.FONT_BODY,
            text_color=T.TEXT_DIM,
            wraplength=560,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 16))

        ctk.CTkLabel(frame, text="Your Hardware ID", font=T.FONT_HEADING, text_color=T.TEXT).pack(
            anchor="w", padx=20
        )
        hw_row = ctk.CTkFrame(frame, fg_color="transparent")
        hw_row.pack(fill="x", padx=20, pady=(6, 16))
        self.hwid_var = tk.StringVar(value=self.hwid)
        ctk.CTkEntry(
            hw_row,
            textvariable=self.hwid_var,
            font=T.FONT_MONO,
            state="readonly",
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            hw_row,
            text="Copy",
            width=80,
            fg_color=T.MINT,
            hover_color=T.LIME,
            text_color="#111",
            command=self._copy_hwid,
        ).pack(side="right")

        ctk.CTkLabel(frame, text="License Key", font=T.FONT_HEADING, text_color=T.TEXT).pack(
            anchor="w", padx=20
        )
        self.key_box = ctk.CTkTextbox(frame, height=120, font=T.FONT_MONO)
        self.key_box.pack(fill="x", padx=20, pady=(6, 16))

        ctk.CTkButton(
            frame,
            text="Activate",
            height=40,
            fg_color=T.PINK,
            hover_color=T.PINK_HOVER,
            command=self._activate,
        ).pack(fill="x", padx=20, pady=(0, 20))

    def _copy_hwid(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.hwid)
        messagebox.showinfo("Copied", "Hardware ID copied to clipboard.")

    def _activate(self) -> None:
        key = self.key_box.get("1.0", "end").strip()
        if not key:
            messagebox.showwarning("Activation", "Paste your license key first.")
            return
        try:
            validate_license_key(key)
            save_license(key)
            self.license_key = key
            self.activated = True
            messagebox.showinfo("Activated", "License accepted. Starting Tropic Time Checker...")
            self.destroy()
        except ValueError as exc:
            messagebox.showerror("Activation Failed", str(exc))


def ensure_activated() -> None:
    """Exit unless a valid license is present or user activates."""
    saved = load_saved_license()
    if saved:
        try:
            validate_license_key(saved)
            return
        except ValueError:
            pass

    app = ActivationApp()
    app.mainloop()
    if not app.activated:
        raise SystemExit("Activation required")
