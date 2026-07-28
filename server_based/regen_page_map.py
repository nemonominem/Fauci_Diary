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
JSON_PATH = os.path.join(HERE, "2026.07.24_Tonys-Diary-Package.json")
OUT_PATH = os.path.join(HERE, "page_map.json")


def load_expected_entry_counts():
    """How many real diary entries the content JSON has per ISO date.

    A handful of dates legitimately have two separate entries (e.g.
    2020-03-29 has both "Mar. 29, 2020" and "March 29, 2020"). Used to tell
    a genuine second entry for the same date apart from a same-date mention
    embedded in pasted press content (a byline, a cartoon-list date, etc.)."""
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    counts = {}
    for e in data["entries"]:
        counts[e["date"]] = counts.get(e["date"], 0) + 1
    return counts

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


def clean_with_pages(line_pages):
    """Mirror clean_json_breaks.clean_content while tracking PDF page per character.

    line_pages: list of (line_str, page_number)
    Returns (cleaned_text, breaks) where breaks is [[char_offset, page], ...]
    at every page change (including offset 0).
    """
    paragraphs = []
    current = []

    def flush():
        nonlocal current
        if current:
            paragraphs.append(current)
            current = []

    for line, page in line_pages:
        s = line.strip()
        if not s:
            flush()
            continue
        if s.upper().startswith("PRESS:"):
            flush()
            current.append((s, page))
            continue
        if s.endswith(":") and len(s) < 80:
            flush()
            current.append((s, page))
            continue
        current.append((s, page))
    flush()

    cleaned_parts = []
    char_pages = []
    for pi, para in enumerate(paragraphs):
        if pi:
            cleaned_parts.append("\n\n")
            char_pages.extend([para[0][1], para[0][1]])
        first = True
        for text, page in para:
            if not first:
                cleaned_parts.append(" ")
                char_pages.append(page)
            t = re.sub(r"\s+", " ", text).strip()
            cleaned_parts.append(t)
            char_pages.extend([page] * len(t))
            first = False

    cleaned = "".join(cleaned_parts)
    if len(cleaned) != len(char_pages):
        # Fallback: no per-char map
        pages = sorted({p for _, p in line_pages}) or [1]
        return cleaned, [[0, pages[0]]], pages[0], pages[-1]

    breaks = []
    prev = None
    for i, p in enumerate(char_pages):
        if p != prev:
            breaks.append([i, p])
            prev = p
    start = breaks[0][1] if breaks else 1
    end = breaks[-1][1] if breaks else start
    return cleaned, breaks, start, end


def looks_like_bare_link_reference(rest_of_line, lines, i):
    """Detect date-list lines like 'May 11, 2020' inside 'Other Tatulli
    cartoons with Lio:' reference blocks — a bare date with nothing else on
    the line, immediately followed by a URL. Real entry headers always carry
    same-line content (e.g. the Global/USA case counts)."""
    if rest_of_line.strip():
        return False
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return False
    nxt = lines[j].strip().lower()
    return nxt.startswith("http") or nxt.startswith("sharethis")


def build_page_map():
    """Build rich page map: start/end + char-offset breaks for hit→page jumps.

    Content lines are accumulated per entry *key* (not per "currently active"
    entry) so that a self-referencing repeat header correctly resumes
    appending to its own original entry even if a different date's entry was
    parsed in between (e.g. headers appear out of order as June 24, June 23,
    June 24 in the source: the second "June 24" chunk must still land back in
    the June 24 entry, not get folded into June 23's).
    """
    with open(TEXT_PATH, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f.readlines()]

    page_of_line = {}
    current_page = 1
    for i, line in enumerate(lines):
        m = PAGE_MARKER_RE.match(line.strip())
        if m:
            current_page = int(m.group(1))
        page_of_line[i] = current_page

    expected_counts = load_expected_entry_counts()
    started_counts = {}

    accum = {}  # key -> list of (text, page)
    order = []  # keys in first-seen order
    active_key = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        m = DATE_HEADER_RE.match(stripped)
        if m:
            month_txt = m.group(1)
            day = int(m.group(2))
            end_day_s = m.group(3)
            year = int(m.group(4))
            rest_of_line = stripped[m.end():]

            if looks_like_bare_link_reference(rest_of_line, lines, i):
                if active_key is not None and not is_strip_line(stripped):
                    accum[active_key].append((line, page_of_line[i]))
                continue

            if looks_like_article_date(rest_of_line) or looks_like_article_date(stripped):
                if active_key is not None and not is_strip_line(stripped):
                    accum[active_key].append((line, page_of_line[i]))
                continue

            try:
                month = parse_month(month_txt)
            except KeyError:
                if active_key is not None and not is_strip_line(stripped):
                    accum[active_key].append((line, page_of_line[i]))
                continue

            raw_candidate = format_raw_date(month_txt, day, end_day_s, year)
            candidate_iso = safe_date(year, month, day).isoformat()
            corrected_candidate_iso = apply_corrections(candidate_iso, raw_candidate, "")
            already_started = started_counts.get(corrected_candidate_iso, 0)
            expected = expected_counts.get(corrected_candidate_iso, 1)
            # Grouping key uses the *uncorrected* iso (matching the original
            # cur_iso/cur_raw pairing); content-dependent corrections are
            # applied once, after all lines for the entry are known, below.
            key = candidate_iso + "|" + raw_candidate
            if already_started >= expected:
                # The content JSON says this date already has as many real
                # entries as expected; this is a same-date self-reference
                # embedded in pasted press content (a byline, a cartoon-list
                # date, etc.), not another new entry. Resume appending to the
                # entry it belongs to, even if something else is active now.
                if key in accum:
                    active_key = key
                    if rest_of_line.strip():
                        accum[active_key].append((rest_of_line, page_of_line[i]))
                elif active_key is not None and not is_strip_line(stripped):
                    accum[active_key].append((line, page_of_line[i]))
                continue

            started_counts[corrected_candidate_iso] = already_started + 1
            accum[key] = []
            order.append(key)
            active_key = key
            if rest_of_line.strip():
                accum[active_key].append((rest_of_line, page_of_line[i]))
        else:
            if active_key is not None and not is_strip_line(stripped):
                accum[active_key].append((line, page_of_line[i]))

    page_map = {}
    for key in order:
        iso, raw = key.split("|", 1)
        raw_content = "\n".join(t for t, _ in accum[key]).strip()
        corrected_iso = apply_corrections(iso, raw, raw_content)
        cleaned, breaks, start, end = clean_with_pages(accum[key])
        page_map[corrected_iso + "|" + raw] = {
            "start": start,
            "end": end,
            "breaks": breaks,
        }
    return page_map


def main():
    page_map = build_page_map()

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(page_map, f, ensure_ascii=False, indent=2)

    multi = sum(1 for v in page_map.values() if v.get("end", v.get("start")) > v.get("start", 0))
    print(f"Wrote {len(page_map)} entries to {OUT_PATH} ({multi} multi-page)")

    for k in sorted(page_map.keys()):
        if "2021-08-03" in k or "2021-08-15" in k:
            v = page_map[k]
            print(f"  {k} -> p.{v['start']}-{v['end']} breaks={v['breaks']}")


if __name__ == "__main__":
    main()

