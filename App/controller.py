from tkinter import filedialog, messagebox
import json

from App.formatter import format_results_nl
from App.config import SHACL_GRAPH, ONTOLOGY_GRAPH
from App.graphdb_client import (
    upload_ttl,
    run_shacl_validation,
    run_select_query,
    run_update_query
)

def clear_repository():
    try:
        run_update_query("CLEAR ALL", from_file=False)
        shaclShapes = load_file_contents("Prompting_Files\Section 121 SHACL Shapes.ttl")
        ontology = load_file_contents("Prompting_Files\Section 121 Taxpayer Ontology.ttl")
        upload_ttl(shaclShapes, target_graph=SHACL_GRAPH)
        upload_ttl(ontology, target_graph=ONTOLOGY_GRAPH)
    except Exception as e:
        messagebox.showerror("Error", str(e))

def load_file_contents(path: str) -> str:
    """Returns the TTL content of a file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_file(ttl_text):
    path = filedialog.askopenfilename(filetypes=[("TTL Files", "*.ttl")])
    if path:
        with open(path, "r", encoding="utf-8") as f:
            ttl_text.delete("1.0", "end")
            ttl_text.insert("end", f.read())


def submit(ttl_text, output_text):
    ttl_content = ttl_text.get("1.0", "end")

    try:
        # Upload TTL
        upload_ttl(ttl_content)

        # Run SHACL validation
        validation_result = run_shacl_validation()
        if validation_result:
            messagebox.showerror("SHACL Validation Errors", validation_result)
            return

        # Run preliminary SPARQL query
        results = run_select_query("NYICheck.sparql")
        output_text.configure(state="normal")
        output_text.insert("end", "=== NYI Check Results ===\n")
        output_text.insert("end", json.dumps(results, indent=2) + "\n\n")

        # Execute updates / rules
        run_update_query("DerivedInfoQuery.sparql")
        run_update_query("InterpretationQuery.sparql")

        # Run final SPARQL query
        results = run_select_query("ResultsQuery.sparql")
        output_text.insert("end", "=== Final Results ===\n")
        output_text.insert("end", format_results_nl(results) + "\n\n")

        output_text.configure(state="disabled")
        output_text.see("end")

    except Exception as e:
        messagebox.showerror("Error", str(e))
