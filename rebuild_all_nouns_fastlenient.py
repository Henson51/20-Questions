import os, json, re, time, difflib, pathlib
import pandas as pd
import requests

# ---------- Tunables ----------
MODEL = "phi3:mini"     # Ollama model
BATCH = 140             # nouns per batch (100–180 is a good range)
TEMP = 0.1              # low but not zero to reduce repetition
RETRIES = 1             # whole-batch retries on bad output
PAUSE = 0.02            # tiny pause between calls

SRC_TXT = "nouns.txt"   # ~1852 nouns
OUT = "nouns_all.csv"   # final single file (noun,category)
LOGDIR = "logs"         # capture raw model output when parsing fails

CATS_CANDIDATES = [
    "category_properties.json",
    os.path.join("data", "category_properties.json"),
    os.path.join(".", "data", "category_properties.json"),
    os.path.join("config", "category_properties.json"),
]

# ---------- Helpers ----------
def ensure_dir(p):
    pathlib.Path(p).mkdir(parents=True, exist_ok=True)

def find_categories_file():
    for p in CATS_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("ERROR: category_properties.json not found in expected locations.")

def load_allowed_categories():
    path = find_categories_file()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # {"categories":[{"name":"..."}, ...]}
    if isinstance(data, dict) and "categories" in data:
        names = []
        for it in data["categories"]:
            if isinstance(it, dict) and "name" in it:
                names.append(it["name"])
            elif isinstance(it, str):
                names.append(it)
        if names:
            print(f"Loaded {len(names)} categories (from categories[])")
            return names

    # ["Fruits","Wild Mammals", ...]
    if isinstance(data, list) and all(isinstance(x, str) for x in data):
        print(f"Loaded {len(data)} categories (list of strings)")
        return data

    # {"Fruits": {...}, "Wild Mammals": {...}}
    if isinstance(data, dict) and all(isinstance(k, str) for k in data.keys()):
        names = list(data.keys())
        print(f"Loaded {len(names)} categories (object keys)")
        return names

    raise SystemExit("ERROR: Unexpected JSON shape in category_properties.json")

def load_nouns():
    if not os.path.exists(SRC_TXT):
        raise SystemExit(f"ERROR: {SRC_TXT} not found.")
    raw = open(SRC_TXT, "r", encoding="utf-8").read()
    parts = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # split on commas unless quoted
        if "," in line and not re.search(r'".*,.*"', line):
            parts.extend([p.strip() for p in line.split(",") if p.strip()])
        else:
            parts.append(line)
    # dedupe, keep first casing
    seen = set()
    nouns = []
    for p in parts:
        k = p.strip().lower()
        if k and k not in seen:
            seen.add(k)
            nouns.append(p.strip())
    print(f"Loaded {len(nouns)} unique nouns from {SRC_TXT}")
    return nouns

def numbered_categories(allowed):
    return "\n".join([f"{i+1}. {name}" for i, name in enumerate(allowed)])

def ask_batch_lines(nouns, allowed):
    """
    Ask for TSV-like lines: <noun>\t<category name>
    We accept some drift and fix it later in Python.
    """
    cats = numbered_categories(allowed)
    sys = (
        "You classify nouns into exactly one category from a list. "
        "Return plain text only, one mapping per line."
    )
    usr = f"""
Classify EACH noun into exactly ONE category from this list (use exact category names when possible):

{cats}

Output format (plain text, one per line, NO extra commentary):
<noun><TAB><category name>

Examples:
banana\tFruits
bridge\tBuildings & Large Structures

Nouns to classify:
{json.dumps(nouns, ensure_ascii=False, indent=2)}
"""
    payload = {
        "model": MODEL,
        "prompt": f"{sys}\n\n{usr}",
        "options": {"temperature": TEMP, "top_p": 0.9, "num_ctx": 4096},
        "stream": False
    }
    r = requests.post("http://localhost:11434/api/generate", json=payload, timeout=240)
    r.raise_for_status()
    return r.json().get("response", "")

def normalize_category(raw_cat: str, allowed: list[str]) -> str | None:
    """
    Map model's category string to one of the allowed names.
    Tries exact (case-insensitive), common punctuation trims, then fuzzy.
    """
    if not raw_cat:
        return None
    s = raw_cat.strip().strip('"\'')

    # exact (case-insensitive)
    for a in allowed:
        if s.lower() == a.lower():
            return a

    # try removing surrounding quotes and extra spaces
    s2 = re.sub(r"\s+", " ", s).strip()
    for a in allowed:
        if s2.lower() == a.lower():
            return a

    # fuzzy (category name drift)
    m = difflib.get_close_matches(s2, allowed, n=1, cutoff=0.70)
    if m:
        return m[0]
    return None

def fallback_guess(noun: str, allowed: list[str]) -> str:
    n = noun.lower()
    if any(k in n for k in ["car","truck","boat","motor","engine","sedan","suv","yacht"]):
        for a in allowed:
            if "Vehicle" in a or "Cars" in a or "Boats" in a:
                return a
    if any(k in n for k in ["eagle","hawk","fish","shark","bird","bear","tiger","ant","bee","dog","cat","wolf","lion"]):
        for a in allowed:
            if "Animals" in a or "Birds" in a or "Fish" in a or "Insects" in a:
                return a
    if any(k in n for k in ["building","bridge","tower","stadium","skyscraper","house","hut","castle","cathedral"]):
        for a in allowed:
            if "Building" in a or "Structure" in a:
                return a
    # final fuzzy to category names (rare)
    m = difflib.get_close_matches(noun, allowed, n=1, cutoff=0.0)
    if m:
        return m[0]
    return allowed[0]

# ---------- Main ----------
def main():
    ensure_dir(LOGDIR)
    allowed = load_allowed_categories()
    nouns = load_nouns()

    resolved = {}
    total = len(nouns)

    for start in range(0, total, BATCH):
        batch = nouns[start:start+BATCH]
        raw = ""
        ok = False

        for attempt in range(RETRIES + 1):
            try:
                raw = ask_batch_lines(batch, allowed)
                ok = True
                break
            except Exception as e:
                print(f"Batch {start} error: {e}")
                time.sleep(0.2)

        if not ok or not raw.strip():
            # leave to final fallback loop
            logpath = os.path.join(LOGDIR, f"batch_{start}_error.txt")
            open(logpath, "w", encoding="utf-8").write(str(raw))
            continue

        # Parse lines "noun<TAB>category"
        mapped = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            # accept "noun\tcat", "noun - cat", "noun : cat"
            m = re.split(r"\t| {0,1}[-:|] {0,1}", line, maxsplit=1)
            if len(m) != 2:
                continue
            noun_out, cat_out = m[0].strip(), m[1].strip()
            if not noun_out:
                continue
            # require the noun to be from this batch (prevent hallucinations)
            if noun_out.lower().strip() not in {n.lower().strip() for n in batch}:
                continue
            category = normalize_category(cat_out, allowed)
            if category:
                mapped[noun_out.lower().strip()] = category

        # any batch lines we missed will get handled later
        resolved.update(mapped)
        print(f"Batch {start}..{start+len(batch)-1}: got {len(mapped)}/{len(batch)} from model; total resolved={len(resolved)}")
        # keep the raw for debugging
        open(os.path.join(LOGDIR, f"batch_{start}.txt"), "w", encoding="utf-8").write(raw)
        time.sleep(PAUSE)

    # Per-noun fallback for anything unresolved
    unresolved = [n for n in nouns if n.lower().strip() not in resolved]
    print(f"Unresolved after fast batched pass: {len(unresolved)}")

    # Light per-noun heuristic only (no extra LLM calls, to stay fast)
    for n in unresolved:
        resolved[n.lower().strip()] = fallback_guess(n, allowed)

    # Build final ordered rows
    rows = [{"noun": n, "category": resolved[n.lower().strip()]} for n in nouns]

    # No 'Other' / 'Uncategorized'
    def clean(c):
        s = str(c).strip().lower()
        return allowed[0] if s in ("other","uncategorized","") else c
    for r in rows:
        r["category"] = clean(r["category"])

    df = pd.DataFrame(rows, columns=["noun","category"])
    df.to_csv(OUT, index=False)
    print(f"Done. Wrote {OUT} with rows: {len(df)}")

if __name__ == "__main__":
    main()
