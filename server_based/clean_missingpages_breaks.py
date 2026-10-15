#!/usr/bin/env python3
"""
Clean PDF-induced line breaks from the Missing Pages diary JSON content.

Same heuristic as clean_missingyears_breaks.py, for the Missing Pages
release (2026.10.07_Missing-Pages-Diary_Full-Package).
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(HERE, "2026.10.07_Missing-Pages-Diary_Full-Package_fixed.json")
OUT_PATH = os.path.join(HERE, "2026.10.07_Missing-Pages-Diary_Full-Package.json")


def clean_content(content):
    """Join PDF-wrapped lines; keep paragraph breaks at logical points."""
    lines = content.split("\n")
    paragraphs = []
    current = []

    for line in lines:
        s = line.strip()
        if not s:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if s.upper().startswith("PRESS:"):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            current.append(s)
            continue
        # A short colon-ending line is usually a standalone label ("Rochelle:",
        # "See e-mail below:") that should start its own paragraph - but a
        # long sentence wrapped across two PDF lines sometimes happens to end
        # on a colon too ("...we must get them" / "tested with an Ag test
        # after 45 days:"), and flushing there would cut it in half. A label
        # starts with a capital; a wrapped continuation starts lowercase.
        if s.endswith(":") and len(s) < 80 and not (s[:1].islower()):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            current.append(s)
            continue
        current.append(s)

    if current:
        paragraphs.append(" ".join(current))

    cleaned = []
    for p in paragraphs:
        p = re.sub(r"\s+", " ", p).strip()
        if p:
            cleaned.append(p)
    return "\n\n".join(cleaned)


def main():
    with open(SRC_PATH, encoding="utf-8") as f:
        data = json.load(f)

    for entry in data.get("entries", []):
        if "content" in entry:
            entry["content"] = clean_content(entry["content"])

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Cleaned {len(data.get('entries', []))} entries -> {OUT_PATH}")


if __name__ == "__main__":
    main()
