"""
main.py — Application entry point and UI assembly.

Layout
------
  build_top_bar(root)          → top banner + status badge
  build_tab_editor(nb)         → Tab 1: TTL Editor & pipeline submission
  build_tab_prompt(nb)         → Tab 2: Prompt Builder
  build_tab_guide(nb)          → Tab 3: How-to-Use guide
  wire_ttk_style(root)         → configure ttk.Notebook appearance
  main()                       → create root window, assemble, start loop

All UI state shared between tabs (log widget, status, etc.) is captured
via closure — no module-level mutable globals.
"""

import datetime
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

try:
    from App.controller import load_file, submit_with_callback, clear_repository
except ModuleNotFoundError:
    from controller import load_file, submit_with_callback, clear_repository

from App.theme import (
    ACCENT, ACCENT2, BG, BORDER, ERROR_COL, FONT_HEAD, FONT_UI,
    PANEL, SUBTEXT, SUCCESS, TEXT, WARNING,
)
from App.widgets import pill_button, section_label, styled_scrolled


# ──────────────────────────────────────────────
#  Pre-prompt constant
# ──────────────────────────────────────────────

PRE_PROMPT = open("Prompting_Files/Combined_Prompting_File", "r", encoding="utf-8").read()

SCENARIO_INSTRUCTIONS = (
    "Include the following facts in your scenario description:\n\n"
    "TAXPAYER(S)\n"
    "  \u2022 Name or identifier for each taxpayer (e.g. \"Taxpayer A\")\n"
    "  \u2022 Whether taxpayers are married or unmarried\n"
    "  \u2022 Whether they are filing jointly or separately\n\n"
    "PROPERTY / PROPERTIES\n"
    "  \u2022 Name or identifier for each property (e.g. \"Main Residence\", \"Florida Condo\")\n\n"
    "OWNERSHIP\n"
    "  \u2022 Ownership start date per taxpayer per property\n"
    "  \u2022 Ownership end date per taxpayer per property\n"
    "  \u2022 Percentage owned if split between co-owners (e.g. \"50/50\")\n"
    "  \u2022 Whether ownership was continuous or consisted of separate intervals\n\n"
    "RESIDENCE / USE\n"
    "  \u2022 Residence start date per taxpayer per property\n"
    "  \u2022 Residence end date per taxpayer per property\n"
    "  \u2022 Whether residence was continuous or had separate intervals\n\n"
    "DISPOSITION (SALE)\n"
    "  \u2022 Sale date for each property\n"
    "  \u2022 Realized gain (positive) or loss (negative) for each property\n\n"
    "TAX RETURN\n"
    "  \u2022 Return type: Single or Joint\n"
    "  \u2022 Which taxpayer(s) are a part of which return\n"
    "  \u2022 Which property sale is linked to the return\n\n"
    "PARTIAL EXCLUSION REASON (only if applicable)\n"
    "  \u2022 Employment-related  \u2014 job change / reassignment / distance \u2265 50 miles\n"
    "  \u2022 Health-related      \u2014 illness, injury, or care for a family member\n"
    "  \u2022 Unforeseen circumstance \u2014 divorce, death, financial hardship, etc.\n"
    "  \u2022 Non-qualifying reason  \u2014 explicitly does NOT qualify for partial exclusion\n\n"
    "TIPS\n"
    "  \u2022 Dates can be written naturally: \"January 15, 1999\", \"early 2003\", \"throughout 2001\"\n"
    "  \u2022 Amounts can be written naturally: \"$300k\", \"three hundred thousand dollars\"\n"
    "  \u2022 Do NOT compute or include exclusion amounts \u2014 those are calculated automatically"
)

GUIDE_STEPS = [
    (
        "Step 1 — Write Your Scenario  (Prompt Builder tab)",
        ACCENT,
        [
            "Open the Prompt Builder tab.",
            "Click '▶ What to include in your scenario' to expand the checklist.",
            "Read the checklist and write your taxpayer scenario in plain English in the left box.",
            "  Include: taxpayer names, property names, ownership dates, residence dates,",
            "  sale date, realized gain/loss, return type (Single or Joint), and any",
            "  partial exclusion reason if one applies (employment, health, unforeseen).",
            "  Tip: dates and amounts can be written naturally — the LLM will format them as needed.",
            "Click '⚙ Build Prompt' to assemble the full instruction prompt + your scenario.",
        ],
    ),
    (
        "Step 2 — Generate the TTL File  (LLM of your choice)",
        ACCENT2,
        [
            "Click one of the LLM buttons (↗ ChatGPT, ↗ Claude, ↗ Gemini) to open it.",
            "Click '📋 Copy Full Prompt' then paste the prompt into the LLM chat.",
            "If the LLM has all the necessary information to proceed, it will return a Turtle (.ttl) file inside a code block.",
            "Otherwise, it may ask you follow-up questions to clarify missing or ambiguous details in your scenario — answer these as best you can until the LLM has what it needs.",
            "Then, copy the entire TTL output from the LLM (including all @prefix lines).",
        ],
    ),
    (
        "Step 3 — Submit & Run the Pipeline  (TTL Editor tab)",
        SUCCESS,
        [
            "Switch to the TTL Editor tab.",
            "Paste the TTL into the editor on the left, or use '📂 Load File' to load a .ttl file.",
            "Click '▶ Submit & Run Rules' (or press Ctrl+Enter).",
            "Watch the Pipeline Output on the right:",
            "  ✔ Green  — step passed successfully.",
            "  ✘ Red    — an error occurred (see message for details).",
            "  ⚠ Yellow — a warning (e.g. undefined entities found in NYI check).",
            "The final exclusion results will appear at the bottom of the output panel if no errors occur.",
        ],
    ),
    (
        "Step 4 — Fix Errors If Needed  (back to LLM)",
        WARNING,
        [
            "If a SHACL violation or upload error appears in the output panel:",
            "  Copy the red error text from the Pipeline Output panel.",
            "  Return to your LLM conversation and paste the error message.",
            "  The LLM will repair the TTL — copy the corrected version.",
            "  Paste it back into the TTL Editor and re-submit.",
            "Repeat until all steps show green checkmarks.",
        ],
    ),
    (
        "Step 5 — Reset Between Cases  (TTL Editor tab)",
        ERROR_COL,
        [
            "Before submitting a NEW taxpayer scenario, click '⟳ Reset Repository'.",
            "This clears all previously uploaded data from GraphDB and reloads the",
            "base ontology and SHACL shapes, giving you a clean slate.",
            "You will be asked to confirm before the reset runs.",
            "After resetting, you can paste a new TTL and submit immediately.",
            "This step is important to prevent data from previous scenarios interfering with new ones.",
        ],
    ),
    (
        "Quick Reference — Output Colors",
        SUBTEXT,
        [
            "Green   ✔  Step completed without issues.",
            "Red     ✘  Error — check the message and repair the TTL.",
            "Yellow  ⚠  Warning — review but pipeline may still continue.",
            "Blue       Section heading / timestamp.",
            "White      Final exclusion results.",
        ],
    ),
]

LLM_LINKS = {
    "ChatGPT": "https://chat.openai.com/",
    "Claude":  "https://claude.ai/new",
    "Gemini":  "https://gemini.google.com/app",
}


# ──────────────────────────────────────────────
#  Top bar
# ──────────────────────────────────────────────

def build_top_bar(root):
    """
    Build the top banner with app title and a live status badge.
    Returns set_status(msg, color) callable.
    """
    bar = tk.Frame(root, bg=PANEL, height=52)
    bar.pack(fill="x", side="top")
    bar.pack_propagate(False)

    tk.Label(bar, text="§ 121", bg=PANEL, fg=ACCENT,
             font=("Segoe UI Black", 18)).pack(side="left", padx=16, pady=8)
    tk.Label(bar, text="Exclusion Calculation System", bg=PANEL, fg=TEXT,
             font=("Segoe UI", 13)).pack(side="left", pady=8)

    status_var = tk.StringVar(value="● Ready")
    status_lbl = tk.Label(bar, textvariable=status_var, bg=PANEL, fg=SUCCESS,
                          font=FONT_UI)
    status_lbl.pack(side="right", padx=16)

    def set_status(msg, color=SUCCESS):
        status_var.set(f"● {msg}")
        status_lbl.config(fg=color)

    return set_status


# ──────────────────────────────────────────────
#  Tab 1 — TTL Editor & Submission
# ──────────────────────────────────────────────

def build_tab_editor(nb, set_status):
    """
    Build the TTL Editor tab.
    Returns the tab frame (already added to *nb*).
    """
    tab = tk.Frame(nb, bg=BG)
    nb.add(tab, text="  TTL Editor  ")

    pane = tk.PanedWindow(tab, orient="horizontal", bg=BORDER,
                          sashwidth=4, sashrelief="flat", handlesize=0)
    pane.pack(fill="both", expand=True)

    # ── Left: editor ──────────────────────────
    left = tk.Frame(pane, bg=BG)
    pane.add(left, minsize=340)

    # Header
    hdr = tk.Frame(left, bg=BG)
    hdr.pack(fill="x", padx=10, pady=(10, 4))
    section_label(hdr, "TURTLE (.ttl) INPUT").pack(side="left")

    # Button row
    btn_row = tk.Frame(left, bg=BG)
    btn_row.pack(fill="x", padx=10, pady=(0, 6))

    editor_frame, ttl_input = styled_scrolled(left, height=20)
    editor_frame.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    # Char-count footer
    char_count_var = tk.StringVar(value="0 chars")
    tk.Label(left, textvariable=char_count_var, bg=BG, fg=SUBTEXT,
             font=("Segoe UI", 8)).pack(anchor="e", padx=10)

    def update_char_count(event=None):
        n = len(ttl_input.get("1.0", "end-1c"))
        char_count_var.set(f"{n:,} chars")

    ttl_input.bind("<KeyRelease>", update_char_count)
    ttl_input.bind("<ButtonRelease>", update_char_count)

    # Submit / reset row
    submit_row = tk.Frame(left, bg=BG)
    submit_row.pack(fill="x", padx=10, pady=(0, 10))

    btn_submit = pill_button(submit_row, "▶  Submit & Run Rules",
                             command=lambda: on_submit(), width=24)
    btn_submit.pack(side="left")

    btn_clear_repo = pill_button(submit_row, "⟳  Reset Repository",
                                 command=lambda: on_clear_repo(),
                                 color="#5C3A3A", width=20)
    btn_clear_repo.pack(side="left", padx=(8, 0))

    # ── Right: results ─────────────────────────
    right = tk.Frame(pane, bg=BG)
    pane.add(right, minsize=340)

    results_hdr = tk.Frame(right, bg=BG)
    results_hdr.pack(fill="x", padx=10, pady=(10, 4))
    section_label(results_hdr, "PIPELINE OUTPUT").pack(side="left")

    pill_button(results_hdr, "Copy",
                command=lambda: copy_results(),
                color="#3A3F5C").pack(side="right")
    pill_button(results_hdr, "Clear",
                command=lambda: clear_results(),
                color="#3A3F5C").pack(side="right", padx=(0, 6))

    results_frame, results_text = styled_scrolled(right)
    results_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # Color tags
    results_text.tag_configure("system",  foreground=SUBTEXT)
    results_text.tag_configure("success", foreground=SUCCESS)
    results_text.tag_configure("error",   foreground=ERROR_COL)
    results_text.tag_configure("warning", foreground=WARNING)
    results_text.tag_configure("heading", foreground=ACCENT,
                               font=("Consolas", 10, "bold"))
    results_text.tag_configure("result",  foreground=TEXT)
    results_text.tag_configure("user",    foreground=ACCENT2)

    # ── Load-file button (needs results_text for feedback) ──
    btn_load = pill_button(btn_row, "📂  Load File",
                           command=lambda: on_load_file(),
                           color="#3A3F5C", width=14)
    btn_load.pack(side="left", padx=(0, 6))

    pill_button(btn_row, "✕  Clear",
                command=lambda: ttl_input.delete("1.0", "end"),
                color="#3A3F5C", width=8).pack(side="left")

    # ── Callbacks ──────────────────────────────

    def log(msg, tag="result"):
        results_text.config(state="normal")
        results_text.insert("end", msg + "\n", tag)
        results_text.config(state="disabled")
        results_text.see("end")

    def clear_results():
        results_text.config(state="normal")
        results_text.delete("1.0", "end")
        results_text.config(state="disabled")

    def copy_results():
        results_text.master.clipboard_clear()
        results_text.master.clipboard_append(results_text.get("1.0", "end-1c"))
        set_status("Copied to clipboard", color=SUCCESS)

    def on_load_file():
        loaded = load_file(ttl_input)
        if loaded:
            update_char_count()
            log("── Loaded TTL file ──────────────────────────────", "system")
            set_status("File loaded", color=SUCCESS)

    def on_submit():
        content = ttl_input.get("1.0", "end-1c").strip()
        if not content:
            messagebox.showwarning("No Input",
                                   "Please enter or load a TTL file before submitting.")
            return

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        set_status("Running…", color=WARNING)
        btn_submit.config(state="disabled", text="Running…")
        log(f"\n══ Submission ({timestamp}) ═══════════════════════════", "heading")

        def run():
            try:
                submit_with_callback(content, log)
                results_text.after(0, lambda: set_status("Done", color=SUCCESS))
            except Exception as exc:
                results_text.after(0, lambda: log(f"Unexpected error: {exc}", "error"))
                results_text.after(0, lambda: set_status("Error", color=ERROR_COL))
            finally:
                results_text.after(
                    0, lambda: btn_submit.config(state="normal",
                                                 text="▶  Submit & Run Rules")
                )

        threading.Thread(target=run, daemon=True).start()

    def on_clear_repo():
        confirmed = messagebox.askyesno(
            "Confirm Reset",
            "This will CLEAR ALL data in the repository and reload "
            "the base SHACL shapes and ontology.\n\nContinue?",
            icon="warning",
        )
        if not confirmed:
            return
        set_status("Clearing repository…", color=WARNING)
        try:
            clear_repository()
            log("  ✔ Repository cleared and base files reloaded.", "success")
            set_status("Repository reset", color=SUCCESS)
        except Exception as exc:
            log(f"  ✘ Reset error: {exc}", "error")
            set_status("Reset failed", color=ERROR_COL)

    return tab, on_submit, on_load_file


# ──────────────────────────────────────────────
#  Tab 2 — Prompt Builder
# ──────────────────────────────────────────────

def build_tab_prompt(nb, set_status):
    """Build the Prompt Builder tab and return the tab frame."""
    tab = tk.Frame(nb, bg=BG)
    nb.add(tab, text="  Prompt Builder  ")

    pb_left = tk.Frame(tab, bg=BG)
    pb_left.pack(side="left", fill="both", expand=True, padx=(10, 4), pady=10)

    pb_right = tk.Frame(tab, bg=BG)
    pb_right.pack(side="right", fill="both", expand=True, padx=(4, 10), pady=10)

    # ── Instructions toggle ────────────────────
    instructions_visible = tk.BooleanVar(value=False)

    toggle_row = tk.Frame(pb_left, bg=BG)
    toggle_row.pack(fill="x", pady=(0, 4))

    # Instructions body (packed on demand before scenario_label_frame)
    instr_body = tk.Frame(pb_left, bg=BORDER, bd=1)
    instr_inner = tk.Text(
        instr_body, bg="#1E2235", fg=SUBTEXT,
        font=("Consolas", 9), relief="flat", bd=0,
        state="normal", wrap="word", height=14,
        selectbackground=ACCENT, selectforeground="#FFFFFF",
        highlightthickness=0,
    )
    instr_sb = tk.Scrollbar(instr_body, command=instr_inner.yview, bg=PANEL,
                             troughcolor=BG, activebackground=ACCENT,
                             relief="flat", width=8)
    instr_inner.configure(yscrollcommand=instr_sb.set)
    instr_inner.insert("1.0", SCENARIO_INSTRUCTIONS)
    instr_inner.config(state="disabled")
    instr_inner.pack(side="left", fill="both", expand=True, padx=8, pady=6)
    instr_sb.pack(side="right", fill="y")

    # Scenario label frame (anchor for toggle insertion point)
    scenario_label_frame = tk.Frame(pb_left, bg=BG)
    scenario_label_frame.pack(fill="x")
    section_label(scenario_label_frame, "YOUR SCENARIO (plain English)").pack(anchor="w", pady=(0, 4))
    tk.Label(
        scenario_label_frame,
        text='Describe the taxpayer scenario below. Click "Build Prompt" to\n'
             "assemble the full pre-prompt + your text, ready to paste into an LLM.",
        bg=BG, fg=SUBTEXT, font=("Segoe UI", 9), justify="left",
    ).pack(anchor="w", pady=(0, 6))

    def toggle_instructions():
        if instructions_visible.get():
            instr_body.pack_forget()
            instructions_visible.set(False)
            toggle_btn.config(text="\u25b6  What to include in your scenario")
        else:
            instr_body.pack(fill="x", before=scenario_label_frame, pady=(0, 6))
            instructions_visible.set(True)
            toggle_btn.config(text="\u25bc  What to include in your scenario")

    toggle_btn = tk.Button(
        toggle_row, text="\u25b6  What to include in your scenario",
        command=toggle_instructions,
        bg=BG, fg=ACCENT, activebackground=BG, activeforeground=ACCENT2,
        relief="flat", bd=0, cursor="hand2",
        font=("Segoe UI Semibold", 9), anchor="w",
    )
    toggle_btn.pack(side="left")

    # ── Scenario input ─────────────────────────
    scenario_frame, scenario_input = styled_scrolled(pb_left, height=12)
    scenario_frame.pack(fill="both", expand=True)

    pb_btn_row = tk.Frame(pb_left, bg=BG)
    pb_btn_row.pack(fill="x", pady=(8, 0))

    # ── Right: assembled prompt ────────────────
    section_label(pb_right, "ASSEMBLED PROMPT (copy & paste)").pack(anchor="w", pady=(0, 4))
    assembled_container = tk.Frame(pb_right, bg=BG)
    assembled_container.pack(fill="both", expand=True)
    assembled_frame, assembled_text = styled_scrolled(assembled_container)
    assembled_frame.pack(fill="both", expand=True)

    pb_copy_row = tk.Frame(pb_right, bg=BG)
    pb_copy_row.pack(fill="x", pady=(8, 0))

    # Pre-populate assembled panel
    assembled_text.config(state="normal")
    assembled_text.insert("1.0", PRE_PROMPT + "\n[Your scenario will appear here after clicking Build Prompt]")
    assembled_text.config(state="disabled")

    # ── Callbacks ──────────────────────────────

    def build_prompt():
        scenario = scenario_input.get("1.0", "end-1c").strip()
        if not scenario:
            messagebox.showwarning("Empty Scenario",
                                   "Please enter a scenario description first.")
            return
        assembled_text.config(state="normal")
        assembled_text.delete("1.0", "end")
        assembled_text.insert("1.0", PRE_PROMPT + scenario)
        assembled_text.config(state="disabled")
        set_status("Prompt ready — copy and paste into your chosen LLM", color=ACCENT)

    def copy_assembled():
        assembled_text.master.clipboard_clear()
        assembled_text.master.clipboard_append(assembled_text.get("1.0", "end-1c"))
        set_status("Prompt copied to clipboard!", color=SUCCESS)

    # Build button + LLM shortcuts
    pill_button(pb_btn_row, "\u2699  Build Prompt",
                command=build_prompt, width=18).pack(side="left")

    for name, url in LLM_LINKS.items():
        pill_button(pb_btn_row, f"\u2197 {name}",
                    command=lambda u=url: webbrowser.open(u),
                    color="#3A3F5C").pack(side="left", padx=(6, 0))

    pill_button(pb_copy_row, "\U0001f4cb  Copy Full Prompt",
                command=copy_assembled, width=22).pack(side="left")

    return tab


# ──────────────────────────────────────────────
#  Tab 3 — How to Use
# ──────────────────────────────────────────────

def build_tab_guide(nb):
    """Build the How-to-Use guide tab and return the tab frame."""
    tab = tk.Frame(nb, bg=BG)
    nb.add(tab, text="  How to Use  ")

    # Scrollable canvas
    canvas = tk.Canvas(tab, bg=BG, highlightthickness=0)
    scrollbar = tk.Scrollbar(tab, orient="vertical", command=canvas.yview,
                              bg=PANEL, troughcolor=BG, activebackground=ACCENT,
                              relief="flat", width=10)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg=BG)
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    inner.bind("<Configure>", lambda e: canvas.configure(
        scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

    def _scroll(e):
        canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _bind_mousewheel(widget):
        widget.bind("<MouseWheel>", _scroll)
        for child in widget.winfo_children():
            _bind_mousewheel(child)

    canvas.bind("<MouseWheel>", _scroll)
    inner.bind("<Configure>", lambda e: _bind_mousewheel(inner), add="+")

    # Header
    hdr_frame = tk.Frame(inner, bg=BG)
    hdr_frame.pack(fill="x", padx=30, pady=(24, 4))
    tk.Label(hdr_frame, text="§121 Exclusion Calculation Pipeline — How to Use",
             bg=BG, fg=TEXT, font=("Segoe UI Semibold", 16)).pack(side="left")
    tk.Label(hdr_frame,
             text="Follow the steps below in order for each taxpayer scenario.",
             bg=BG, fg=SUBTEXT, font=("Segoe UI", 10)).pack(side="left", padx=(16, 0))

    tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(4, 20))

    # Step blocks
    for title, color, bullets in GUIDE_STEPS:
        block = tk.Frame(inner, bg=PANEL, bd=0)
        block.pack(fill="x", padx=30, pady=(0, 12), ipady=10)

        tk.Frame(block, bg=color, width=4).pack(side="left", fill="y")

        content = tk.Frame(block, bg=PANEL)
        content.pack(side="left", fill="both", expand=True, padx=(14, 14), pady=(8, 8))

        tk.Label(content, text=title, bg=PANEL, fg=color,
                 font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x", pady=(0, 6))

        for line in bullets:
            indented = line.startswith("  ")
            tk.Label(
                content, text=line, bg=PANEL,
                fg=SUBTEXT if indented else TEXT,
                font=("Consolas", 9) if indented else ("Segoe UI", 10),
                anchor="w", justify="left", wraplength=700,
            ).pack(fill="x", pady=1)

    tk.Frame(inner, bg=BG, height=20).pack()
    return tab


# ──────────────────────────────────────────────
#  ttk style
# ──────────────────────────────────────────────

def wire_ttk_style(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TNotebook",        background=BG,    borderwidth=0)
    style.configure("TNotebook.Tab",    background=PANEL, foreground=SUBTEXT,
                    padding=[14, 6],    font=FONT_HEAD,   borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", BORDER)],
              foreground=[("selected", TEXT)])
    style.configure("TFrame",              background=BG)
    style.configure("TPanedwindow",        background=BG)
    style.configure("Vertical.TSeparator", background=BORDER)


# ──────────────────────────────────────────────
#  Footer
# ──────────────────────────────────────────────

def build_footer(root):
    footer = tk.Frame(root, bg=PANEL, height=24)
    footer.pack(fill="x", side="bottom")
    footer.pack_propagate(False)
    tk.Label(footer, text="Ctrl+Enter to Submit  ·  Ctrl+O to Load File",
             bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 8)).pack(side="left", padx=12)
    tk.Label(footer, text="§121 Exclusion Calculation System",
             bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 8)).pack(side="right", padx=12)


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.title("§121 Exclusion Calculation System")
    root.geometry("1100x700")
    root.minsize(900, 600)
    root.configure(bg=BG)

    wire_ttk_style(root)
    set_status = build_top_bar(root)
    build_footer(root)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True)

    _tab_editor, on_submit, on_load_file = build_tab_editor(nb, set_status)
    build_tab_prompt(nb, set_status)
    build_tab_guide(nb)

    # Keyboard shortcuts
    root.bind("<Control-Return>", lambda e: on_submit())
    root.bind("<Control-o>",      lambda e: on_load_file())

    root.mainloop()


if __name__ == "__main__":
    main()