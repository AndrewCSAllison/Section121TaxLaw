from pathlib import Path

import requests
import urllib.parse

from App.config import GRAPHDB_REPO, SHACL_GRAPH

BASE_DIR = Path(__file__).resolve().parent
SPARQL_DIR = BASE_DIR / "Resources" / "SPARQL_Queries"

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

def load_query_file(filename):
    path = SPARQL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"SPARQL file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def run_update_query(filename):
    query = load_query_file(filename)
    headers = {"Content-Type": "application/sparql-update"}
    response = requests.post(
        f"{GRAPHDB_REPO}/statements",
        data=query.encode("utf-8"),
        headers=headers
    )
    response.raise_for_status()


def run_select_query(filename):
    query = load_query_file(filename)
    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = f"query={urllib.parse.quote(query)}"
    response = requests.post(GRAPHDB_REPO, data=data, headers=headers)
    response.raise_for_status()
    return response.json()
