import json

with open("grouped_noun_property_ratings_wide.jsonl", "r") as file:
    for i, line in enumerate(file, start=1):
        try:
            entry = json.loads(line)
            if "_meta" not in entry:
                print(f"Line {i} missing _meta: {line.strip()}")
            elif not isinstance(entry["_meta"], dict):
                print(f"Line {i} has malformed _meta (not a dict): {line.strip()}")
            elif "category" not in entry["_meta"]:
                print(f"Line {i} missing category in _meta: {line.strip()}")
        except json.JSONDecodeError as e:
            print(f"Line {i} is invalid JSON: {line.strip()} — {e}")