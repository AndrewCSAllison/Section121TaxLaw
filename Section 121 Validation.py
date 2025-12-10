import pandas as pd
import numpy as np

# Load CSV
df = pd.read_csv("section121_results.csv")

# Function to compute expected excluded gain
def compute_expected_excluded(row):
    gain = 0
    if row['Rule121aFinal']:
        if row['Rule121b1Excluded'] != 0:
            gain = row['Rule121b1Excluded']
        elif row['Rule121b2AExcluded'] > 0 or row['Rule121b2BExcluded'] > 0:
            gain = row['Rule121b2AExcluded'] + row['Rule121b2BExcluded']
        elif row['Rule121b3Applies']:
            gain = 0  # 121b3 applies but results in zero
    elif row['Rule121cExcluded'] > 0:
        gain = row['Rule121cExcluded']
    elif row['Rule121d1Applies']:
        gain = row['Rule121cExcluded'] if row['Rule121cExcluded'] > 0 else 0
    return min(gain, row['realizedGain'])

# Apply expected gain computation
df['expectedExcludedGain'] = df.apply(compute_expected_excluded, axis=1)

# Compare against reported excluded gain
df['resultMismatch'] = df['expectedExcludedGain'] != df['excludedGain']

# Compute expected taxable gain
df['expectedTaxableGain'] = (df['realizedGain'] - df['expectedExcludedGain']).round(2)
df['taxableMismatch'] = df['expectedTaxableGain'] != df['taxableGain']

# Full summary
summary = {
    'total_rows': len(df),
    'excluded_gain_matches': (~df['resultMismatch']).sum(),
    'excluded_gain_mismatches': df['resultMismatch'].sum(),
    'taxable_gain_matches': (~df['taxableMismatch']).sum(),
    'taxable_gain_mismatches': df['taxableMismatch'].sum()
}

print("Full results summary:")
for k, v in summary.items():
    print(f"  {k}: {v}")

# Optional: print detailed mismatches
print("\nRows with excluded gain mismatches:")
print(df[df['resultMismatch']])

print("\nRows with taxable gain mismatches:")
print(df[df['taxableMismatch']])
