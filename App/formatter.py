from collections import defaultdict

def format_results_nl(results_json):
    """
    Aggregates results per taxpayer per property, sums realized/excluded gains per property,
    caps exclusions (500k joint, 250k single), handles negative realized gains,
    and displays numeric exclusions concisely for joint filers.
    """
    # Step 1: group rows by property + sellDate
    groups = defaultdict(list)
    for row in results_json.get("results", {}).get("bindings", []):
        prop = row.get("property", {}).get("value", "Unknown property").split("#")[-1]
        sell_date = row.get("sellDate", {}).get("value", "Unknown date")
        groups[(prop, sell_date)].append(row)

    messages = []

    rules_map = {
        "Rule121aFinal": "§121(a) applies",
        "Rule121b1Excluded": "§121(b)(1) exclusion",
        "Rule121b2AExcluded": "§121(b)(2)(A) exclusion",
        "Rule121b2BExcluded": "§121(b)(2)(B) exclusion",
        "Rule121b3Applies": "§121(b)(3) applies",
        "Rule121cExcluded": "§121(c) exclusion",
        "Rule121d1Applies": "§121(d)(1) applies",
    }

    for (prop, sell_date), rows in groups.items():
        # Step 2: aggregate per taxpayer per property
        taxpayer_data = defaultdict(lambda: {"realized": 0, "excluded": 0, "rules": defaultdict(list)})
        for row in rows:
            taxpayer = row.get("taxpayer", {}).get("value", "").split("#")[-1]
            realized = float(row.get("realizedGain", {}).get("value", 0))
            excluded = float(row.get("excludedGain", {}).get("value", 0))
            taxpayer_data[taxpayer]["realized"] += realized
            taxpayer_data[taxpayer]["excluded"] += excluded

            # collect all rule info per taxpayer
            for key, label in rules_map.items():
                value = row.get(key, {}).get("value")
                if value:
                    taxpayer_data[taxpayer]["rules"][label].append(value)

        taxpayers = list(taxpayer_data.keys())
        joint_filing = len(taxpayers) > 1

        # Step 3: sum totals across taxpayers for this property
        total_realized = sum(t["realized"] for t in taxpayer_data.values())
        total_excluded_raw = sum(t["excluded"] for t in taxpayer_data.values())

        max_exclusion = 500000 if joint_filing else 250000
        if total_realized < 0:
            total_excluded = max(total_excluded_raw, -max_exclusion)
        else:
            total_excluded = min(total_excluded_raw, max_exclusion)

        lines = [
            f"Taxpayers {', '.join(taxpayers)} sold property {prop} on {sell_date}."
            if joint_filing else f"Taxpayer {taxpayers[0]} sold property {prop} on {sell_date}."
        ]

        # Step 4: process rules and numeric exclusions
        for label, values in rules_map.items():
            # collect numeric values for this rule
            numeric_values = []
            bool_applies = False
            for t in taxpayers:
                v_list = taxpayer_data[t]["rules"].get(values)
                if v_list:
                    for v in v_list:
                        if str(v).lower() in ["true", "1"]:
                            bool_applies = True
                        elif str(v).lower() not in ["false", "0", "0.0"]:
                            numeric_values.append(float(v))

            if bool_applies:
                lines.append(f"- {values}")
            elif numeric_values:
                numeric_total = sum(numeric_values)
                scale = total_excluded / numeric_total if numeric_total != 0 else 0
                scaled_values = [round(v*scale,2) for v in numeric_values]

                if joint_filing:
                    # concise joint display if all scaled values equal
                    if all(v == scaled_values[0] for v in scaled_values):
                        lines.append(f"- {values}: {scaled_values[0]} each")
                    else:
                        for t, v in zip(taxpayers, scaled_values):
                            lines.append(f"- {values} for {t}: {v}")
                else:
                    lines.append(f"- {values}: {scaled_values[0]}")

        taxable = max(round(total_realized - total_excluded, 2), 0)
        lines.append(
            f"Realized gain: {round(total_realized,2)}, Excluded gain: {round(total_excluded,2)}, Taxable gain: {taxable}"
        )

        messages.append("\n".join(lines))

    return "\n\n".join(messages)