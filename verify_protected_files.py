"""
Protected file integrity checker.
Computes SHA-256 hashes of files that must not be modified.
Run before and after implementation to verify integrity.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PROTECTED_FILES = [
    "portfolio_database.db",
    "ground_truth_dataset.json",
    "README.md",
    "database_schema.sql",
    "data/benchmarks.csv",
    "data/historical_prices.csv",
    "data/holdings.csv",
    "data/portfolio_performance.csv",
    "data/portfolios.csv",
    "data/risk_metrics.csv",
    "data/sectors.csv",
    "data/securities.csv",
    "data/transactions.csv",
]

def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

hashes = {}
for rel in PROTECTED_FILES:
    p = ROOT / rel
    if p.exists():
        hashes[rel] = file_hash(p)
        print(f"  OK  {rel}: {hashes[rel][:16]}...")
    else:
        print(f"  MISSING  {rel}")

# Save baseline
baseline_path = ROOT / ".protected_hashes.json"
if baseline_path.exists():
    with open(baseline_path) as f:
        baseline = json.load(f)
    print("\n=== INTEGRITY CHECK vs BASELINE ===")
    all_ok = True
    for rel, h in hashes.items():
        if rel in baseline:
            if baseline[rel] == h:
                print(f"  UNCHANGED  {rel}")
            else:
                print(f"  *** CHANGED ***  {rel}")
                all_ok = False
        else:
            print(f"  NEW (not in baseline)  {rel}")
    if all_ok:
        print("\nAll protected files are UNCHANGED.")
    else:
        print("\n*** WARNING: Protected files have been modified! ***")
else:
    with open(baseline_path, "w") as f:
        json.dump(hashes, f, indent=2)
    print(f"\nBaseline saved to {baseline_path}")
    print("Run this script again after changes to check integrity.")
