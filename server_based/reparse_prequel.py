#!/usr/bin/env python3
"""
Re-parser for the Diary Prequel (2026.07.27_Diary-Prequel-.pdf).

The Prequel is Fauci's earlier "HISTORICAL RECORD OF HIV/AIDS" (March 2001 –
July 2015), released as a separate Congressional package.  It uses the same
"Month Day, Year –" date-header convention as the main Tony's Diary Package,
so the core date-header regex is shared with reparse_diary.py.

Key differences from the main diary that this parser accounts for:
  • No known source-typo corrections yet (apply_corrections is a no-op;
    add them here once identified).
  • Retrospective entries are legitimate (the author jumps back to fill in
    missed dates, e.g. Jan-2001 entries written after Dec-2001 entries).
    The main diary's 60-day backward-jump "out-of-sequence" merge is
    therefore DISABLED here — it would wrongly fold real entries into the
    preceding one.
  • The first ~2 pages are an email cover-sheet + document prologue with no
    date header; that orphan content is captured into a synthetic "prologue"
    entry so it is not lost.
  • Embedded forwarded-email dates use numeric formats (04/11/2001) that the
    month-name regex does not match, so they do not create fake entries.
"""

import calendar
import json
import os
import re
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT_PATH = os.path.join(HERE, "2026.07.27_Diary-Prequel-.txt")
OUT_PATH = os.path.join(HERE, "2026.07.27_Diary-Prequel-_fixed.json")

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
    """Apply known source-typo corrections for the Prequel."""
    note = None
    # Year typos (author wrote wrong year)
    if raw_date == "Jan. 11, 2103":
        iso_date = "2013-01-11"
        note = "Source year typo (2103->2013) corrected based on sequence/context."
    elif raw_date == "Jan. 16, 2016":
        iso_date = "2015-01-16"
        note = "Source year typo (2016->2015) corrected based on sequence/context."
    elif raw_date == "September 9, 2019":
        iso_date = "2014-09-09"
        note = "Source year typo (2019->2014) corrected based on sequence/context."
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


def parse_text():
    with open(TEXT_PATH, encoding="utf-8") as f:
        lines = f.readlines()

    entries = []
    cur_iso = None
    cur_raw = None
    cur_lines = []
    prologue_lines = []  # content before the first date header

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
            else:
                # First date header — save any preceding prologue content
                prologue_text = "\n".join(prologue_lines).strip()
                if prologue_text:
                    entries.append({
                        "date": "prologue",
                        "raw_date": "Prologue",
                        "content": prologue_text,
                    })

            cur_raw = format_raw_date(month_txt, day, end_day_s, year)
            cur_iso = safe_date(year, month, day).isoformat()
            cur_lines = []
            if rest_of_line.strip():
                cur_lines.append(rest_of_line)
        else:
            if cur_iso is not None and not is_strip_line(stripped):
                cur_lines.append(line)
            elif cur_iso is None and not is_strip_line(stripped):
                prologue_lines.append(line)

    if cur_iso is not None:
        content = "\n".join(cur_lines).strip()
        iso2, note = apply_corrections(cur_iso, cur_raw, content)
        e = {"date": iso2, "raw_date": cur_raw, "content": content}
        if note:
            e["date_note"] = note
        entries.append(e)

    return entries


def post_process(entries):
    """Filter fakes.  Out-of-sequence merge is DISABLED for the Prequel.

    The Prequel contains legitimate retrospective entries (the author jumps
    back to record missed dates), so the main diary's 60-day backward-jump
    merge must not be applied here.
    """
    entries = [e for e in entries if not is_likely_fake_entry(e)]
    return entries


def is_likely_fake_entry(entry):
    content = entry["content"].strip()
    if not content:
        return True
    if content.startswith("http") and content.count("\n") == 0:
        return True
    if re.match(r"^\|?\s*\d{1,2}:\d{2}", content):
        return True
    return False

def main():
    entries = parse_text()
    entries = post_process(entries)

    # Sort by date; keep the prologue (date=="prologue") first
    prologue = [e for e in entries if e["date"] == "prologue"]
    dated = [e for e in entries if e["date"] != "prologue"]
    dated.sort(key=lambda e: e["date"])

    real_entries = prologue + dated
    dates_list = [e["date"] for e in dated]
    date_range = {"start": dates_list[0], "end": dates_list[-1]} if dates_list else {}

    out = {
        "source_file": "2026.07.27_Diary-Prequel-.pdf",
        "title": "Fauci Diary Prequel -- Historical Record of HIV/AIDS",
        "released_by": "Chairman Rand Paul",
        "total_entries": len(real_entries),
        "date_range": date_range,
        "entries": real_entries,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("Re-parsed entries: " + str(len(real_entries))
          + " (incl. " + str(len(prologue)) + " prologue)")
    print("Date range: " + str(date_range))

    seen = {}
    dups = []
    for i, e in enumerate(dated):
        if e["date"] in seen:
            dups.append((e["date"], seen[e["date"]], i))
        seen[e["date"]] = i
    print("\nDuplicate dates: " + str(len(dups)))
    for d, j, i in dups[:30]:
        print("  " + d + " at idx " + str(j) + " and " + str(i))

    bad = []
    for i in range(1, len(dated)):
        if dated[i]["date"] < dated[i - 1]["date"]:
            bad.append((i, dated[i - 1]["date"], dated[i]["date"]))
    print("\nOut-of-sequence (after sort, should be 0): " + str(len(bad)))
    for b in bad[:30]:
        print("  " + str(b))

    # Show year-typos: entries where year is suspicious given neighbors
    print("\nText-order out-of-sequence (backward jumps >60d, possible typos):")
    jump_count = 0
    for i in range(1, len(dated)):
        prev_d = date.fromisoformat(dated[i - 1]["date"])
        cur_d = date.fromisoformat(dated[i]["date"])
        if (prev_d - cur_d).days > 60:
            jump_count += 1
            if jump_count <= 30:
                print("  idx " + str(i) + ": " + dated[i - 1]["raw_date"]
                      + " -> " + dated[i]["raw_date"] + " ("
                      + str((prev_d - cur_d).days) + "d back)")
    print("  total backward jumps >60d: " + str(jump_count))

    months = Counter()
    for e in dated:
        ym = e["date"][:7]
        months[ym] += 1
    print("\nEntries per year-month (first/last 20):")
    for ym in sorted(months)[:20]:
        print("  " + ym + ": " + str(months[ym]))
    if len(months) > 20:
        print("  ...")
        for ym in sorted(months)[-20:]:
            print("  " + ym + ": " + str(months[ym]))


if __name__ == "__main__":
    main()

