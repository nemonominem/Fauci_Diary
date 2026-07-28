#!/usr/bin/env python3
"""
Merge diary entries that share the same date.

reparse_diary.py's date-header regex occasionally matches a bare date-like
line embedded in pasted press-citation text (e.g. an article's own byline
date), producing a spurious extra "entry" for a date that already has one.
Separately, a handful of dates genuinely have two distinct diary notes with
the identical raw_date header text (the source gives no way to tell them
apart), and in one case an out-of-sequence entry (a probable source typo)
sits physically between the two same-date entries. Either way, when two
entries share the same `date`, they belong together: fold every later
occurrence's content into the first, in list order, and drop it from its own
position.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(HERE, "2026.07.24_Tonys-Diary-Package.json")


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
    for date, raw1, raw2 in merges:
        print(f"  {date}: '{raw1}' + '{raw2}'")


if __name__ == "__main__":
    main()
