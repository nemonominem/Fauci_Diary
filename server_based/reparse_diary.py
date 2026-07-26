#!/usr/bin/env python3
"""
Re-parser for Tony's Diary Package.

The original JSON parser only recognised 3-letter month abbreviations with a
period (Jan., Feb., ..., Dec.) and therefore missed every entry whose header
used a full month name (April, June, July, August, September) or the 4-letter
abbreviation "Sept.".  It also split several embedded article timestamps into
fake "diary entries".

This script re-parses the OCR text file from scratch with a comprehensive
date pattern, cleans the content, applies known typo corrections, filters out
embedded article clippings, and writes a corrected JSON file.
"""

import json
import re
import calendar
from datetime import date, timedelta
from collections import Counter

TEXT_PATH = "/Users/gillesdemaneuf/Work/DataWharehouse/DRASTIC/external_processed/congressional/2026.07.24_Tonys-Diary-Package.txt"
OUT_PATH = "/Users/gillesdemaneuf/Work/DataWharehouse/DRASTIC/external_processed/congressional/2026.07.24_Tonys-Diary-Package_fixed.json"

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

# groups: 1=month, 2=day, 3=optional end-day (range), 4=year
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

# Patterns that indicate content is an embedded article clipping, not a diary entry
ARTICLE_START_PATTERNS = [
    re.compile(r"^Photograph by", re.I),
    re.compile(r"^\d{1,2}\s*[AP]M\b", re.I),  # "6 AM" at start
    re.compile(r"^ShareThis", re.I),
    re.compile(r"^Screen cap", re.I),
    re.compile(r"^Press Release\s*$", re.I),
    re.compile(r"^[•\-\*]?\s*Statements and Releases", re.I),
    re.compile(r"^ALEX WONG|^BRIAN SMIALOWSKI|^Getty", re.I),
    re.compile(r"^Based on COVID-19 data,? Dr\. Fauci", re.I),
    re.compile(r"^Following up on the regular briefings he", re.I),
    re.compile(r"^During my time as Vice President", re.I),
    re.compile(r"^for a religious institution", re.I),
    re.compile(r"^CNN'?s Drew Griffin", re.I),
    re.compile(r"^Screen cap", re.I),
]


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
    return MONTH_MAP[month_text.lower().rstrip(".")]


def safe_date(year, month, day):
    max_day = calendar.monthrange(year, month)[1]
    day = min(day, max_day)
    return date(year, month, day)


def apply_corrections(iso_date, raw_date, content):
    """Apply known source-typo corrections."""
    note = None
    # Year typos (source wrote wrong year)
    if raw_date == "Jan. 28, 2019":
        iso_date = "2020-01-28"
        note = "Source year typo (2019->2020) corrected based on sequence/context."
    elif raw_date == "Feb. 3, 2019":
        iso_date = "2020-02-03"
        note = "Source year typo (2019->2020) corrected based on sequence/context."
    elif raw_date == "Feb. 5, 2000":
        iso_date = "2020-02-05"
        note = "Source year typo (2000->2020) corrected based on sequence/context."
    elif raw_date == "Sept. 20, 2020":
        iso_date = "2022-09-20"
        note = "Source year typo (2020->2022) corrected based on sequence/context."
    elif raw_date == "August 25, 2025":
        iso_date = "2022-08-25"
        note = "Source year typo (2025->2022) corrected based on sequence/context."
    # January 2020 dates that are actually January 2021 (appear in 2021 section)
    elif raw_date == "January 23, 2020":
        iso_date = "2021-01-23"
        note = "Source year typo (2020->2021) corrected based on sequence/context."
    elif raw_date == "January 26, 2020":
        iso_date = "2021-01-26"
        note = "Source year typo (2020->2021) corrected based on sequence/context."
    elif raw_date == "January 27, 2020":
        iso_date = "2021-01-27"
        note = "Source year typo (2020->2021) corrected based on sequence/context."
    elif raw_date == "January 28, 2020":
        iso_date = "2021-01-28"
        note = "Source year typo (2020->2021) corrected based on sequence/context."
    elif raw_date == "January 29, 2020":
        iso_date = "2021-01-29"
        note = "Source year typo (2020->2021) corrected based on sequence/context."
    # Month typos: two March entries mislabelled "May"
    if iso_date == "2020-05-21" and "234,100" in content:
        iso_date = "2020-03-21"
        note = "Source month typo (May->March) corrected based on case counts."
    elif iso_date == "2020-05-23" and "292,000" in content:
        iso_date = "2020-03-23"
        note = "Source month typo (May->March) corrected based on case counts."
    return iso_date, note


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


def is_likely_fake_entry(entry):
    content = entry["content"].strip()
    if not content:
        return True
    if content.startswith("http") and content.count("\n") == 0:
        return True
    if re.match(r"^\|?\s*\d{1,2}:\d{2}", content):
        return True
    return False


def is_article_clipping(entry):
    """Detect embedded article clippings masquerading as diary entries."""
    content = entry["content"].strip()
    first_line = content.split("\n")[0].strip() if content else ""
    for pat in ARTICLE_START_PATTERNS:
        if pat.match(first_line):
            return True
    return False


def parse_text():
    with open(TEXT_PATH, encoding="utf-8") as f:
        lines = f.readlines()

    entries = []
    cur_iso = None
    cur_raw = None
    cur_lines = []

    for raw_line in lines:
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
                if cur_iso is not None and not is_strip_line(stripped):
                    cur_lines.append(line)
                continue

            try:
                month = parse_month(month_txt)
            except KeyError:
                if cur_iso is not None and not is_strip_line(stripped):
                    cur_lines.append(line)
                continue

            if cur_iso is not None:
                content = "\n".join(cur_lines).strip()
                iso2, note = apply_corrections(cur_iso, cur_raw, content)
                e = {"date": iso2, "raw_date": cur_raw, "content": content}
                if note:
                    e["date_note"] = note
                entries.append(e)

            cur_raw = format_raw_date(month_txt, day, end_day_s, year)
            cur_iso = safe_date(year, month, day).isoformat()
            cur_lines = []
            # Preserve content that was on the same line after the date header
            if rest_of_line.strip():
                cur_lines.append(rest_of_line)
        else:
            if cur_iso is not None and not is_strip_line(stripped):
                cur_lines.append(line)

    if cur_iso is not None:
        content = "\n".join(cur_lines).strip()
        iso2, note = apply_corrections(cur_iso, cur_raw, content)
        e = {"date": iso2, "raw_date": cur_raw, "content": content}
        if note:
            e["date_note"] = note
        entries.append(e)

    return entries


def post_process(entries):
    """Filter fakes, merge article clippings into preceding entries."""
    # 1. Remove obviously fake entries
    entries = [e for e in entries if not is_likely_fake_entry(e)]

    # 2. Merge article clippings and out-of-sequence entries into preceding entry
    merged = []
    for e in entries:
        is_clip = is_article_clipping(e)
        # Check if date jumps backward by more than 60 days (embedded article)
        is_out_of_seq = False
        if merged:
            prev_d = date.fromisoformat(merged[-1]["date"])
            cur_d = date.fromisoformat(e["date"])
            if (prev_d - cur_d).days > 60:
                is_out_of_seq = True
        if is_clip or is_out_of_seq:
            # Merge into preceding entry
            if merged:
                sep = "\n"
                merged[-1]["content"] += sep + e["content"]
            # else: drop orphan clipping
        else:
            merged.append(e)

    return merged


def main():
    entries = parse_text()
    entries = post_process(entries)

    dates_list = sorted(e["date"] for e in entries)
    date_range = {"start": dates_list[0], "end": dates_list[-1]} if dates_list else {}

    out = {
        "source_file": "2026.07.24_Tonys-Diary-Package.pdf",
        "title": "Tony's Diary Package",
        "released_by": "Chairman Rand Paul",
        "total_entries": len(entries),
        "date_range": date_range,
        "entries": entries,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("Original entries: 292")
    print("Re-parsed entries: " + str(len(entries)))
    print("Date range: " + str(date_range))

    seen = {}
    dups = []
    for i, e in enumerate(entries):
        if e["date"] in seen:
            dups.append((e["date"], seen[e["date"]], i))
        seen[e["date"]] = i
    print("\nDuplicate dates: " + str(len(dups)))
    for d, j, i in dups[:30]:
        print("  " + d + " at idx " + str(j) + " and " + str(i))

    bad = []
    for i in range(1, len(entries)):
        if entries[i]["date"] < entries[i-1]["date"]:
            bad.append((i, entries[i-1]["date"], entries[i]["date"]))
    print("\nOut-of-sequence (text order): " + str(len(bad)))
    for b in bad[:30]:
        print("  " + str(b))

    months = Counter()
    for e in entries:
        ym = e["date"][:7]
        months[ym] += 1
    print("\nEntries per year-month:")
    for ym in sorted(months):
        print("  " + ym + ": " + str(months[ym]))


if __name__ == "__main__":
    main()
