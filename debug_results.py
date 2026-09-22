"""
debug_results.py — print what GraphDB returns at the ResultsQuery point.

The app renders results through App.formatter, which groups rows and names rules.
That is the wrong view when the question is what the SPARQL layer actually
produced, so this script stops one step earlier and prints the raw bindings,
values as GraphDB returned them.

By default each row shows only its gain figures — the row's own realized,
excluded and taxable gain, then the per-sale and per-return totals that
aggregate them.  --all restores every variable in the query, which is what to
reach for when a day count or a rule flag is the thing in question.

Usage:
    .venv\\Scripts\\python debug_results.py T046
    .venv\\Scripts\\python debug_results.py T046 T047 T077
    .venv\\Scripts\\python debug_results.py T046-T050          # a range
    .venv\\Scripts\\python debug_results.py T001-T077 E100-E105
    .venv\\Scripts\\python debug_results.py Test_Cases/T001    # one folder only
    .venv\\Scripts\\python debug_results.py "T008a & T008b"
    .venv\\Scripts\\python debug_results.py Taxpayer_Scenarios/Test_Cases/T010.ttl
    .venv\\Scripts\\python debug_results.py T046 --all         # every variable
    .venv\\Scripts\\python debug_results.py T046 --json

A range runs every case it covers, skipping numbers with no scenario file.  Case
numbers repeat across folders (there is a T001 in both Accuracy_Validation_Cases
and Test_Cases), so a range takes each of them.  Give a folder to narrow it:
"Test_Cases/T001-T005".

The repository in App.config.GRAPHDB_REPO is cleared once and the ontology and
SHACL shapes loaded once — they are the expensive part and no scenario touches
them.  The scenarios then go up in small passes: upload, SHACL, DerivedInfoQuery,
InterpretationQuery, ResultsQuery, then wipe the scenario data and derived graphs
and take the next pass.  The rows are split back out per scenario by the taxpayer
that owns them, and each gets its own heading.  This mirrors
controller.clear_repository() and controller.submit_with_callback() minus the
formatting.

Scenarios only stay independent because the queries key on the taxpayer and the
disposition, so two files may not share a fact-carrying IRI in one pass.  They do
share them often — the same case number in two folders declares the same taxpayer,
and eighteen Evaluation_Cases files declare :HouseDisposition with different sell
dates and gains — which is why a pass is closed early the moment the next file
would reuse one.  Bare vocabulary nodes (":House a :Property .") are exempt: they
are the same triple wherever they appear and the queries only reach them from a
node the taxpayer owns.  Exits 1 if the run fails.
"""

import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from App.config import ONTOLOGY_GRAPH, SHACL_GRAPH
from App.graphdb_client import (
    ShaclViolation,
    run_select_query,
    run_update_query,
    upload_ttl,
)

SCENARIOS = ROOT / "Taxpayer_Scenarios"
PROMPTS = ROOT / "Prompting_Files"
UNBOUND = "—"

# "T046-T050", "T046-050" and "T046-50" all mean the same thing.
RANGE = re.compile(r"^([A-Za-z_]*?)(\d+)\s*-\s*([A-Za-z_]*?)(\d+)$")

# A guard against a typo like "T1-T99999" spinning up thousands of full pipeline
# runs before anyone notices.
RANGE_LIMIT = 500


def split_folder(name):
    """Separate an optional folder qualifier from the case name."""
    folder, _, stem = name.replace("\\", "/").rpartition("/")
    return folder, stem


def match_scenarios(name):
    """
    Every scenario file a name matches.

    Exact stem first, then a prefix match — some scenarios are named for the pair
    of taxpayers they describe ("T008a & T008b.ttl"), so "T008" should still find
    them.  An optional folder qualifier ("Test_Cases/T001") restricts the search
    to folders whose name contains it, which is how a case number that repeats
    across folders gets pinned down.
    """
    folder, stem = split_folder(name)
    candidates = [
        p for p in SCENARIOS.rglob("*.ttl")
        if not folder or folder.lower() in p.parent.name.lower()
    ]
    exact = [p for p in candidates if p.stem == stem]
    return sorted(exact or [p for p in candidates if p.stem.startswith(stem)])


def expand_range(token):
    """
    Expand "T046-T050" into the case names it covers, or None if not a range.

    Numbers are zero-padded to the width the start was written with, so
    "T046-T050" produces T046…T050 rather than T46…T50.  Any folder qualifier on
    the token carries over to every name in the range.
    """
    folder, spec = split_folder(token)
    parsed = RANGE.match(spec)
    if not parsed:
        return None

    start_prefix, start_digits, end_prefix, end_digits = parsed.groups()
    if end_prefix and end_prefix.lower() != start_prefix.lower():
        print(f"{token!r}: a range needs one prefix — got {start_prefix!r} and {end_prefix!r}")
        return []

    start, end = int(start_digits), int(end_digits)
    if end < start:
        print(f"{token!r}: range ends before it starts")
        return []
    if end - start + 1 > RANGE_LIMIT:
        print(f"{token!r}: {end - start + 1} cases exceeds the {RANGE_LIMIT}-case limit")
        return []

    width = len(start_digits)
    prefix = f"{folder}/{start_prefix}" if folder else start_prefix
    return [f"{prefix}{number:0{width}d}" for number in range(start, end + 1)]


def resolve(tokens):
    """
    Turn the command-line arguments into scenario files, in the order given.

    A plain name must identify exactly one scenario; anything else is reported so
    it can be qualified.  A range is a sweep, so it takes every file each of its
    names matches and passes silently over numbers that have no file — ranges are
    expected to have gaps.  Returns (paths, saw_error).
    """
    paths, seen, saw_error = [], set(), False

    def keep(path):
        if path not in seen:
            seen.add(path)
            paths.append(path)

    for token in tokens:
        given = Path(token)
        if given.suffix == ".ttl":
            path = given if given.is_absolute() else ROOT / given
            if path.is_file():
                keep(path.resolve())
            else:
                print(f"no such file: {path}")
                saw_error = True
            continue

        names = expand_range(token)
        if names is not None:
            if not names:
                saw_error = True
                continue
            found = [p for name in names for p in match_scenarios(name)]
            if not found:
                print(f"{token!r}: no scenarios in that range")
                saw_error = True
            for path in found:
                keep(path)
            continue

        matches = match_scenarios(token)
        if not matches:
            print(f"no scenario matched {token!r} under {SCENARIOS.name}/")
            saw_error = True
        elif len(matches) > 1:
            print(f"{token!r} matched {len(matches)} scenarios — name one of them:")
            for path in matches:
                print(f"    {path.relative_to(ROOT).as_posix()}")
            saw_error = True
        else:
            keep(matches[0])

    return paths, saw_error


def local_name(value):
    """Shorten a URI to the part that identifies it; leave literals alone."""
    return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def is_amount(variable):
    """
    True for the gain figures, at whichever level the query reports them —
    ?realizedGain for the row, ?saleRealizedGain for the disposition,
    ?netRealizedGain for the return's same-day sales, and so on.
    """
    return variable.lower().endswith(("realizedgain", "excludedgain", "taxablegain"))


def amount_order(variable):
    """
    Row figures first, then the totals that aggregate them; within each level,
    realized before excluded before taxable, which is the order they derive in.
    """
    level = {"sale": 1, "net": 2}
    tier = next((rank for prefix, rank in level.items()
                 if variable.startswith(prefix)), 0)
    figure = ("realizedgain", "excludedgain", "taxablegain")
    return (tier, next((n for n, f in enumerate(figure)
                        if variable.lower().endswith(f)), len(figure)))


def cell_value(row, variable):
    cell = row.get(variable)
    if cell is None:
        # Shown rather than skipped: a binding that has gone missing is usually
        # the thing being debugged.
        return UNBOUND
    if cell.get("type") == "uri":
        return local_name(cell["value"])
    return cell["value"]


def row_label(row):
    """What the row is about, so the figures under it can be told apart."""
    parts = [cell_value(row, name) for name in ("taxpayer", "property", "sellDate")]
    return " | ".join(p for p in parts if p != UNBOUND)


def print_bindings(results, everything=False):
    """
    One block per row.

    By default only the gain figures are printed — the question this script
    usually answers is what the SPARQL layer computed, and the day counts and
    rule flags bury it.  Pass --all for every variable in the query's own order.
    """
    variables = results.get("head", {}).get("vars", [])
    rows = results.get("results", {}).get("bindings", [])
    print(f"ResultsQuery: {len(rows)} row{'' if len(rows) == 1 else 's'}")

    if not everything:
        variables = sorted((v for v in variables if is_amount(v)), key=amount_order)

    width = max((len(v) for v in variables), default=0)
    for number, row in enumerate(rows, start=1):
        label = row_label(row)
        print(f"\n--- row {number}{f'  {label}' if label else ''} ---")
        for variable in variables:
            print(f"  {variable.ljust(width)}  {cell_value(row, variable)}")


DECLARATION = re.compile(r"^:(\S+)\s+a\s+([^;.]+)([\s\S]*?)(?=^:|\Z)", re.M)

# A subject that carries no predicate of its own — ":House a :Property ." — is the
# same triple in every file that declares it, and the queries only ever reach it
# from a node the taxpayer owns, so two scenarios can hold it at once.
CARRIES_FACTS = re.compile(r":\w+\s+\S")

# How many scenarios go up at once.  Small enough that a pass stays quick to
# re-run when one case needs a second look, and that a SHACL violation names a
# short list of suspects.
PASS_SIZE = 3


def declared_subjects(path):
    """
    The subjects a scenario file declares, each mapped to whether it is shareable.

    Shareable means a bare vocabulary node — a :Property or a :ReasonType with
    nothing but its type.  Everything else (taxpayers, dispositions, intervals,
    returns) carries scenario facts, and two files declaring the same one merge
    into a scenario nobody wrote.  A :Taxpayer is never shareable even when it is
    declared bare, because partition() attributes rows by the taxpayer that owns
    them and needs exactly one file to answer for each.
    """
    text = path.read_text(encoding="utf-8")
    return {name: not CARRIES_FACTS.search(body) and ":Taxpayer" not in classes
            for name, classes, body in DECLARATION.findall(text)}


def plan_passes(paths):
    """
    Split the selection into small passes that can each share a repository.

    Scenario files reuse IRIs freely across cases: Evaluation_Cases has eighteen
    files declaring :HouseDisposition with different sell dates and gains.  Loaded
    together they either trip SHACL — one disposition with two sellDates — or,
    where the facts happen to agree (E160, E161 and E162), merge quietly and answer
    for a scenario nobody wrote.

    So the files are taken in order, PASS_SIZE at a time, and a pass is closed early
    the moment the next file would reuse an IRI already in it.  Each pass is
    (paths, name -> owning file), the second being what partition() attributes rows
    with.
    """
    passes = []
    kept, claimed, bare, owners = [], set(), set(), {}

    for path in paths:
        subjects = declared_subjects(path)
        exclusive = {n for n, shareable in subjects.items() if not shareable}
        shared = {n for n, shareable in subjects.items() if shareable}
        collides = bool(exclusive & (claimed | bare) or shared & claimed)

        if kept and (collides or len(kept) >= PASS_SIZE):
            passes.append((kept, owners))
            kept, claimed, bare, owners = [], set(), set(), {}

        kept.append(path)
        claimed |= exclusive
        bare |= shared
        owners.update(dict.fromkeys(exclusive, path))

    if kept:
        passes.append((kept, owners))
    return passes


def partition(results, paths, owners):
    """
    Split one ResultsQuery response into (name, source, response) per scenario.

    Every scenario is in the repository at once, so the query answers for all of
    them together; each row goes back to the file that declared its taxpayer, in
    the order the files were given.  Rows nothing claims are kept rather than
    dropped, since a row with no home is a symptom worth seeing.
    """
    head = results.get("head", {})
    groups = OrderedDict((path, []) for path in paths)
    orphans = []

    for row in results.get("results", {}).get("bindings", []):
        cell = row.get("taxpayer")
        owner = owners.get(local_name(cell["value"])) if cell else None
        (groups[owner] if owner in groups else orphans).append(row)

    listed = [(path.stem, path.relative_to(ROOT).as_posix(), rows)
              for path, rows in groups.items()]
    if orphans:
        listed.append(("unattributed", "no selected scenario declared this taxpayer",
                       orphans))
    return [(name, source, {"head": head, "results": {"bindings": rows}})
            for name, source, rows in listed]


DATA_GRAPHS = ("http://example.org/section121#DerivedInfo",
               "http://example.org/section121#InterpretationInfo")


def load_ontology():
    """Wipe the repository and put the ontology and the SHACL shapes back."""
    run_update_query("CLEAR ALL", from_file=False)
    upload_ttl((PROMPTS / "Section_121_SHACL_Shapes.ttl").read_text(encoding="utf-8"),
               target_graph=SHACL_GRAPH)
    upload_ttl((PROMPTS / "Section_121_Taxpayer_Ontology.ttl").read_text(encoding="utf-8"),
               target_graph=ONTOLOGY_GRAPH)


def clear_scenario_data():
    """
    Drop the scenario data and everything derived from it, keeping the ontology.

    This is what makes a second pass independent of the first: DerivedInfoQuery and
    InterpretationQuery only ever INSERT, so rows left from the previous pass would
    otherwise still be there for ResultsQuery to read.
    """
    clauses = ["CLEAR DEFAULT"] + [f"CLEAR GRAPH <{graph}>" for graph in DATA_GRAPHS]
    run_update_query(" ; ".join(clauses), from_file=False)


def run_pass(paths, owners, everything, label=""):
    """
    Run the pipeline once over one collision-free set of scenarios.

    The scenarios go up together and a single DerivedInfoQuery / InterpretationQuery
    / ResultsQuery covers the lot; the rows are then split back out by the taxpayer
    that owns them.  Returns (reached ResultsQuery, the raw response).
    """
    print(f"[1/4] uploading {len(paths)} scenario{'' if len(paths) == 1 else 's'}{label}")
    for path in paths:
        try:
            upload_ttl(path.read_text(encoding="utf-8"))
        except ShaclViolation as exc:
            # The shapes are enforced on commit, so the upload that raised names
            # the file at fault; the ones printed before it are already in.
            print(f"  SHACL VIOLATIONS - {path.relative_to(ROOT).as_posix()} was rejected:")
            for violation in exc.violations:
                print(f"    {violation}")
            return False, None
        if len(paths) > 1:
            print(f"  {path.relative_to(ROOT).as_posix()}")

    print("[2/4] SHACL validation")
    print("  no violations (the shapes are enforced on commit)")

    print("[3/4] NYI check")
    undefined = run_select_query("NYICheck.sparql")["results"]["bindings"]
    if undefined:
        # Not fatal: the queries still run, the undefined terms just do nothing.
        print(f"  {len(undefined)} undefined entit{'y' if len(undefined) == 1 else 'ies'}:")
        for row in undefined:
            print(f"    {row['type']['value']}: {local_name(row['undefined']['value'])}"
                  f"  (on {local_name(row['s']['value'])})")
    else:
        print("  no undefined entities")

    print("[4/4] applying DerivedInfoQuery, InterpretationQuery")
    run_update_query("DerivedInfoQuery.sparql")
    run_update_query("InterpretationQuery.sparql")
    return True, run_select_query("ResultsQuery.sparql")


def run_all(passes, as_json, everything=False):
    """
    Run every pass, wiping the scenario data between them, and report.

    The ontology and the shapes are loaded once and left alone — they are the
    expensive part, and nothing a scenario does touches them.

    True if every pass reached ResultsQuery.
    """
    print("clearing repository; loading ontology + SHACL shapes")
    load_ontology()

    ok, merged, reports = True, None, []
    for number, (paths, owners) in enumerate(passes, start=1):
        if number > 1:
            clear_scenario_data()
        label = f"  (pass {number} of {len(passes)})" if len(passes) > 1 else ""
        try:
            reached, results = run_pass(paths, owners, everything, label)
        except Exception as exc:
            # One unloadable scenario should not cost the other 230 their run, so
            # the pass is abandoned and the sweep carries on.  The files named just
            # above are the ones that went unreported.
            print(f"  PASS FAILED: {exc}")
            reached, results = False, None
        if not reached:
            ok = False
            continue
        if merged is None:
            merged = {"head": results.get("head", {}),
                      "results": {"bindings": []}}
        merged["results"]["bindings"] += results["results"]["bindings"]
        reports += partition(results, paths, owners)

    if as_json:
        # One response for the whole run: partitioning it would misrepresent what
        # the query returned, which is the point of asking for the JSON.
        print(json.dumps(merged or {"head": {}, "results": {"bindings": []}}, indent=2))
        return ok

    for name, source, subset in reports:
        print(f"\n=== {name}  ({source}) ===")
        print_bindings(subset, everything)
    return ok


def main(argv):
    as_json = "--json" in argv
    everything = "--all" in argv
    tokens = [a for a in argv if not a.startswith("--")]

    if not tokens:
        print(__doc__.strip())
        return 1

    paths, failed = resolve(tokens)
    if not paths:
        return 1

    passes = plan_passes(paths)
    if len(paths) > 1:
        print(f"{len(paths)} scenarios to run in "
              f"{len(passes)} pass{'' if len(passes) == 1 else 'es'}")

    try:
        if not run_all(passes, as_json, everything):
            failed = True
    except Exception as exc:
        print(f"  PIPELINE FAILED: {exc}")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
