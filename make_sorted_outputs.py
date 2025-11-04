import os, json, collections
import pandas as pd

SRC = "noun_categories_phi.csv"

if not os.path.exists(SRC):
    raise SystemExit(f"ERROR: {SRC} not found in {os.getcwd()}")

df = pd.read_csv(SRC)

# Ensure required columns exist
for col in ("noun", "category"):
    if col not in df.columns:
        raise SystemExit(f"ERROR: column '{col}' missing in {SRC}. Columns = {list(df.columns)}")

# 1) Sorted CSV: category,noun (no confidence), alphabetized
df_sorted = (
    df[["category", "noun"]]
    .dropna()
    .astype(str)
    .sort_values(["category", "noun"])
)
df_sorted.to_csv("nouns_by_category.csv", index=False)

# 2) Grouped JSON: { "Category": ["noun1", "noun2", ...], ... }
grouped = {}
for cat, sub in df_sorted.groupby("category"):
    nouns = sorted(set(map(str, sub["noun"])))
    grouped[str(cat)] = nouns
with open("nouns_by_category.json", "w", encoding="utf-8") as f:
    json.dump(grouped, f, ensure_ascii=False, indent=2)

# 3) Counts markdown for a quick summary
counts = df["category"].value_counts().sort_index()
with open("category_counts.md", "w", encoding="utf-8") as f:
    f.write("| Category | Count |\n|---|---:|\n")
    for cat, cnt in counts.items():
        f.write(f"| {cat} | {cnt} |\n")

# 4) Alternate expected filename (often requested)
df_sorted.to_csv("noun_categories.csv", index=False)

print("Wrote: nouns_by_category.csv, nouns_by_category.json, category_counts.md, noun_categories.csv")
