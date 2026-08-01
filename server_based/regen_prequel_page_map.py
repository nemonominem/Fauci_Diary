#!/usr/bin/env python3
"""
Regenerate page_map for the Prequel diary (2026.07.27_Diary-Prequel-).

Same content-start heuristic as regen_page_map.py but adapted for the
Prequel: prequel file paths, prequel source-typo corrections, and a manual
page-map entry for the prologue (which has no date header in the text).
"""

import json
import re
import os
import calendar
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT_PATH = os.path.join(HERE, "2026.07.27_Diary-Prequel-.txt")
JSON_PATH = os.path.join(HERE, "2026.07.27_Diary-Prequel-.json")
OUT_PATH = os.path.join(HERE, "prequel_page_map.json")


def load_expected_entry_counts():
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    counts = {}
    for e in data["entries"]:
        counts[e["date"]] = counts.get(e["date"], 0) + 1
    return counts

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
    """Prequel source-typo corrections (mirrors reparse_prequel.py)."""
    if raw_date == "Jan. 11, 2103":
        iso_date = "2013-01-11"
    elif raw_date == "Jan. 16, 2016":
        iso_date = "2015-01-16"
    elif raw_date == "September 9, 2019":
        iso_date = "2014-09-09"
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
    """Mirror clean_prequel_breaks.clean_content while tracking PDF page."""
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


def build_page_map():
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

    accum = {}
    order = []
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
            key = candidate_iso + "|" + raw_candidate
            if already_started >= expected:
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
    # Prologue: content before the first date header (email cover + intro)
    page_map["prologue|Prologue"] = {"start": 1, "end": 2, "breaks": [[0, 1]]}

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


if __name__ == "__main__":
    main()

