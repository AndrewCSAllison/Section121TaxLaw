"""
widgets.py — Reusable themed widget factories.
"""
import tkinter as tk
from App.theme import (
    BG, PANEL, BORDER, ACCENT, ACCENT2, TEXT, SUBTEXT, 
    FONT_MONO, FONT_HEAD, FONT_SMALL, WIDGET_CONFIG, IS_MAC
)

def styled_text(parent, **kw):
    """A flat, dark-themed tk.Text widget using global theme config."""
    # Start with global defaults, then allow kw to override (like height/width)
    conf = WIDGET_CONFIG.copy()
    conf.update({
        "bg": PANEL,
        "font": FONT_MONO,
        "highlightthickness": 1,
        "highlightbackground": BORDER,
        "highlightcolor": ACCENT,
    })
    conf.update(kw)
    return tk.Text(parent, **conf)


def styled_scrolled(parent, **kw):
    """Bordered frame containing a styled tk.Text with a vertical scrollbar."""
    frame = tk.Frame(parent, bg=BORDER, bd=0, highlightthickness=0)
    
    t = styled_text(frame, **kw)
    
    # Scrollbar styling is limited on Mac, but these settings
    # prevent the "white box" clash on Windows/Linux.
    sb = tk.Scrollbar(
        frame, 
        command=t.yview, 
        bg=PANEL, 
        troughcolor=BG,
        activebackground=ACCENT, 
        relief="flat", 
        width=10,
        highlightthickness=0,
        bd=0
    )
    
    t.configure(yscrollcommand=sb.set)
    t.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frame, t


def pill_button(parent, text, command, color=ACCENT, width=None):
    """
    A 'pill' button factory. 
    Uses tk.Label on macOS to bypass background color restrictions.
    """
    if IS_MAC:
        # Mac-safe version using Label
        btn = tk.Label(
            parent, text=text, bg=color, fg="#FFFFFF",
            font=FONT_HEAD, padx=14, pady=6, cursor="hand2",
            relief="flat", **({"width": width} if width else {})
        )
        # Bind the click action
        btn.bind("<Button-1>", lambda e: command() if btn.cget("state") != "disabled" else None)
    else:
        # Windows/Linux version using standard Button
        btn = tk.Button(
            parent, text=text, command=command,
            bg=color, fg="#FFFFFF", activebackground=ACCENT2,
            activeforeground="#FFFFFF", relief="flat", bd=0,
            cursor="hand2", font=FONT_HEAD, padx=14, pady=6,
            highlightthickness=0, **({"width": width} if width else {})
        )

    def on_enter(e):
        if btn.cget("state") != "disabled":
            btn.config(bg=ACCENT2)

    def on_leave(e):
        if btn.cget("state") != "disabled":
            btn.config(bg=color)

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    
    # Add a state property manually for the Label version if needed
    if IS_MAC:
        btn.config(state="normal")
        
    return btn


def section_label(parent, text):
    """Small uppercase section header label."""
    # Use the specific small font from theme
    return tk.Label(
        parent, 
        text=text.upper(), 
        bg=parent.cget("bg"), 
        fg=SUBTEXT,
        font=FONT_SMALL, 
        anchor="w",
    )