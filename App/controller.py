from tkinter import filedialog, messagebox
import json

from App.graphdb_client import (
    upload_ttl,
    run_shacl_validation,
    run_select_query,
    run_update_query
)


def load_file(ttl_text):
    path = filedialog.askopenfilename(filetypes=[("TTL Files", "*.ttl")])
    if path:
        with open(path, "r", encoding="utf-8") as f:
            ttl_text.delete("1.0", "end")
            ttl_text.insert("end", f.read())


def submit(ttl_text, output_text):
    ttl_content = ttl_text.get("1.0", "end")

    try:
        upload_ttl(ttl_content)

        validation_result = run_shacl_validation()
        if validation_result:
            messagebox.showerror("SHACL Validation Errors", validation_result)
            return

        output_text.delete("1.0", "end")

        results = run_select_query("NYICheck.sparql")
        output_text.insert("end", json.dumps(results, indent=2) + "\n")

        run_update_query("DerivedInfoQuery.sparql")
        run_update_query("InterpretationQuery.sparql")

        results = run_select_query("ResultsQuery.sparql")
        output_text.insert("end", json.dumps(results, indent=2))

    except Exception as e:
        messagebox.showerror("Error", str(e))
