from collections import defaultdict


def format_results_nl(results_json):
    """
    Formats Section 121 gain/exclusion results into human-readable text.

    Key design: the §121(b)(1) 250k cap (and 500k joint cap) applies to the
    taxpayer's *total* net gain across ALL properties on the same return, not
    per property.  A loss on one property offsets gain on another before the
    cap is applied.

    Grouping strategy
    -----------------
    1.  Collect every row, keyed by taxpayer.
    2.  Within each taxpayer bucket, sub-group by (property, sell_date) so
        multiple rows for the same sale are collapsed first.
    3.  After collecting per-property gains/losses for the taxpayer, sum them
        to get the taxpayer's total net realized gain, then apply the cap once.
    4.  For joint-trigger rules (§121(b)(2)(A/B), §121(d)(1)) multiple
        taxpayers on the same disposition are aggregated together as before.
    """

    # ── Rule labels ───────────────────────────────────────────────────────────
    rules_map = {
        "Rule121aFinal":      "§121(a) applies",
        "Rule121b1Excluded":  "§121(b)(1) exclusion",
        "Rule121b2AExcluded": "§121(b)(2)(A) exclusion",
        "Rule121b2BExcluded": "§121(b)(2)(B) exclusion",
        "Rule121b3Applies":   "§121(b)(3) applies",
        "Rule121cExcluded":   "§121(c) exclusion",
        "Rule121d1Applies":   "§121(d)(1) applies",
    }

    joint_rules_set = {
        "§121(b)(2)(A) exclusion",
        "§121(b)(2)(B) exclusion",
        "§121(d)(1) applies",
    }

    b1_only_allowed = {"§121(a) applies", "§121(b)(1) exclusion"}

    # ── Step 1: collect all rows keyed by taxpayer ────────────────────────────
    # taxpayer_props[taxpayer][(prop, sell_date)] = {realized, excluded, rules}
    taxpayer_props   = defaultdict(lambda: defaultdict(lambda: {"realized": 0.0, "excluded": 0.0, "rules": set()}))
    taxpayer_return  = {}   # taxpayer -> "single" | "joint" | "unknown"
    # disposition_taxpayers[(prop, sell_date)] -> set of taxpayers (for joint logic)
    disposition_taxpayers = defaultdict(set)

    for row in results_json.get("results", {}).get("bindings", []):
        taxpayer  = row.get("taxpayer",  {}).get("value", "").split("#")[-1]
        prop      = row.get("property",  {}).get("value", "Unknown property").split("#")[-1]
        sell_date = row.get("sellDate",  {}).get("value", "Unknown date")
        realized  = float(row.get("realizedGain", {}).get("value", 0))
        excluded  = float(row.get("excludedGain",  {}).get("value", 0))

        bucket = taxpayer_props[taxpayer][(prop, sell_date)]
        bucket["realized"] += realized
        bucket["excluded"] += excluded

        for key, label in rules_map.items():
            val = row.get(key, {}).get("value")
            if val and str(val).lower() not in ("false", "0", "0.0"):
                bucket["rules"].add(label)

        is_single = row.get("isSingleReturn", {}).get("value", "false").lower() == "true"
        is_joint  = row.get("isJointReturn",  {}).get("value", "false").lower() == "true"
        taxpayer_return[taxpayer] = "single" if is_single else "joint" if is_joint else "unknown"

        disposition_taxpayers[(prop, sell_date)].add(taxpayer)

    # ── Step 2: identify dispositions that use joint-trigger rules ────────────
    # For these, taxpayers on the same disposition must be aggregated together
    # rather than summed across their individual property portfolios.
    joint_trigger_dispositions = set()
    for taxpayer, props in taxpayer_props.items():
        for (prop, sell_date), bucket in props.items():
            if bucket["rules"] & joint_rules_set:
                joint_trigger_dispositions.add((prop, sell_date))

    # ── Step 3: build output ──────────────────────────────────────────────────
    messages = []
    emitted_dispositions = set()   # track joint-trigger dispositions already written

    for taxpayer in taxpayer_props:
        props      = taxpayer_props[taxpayer]
        ret_type   = taxpayer_return.get(taxpayer, "unknown")

        # ── Joint-trigger dispositions: aggregate all taxpayers on that sale ──
        for (prop, sell_date) in list(props.keys()):
            if (prop, sell_date) not in joint_trigger_dispositions:
                continue
            if (prop, sell_date) in emitted_dispositions:
                continue
            emitted_dispositions.add((prop, sell_date))

            involved = sorted(disposition_taxpayers[(prop, sell_date)])
            total_realized     = sum(taxpayer_props[t][(prop, sell_date)]["realized"] for t in involved)
            total_excluded_raw = sum(taxpayer_props[t][(prop, sell_date)]["excluded"] for t in involved)
            max_exclusion      = 500000 if len(involved) > 1 else 250000
            total_excluded     = (min(total_excluded_raw, max_exclusion)
                                  if total_realized >= 0
                                  else max(total_excluded_raw, -max_exclusion))
            taxable = max(round(total_realized - total_excluded, 2), 0)

            applied_rules = set()
            for t in involved:
                applied_rules.update(taxpayer_props[t][(prop, sell_date)]["rules"])

            tp_label = f"Taxpayers {', '.join(involved)}" if len(involved) > 1 else f"Taxpayer {involved[0]}"
            lines = [f"{tp_label} sold property {prop} on {sell_date}."]
            for rule in sorted(applied_rules):
                lines.append(f"- {rule}")
            lines.append(
                f"Realized gain: {round(total_realized, 2)}, "
                f"Excluded gain: {round(total_excluded, 2)}, "
                f"Taxable gain: {taxable}"
            )
            messages.append("\n".join(lines))

        # ── Non-joint-trigger dispositions: aggregate across taxpayer's properties ──
        non_jt_props = {
            (p, sd): bucket
            for (p, sd), bucket in props.items()
            if (p, sd) not in joint_trigger_dispositions
        }
        if not non_jt_props:
            continue

        # Check if all non-JT properties share the same §121(b)(1)-only rules
        # AND the taxpayer is a joint-return filer with multiple co-owners:
        # in that case follow the existing per-property individual path instead.
        all_rules_across_props = set()
        for bucket in non_jt_props.values():
            all_rules_across_props |= bucket["rules"]

        # Determine whether this taxpayer has co-owners on the same non-JT dispositions
        # who are also joint-return filers (default-joint aggregation path).
        co_owner_joint = False
        for (p, sd) in non_jt_props:
            others = disposition_taxpayers[(p, sd)] - {taxpayer}
            if others and any(taxpayer_return.get(o) == "joint" for o in others):
                co_owner_joint = True
                break

        b1_only_scenario = (
            ret_type == "single" and
            all_rules_across_props and
            all_rules_across_props.issubset(b1_only_allowed) and
            len(non_jt_props) > 1
        )

        if b1_only_scenario:
            # ── Cross-property aggregation: single taxpayer, b1-only rules ──
            #
            # The 250k cap under §121(b)(1) applies to the taxpayer's TOTAL net
            # gain across ALL properties sold on the same return — losses on one
            # property offset gains on another before the cap is checked.
            #
            # SPARQL computes exclusion per-property in isolation, so those
            # per-property values cannot simply be summed.  We recompute from
            # first principles and then show two distinct explanatory cases:
            #
            #   Case A — loss-offset: at least one property has a loss.
            #     The net gain after offsetting the loss may fall under 250k,
            #     allowing a larger fraction (or all) of the gain to be excluded.
            #
            #   Case B — cap-limited: all properties have gains that together
            #     exceed 250k, so only 250k total can be excluded.
            #
            # Per-property excluded amounts are shown in the breakdown so it is
            # clear which property contributes gain vs. loss and how the cap was
            # applied across them.

            total_realized = sum(b["realized"] for b in non_jt_props.values())
            max_exclusion  = 250000

            # Allocate the available exclusion budget across properties.
            # Priority: positive-gain properties consume the budget in descending
            # gain order; loss properties contribute nothing to the budget but
            # reduce the net realized amount on which the cap is assessed.
            if total_realized <= 0:
                total_excluded = 0.0
                prop_excluded  = {k: 0.0 for k in non_jt_props}
            else:
                total_excluded = min(total_realized, max_exclusion)
                # Distribute the exclusion budget to each positive-gain property,
                # largest first, until the budget is exhausted.
                remaining_budget = total_excluded
                prop_excluded = {}
                for (p, sd), bucket in sorted(
                    non_jt_props.items(),
                    key=lambda kv: kv[1]["realized"],
                    reverse=True,
                ):
                    gain = bucket["realized"]
                    if gain <= 0:
                        prop_excluded[(p, sd)] = 0.0
                    else:
                        alloc = min(gain, remaining_budget)
                        prop_excluded[(p, sd)] = alloc
                        remaining_budget = max(remaining_budget - alloc, 0.0)

            taxable = max(round(total_realized - total_excluded, 2), 0)

            has_loss      = any(b["realized"] < 0 for b in non_jt_props.values())
            cap_hit       = total_realized > max_exclusion
            if has_loss and not cap_hit:
                cap_note = "  (loss on one property offsets gain; full net gain excluded)"
            elif has_loss and cap_hit:
                cap_note = "  (loss offsets gain, but net gain still exceeds $250,000 cap)"
            else:
                cap_note = "  ($250,000 exclusion cap applies across all properties)"

            # Build per-property breakdown with individual excluded amounts
            prop_lines = []
            for (p, sd), bucket in sorted(non_jt_props.items()):
                excl = prop_excluded.get((p, sd), 0.0)
                prop_taxable = max(round(bucket["realized"] - excl, 2), 0)
                if bucket["realized"] < 0:
                    prop_lines.append(
                        f"  {p} (sold {sd}): "
                        f"realized {round(bucket['realized'], 2)}  [loss — not excludable]"
                    )
                else:
                    prop_lines.append(
                        f"  {p} (sold {sd}): "
                        f"realized {round(bucket['realized'], 2)}, "
                        f"excluded {round(excl, 2)}, "
                        f"taxable {round(prop_taxable, 2)}"
                    )

            lines = [f"Taxpayer {taxpayer} sold multiple properties:"]
            lines.extend(prop_lines)
            lines.append(cap_note)
            for rule in sorted(all_rules_across_props):
                lines.append(f"- {rule}")
            lines.append(
                f"Total realized gain: {round(total_realized, 2)}, "
                f"Total excluded: {round(total_excluded, 2)}, "
                f"Total taxable: {taxable}"
            )
            messages.append("\n".join(lines))

        else:
            # ── Per-property output (original behaviour) ──
            for (p, sd), bucket in sorted(non_jt_props.items()):
                # Skip if this disposition belongs to a group being handled
                # by another taxpayer's aggregation path (co_owner_joint case).
                realized = bucket["realized"]
                max_exclusion = 250000
                excluded = (min(bucket["excluded"], max_exclusion)
                            if realized >= 0
                            else max(bucket["excluded"], -max_exclusion))
                taxable = max(round(realized - excluded, 2), 0)

                lines = [f"Taxpayer {taxpayer} sold property {p} on {sd}."]
                for rule in sorted(bucket["rules"]):
                    lines.append(f"- {rule}")
                lines.append(
                    f"Realized gain: {round(realized, 2)}, "
                    f"Excluded gain: {round(excluded, 2)}, "
                    f"Taxable gain: {taxable}"
                )
                messages.append("\n".join(lines))

    return "\n\n".join(messages)