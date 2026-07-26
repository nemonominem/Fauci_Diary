#!/usr/bin/env python3
"""
Clean PDF-induced line breaks from the diary JSON content.

The OCR text (and thus the JSON derived from it) has hard line breaks at
every PDF line boundary.  Since the diary is semi-structured prose, these
breaks are meaningless — the text should flow naturally and let the browser
wrap it.

Heuristic:
  • Join consecutive lines with a space (collapsing PDF line wraps).
  • Start a new paragraph before lines that begin with "PRESS:".
  • Empty lines also start a new paragraph.
  • Lines ending with ':' and shorter than 80 chars are treated as
    headings and start a new paragraph.

The cleaned text is written to the .json file the app loads.
The .txt file is left untouched.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(HERE, "2026.07.24_Tonys-Diary-Package_fixed.json")
OUT_PATH = os.path.join(HERE, "2026.07.24_Tonys-Diary-Package.json")


def clean_content(content):
    """Join PDF-wrapped lines; keep paragraph breaks at logical points."""
    lines = content.split("\n")
    paragraphs = []
    current = []

    for line in lines:
        s = line.strip()

        # Empty line → paragraph break
        if not s:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue

        # PRESS: starts a new paragraph
        if s.upper().startswith("PRESS:"):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            current.append(s)
            continue

        # Short heading ending with ':' → own paragraph
        if s.endswith(":") and len(s) < 80:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            current.append(s)
            continue

        current.append(s)

    if current:
        paragraphs.append(" ".join(current))

    # Collapse multiple spaces within each paragraph
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

    print(f"Cleaned {len(data.get('entries', []))} entries → {OUT_PATH}")

    # Show sample
    for e in data["entries"]:
        if e.get("date") == "2021-08-15":
            print("\n--- Sample (2021-08-15) ---")
            print(e["content"][:600])
            break


if __name__ == "__main__":
    main()
