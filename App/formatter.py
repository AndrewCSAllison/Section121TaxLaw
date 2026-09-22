"""
formatter.py — Presentation layer for ResultsQuery output.

This module does no tax arithmetic.  Every gain figure it prints — realized,
excluded and taxable — is the value GraphDB returned for that row, rendered
verbatim.  All §121 logic (dollar limitations, loss offsets, per-spouse
attribution, taxable-gain arithmetic) belongs in the SPARQL layer, where it can
be inspected and validated on its own; anything this module recomputed would
silently diverge from the knowledge graph it is supposed to be reporting.

Its only jobs are:
  1. group the rows of a single sale (one row per taxpayer) together,
  2. name the rules each row triggered, and
  3. lay the numbers out readably.
"""

from collections import OrderedDict


# ── Rule labels ───────────────────────────────────────────────────────────────
RULES_MAP = OrderedDict([
    ("Rule121aFinal",      "§121(a) applies"),
    ("Rule121b1Excluded",  "§121(b)(1) exclusion"),
    ("Rule121b2AExcluded", "§121(b)(2)(A) exclusion"),
    ("Rule121b2BExcluded", "§121(b)(2)(B) exclusion"),
    ("Rule121b3Applies",   "§121(b)(3) applies"),
    ("Rule121cExcluded",   "§121(c) exclusion"),
    # A §121(c) claim the graph considered and refused.  It never coincides with
    # the entry above — one requires a qualifying circumstance and the other its
    # absence — and it earns a line because the row it sits on otherwise reports
    # a bare $0, which reads as though no partial exclusion was ever in play.
    ("Rule121cReasonNonQualifying",
     "§121(c) does not apply — the sale was not by reason of health, "
     "employment, or qualifying unforeseen circumstances"),
    ("Rule121d1Applies",   "§121(d)(1) applies"),
])

# The three circumstances §121(c)(2)(B) admits, in the statute's own words.
REASON_PHRASES = {
    "EmploymentRelatedReason":     "a change in place of employment",
    "HealthRelatedReason":         "health",
    "UnforeseenCircumstanceReason": "unforeseen circumstances",
}

_FALSEY = {"", "false", "0", "0.0", "0.00"}

# The one limitation that belongs to a couple rather than to each spouse.
B121B2A = RULES_MAP["Rule121b2AExcluded"]


def _local_name(uri: str) -> str:
    """Strip the namespace from a URI so :T046a renders as T046a."""
    return uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _value(row, key, default=""):
    return row.get(key, {}).get("value", default)


def _num(row, key):
    """
    Return a row's numeric literal as returned by GraphDB.

    Parsed to float only so it can be laid out (thousands separator, trailing
    ".0" dropped); the value itself is never adjusted.  Rows missing the
    binding return None so the caller can print "—" rather than invent a 0.
    """
    raw = _value(row, key)
    if raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _fmt(amount) -> str:
    """
    Render a figure for display without changing it.

    A loss carries its sign outside the currency symbol — "-$25,000", not
    "$-25,000" — since loss rows are now printed as such and read alongside the
    combined total that offsets them.
    """
    if amount is None:
        return "—"
    sign = "-" if amount < 0 else ""
    size = abs(amount)
    if size == int(size):
        return f"{sign}${int(size):,}"
    return f"{sign}${size:,.2f}"


def _partial_exclusion_label(rows) -> str:
    """
    The §121(c) label, naming the circumstance that opened the reduced exclusion.

    §121(c)(2)(B) admits only three, and which of them applied is the fact the
    reduced exclusion turns on, so the entry names it rather than leaving the
    reader to go back to the scenario for it.  The reason is a property of the
    disposition, so every row of a sale carries the same one; a reason the query
    did not return, or one outside the three, leaves the bare label — the rule
    fired, and inventing a circumstance for it would be worse than saying
    nothing.
    """
    label = RULES_MAP["Rule121cExcluded"]
    for row in rows:
        phrase = REASON_PHRASES.get(_local_name(_value(row, "partialExclusionReason")))
        if phrase:
            return f"{label} — the sale was by reason of {phrase}"
    return label


def _rules_for(*rows):
    """The labels of every rule the given rows triggered, in statute order."""
    fired = []
    for key, label in RULES_MAP.items():
        if any(_value(row, key).lower() not in _FALSEY for row in rows):
            if key == "Rule121cExcluded":
                label = _partial_exclusion_label(rows)
            fired.append(label)
    return fired


def _return_type(row) -> str:
    if _value(row, "isSingleReturn").lower() == "true":
        return "single return"
    if _value(row, "isJointReturn").lower() == "true":
        return "joint return"
    return ""


def _files_separately(rows) -> bool:
    """
    True when a sale's rows are co-owners filing their own returns rather than
    the spouses of one return.

    Nothing about §121 is determined jointly for them: each owns a share, each
    gets their own $250,000 limitation under §121(b)(1) against that share, and
    neither one's ownership, use or prior-sale history bears on the other's.
    Scenario T031 is the case — two single filers holding one residence 50/50 —
    and reporting them as one entry reads as a couple's return, which is the one
    thing they are not.  Contrast the joint provisions, where the shared entry is
    the substance: §121(b)(2)(A) grants the couple a single limitation and
    §121(b)(2)(B) sums the two they would have had unmarried.
    """
    return len(rows) > 1 and all(
        _value(row, "isSingleReturn").lower() == "true" for row in rows
    )


def _reports_as_one_joint_entry(rows) -> bool:
    """
    True when a joint return's rows should be reported as a single entry for the
    couple rather than broken out per spouse.

    Two quite different row shapes reach that same conclusion:

    §121(b)(2)(A) grants the couple a single $500,000 limitation against the
    whole gain.  The rules layer has to park that whole gain on one spouse's row
    for the limitation to be applied to it once, so the rows are *not* alike —
    one holds the sale's gain and the other zero.  Printing that split would
    show one spouse owning the property and excluding alone.

    A mirrored split is the opposite case: neither spouse carries the whole
    gain, each holds their own share of it, and each applied their own
    limitation to that share.  Reg. §1.121-3(g)(1) is the usual reason — on a
    joint return each spouse computes a separate §121(c) reduced maximum
    limitation and the two are summed (scenario T066).  When both rows then fire
    the same rules and print the same figures, the per-spouse breakdown says
    nothing the sale totals do not, and two identical halves read as two
    co-owners each holding half the house rather than as one couple's return.

    Comparing the rendered figures rather than the parsed numbers is deliberate:
    the question here is whether a reader would see the same line twice, which
    is exactly what the breakdown has to earn.

    This is presentation only.  The underlying split must stay — the spouses'
    limitations really are separate, and merging their shares onto one row would
    apply a single reduced limitation to the whole gain.  Scenario T067 is the
    proof: a $150,000 gain, $125,342.47 of reduced exclusion each, fully
    excluded only because each half is decided against its own limitation.
    """
    if len(rows) < 2 or _value(rows[0], "isJointReturn").lower() != "true":
        return False
    if B121B2A in _rules_for(*rows):
        return True
    first = rows[0]
    return all(
        _rules_for(row) == _rules_for(first) and _row_figures(row) == _row_figures(first)
        for row in rows[1:]
    )


def _figures(realized, excluded, taxable) -> str:
    return (
        f"Realized gain: {_fmt(realized)}, "
        f"Excluded gain: {_fmt(excluded)}, "
        f"Taxable gain: {_fmt(taxable)}"
    )


def _row_figures(row) -> str:
    return _figures(_num(row, "realizedGain"),
                    _num(row, "excludedGain"),
                    _num(row, "taxableGain"))


def _sale_amounts(row):
    """
    The sale's own figures, totalled by ResultsQuery across the rows of the
    disposition.  Returns None when the query did not supply them — the totals
    are then omitted rather than added up here.
    """
    amounts = (_num(row, "saleRealizedGain"),
               _num(row, "saleExcludedGain"),
               _num(row, "saleTaxableGain"))
    return None if all(a is None for a in amounts) else amounts


def _sale_totals(row):
    amounts = _sale_amounts(row)
    if amounts is None:
        return None
    realized, excluded, taxable = amounts
    return (
        f"Sale totals — realized gain: {_fmt(realized)}, "
        f"excluded gain: {_fmt(excluded)}, "
        f"taxable gain: {_fmt(taxable)}"
    )


def _net_group_key(row, fallback):
    """
    The sales ResultsQuery netted together — a (return, sell date) pair.  Rows
    with no return fall back to their own disposition, so they stand alone.
    """
    group = _value(row, "netGroup")
    if group == "":
        return ("", fallback)
    return (group, _value(row, "sellDate"))


def _net_totals(row):
    """
    The combined figures for a return's same-day sales, totalled by ResultsQuery
    under Reg. §1.121-1(b)(3).  Returned only when the group actually spans
    several sales and one of them was a loss — otherwise the combined line would
    merely restate the sale above it.  Like every other figure here, the numbers
    are the query's own.
    """
    if _value(row, "netGroupHasLoss").lower() in _FALSEY:
        return None
    count = _num(row, "netSaleCount")
    if count is None or count < 2:
        return None
    amounts = (_num(row, "netRealizedGain"),
               _num(row, "netExcludedGain"),
               _num(row, "netTaxableGain"))
    if any(a is None for a in amounts):
        return None
    realized, excluded, taxable = amounts
    return (
        "Combined same-day sale totals (Reg. §1.121-1(b)(3) — treated as one sale) — "
        f"realized gain: {_fmt(realized)}, "
        f"excluded gain: {_fmt(excluded)}, "
        f"taxable gain: {_fmt(taxable)}"
    )


def _sale_block(prop, sell_date, rows) -> str:
    """One sale's entry: its header, the rules it fired, and its figures."""
    if len(rows) == 1:
        row = rows[0]
        taxpayer = _local_name(_value(row, "taxpayer", "Unknown taxpayer"))
        ret = _return_type(row)
        suffix = f" ({ret})" if ret else ""

        lines = [f"Taxpayer {taxpayer} sold property {prop} on {sell_date}{suffix}."]
        lines.extend(f"- {rule}" for rule in _rules_for(row))
        lines.append(_row_figures(row))
        return "\n".join(lines)

    # Several taxpayers on one sale: one block, one sub-entry per taxpayer.
    taxpayers = [_local_name(_value(r, "taxpayer", "Unknown taxpayer")) for r in rows]
    ret = _return_type(rows[0])
    suffix = f" ({ret})" if ret else ""

    header = (f"Taxpayers {', '.join(taxpayers)} sold property {prop} "
              f"on {sell_date}{suffix}.")
    fired_across_rows = _rules_for(*rows)
    sale = _sale_amounts(rows[0])

    # A joint return reports as one entry for the couple when the per-spouse
    # rows add nothing to it — see _reports_as_one_joint_entry.  Contrast
    # §121(b)(2)(B), where each spouse's limitation genuinely is determined
    # separately and the differing rows are the point.  The sale totals are
    # required: with no figures from the query for the couple as a whole there
    # is nothing to print but the breakdown.
    if _reports_as_one_joint_entry(rows) and sale is not None:
        lines = [header]
        if fired_across_rows:
            lines.extend(f"- {rule}" for rule in fired_across_rows)
        else:
            # Neither spouse triggered anything — scenario T068, where the whole
            # gain is taxable.  The per-spouse branch says so rather than leaving
            # the reader to infer it from a bare figure line; so should this one.
            lines.append("- no exclusion rules triggered")
        lines.append(_figures(*sale))
        return "\n".join(lines)

    lines = [header]
    for row, taxpayer in zip(rows, taxpayers):
        lines.append(f"  Taxpayer {taxpayer}:")
        fired = _rules_for(row)
        if fired:
            lines.extend(f"    - {rule}" for rule in fired)
        else:
            lines.append("    - no exclusion rules triggered")
        lines.append(f"    {_row_figures(row)}")

    totals = _sale_totals(rows[0])
    if totals:
        lines.append(totals)
    return "\n".join(lines)


def format_results_nl(results_json):
    """
    Turn ResultsQuery bindings into readable text.

    Rows are grouped by disposition, because a joint return produces one row per
    spouse for the same sale — and because the sale totals ResultsQuery supplies
    are per-disposition.  Grouping on property alone would merge two co-owners
    who each dispose of their own interest into one block under a total covering
    only one of them.  A disposition with a single row is printed flat.  One with
    several is printed as a single joint entry when the couple's rows do not
    differ in a way worth showing — §121(b)(2)(A), whose limitation belongs to
    the couple rather than to either spouse, and mirrored rows that fired the
    same rules for the same figures — and otherwise as a block listing each
    taxpayer's own rules and figures, since the remaining joint provisions do
    turn on what each spouse is separately entitled to.

    The exception is co-owners who each file their own return: they share the
    sale but no §121 determination, so their rows are split back apart and each
    is reported as its own sale entry.

    Sales the query netted together — a dwelling and its vacant land sold the
    same day, which Reg. §1.121-1(b)(3) treats as one sale — are printed in
    sequence and followed by the combined figures ResultsQuery totalled for them.
    """
    bindings = results_json.get("results", {}).get("bindings", [])

    # Group by sale, preserving the order the query returned rows in.
    sales = OrderedDict()
    for row in bindings:
        prop = _local_name(_value(row, "property", "Unknown property"))
        sell_date = _value(row, "sellDate", "Unknown date")
        key = (_value(row, "disposition", f"{prop}|{sell_date}"), prop, sell_date)
        sales.setdefault(key, []).append(row)

    # Co-owners who each file their own return are split back out, one entry per
    # taxpayer, so each is reported on its own terms.  The per-disposition sale
    # totals go with the shared entry: they span two separate returns, and no
    # §121 figure is determined across them.
    entries = []
    for (disposition, prop, sell_date), rows in sales.items():
        if _files_separately(rows):
            entries.extend((disposition, prop, sell_date, [row]) for row in rows)
        else:
            entries.append((disposition, prop, sell_date, rows))

    # Then group the sales themselves by the netting group the query assigned
    # them, so a group's combined line can follow its own sales.
    groups = OrderedDict()
    for disposition, prop, sell_date, rows in entries:
        key = _net_group_key(rows[0], disposition)
        groups.setdefault(key, []).append((prop, sell_date, rows))

    messages = []
    for members in groups.values():
        for prop, sell_date, rows in members:
            messages.append(_sale_block(prop, sell_date, rows))

        combined = _net_totals(members[0][2][0])
        if combined:
            messages.append(combined)

    return "\n\n".join(messages)