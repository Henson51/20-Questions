import os, json, re, time, pathlib
from typing import List, Dict, Any, Optional
import requests
from tqdm import tqdm
import pandas as pd

# ---------------- Tunables ----------------
BATCH_SIZE = 50                      # safer context size
CONFIDENCE_THRESHOLD = 0.5
SLEEP_BETWEEN_CALLS = 0.1
BACKEND = "ollama"                   # we're using Ollama here
LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)
# ------------------------------------------

# Ollama endpoints / model
OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi3:mini")

def read_categories(path="category_properties.json") -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "categories" in data and isinstance(data["categories"], list):
        cats = [c["name"] if isinstance(c, dict) and "name" in c else str(c) for c in data["categories"]]
    elif isinstance(data, dict):
        cats = list(data.keys())
    else:
        raise ValueError("Unrecognized category_properties.json format.")
    return sorted(set(cats))

def read_nouns(path="nouns.txt") -> List[str]:
    nouns = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip()
            if w:
                nouns.append(w)
    return nouns

SYSTEM_PROMPT = """You are a precise classifier. Output STRICT JSON only.
Schema:
{"items":[{"noun":"string","category":"string","confidence":0.0}]}
- The "category" MUST be exactly one from the allowed list provided.
- "confidence" MUST be a number between 0.0 and 1.0.
- Do not add any extra keys or commentary.
"""

def make_user_prompt(nouns: List[str], categories: List[str]) -> str:
    return (
        "Allowed categories:\n"
        + json.dumps(categories, ensure_ascii=False)
        + "\n\nClassify each noun into exactly ONE allowed category.\n"
        + json.dumps({"nouns": nouns}, ensure_ascii=False)
    )

def ollama_generate(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\nUser:\n{prompt}",
        "stream": False,
        "format": "json",  # ask for JSON
        "options": {
            "temperature": 0.0,
            "num_ctx": 8192
        }
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=180)
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip()

def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return s

def _repair_common_json_issues(s: str) -> str:
    s = _strip_code_fences(s)

    # Keep just the outermost JSON object if there is extra text
    if "{" in s and "}" in s:
        s = s[s.find("{"): s.rfind("}") + 1]

    # Remove trailing commas before } or ]
    s = re.sub(r",\s*([}\]])", r"\1", s)

    # Replace single quotes with double quotes IF it looks like JSON-ish but used singles
    # (Be careful not to destroy apostrophes inside strings; this heuristic is minimal.)
    if s.count('"') == 0 and s.count("'") > 0:
        s = s.replace("'", '"')

    # Replace bare NaN/Infinity if any
    s = s.replace("NaN", "null").replace("Infinity", "null").replace("-Infinity", "null")

    return s

def parse_or_fix_json(s: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(_strip_code_fences(s))
    except Exception:
        pass
    try:
        return json.loads(_repair_common_json_issues(s))
    except Exception:
        return None

def classify_batch(batch: List[str], categories: List[str], i: int) -> List[Dict[str, Any]]:
    """Try to classify a batch; if JSON fails, fall back to per-item."""
    user_prompt = make_user_prompt(batch, categories)
    raw = None
    try:
        raw = ollama_generate(user_prompt)
        data = parse_or_fix_json(raw)
        if data and isinstance(data, dict) and isinstance(data.get("items"), list):
            out = []
            for item in data["items"]:
                noun = str(item.get("noun", "")).strip()
                cat  = str(item.get("category", "")).strip()
                conf = item.get("confidence", 0.0)
                try:
                    conf = float(conf)
                except Exception:
                    conf = 0.0
                if noun and cat in categories:
                    out.append({"noun": noun, "category": cat, "confidence": max(0.0, min(1.0, conf))})
            # If it returned nothing sensible, fall through to per-item
            if out:
                return out
        # If parse failed, drop to per-item
        raise ValueError("Batch JSON invalid")
    except Exception as e:
        # Log the raw batch for debugging
        with open(LOG_DIR / f"batch_{i}.txt", "w", encoding="utf-8") as f:
            f.write(raw if raw else "<no content>")
        # per-item fallback
        out = []
        for noun in batch:
            try:
                single_prompt = make_user_prompt([noun], categories)
                raw_single = ollama_generate(single_prompt)
                data_single = parse_or_fix_json(raw_single)
                if data_single and isinstance(data_single.get("items"), list) and data_single["items"]:
                    item = data_single["items"][0]
                    cat  = str(item.get("category", "")).strip()
                    conf = item.get("confidence", 0.0)
                    try:
                        conf = float(conf)
                    except Exception:
                        conf = 0.0
                    if cat in categories:
                        out.append({"noun": noun, "category": cat, "confidence": max(0.0, min(1.0, conf))})
                        continue
                # if we get here, noun not mapped
                out.append({"noun": noun, "category": "", "confidence": 0.0})
            except Exception:
                out.append({"noun": noun, "category": "", "confidence": 0.0})
            time.sleep(SLEEP_BETWEEN_CALLS/2)
        return out

def main():
    categories = read_categories("category_properties.json")
    nouns = read_nouns("nouns.txt")

    print(f"Loaded {len(categories)} categories and {len(nouns)} nouns.")
    print("First 5 categories:", categories[:5])
    print("First 5 nouns:", nouns[:5])

    results: List[Dict[str, Any]] = []
    for i in tqdm(range(0, len(nouns), BATCH_SIZE), desc="Classifying"):
        batch = nouns[i:i+BATCH_SIZE]
        batch_results = classify_batch(batch, categories, i)
        results.extend(batch_results)
        time.sleep(SLEEP_BETWEEN_CALLS)

    # Split into mapped/unmapped
    mapped   = [r for r in results if r["category"]]
    unmapped = [r["noun"] for r in results if not r["category"] or r["confidence"] < CONFIDENCE_THRESHOLD]

    # Write outputs
    pd.DataFrame(mapped).to_csv("noun_categories_phi.csv", index=False)

    with open("noun_categories_phi.jsonl", "w", encoding="utf-8") as f:
        for r in mapped:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open("unmapped_nouns.txt", "w", encoding="utf-8") as f:
        for n in sorted(set(unmapped)):
            f.write(n + "\n")

    print("\n✅ Done! Files written:")
    print("  noun_categories_phi.csv")
    print("  noun_categories_phi.jsonl")
    print("  unmapped_nouns.txt")
    if any(LOG_DIR.iterdir()):
        print(f"  (Debug logs in .\\{LOG_DIR.name}\\ for any batch JSON captures)")

if __name__ == "__main__":
    main()
