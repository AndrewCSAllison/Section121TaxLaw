"""
controller.py — Backend logic layer.

Responsibilities:
  - File I/O (load_file, load_file_contents)
  - Repository management (clear_repository)
  - Pipeline orchestration (submit_with_callback)

UI concerns (tkinter widgets, messagebox) are kept out of
submit_with_callback intentionally — the caller passes a `log`
callback so this module stays testable and UI-agnostic.
"""

import json
from tkinter import filedialog, messagebox

try:
    from App.formatter import format_results_nl
    from App.config import SHACL_GRAPH, ONTOLOGY_GRAPH
    from App.graphdb_client import (
        ShaclViolation,
        upload_ttl,
        run_select_query,
        run_update_query,
    )
except ModuleNotFoundError:
    from formatter import format_results_nl
    from config import SHACL_GRAPH, ONTOLOGY_GRAPH
    from graphdb_client import (
        ShaclViolation,
        upload_ttl,
        run_select_query,
        run_update_query,
    )


# ──────────────────────────────────────────────
#  File helpers
# ──────────────────────────────────────────────

def load_file_contents(path: str) -> str:
    """Return the text content of *path*."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_file(ttl_text_widget) -> bool:
    """
    Open a file-picker dialog and load a .ttl file into *ttl_text_widget*.
    Returns True if a file was loaded, False if the dialog was cancelled.
    """
    path = filedialog.askopenfilename(filetypes=[("TTL Files", "*.ttl")])
    if not path:
        return False
    with open(path, "r", encoding="utf-8") as f:
        ttl_text_widget.delete("1.0", "end")
        ttl_text_widget.insert("end", f.read())
    return True


# ──────────────────────────────────────────────
#  Repository management
# ──────────────────────────────────────────────

def clear_repository():
    """
    Wipe all statements from the repository, then reload the base
    ontology and SHACL shapes.  Raises on failure (caller handles UI).
    """
    run_update_query("CLEAR ALL", from_file=False)
    shacl = load_file_contents(r"Prompting_Files\Section_121_SHACL_Shapes.ttl")
    ontology = load_file_contents(r"Prompting_Files\Section_121_Taxpayer_Ontology.ttl")
    upload_ttl(shacl, target_graph=SHACL_GRAPH)
    upload_ttl(ontology, target_graph=ONTOLOGY_GRAPH)


# ──────────────────────────────────────────────
#  Pipeline
# ──────────────────────────────────────────────

def submit_with_callback(ttl_content: str, log):
    """
    Run the full §121 pipeline for *ttl_content*, routing every status
    message through *log(message, tag)*.

    Tags mirror the results-pane color tags in the UI:
        "system"  — neutral status lines
        "success" — step passed
        "error"   — step failed  (returns early on hard failures)
        "warning" — non-fatal issue
        "heading" — section dividers
        "result"  — final human-readable output

    This function is intentionally UI-agnostic: it never touches tkinter
    widgets directly, making it straightforward to unit-test or reuse.
    """

    # 1. Upload TTL.  GraphDB validates against the SHACL shapes as it commits,
    #    so a violating scenario is refused here and never reaches step 2.
    log("  Uploading TTL…", "system")
    try:
        upload_ttl(ttl_content)
    except ShaclViolation as exc:
        # The Turtle parsed — it is the facts the shapes reject — so say that
        # before listing what has to change.
        log("  ✔ TTL parsed", "success")
        log("  ✘ SHACL Violations Found:", "error")
        for violation in exc.violations:
            log(f"    {violation}", "error")
        return
    except Exception as exc:
        log(f"  ✘ Upload failed: {exc}", "error")
        return
    log("  ✔ TTL uploaded successfully", "success")

    # 2. SHACL validation — enforced by the store on the commit above, so
    #    arriving here with the data in place is the pass.
    log("  ✔ SHACL: no violations", "success")

    # 3. NYI check
    log("  Running NYI check…", "system")
    try:
        nyi = run_select_query("NYICheck.sparql")
        bindings = nyi.get("results", {}).get("bindings", [])
        if bindings:
            log("  ⚠ Undefined entities found:", "warning")
            log(json.dumps(nyi, indent=2), "warning")
        else:
            log("  ✔ NYI Check: no undefined entities", "success")
    except Exception as exc:
        log(f"  ✘ NYI check error: {exc}", "error")
        return

    # 4. Derived-info update queries
    log("  Running derived-info queries…", "system")
    for query_file in ("DerivedInfoQuery.sparql", "InterpretationQuery.sparql"):
        try:
            run_update_query(query_file)
            log(f"  ✔ {query_file}", "success")
        except Exception as exc:
            log(f"  ✘ {query_file} failed: {exc}", "error")
            return

    # 5. Final results
    log("  Fetching results…", "system")
    try:
        results = run_select_query("ResultsQuery.sparql")
        output = format_results_nl(results)
        log("\n── Final Results ────────────────────────────────", "heading")
        log(output if output.strip() else "(no results returned)", "result")
    except Exception as exc:
        log(f"  ✘ Results query error: {exc}", "error")


# ──────────────────────────────────────────────
#  Legacy entry point (kept for back-compat)
# ──────────────────────────────────────────────

def submit(ttl_text_widget, output_text_widget):
    """
    Original submit() — kept for backwards compatibility.
    New callers should prefer submit_with_callback().
    """
    ttl_content = ttl_text_widget.get("1.0", "end")

    def _log(msg, _tag="result"):
        output_text_widget.configure(state="normal")
        output_text_widget.insert("end", msg + "\n")
        output_text_widget.configure(state="disabled")
        output_text_widget.see("end")

    try:
        submit_with_callback(ttl_content, _log)
    except Exception as exc:
        messagebox.showerror("Error", str(exc))