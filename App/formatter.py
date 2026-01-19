
def format_results_nl(results_json):
    """
    Converts JSON results from SPARQL queries into human-readable messages.
    """
    messages = []

    for row in results_json.get("results", {}).get("bindings", []):
        taxpayer = row.get("taxpayer", {}).get("value", "Unknown taxpayer").split("#")[-1]
        prop = row.get("property", {}).get("value", "Unknown property").split("#")[-1]
        sell_date = row.get("sellDate", {}).get("value", "Unknown date")

        lines = [f"Taxpayer {taxpayer} sold property {prop} on {sell_date}."]

        rules_map = {
            "Rule121aFinal": "§121(a) applies",
            "Rule121b1Excluded": "§121(b)(1) exclusion",
            "Rule121b2AExcluded": "§121(b)(2)(A) exclusion",
            "Rule121b2BExcluded": "§121(b)(2)(B) exclusion",
            "Rule121b3Applies": "§121(b)(3) applies",
            "Rule121cExcluded": "§121(c) exclusion",
            "Rule121d1Applies": "§121(d)(1) applies",
        }

        for key, msg in rules_map.items():
            value = row.get(key, {}).get("value")
            if value:
                if value.lower() in ["true", "1"]:
                    lines.append(f"- {msg}")
                elif value.lower() not in ["0", "0.0", "false"]:
                    lines.append(f"- {msg}: {value}")

        realized = row.get("realizedGain", {}).get("value")
        excluded = row.get("excludedGain", {}).get("value")
        taxable = row.get("taxableGain", {}).get("value")

        lines.append(f"Realized gain: {realized}, Excluded gain: {excluded}, Taxable gain: {taxable}")

        messages.append("\n".join(lines))

    return "\n\n".join(messages)
