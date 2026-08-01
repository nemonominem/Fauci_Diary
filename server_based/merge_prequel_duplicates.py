#!/usr/bin/env python3
"""
Merge Prequel diary entries that share the same date.

Same logic as merge_duplicate_entries.py but for the Prequel
(2026.07.27_Diary-Prequel-).  The Prequel has several same-date splits:
range entries (e.g. "Oct. 25-28, 2001" starts on the same ISO date as
"Oct. 25, 2001"), continuation fragments, and genuine two-notes-same-day.
Fold every later occurrence's content into the first, in list order.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(HERE, "2026.07.27_Diary-Prequel-.json")


def main():
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    entries = data["entries"]
    first_by_date = {}
    merged = []
    merges = []
    for e in entries:
        prev = first_by_date.get(e["date"])
        if prev is not None:
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
