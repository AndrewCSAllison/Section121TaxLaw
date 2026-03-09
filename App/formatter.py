from collections import defaultdict

def format_results_nl(results_json):
    """
    Formats Section 121 gain/exclusion results into human-readable text.

    Behavior:
    - Group by property + sale date
    - Aggregate per taxpayer first
    - Aggregation priority:
        1) Joint-trigger rules: §121(b)(2)(A), §121(b)(2)(B), §121(d)(1)
        2) Multiple taxpayers with only §121(c) AND joint return
        3) Default multi-owner aggregation if joint return
        4) Single-return taxpayers are always output individually
    - Caps exclusions (250k individual, 500k aggregated group)
    """

    # --- Group by property + sale date ---
    groups = defaultdict(list)
    for row in results_json.get("results", {}).get("bindings", []):
        prop = row.get("property", {}).get("value", "Unknown property").split("#")[-1]
        sell_date = row.get("sellDate", {}).get("value", "Unknown date")
        groups[(prop, sell_date)].append(row)

    messages = []

    # --- Rule labels ---
    rules_map = {
        "Rule121aFinal": "§121(a) applies",
        "Rule121b1Excluded": "§121(b)(1) exclusion",
        "Rule121b2AExcluded": "§121(b)(2)(A) exclusion",
        "Rule121b2BExcluded": "§121(b)(2)(B) exclusion",
        "Rule121b3Applies": "§121(b)(3) applies",
        "Rule121cExcluded": "§121(c) exclusion",
        "Rule121d1Applies": "§121(d)(1) applies",
    }

    joint_rules_set = {
        "§121(b)(2)(A) exclusion",
        "§121(b)(2)(B) exclusion",
        "§121(d)(1) applies",
    }

    # Allowed rules for "b1-only" scenario
    b1_only_allowed = {"§121(a) applies", "§121(b)(1) exclusion"}

    # --- Process each property sale ---
    for (prop, sell_date), rows in groups.items():

        taxpayer_data = defaultdict(lambda: {"realized": 0.0, "excluded": 0.0, "rules": set()})
        taxpayer_return_type = {}

        for row in rows:
            taxpayer = row.get("taxpayer", {}).get("value", "").split("#")[-1]
            realized = float(row.get("realizedGain", {}).get("value", 0))
            excluded = float(row.get("excludedGain", {}).get("value", 0))

            taxpayer_data[taxpayer]["realized"] += realized
            taxpayer_data[taxpayer]["excluded"] += excluded

            for key, label in rules_map.items():
                value = row.get(key, {}).get("value")
                if value and str(value).lower() not in ["false", "0", "0.0"]:
                    taxpayer_data[taxpayer]["rules"].add(label)

            # Save return type
            is_single = row.get("isSingleReturn", {}).get("value", "false").lower() == "true"
            is_joint = row.get("isJointReturn", {}).get("value", "false").lower() == "true"
            taxpayer_return_type[taxpayer] = "single" if is_single else "joint" if is_joint else "unknown"

        taxpayers = list(taxpayer_data.keys())

        # Separate single-return taxpayers (always output individually)
        single_return_taxpayers = [t for t in taxpayers if taxpayer_return_type[t] == "single"]
        joint_return_taxpayers = [t for t in taxpayers if taxpayer_return_type[t] == "joint"]

        # --- Aggregation classification for joint return taxpayers ---
        joint_trigger_taxpayers = [t for t in joint_return_taxpayers if taxpayer_data[t]["rules"] & joint_rules_set]
        c_only_taxpayers = [t for t in joint_return_taxpayers if taxpayer_data[t]["rules"] == {"§121(c) exclusion"}]

        b1_only_all = (
            len(joint_return_taxpayers) > 1 and
            all(taxpayer_data[t]["rules"] and taxpayer_data[t]["rules"].issubset(b1_only_allowed)
                for t in joint_return_taxpayers)
        )

        # --- Decide aggregation ---
        if joint_trigger_taxpayers:
            aggregated_taxpayers = joint_trigger_taxpayers
            aggregation_type = "joint-trigger"
        elif len(c_only_taxpayers) > 1:
            aggregated_taxpayers = c_only_taxpayers
            aggregation_type = "c-only"
        elif b1_only_all:
            aggregated_taxpayers = []
            aggregation_type = "none"
        elif len(joint_return_taxpayers) > 1:
            aggregated_taxpayers = joint_return_taxpayers
            aggregation_type = "default-joint"
        else:
            aggregated_taxpayers = []
            aggregation_type = "none"

        # --- Case 1: Individual output ---
        for taxpayer in single_return_taxpayers:
            data = taxpayer_data[taxpayer]
            realized = data["realized"]
            max_exclusion = 250000
            excluded = min(data["excluded"], max_exclusion) if realized >= 0 else max(data["excluded"], -max_exclusion)
            taxable = max(round(realized - excluded, 2), 0)

            lines = [f"Taxpayer {taxpayer} sold property {prop} on {sell_date}."]
            for rule in sorted(data["rules"]):
                lines.append(f"- {rule}")
            lines.append(f"Realized gain: {round(realized,2)}, Excluded gain: {round(excluded,2)}, Taxable gain: {taxable}")
            messages.append("\n".join(lines))

        if aggregation_type == "none":
            # output joint-return taxpayers individually
            for taxpayer in joint_return_taxpayers:
                if taxpayer in aggregated_taxpayers:
                    continue  # skip already aggregated
                data = taxpayer_data[taxpayer]
                realized = data["realized"]
                max_exclusion = 250000
                excluded = min(data["excluded"], max_exclusion) if realized >= 0 else max(data["excluded"], -max_exclusion)
                taxable = max(round(realized - excluded, 2), 0)
                lines = [f"Taxpayer {taxpayer} sold property {prop} on {sell_date}."]
                for rule in sorted(data["rules"]):
                    lines.append(f"- {rule}")
                lines.append(f"Realized gain: {round(realized,2)}, Excluded gain: {round(excluded,2)}, Taxable gain: {taxable}")
                messages.append("\n".join(lines))
        else:
            # --- Case 2: Aggregated output for joint-return taxpayers ---
            total_realized = sum(taxpayer_data[t]["realized"] for t in aggregated_taxpayers)
            total_excluded_raw = sum(taxpayer_data[t]["excluded"] for t in aggregated_taxpayers)
            max_exclusion = 500000 if len(aggregated_taxpayers) > 1 else 250000
            total_excluded = min(total_excluded_raw, max_exclusion) if total_realized >= 0 else max(total_excluded_raw, -max_exclusion)
            taxable = max(round(total_realized - total_excluded, 2), 0)

            lines = [f"Taxpayers {', '.join(aggregated_taxpayers)} sold property {prop} on {sell_date}."]
            applied_rules = set()
            for t in aggregated_taxpayers:
                applied_rules.update(taxpayer_data[t]["rules"])
            for rule in sorted(applied_rules):
                lines.append(f"- {rule}")
            lines.append(f"Realized gain: {round(total_realized,2)}, Excluded gain: {round(total_excluded,2)}, Taxable gain: {taxable}")
            messages.append("\n".join(lines))

    return "\n\n".join(messages)