#!/usr/bin/env python3
"""
Regenerate page_map.json for Tony's Diary.

The original page_map pointed to the page where the date *header* appears,
but the actual entry content often starts on the NEXT page (when the header
sits at the bottom of a page, e.g. "August 15, 2021" at the bottom of p.847
while the body text is on p.848).

Heuristic: for each date header found on page P, count the *substantive*
content lines that follow on the same page (before the next page marker or
next date header).  If fewer than 3 substantive lines remain, the real
content starts on page P+1.
"""

import json
import re
import os
import calendar
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT_PATH = os.path.join(HERE, "2026.07.24_Tonys-Diary-Package.txt")
OUT_PATH = os.path.join(HERE, "page_map.json")

# ── Month / date parsing (mirrors reparse_diary.py) ──────────────────────

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_month_alts = sorted(MONTH_MAP.keys(), key=len, reverse=True)
MONTH_RE = "(" + "|".join(_month_alts) + ")"
ENDASH = chr(0x2013)
EMDASH = chr(0x2014)

DATE_HEADER_RE = re.compile(
    r"^\s*" + MONTH_RE + r"\.?\s+"
    + r"(\d{1,2})"
    + r"(?:\s*[-" + ENDASH + r"](\d{1,2}))?"
    + r"\s*[,.]?\s*"
    + r"(\d{4})"
    + r"\s*[-" + ENDASH + EMDASH + r":]?",
    re.IGNORECASE,
)

STRIP_PATTERNS = [
    re.compile(r"^---\s*Page\s+\d+\s*---\s*$"),
    re.compile(r"^Released by Chairman Rand Paul\s*$"),
    re.compile(r"^\d{1,4}\s*$"),
]

ARTICLE_TIME_HINTS = [
    re.compile(r"\d{1,2}:\d{2}\s*[ap]\.?m\.?", re.I),
    re.compile(r"\d{1,2}:\d{2}\s*(?:GMT|UTC|AEDT|EST|EDT|CST|PST|PDT)", re.I),
    re.compile(r"\|\s*\d{1,2}:\d{2}", re.I),
    re.compile(r"\bAEDT\b"),
    re.compile(r"\d{1,2}\s*[AP]M\s+PT", re.I),
    re.compile(r"\bUpdated\b", re.I),
]

PAGE_MARKER_RE = re.compile(r"^---\s*Page\s+(\d+)\s*---\s*$")

def is_strip_line(line):
    for pat in STRIP_PATTERNS:
        if pat.match(line):
            return True
    return False


def looks_like_article_date(text):
    for pat in ARTICLE_TIME_HINTS:
        if pat.search(text):
            return True
    return False


def parse_month(month_text):
    return MONTH_MAP[month_text.lower()]


def safe_date(year, month, day):
    max_day = calendar.monthrange(year, month)[1]
    day = min(day, max_day)
    return date(year, month, day)


def apply_corrections(iso_date, raw_date, content):
    """Apply known source-typo corrections (same as reparse_diary.py)."""
    if raw_date == "Jan. 28, 2019":
        iso_date = "2020-01-28"
    elif raw_date == "Feb. 3, 2019":
        iso_date = "2020-02-03"
    elif raw_date == "Feb. 5, 2000":
        iso_date = "2020-02-05"
    elif raw_date == "Sept. 20, 2020":
        iso_date = "2022-09-20"
    elif raw_date == "August 25, 2025":
        iso_date = "2022-08-25"
    elif raw_date == "January 23, 2020":
        iso_date = "2021-01-23"
    elif raw_date == "January 26, 2020":
        iso_date = "2021-01-26"
    elif raw_date == "January 27, 2020":
        iso_date = "2021-01-27"
    elif raw_date == "January 28, 2020":
        iso_date = "2021-01-28"
    elif raw_date == "January 29, 2020":
        iso_date = "2021-01-29"
    if iso_date == "2020-05-21" and "234,100" in content:
        iso_date = "2020-03-21"
    elif iso_date == "2020-05-23" and "292,000" in content:
        iso_date = "2020-03-23"
    return iso_date


def format_raw_date(month_txt, day, end_day_s, year):
    base = month_txt.rstrip(".")
    if len(base) <= 4 and base.lower() != "may":
        raw = base + ". " + str(day)
    else:
        raw = base + " " + str(day)
    if end_day_s:
        raw += "-" + end_day_s
    raw += ", " + str(year)
    return raw


def build_page_map():
    with open(TEXT_PATH, encoding="utf-8") as f:
        lines = f.readlines()

    # First pass: record the page number for every line index
    page_of_line = {}
    current_page = 1
    for i, raw_line in enumerate(lines):
        line = raw_line.rstrip("\n")
        m = PAGE_MARKER_RE.match(line.strip())
        if m:
            current_page = int(m.group(1))
        page_of_line[i] = current_page

    # Second pass: find date headers and determine content pages
    page_map = {}
    pending = None  # {iso, raw, line_idx, content_preview}

    for i, raw_line in enumerate(lines):
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        m = DATE_HEADER_RE.match(stripped)
        if m:
            month_txt = m.group(1)
            day = int(m.group(2))
            end_day_s = m.group(3)
            year = int(m.group(4))
            rest_of_line = stripped[m.end():]

            if looks_like_article_date(rest_of_line) or looks_like_article_date(stripped):
                continue

            try:
                month = parse_month(month_txt)
            except KeyError:
                continue

            iso = safe_date(year, month, day).isoformat()
            raw = format_raw_date(month_txt, day, end_day_s, year)

            # Finalize previous pending header
            if pending is not None:
                header_page = page_of_line[pending["line_idx"]]
                substantive = 0
                for j in range(pending["line_idx"] + 1, i):
                    ln = lines[j].rstrip("\n").strip()
                    if page_of_line[j] != header_page:
                        break
                    if not ln or is_strip_line(ln):
                        continue
                    substantive += 1

                if substantive >= 3:
                    content_page = header_page
                else:
                    content_page = header_page + 1

                corrected_iso = apply_corrections(
                    pending["iso"], pending["raw"], pending.get("content_preview", "")
                )
                key = corrected_iso + "|" + pending["raw"]
                page_map[key] = content_page

            pending = {
                "iso": iso,
                "raw": raw,
                "line_idx": i,
                "content_preview": rest_of_line,
            }

    # Finalize last pending header
    if pending is not None:
        header_page = page_of_line[pending["line_idx"]]
        substantive = 0
        for j in range(pending["line_idx"] + 1, len(lines)):
            ln = lines[j].rstrip("\n").strip()
            if page_of_line[j] != header_page:
                break
            if not ln or is_strip_line(ln):
                continue
            substantive += 1

        if substantive >= 3:
            content_page = header_page
        else:
            content_page = header_page + 1

        corrected_iso = apply_corrections(
            pending["iso"], pending["raw"], pending.get("content_preview", "")
        )
        key = corrected_iso + "|" + pending["raw"]
        page_map[key] = content_page

    return page_map


def main():
    page_map = build_page_map()

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(page_map, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(page_map)} entries to {OUT_PATH}")

    # Show samples around the known problem area
    for k in sorted(page_map.keys()):
        if "2021-08-1" in k:
            print(f"  {k} -> {page_map[k]}")


if __name__ == "__main__":
    main()

