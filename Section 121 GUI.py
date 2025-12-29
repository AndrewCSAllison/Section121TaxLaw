import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import requests
import urllib.parse
import json

# ------------------------------
# Configuration (GraphDB)
# ------------------------------
GRAPHDB_REPO = "http://localhost:7200/repositories/Section_121_Tax_Law"
SHACL_GRAPH = "http://rdf4j.org/schema/rdf4j#SHACLShapeGraph"

# ------------------------------
# GraphDB helper functions
# ------------------------------
def upload_ttl(ttl_content, target_graph=None):
    """Upload TTL content to a named graph (or default graph if None)."""
    ttl_content = ttl_content.strip()
    if not ttl_content:
        raise ValueError("TTL content is empty!")

    headers = {"Content-Type": "application/x-turtle", "Accept": "text/plain"}
    upload_url = f"{GRAPHDB_REPO}/statements"
    if target_graph:
        upload_url += f"?context={urllib.parse.quote(target_graph)}"

    response = requests.post(upload_url, data=ttl_content.encode("utf-8"), headers=headers)
    response.raise_for_status()
    return response.text


def run_shacl_validation():
    """Run SHACL validation and return TTL of violations (empty if none)."""
    query = f"""
    PREFIX sh: <http://www.w3.org/ns/shacl#>
    CONSTRUCT {{
        ?v a sh:ValidationResult ;
           sh:focusNode ?f ;
           sh:resultMessage ?m .
    }}
    WHERE {{
        GRAPH <{SHACL_GRAPH}> {{
            ?v a sh:ValidationResult ;
               sh:focusNode ?f ;
               sh:resultMessage ?m .
        }}
    }}
    """
    headers = {"Accept": "text/turtle", "Content-Type": "application/x-www-form-urlencoded"}
    data = f"query={urllib.parse.quote(query)}"
    response = requests.post(GRAPHDB_REPO, data=data, headers=headers)
    response.raise_for_status()
    ttl = response.text.strip()
    lines = [line for line in ttl.splitlines() if line.strip() and not line.startswith("@prefix")]
    return "\n".join(lines)


def load_query_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def run_update_query(file_path):
    """Run INSERT/UPDATE/DELETE queries."""
    query = load_query_file(file_path)
    headers = {"Content-Type": "application/sparql-update"}
    response = requests.post(f"{GRAPHDB_REPO}/statements", data=query.encode("utf-8"), headers=headers)
    response.raise_for_status()


def run_select_query(file_path):
    """Run SELECT/CONSTRUCT queries and return JSON results."""
    query = load_query_file(file_path)
    headers = {"Accept": "application/sparql-results+json", "Content-Type": "application/x-www-form-urlencoded"}
    data = f"query={urllib.parse.quote(query)}"
    response = requests.post(GRAPHDB_REPO, data=data, headers=headers)
    response.raise_for_status()
    return response.json()

# ------------------------------
# GUI Functions
# ------------------------------
def load_file():
    path = filedialog.askopenfilename(filetypes=[("TTL Files", "*.ttl")])
    if path:
        with open(path, "r", encoding="utf-8") as f:
            ttl_text.delete("1.0", tk.END)
            ttl_text.insert(tk.END, f.read())


def submit():
    ttl_content = ttl_text.get("1.0", tk.END)
    try:
        # Upload TTL first
        upload_ttl(ttl_content)

        # Run SHACL validation
        validation_result = run_shacl_validation()
        if validation_result:
            messagebox.showerror("SHACL Validation Errors", validation_result)
            print("SHACL Validation Errors:\n", validation_result)
            return

        # Manually execute queries
        output_text.delete("1.0", tk.END)

        # 1. NYICheck.sparql (SELECT)
        results = run_select_query("NYICheck.sparql")
        output_text.insert(tk.END, "--- Results from NYICheck.sparql ---\n")
        output_text.insert(tk.END, json.dumps(results, indent=2) if results["results"]["bindings"] else "✅ No results returned.\n")

        # 2. DerivedInfoQuery.sparql (INSERT)
        run_update_query("DerivedInfoQuery.sparql")
        output_text.insert(tk.END, "\n✅ Ran INSERT query: DerivedInfoQuery.sparql\n")

        # 3. InterpretationQuery.sparql (INSERT)
        run_update_query("InterpretationQuery.sparql")
        output_text.insert(tk.END, "✅ Ran INSERT query: InterpretationQuery.sparql\n")

        # 4. ResultsQuery.sparql (SELECT)
        results = run_select_query("ResultsQuery.sparql")
        output_text.insert(tk.END, "\n--- Results from ResultsQuery.sparql ---\n")
        output_text.insert(tk.END, json.dumps(results, indent=2) if results["results"]["bindings"] else "✅ No results returned.\n")


    except requests.HTTPError as e:
        messagebox.showerror("HTTP Error", str(e))
    except Exception as e:
        messagebox.showerror("Error", str(e))



# ------------------------------
# GUI Setup
# ------------------------------
root = tk.Tk()
root.title("§121 GraphDB Pipeline")

ttl_text = scrolledtext.ScrolledText(root, width=100, height=20)
ttl_text.pack(pady=5)

load_btn = tk.Button(root, text="Load TTL File", command=load_file)
load_btn.pack(pady=5)

submit_btn = tk.Button(root, text="Submit to GraphDB", command=submit)
submit_btn.pack(pady=5)

output_text = scrolledtext.ScrolledText(root, width=100, height=20)
output_text.pack(pady=5)

root.mainloop()
