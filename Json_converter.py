#!/usr/bin/env python3
"""
Convert long-form JSONL (one row per noun-property) into wide-form JSONL
(one row per noun with all properties flattened).

Input file:  noun_property_ratings.jsonl
Output file: noun_property_ratings_new.jsonl
"""

import json
from collections import defaultdict
from statistics import mean
from typing import Dict, Tuple, Any

def convert_long_to_wide_jsonl(
    src_path: str,
    dst_path: str,
    noun_key: str = "noun",
    property_key: str = "property",
    rating_key: str = "rating",
    category_key: str = "category",
    include_category: bool = True,
    on_duplicate: str = "last",  # 'last' | 'first' | 'mean'
    sort_output: bool = True
) -> Tuple[int, int, int]:
    prop_values: Dict[str, Dict[str, Any]] = defaultdict(dict)
    prop_lists: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
    categories: Dict[str, Any] = {}

    rows_in = 0
    properties_seen = set()

    with open(src_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            rows_in += 1
            row = json.loads(line)

            noun = str(row[noun_key]).strip()
            prop = str(row[property_key]).strip()
            rating = row[rating_key]

            if isinstance(rating, str):
                rating = rating.strip()
                rating = float(rating) if ('.' in rating or 'e' in rating.lower()) else int(rating)

            properties_seen.add(prop)

            if include_category and category_key in row and row[category_key] is not None:
                categories.setdefault(noun, row[category_key])

            if on_duplicate == "last":
                prop_values[noun][prop] = rating
            elif on_duplicate == "first":
                prop_values[noun].setdefault(prop, rating)
            elif on_duplicate == "mean":
                prop_lists[noun][prop].append(float(rating))

    if on_duplicate == "mean":
        for noun, props in prop_lists.items():
            for prop, vals in props.items():
                prop_values[noun][prop] = mean(vals)

    nouns = sorted(prop_values.keys()) if sort_output else list(prop_values.keys())
    with open(dst_path, "w", encoding="utf-8") as out:
        for noun in nouns:
            record = {"noun": noun, **prop_values[noun]}
            if include_category and noun in categories:
                record["_meta"] = {"category": categories[noun]}
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    return rows_in, len(nouns), len(properties_seen)

# Hardcoded file names
input_file = "noun_property_ratings.jsonl"
output_file = "noun_property_ratings_new.jsonl"

# Run conversion
rows_in, nouns_out, props_out = convert_long_to_wide_jsonl(
    src_path=input_file,
    dst_path=output_file,
    on_duplicate="last",
    include_category=True,
    sort_output=True
)

print(f"Processed {rows_in} rows → wrote {nouns_out} nouns, {props_out} unique properties to {output_file}")
