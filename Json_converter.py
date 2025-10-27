#!/usr/bin/env python3
"""
Convert long-form JSONL (one row per noun-property) into wide-form JSONL
(one row per noun with all properties flattened).

Input rows look like:
  {"noun": "akita", "category": "Domesticated Mammals", "property": "size", "rating": 7}

Output rows look like:
  {"noun": "akita", "size": 7, "commonness_as_pet": 9, ..., "_meta": {"category": "Domesticated Mammals"}}

Usage:
  python convert_long_to_wide_jsonl.py \
      --in grouped_noun_property_ratings.jsonl \
      --out grouped_noun_property_ratings_wide.jsonl
"""

import argparse
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
    """
    Convert a long JSONL file to wide JSONL.

    Parameters
    ----------
    src_path : str
        Path to source long-form JSONL.
    dst_path : str
        Path to destination wide-form JSONL.
    noun_key : str
        Field name that holds the noun.
    property_key : str
        Field name that holds the property name.
    rating_key : str
        Field name that holds the numeric rating.
    category_key : str
        Field name that holds the category label (optional).
    include_category : bool
        If True, write category under '_meta': {'category': <value>} when available.
    on_duplicate : str
        How to resolve duplicate (noun, property) pairs encountered:
        - 'last'  : keep the last seen rating
        - 'first' : keep the first seen rating
        - 'mean'  : average all ratings seen
    sort_output : bool
        If True, sort nouns alphabetically in the output.

    Returns
    -------
    (rows_in, nouns_out, properties_out) : Tuple[int, int, int]
        A summary of the conversion: number of input rows processed, number of nouns written,
        and number of unique properties encountered (excluding '_meta').
    """
    # Temporary stores
    prop_values: Dict[str, Dict[str, Any]] = defaultdict(dict)  # noun -> {prop: rating}
    prop_lists: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))  # for 'mean'
    categories: Dict[str, Any] = {}

    rows_in = 0
    properties_seen = set()

    with open(src_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            rows_in += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Line {line_no} is not valid JSON: {e}")

            if noun_key not in row or property_key not in row or rating_key not in row:
                raise ValueError(
                    f"Line {line_no} missing required key(s) "
                    f"('{noun_key}', '{property_key}', '{rating_key}'): {row}"
                )

            noun = str(row[noun_key]).strip()
            prop = str(row[property_key]).strip()
            rating = row[rating_key]

            # Coerce rating to numeric if needed
            if isinstance(rating, str):
                rating = rating.strip()
                try:
                    rating = float(rating) if (("." in rating) or ("e" in rating.lower())) else int(rating)
                except ValueError:
                    raise ValueError(f"Line {line_no} rating not numeric: {row}")

            if not isinstance(rating, (int, float)):
                raise ValueError(f"Line {line_no} rating must be numeric: {row}")

            properties_seen.add(prop)

            # Handle category (if present)
            if include_category and (category_key in row) and (row[category_key] is not None):
                cat_val = row[category_key]
                # if conflicting categories appear for the same noun, we keep the first one
                categories.setdefault(noun, cat_val)

            # Resolve duplicates according to policy
            if on_duplicate == "last":
                prop_values[noun][prop] = rating
            elif on_duplicate == "first":
                prop_values[noun].setdefault(prop, rating)
            elif on_duplicate == "mean":
                prop_lists[noun][prop].append(float(rating))
            else:
                raise ValueError("on_duplicate must be one of: 'last', 'first', 'mean'")

    # Finalize 'mean' policy
    if on_duplicate == "mean":
        for noun, props in prop_lists.items():
            for prop, vals in props.items():
                prop_values[noun][prop] = mean(vals)

    # Write output
    nouns = sorted(prop_values.keys()) if sort_output else list(prop_values.keys())
    with open(dst_path, "w", encoding="utf-8") as out:
        for noun in nouns:
            record = {"noun": noun, **prop_values[noun]}
            if include_category and noun in categories:
                record["_meta"] = {"category": categories[noun]}
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    return rows_in, len(nouns), len(properties_seen)


def main():
    ap = argparse.ArgumentParser(description="Convert long JSONL (noun, property, rating) to wide JSONL (one noun per line).")
    ap.add_argument("--in", dest="src", required=True, help="Path to input long JSONL")
    ap.add_argument("--out", dest="dst", required=True, help="Path to output wide JSONL")
    ap.add_argument("--noun-key", default="noun", help="Field name for noun")
    ap.add_argument("--property-key", default="property", help="Field name for property")
    ap.add_argument("--rating-key", default="rating", help="Field name for rating")
    ap.add_argument("--category-key", default="category", help="Field name for category")
    ap.add_argument("--no-category", action="store_true", help="Exclude category from output")
    ap.add_argument("--on-duplicate", choices=["last", "first", "mean"], default="last",
                    help="How to combine duplicate noun+property entries")
    ap.add_argument("--no-sort", action="store_true", help="Do not sort nouns alphabetically")
    args = ap.parse_args()

    rows_in, nouns_out, props_out = convert_long_to_wide_jsonl(
        src_path=args.src,
        dst_path=args.dst,
        noun_key=args.noun_key,
        property_key=args.property_key,
        rating_key=args.rating_key,
        category_key=args.category_key,
        include_category=not args.no_category,
        on_duplicate=args.on_duplicate,
        sort_output=not args.no_sort
    )

    print(f"Processed {rows_in} rows → wrote {nouns_out} nouns, {props_out} unique properties to {args.dst}")

if __name__ == "__main__":
    main()