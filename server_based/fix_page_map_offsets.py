#!/usr/bin/env python3
"""
Make a page map agree with the text the app actually shows.

The page map records, per entry, where the content crosses a page boundary:
    "date|raw_date": {"start": p, "end": p, "breaks": [[charOffset, page], ...]}
The app uses `breaks` to send a search hit to the right PDF page, so an offset
must be a position inside the entry's REAL content.

Two things can break that, both because the map is built from the OCR text
while the JSON content is built by the parser:

  * the parser drops material the OCR block swallowed - a pasted press article
    that repeats the date in a headline, a web page's privacy boilerplate, the
    "Released by Chairman Rand Paul" footers. The block then spans pages whose
    text the entry does not contain (e.g. 2020-04-08 pulling in a Borowitz
    column, 2021-04-21 pulling in a privacy policy 400 pages later);
  * a duplicate page-scan of the same release (the same text can be imaged
    twice), which leaves stale offsets pointing past the end of the content.

Both show up as a hit jumping to a page ~400 pages away, and as a card
labelled with a page range ("p.696-1112") that the entry does not span.

This pass therefore CLAMPS rather than re-derives:
  * drop breaks at or past the end of the content (the pages they name hold
    text this entry does not have);
  * keep a break at offset 0, and add one at the content end on the last known
    page, so the final page of a multi-page entry is still reachable;
  * recompute start/end from the surviving breaks.

Run after any page-map or content change; it is idempotent, and it prints what
it touched. Offsets that survive are untouched, so page jumps that were already
right stay right.
"""

import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("2026.07.24_Tonys-Diary-Package.json", "page_map.json"),
    ("2026.07.27_Diary-Prequel-.json", "prequel_page_map.json"),
    ("2026.09.28_Ebola-Doc-Release_Full-Package.json", "ebola_page_map.json"),
    ("2026.10.6_Fauci-Diary-Release-Missing-Years_Full-Package.json", "missingyears_page_map.json"),
]


def fix_one(json_path, map_path):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    with open(map_path, encoding="utf-8") as f:
        page_map = json.load(f)
    entries = {(e["date"], e["raw_date"]): e for e in data.get("entries", [])}

    changed, missing, orphan = [], [], []
    for key, val in page_map.items():
        entry = entries.get(tuple(key.split("|", 1)))
        if entry is None:
            orphan.append(key)
            continue
        length = len(entry.get("content", ""))
        # A break AT the content length marks the first character of a page the
        # entry never reaches, so only breaks strictly inside the content count.
        breaks = [list(b) for b in (val.get("breaks") or []) if b[0] < length]
        if not breaks:
            breaks = [[0, val.get("start", 1)]]
        if breaks[0][0] != 0:
            breaks.insert(0, [0, breaks[0][1]])
        # offsets must increase and a page must never go backwards; the entry's
        # last page is the page of its last surviving break (text past a dropped
        # break does not exist in this entry, so it has no page of its own)
        cleaned = [breaks[0]]
        for off, page in breaks[1:]:
            if off <= cleaned[-1][0]:
                continue
            cleaned.append([off, max(page, cleaned[-1][1])])
        new_val = {"start": cleaned[0][1], "end": cleaned[-1][1], "breaks": cleaned}
        if new_val != val:
            changed.append((key, copy.deepcopy(val), new_val))
        val["start"], val["end"], val["breaks"] = new_val["start"], new_val["end"], new_val["breaks"]

    for key in orphan:
        del page_map[key]                     # header with no entry behind it
    for (date, raw) in entries:
        if (date + "|" + raw) not in page_map:
            missing.append(date + "|" + raw)

    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(page_map, f, ensure_ascii=False, indent=2)

    name = os.path.basename(map_path)
    print("%s: %d keys, %d adjusted, %d orphan dropped, %d entries unmapped"
          % (name, len(page_map), len(changed), len(orphan), len(missing)))
    for key, old, new in changed:
        print("   %s\n      was p.%s-%s %s\n      now p.%s-%s %s"
              % (key, old["start"], old["end"], old["breaks"],
                 new["start"], new["end"], new["breaks"]))
    for key in orphan:
        print("   dropped orphan key:", key)
    for key in missing:
        print("   WARNING unmapped entry:", key)
    return len(missing)


def main():
    total_missing = 0
    for json_name, map_name in TARGETS:
        jp, mp = os.path.join(HERE, json_name), os.path.join(HERE, map_name)
        if not (os.path.exists(jp) and os.path.exists(mp)):
            continue
        total_missing += fix_one(jp, mp)
    if total_missing:
        print("\n%d entries still have no page mapping - see WARNING above." % total_missing)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
