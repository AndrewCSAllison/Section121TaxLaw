from pathlib import Path
from wsgiref import headers

import requests
import urllib.parse

from App.config import GRAPHDB_REPO, SHACL_GRAPH

BASE_DIR = Path(__file__).resolve().parent
SPARQL_DIR = BASE_DIR.parent / "SPARQL_Queries"


# ──────────────────────────────────────────────
#  Error helper
# ──────────────────────────────────────────────

def _check_response(response: requests.Response, context: str = "") -> None:
    """
    Raise a descriptive RuntimeError when GraphDB returns a non-2xx status.

    requests.raise_for_status() only surfaces the HTTP status code; the actual
    GraphDB error message lives in response.text (e.g. "MALFORMED DATA: Expected
    '.', found ':' [line 23]").  This helper appends that body so the pipeline
    log shows the full, actionable error instead of a bare '400 Client Error'.
    """
    if response.ok:
        return
    body = response.text.strip() if response.text else "(no response body)"
    prefix = f"[{context}] " if context else ""
    raise RuntimeError(
        f"{prefix}HTTP {response.status_code} from GraphDB:\n{body}"
    )


# ──────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────

def upload_ttl(ttl_content: str, target_graph: str = None) -> str:
    """
    Upload TTL content to a named graph (or default graph if None).
    Properly URL-encodes graph URIs with '#' fragments.
    """
    ttl_content = ttl_content.strip()
    if not ttl_content:
        raise ValueError("TTL content is empty!")

    headers = {"Content-Type": "application/x-turtle", "Accept": "text/plain"}
    upload_url = f"{GRAPHDB_REPO}/statements"

    if target_graph:
        params = {'context': f'<{target_graph}>'}
        response = requests.post(upload_url, data=ttl_content.encode("utf-8"), headers=headers, params=params)
    else:
        response = requests.post(upload_url, data=ttl_content.encode("utf-8"), headers=headers)

    response = requests.post(upload_url, data=ttl_content.encode("utf-8"), headers=headers)
    _check_response(response, "upload_ttl")
    return response.text


def run_shacl_validation():
    """Run SHACL validation and return TTL of violations (empty string if none)."""
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
    _check_response(response, "run_shacl_validation")
    ttl = response.text.strip()
    lines = [line for line in ttl.splitlines() if line.strip() and not line.startswith("@prefix")]
    return "\n".join(lines)


def load_query_file(filename):
    path = SPARQL_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"SPARQL file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def run_update_query(query: str, from_file: bool = True):
    """
    Sends a SPARQL UPDATE to GraphDB.
    If from_file=True, *query* is treated as a filename relative to SPARQL_DIR.
    """
    if from_file:
        query = load_query_file(query)

    headers = {"Content-Type": "application/sparql-update"}
    response = requests.post(
        f"{GRAPHDB_REPO}/statements",
        data=query.encode("utf-8"),
        headers=headers,
    )
    _check_response(response, f"run_update_query({query[:40]!r})")


def run_select_query(filename):
    query = load_query_file(filename)
    headers = {
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = f"query={urllib.parse.quote(query)}"
    response = requests.post(GRAPHDB_REPO, data=data, headers=headers)
    _check_response(response, f"run_select_query({filename!r})")
    return response.json()