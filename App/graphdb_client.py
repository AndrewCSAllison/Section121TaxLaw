from pathlib import Path
from wsgiref import headers

import re
import requests
import urllib.parse

from App.config import GRAPHDB_REPO

BASE_DIR = Path(__file__).resolve().parent
SPARQL_DIR = BASE_DIR.parent / "SPARQL_Queries"


# ──────────────────────────────────────────────
#  SHACL rejection reports
# ──────────────────────────────────────────────

class ShaclViolation(RuntimeError):
    """
    Raised when GraphDB refuses a commit because the data breaks the shapes.

    Distinct from a plain upload failure: the Turtle parsed, the store simply
    would not accept the facts it carried.  *violations* holds one readable
    line for each.
    """

    def __init__(self, violations):
        count = len(violations)
        super().__init__(f"{count} SHACL violation{'' if count == 1 else 's'}")
        self.violations = violations


_NT_LINE = re.compile(r"^(\S+)\s+<([^>]+)>\s+(.+?)\s*\.$")
_SH = "http://www.w3.org/ns/shacl#"
_RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def _short(term: str) -> str:
    """Shorten a URI to the part that identifies it."""
    return term.strip("<>").rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def parse_validation_report(body: str):
    """
    Turn GraphDB's rejection body into one readable line per violation.

    The SHACL sail validates as it commits, so a violating transaction is refused
    and its report never reaches the store — it comes back in the error body as
    N-Triples.  That format is flat enough to read with a regex, which keeps
    rdflib off the dependency list for one error path.

    A result carries sh:resultMessage only where its shape declares sh:message,
    so the constraint that failed is named whenever it does not.

    Returns [] when the body is not a validation report, letting the caller fall
    back to the generic HTTP message.
    """
    triples = {}
    for line in body.splitlines():
        match = _NT_LINE.match(line.strip())
        if match:
            subject, predicate, obj = match.groups()
            triples.setdefault(subject, {})[predicate] = obj

    reported = {}
    for properties in triples.values():
        if properties.get(_RDF_TYPE) != f"<{_SH}ValidationResult>":
            continue
        focus = _short(properties.get(f"{_SH}focusNode", ""))
        path = _short(properties.get(f"{_SH}resultPath", ""))
        raw = properties.get(f"{_SH}resultMessage", "")
        authored = raw.startswith('"')
        if authored:
            message = raw[1:raw.rfind('"')]
        else:
            constraint = _short(properties.get(f"{_SH}sourceConstraintComponent", ""))
            message = f"fails {constraint or 'an unnamed constraint'}"
        reported.setdefault((focus, path), {True: set(), False: set()})[authored].add(message)

    # The sail reports a constraint twice when its shape declares sh:message —
    # once bare, once carrying the text — so the authored wording wins, and the
    # constraint name is shown only where no shape supplied one.
    violations = []
    for (focus, path), messages in reported.items():
        for message in sorted(messages[True] or messages[False]):
            violations.append(f"{focus} · {path} — {message}")
    return sorted(violations)


# ──────────────────────────────────────────────
#  Error helper
# ──────────────────────────────────────────────

def _check_response(response: requests.Response, context: str = "") -> None:
    """
    Raise a descriptive error when GraphDB returns a non-2xx status.

    requests.raise_for_status() only surfaces the HTTP status code; the actual
    GraphDB error message lives in response.text (e.g. "MALFORMED DATA: Expected
    '.', found ':' [line 23]").  This helper appends that body so the pipeline
    log shows the full, actionable error instead of a bare '400 Client Error'.

    A SHACL violation arrives the same way but means something different — the
    Turtle was well-formed and the store rejected the facts it carried — so it
    gets its own exception instead of being reported as a failed upload.
    """
    if response.ok:
        return
    body = response.text.strip() if response.text else "(no response body)"

    violations = parse_validation_report(body)
    if violations:
        raise ShaclViolation(violations)

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

    # One request only.  Posting a second time without the context parameter would
    # copy a graph-targeted upload into the default graph as well, putting the
    # ontology and the SHACL shapes into the data graph on every run.
    params = {'context': f'<{target_graph}>'} if target_graph else None
    response = requests.post(
        upload_url,
        data=ttl_content.encode("utf-8"),
        headers=headers,
        params=params,
    )
    _check_response(response, "upload_ttl")
    return response.text


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