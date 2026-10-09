#!/usr/bin/env python3
"""Merge Missing Years diary entries that share the same date.

Same logic as merge_duplicate_entries.py / merge_prequel_duplicates.py but
for the Missing Years release (2026.10.6_Fauci-Diary-Release-Missing-Years).
The release has genuine two-notes-same-day pairs (e.g. two distinct Oct. 2,
2015 notes) plus range/day pairs sharing a start date (June 22 / Oct. 20 /
Mar. 26). Fold every later occurrence's content into the first, in list
order.

Only DIARY entries are folded (the release is diary + one publisher note;
the note has a synthetic date and never collides).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(HERE, "2026.10.6_Fauci-Diary-Release-Missing-Years_Full-Package.json")


def main():
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    entries = data["entries"]
    first_by_date = {}
    merged = []
    merges = []

    def kind_of(entry):
        return (entry.get("kind") or "diary").lower()

    for e in entries:
        prev = first_by_date.get(e["date"])
        if prev is not None and kind_of(prev) == "diary" and kind_of(e) == "diary":
            merges.append((prev["date"], prev["raw_date"], e["raw_date"]))
            prev["content"] = prev["content"] + "\n\n" + e["content"]
        else:
            first_by_date[e["date"]] = e
            merged.append(e)

    data["entries"] = merged
    data["total_entries"] = len(merged)

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Entries: {len(entries)} -> {len(merged)}")
    print(f"Merges performed: {len(merges)}")
    for d, raw1, raw2 in merges:
        print(f"  {d}: '{raw1}' + '{raw2}'")


if __name__ == "__main__":
    main()
