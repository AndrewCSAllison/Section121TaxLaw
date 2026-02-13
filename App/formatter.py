from collections import defaultdict

def format_results_nl(results_json):
    """
    Converts JSON results from SPARQL queries into human-readable messages.
    Realized gains remain per property. Excluded gains offset each other
    in the aggregated summary if there is a mix of positive and negative values.
    """
    groups = defaultdict(list)

    # Group by property + sellDate
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

    property_results = []

    # First pass: collect per-property realized and excluded gains
    for (prop, sell_date), rows in groups.items():
        all_full_ownership = all(
            float(row.get("percentageOwned", {}).get("value", 0)) == 1.0
            for row in rows
        )

        if len(rows) > 1 and all_full_ownership:
            taxpayers = ", ".join(
                row.get("taxpayer", {}).get("value", "").split("#")[-1]
                for row in rows
            )
            lines = [f"Taxpayers {taxpayers} sold property {prop} on {sell_date}."]

            for key, label in rules_map.items():
                values = [
                    row.get(key, {}).get("value")
                    for row in rows
                    if row.get(key, {}).get("value")
                ]
                if not values:
                    continue
                if any(v.lower() in ["true", "1"] for v in values):
                    lines.append(f"- {label}")
                else:
                    numeric_values = [
                        float(v) for v in values if v.lower() not in ["false", "0", "0.0"]
                    ]
                    for nv in numeric_values:
                        lines.append(f"- {label}: {nv}")

            realized = sum(float(r.get("realizedGain", {}).get("value", 0)) for r in rows)
            excluded = sum(float(r.get("excludedGain", {}).get("value", 0)) for r in rows)

            property_results.append({
                "lines": lines,
                "realized": realized,
                "excluded": excluded
            })

        else:
            for row in rows:
                taxpayer = row.get("taxpayer", {}).get("value", "").split("#")[-1]
                lines = [f"Taxpayer {taxpayer} sold property {prop} on {sell_date}."]

                for key, label in rules_map.items():
                    value = row.get(key, {}).get("value")
                    if not value:
                        continue
                    if value.lower() in ["true", "1"]:
                        lines.append(f"- {label}")
                    elif value.lower() not in ["false", "0", "0.0"]:
                        lines.append(f"- {label}: {float(value)}")

                realized = float(row.get("realizedGain", {}).get("value", 0))
                excluded = float(row.get("excludedGain", {}).get("value", 0))

                property_results.append({
                    "lines": lines,
                    "realized": realized,
                    "excluded": excluded
                })

    # Second pass: format per-property messages
    for res in property_results:
        res_lines = res["lines"]
        taxable = max(round(res["realized"] - res["excluded"], 2), 0)
        res_lines.append(
            f"Realized gain: {res['realized']}, Excluded gain: {res['excluded']}, Taxable gain: {taxable}"
        )
        messages.append("\n".join(res_lines))

    return "\n\n".join(messages)
