"""
widgets.py — Reusable themed widget factories.
"""
import tkinter as tk
from App.theme import (
    BG, PANEL, BORDER, ACCENT, ACCENT2, TEXT, SUBTEXT, FONT_MONO, FONT_HEAD
)


def styled_text(parent, **kw):
    """A flat, dark-themed tk.Text widget."""
    defaults = dict(
        bg=PANEL, fg=TEXT, insertbackground=TEXT,
        relief="flat", bd=0, font=FONT_MONO,
        selectbackground=ACCENT, selectforeground="#FFFFFF",
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=ACCENT,
    )
    defaults.update(kw)
    return tk.Text(parent, **defaults)


def styled_scrolled(parent, **kw):
    """
    Returns (frame, text_widget): a bordered frame containing a styled
    tk.Text with an attached vertical scrollbar.
    """
    frame = tk.Frame(parent, bg=BORDER, bd=1)
    t = styled_text(frame, **kw)
    sb = tk.Scrollbar(
        frame, command=t.yview, bg=PANEL, troughcolor=BG,
        activebackground=ACCENT, relief="flat", width=10,
    )
    t.configure(yscrollcommand=sb.set)
    t.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frame, t


def pill_button(parent, text, command, color=ACCENT, width=None):
    """A rounded-look flat button with hover highlight."""
    btn = tk.Button(
        parent, text=text, command=command,
        bg=color, fg="#FFFFFF",
        activebackground=ACCENT2, activeforeground="#FFFFFF",
        relief="flat", bd=0, cursor="hand2",
        font=FONT_HEAD, padx=14, pady=6,
        **({"width": width} if width else {}),
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT2))
    btn.bind("<Leave>", lambda e: btn.config(bg=color))
    return btn


def section_label(parent, text):
    """Small uppercase section header label."""
    return tk.Label(
        parent, text=text, bg=BG, fg=SUBTEXT,
        font=("Segoe UI", 8, "bold"), anchor="w",
    )