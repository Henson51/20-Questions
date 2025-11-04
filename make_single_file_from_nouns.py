import os
import pandas as pd

# -------------------------------------
# Script: make_single_file_from_nouns.py
# Purpose: Combine all nouns (~1852) with categories
#          from noun_categories_phi.csv.
#          Ensures no duplicates and fills missing
#          categories as "Uncategorized".
# -------------------------------------

CLASSIFIED = "noun_categories_phi.csv"   # Model output
OUT = "nouns_all.csv"                    # Final single-file deliverable

# Try to find nouns.txt
CANDIDATES = [
    "nouns.txt",
    os.path.join("data", "nouns.txt"),
    os.path.join(".", "nouns.txt"),
]
nouns_path = None
for c in CANDIDATES:
    if os.path.exists(c):
        nouns_path = c
        break

if nouns_path is None:
    raise SystemExit("ERROR: Could not find nouns.txt. Place it in the repo root or data/nouns.txt.")

# Load all nouns (~1852)
with open(nouns_path, "r", encoding="utf-8") as f:
    nouns_list = [ln.strip() for ln in f if ln.strip()]

if not nouns_list:
    raise SystemExit("ERROR: nouns.txt appears to be empty.")

# Create DataFrame of nouns and normalize
nouns_df = pd.DataFrame({"noun": nouns_list})
nouns_df["__key"] = nouns_df["noun"].str.strip().str.lower()

# Drop duplicates (case-insensitive)
before = len(nouns_df)
nouns_df = nouns_df.drop_duplicates("__key", keep="first")
after = len(nouns_df)
dupes = before - after
if dupes:
    tmp = pd.DataFrame({"noun": nouns_list})
    tmp["__key"] = tmp["noun"].str.strip().str.lower()
    dups_keys = tmp[tmp.duplicated("__key", keep="first")]["__key"].unique().tolist()
    with open("duplicates_in_nouns.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(dups_keys))
    print(f"Dropped {dupes} duplicate noun(s). See duplicates_in_nouns.txt")

# Load classified data
if not os.path.exists(CLASSIFIED):
    raise SystemExit(f"ERROR: {CLASSIFIED} not found. Run your classifier first.")

cls = pd.read_csv(CLASSIFIED)

# Ensure expected columns
if "noun" not in cls.columns:
    raise SystemExit(f"ERROR: 'noun' column missing in {CLASSIFIED}. Columns: {list(cls.columns)}")
if "category" not in cls.columns:
    cls["category"] = None

cls["__key"] = cls["noun"].astype(str).str.strip().str.lower()
cls = cls[["__key", "category"]]

# Merge all nouns with categories
merged = nouns_df.merge(cls, on="__key", how="left")

# Fill missing categories
merged["category"] = merged["category"].fillna("Uncategorized")

# Output final sorted file
out_df = merged[["noun", "category"]].astype(str).sort_values(["noun", "category"])
out_df.to_csv(OUT, index=False)

# Print summary
print(f"Found nouns.txt at: {nouns_path}")
print(f"Wrote {OUT} with rows: {len(out_df)} (should be {len(nouns_df)})")
