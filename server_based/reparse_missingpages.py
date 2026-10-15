#!/usr/bin/env python3
"""
Re-parser for the Missing Pages release (2026.10.07_Missing-Pages-Diary_Full-Package.pdf).

Fills the gap INSIDE the main diary's own range: the main diary
(2026.07.24_Tonys-Diary-Package.json) runs Dec 2019 - Dec 2022 but jumps
straight from Nov 2021 to a single stray May 31, 2022 entry then June 2022 -
this release is the missing Dec 2021 - May 2022 stretch, explicitly
"Continued from Part 4" on its first page. Confirmed genuinely new content
(no overlap check needed): the main diary has zero entries for Dec 2021
through Apr 2022.

Same "Month Day, Year -" date-header convention as the other parsers. Unlike
the Ebola release, embedded emails here are PASTED INSIDE DIARY PROSE
("See e-mail from X below", "I am listing below an email that I sent to..."),
never shipped as standalone documents - so per the Missing Years precedent
(EMAILS.md section 1, reparse_missingyears.py docstring) they stay inside
the diary entry and are NOT split into separate email entries. (One of the
pasted threads is even the same Bono/pdh exchange style as Missing Years'
Bono thread - same author's office, same habit of pasting fan mail into the
diary.)

Differences this parser accounts for:

  * Front matter: p.1 is the publisher's cover + analysis - a SCAN with no
    text layer, transcribed with macOS Vision OCR (ocr_image.swift) into
    missingpages_publisher_analysis.txt. Same "note" treatment as the other
    three releases' front matter (EMAILS.md section 1). The analysis text
    itself flags one correction directly: "(January 2, 2022 [diary entry
    mislabeled "Jan 2, 2021"])".
  * Year typos: four consecutive early entries (Jan 2-5, 2022) are all
    printed with "2021" instead of "2022" - confirmed by the publisher
    analysis for Jan 2, and by sequence/context (sandwiched between the
    correctly-dated Jan 1 and Jan 6 entries) for Jan 3-5. A fifth, "Jan. 19,
    2020", sits between the correctly-dated Jan 18 and Jan 20, 2022 entries.
  * Embedded news-clipping bylines that carry their own "Month Day, Year"
    line (a republished article's own dateline, a preprint's publication
    date, a magazine byline) are mistaken for diary-day headers by the
    shared regex. Two folds clean these up:
      - same-month backward fragments fold into the preceding entry
        (inherited from reparse_diary.py / reparse_missingyears.py);
      - a NEW second pass folds any entry whose date, once everything is
        sorted, turns out to EXACTLY match another entry's date - this
        catches cross-month cases the same-month fold cannot (a byline dated
        "March 1, 2022" sitting inside the Feb 23 entry's trailing article
        quote, nowhere near the real March 1 entry in text order; a bare
        "February 9, 2022" byline sitting inside the March 5 entry, nowhere
        near the real Feb 9 entry either). Every such collision found in
        this release turned out to be a byline coinciding with a REAL diary
        day elsewhere in the document, so folding by exact date is safe
        here; it would need revisiting if a future source legitimately used
        one date twice for unrelated documents.
  * One embedded article is NOT safely handled by either fold: an Axios
    "timeline of Fauci's predictions" retrospective, pasted whole inside the
    April 27, 2022 entry, itself contains a dozen "Month Day, Year:" lines
    running from March 2020 to April 2022 - dates with NO corresponding
    entry anywhere in this release (2020-2021 are covered by a different
    source entirely), so neither fold would catch them and they would ship
    as bogus entries far outside this release's actual date range. This
    span is excluded from date-header scanning entirely (verbatim span,
    identified by its own unique start/end lines, asserted to occur exactly
    once) and kept as plain body text of the April 27 entry.
  * Redacted/blank pages: none found (only p.1 is blank of real text).
"""

import calendar
import json
import os
import re
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT_PATH = os.path.join(HERE, "2026.10.07_Missing-Pages-Diary_Full-Package.txt")
OUT_PATH = os.path.join(HERE, "2026.10.07_Missing-Pages-Diary_Full-Package_fixed.json")

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

# Tolerant like reparse_missingyears.py's header regex (this release has the
# same "no space after the month dot" quirk: "Feb.1, 2022", "Feb.12, 2022"),
# plus two more tolerances attested here:
#   * an ordinal day suffix ("April 14th, 2022");
#   * a handful of headers that drop the year entirely ("April 22 - Global",
#     "April 25 - Global"), mid-sequence inside an otherwise fully-dated
#     month - the year is carried over from the running entry (see parse_text).
# groups: 1=month, 2=day, 3=optional end-day (range, unused here but kept for
# the shared grammar), 4=optional year
DATE_HEADER_RE = re.compile(
    r"^\s*" + MONTH_RE + r"[.,]?\s*"
    + r"(\d{1,2})(?:st|nd|rd|th)?"
    + r"(?:\s*[-" + ENDASH + r"]\s*(\d{1,2}))?"
    + r"(?:\s*\(\w+\))?"
    + r"\s*[,.]?\s*"
    + r"(\d{4})?"
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

ARTICLE_START_PATTERNS = [
    re.compile(r"^Photograph by", re.I),
    re.compile(r"^\d{1,2}\s*[AP]M\b", re.I),
    re.compile(r"^ShareThis", re.I),
    re.compile(r"^Screen cap", re.I),
    re.compile(r"^Press Release\s*$", re.I),
    re.compile(r"^[•\-\*]?\s*Statements and Releases", re.I),
    re.compile(r"^ALEX WONG|^BRIAN SMIALOWSKI|^Getty", re.I),
]

# The one Axios retrospective article (see docstring): everything between
# these two lines (inclusive) is kept as plain text, never scanned for date
# headers. Both cues are asserted to occur exactly once in the source text.
VERBATIM_SPAN_START = "AXIOS: Gave a list of all of my predictions"
VERBATIM_SPAN_END = "Go deeper"


def is_strip_line(line):
    return any(p.match(line) for p in STRIP_PATTERNS)


def looks_like_article_date(text):
    return any(p.search(text) for p in ARTICLE_TIME_HINTS)


def parse_month(month_text):
    return MONTH_MAP[month_text.lower().rstrip(".")]


def safe_date(year, month, day):
    max_day = calendar.monthrange(year, month)[1]
    day = min(day, max_day)
    return date(year, month, day)


def apply_corrections(iso_date, raw_date, content):
    """Apply known source-typo corrections. Listed, not silent."""
    note = None
    # Four consecutive entries printed "2021" instead of "2022" (confirmed
    # for Jan 2 by the publisher's own analysis; Jan 3-5 by sequence - they
    # sit between the correctly-dated Jan 1 and Jan 6, 2022 entries).
    if raw_date == "Jan. 2, 2021":
        iso_date = "2022-01-02"
        note = ("Source year typo (2021->2022) corrected; confirmed by the "
                "publisher's own analysis (\"diary entry mislabeled "
                "'Jan 2, 2021'\").")
    elif raw_date == "Jan. 3, 2021":
        iso_date = "2022-01-03"
        note = "Source year typo (2021->2022) corrected based on sequence/context."
    elif raw_date == "Jan. 4, 2021":
        iso_date = "2022-01-04"
        note = "Source year typo (2021->2022) corrected based on sequence/context."
    elif raw_date == "Jan. 5, 2021":
        iso_date = "2022-01-05"
        note = "Source year typo (2021->2022) corrected based on sequence/context."
    # "Jan. 19, 2020" sits between the correctly-dated Jan 18 / Jan 20, 2022
    # entries (and references the same Omicron case-count run).
    elif raw_date == "Jan. 19, 2020":
        iso_date = "2022-01-19"
        note = "Source year typo (2020->2022) corrected based on sequence/context."
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
    content = entry["content"].strip()
    first_line = content.split("\n")[0].strip() if content else ""
    return any(p.match(first_line) for p in ARTICLE_START_PATTERNS)


ANALYSIS_OCR = os.path.join(HERE, "missingpages_publisher_analysis.txt")


def _analysis_entry():
    """Chairman Rand Paul's cover + analysis, printed on p.1 as a scan.

    Publisher material, not one of the released documents - its own kind
    ("note"), an author, and no date, so never a diary entry and never
    plotted (EMAILS.md section 1, same precedent as prequel/missingyears p.1).
    """
    if not os.path.exists(ANALYSIS_OCR):
        return []
    with open(ANALYSIS_OCR, encoding="utf-8") as f:
        text = f.read()
    lines = [ln.rstrip() for ln in text.split("\n")]
    start = 0
    for i, ln in enumerate(lines):
        if "tony" in ln.lower() and "diary" in ln.lower():
            start = i
            break
    body = "\n".join(lines[start:]).strip()
    if not body:
        return []
    return [{
        "date": "prologue",
        "kind": "note",
        "raw_date": "Analysis by Chairman Rand Paul",
        "title": lines[start].strip(),
        "author": "Chairman Rand Paul",
        "provenance": "Publisher's cover and analysis printed on page 1 of the release "
                      "(a scan, transcribed with macOS Vision OCR). Not one of "
                      "the released documents.",
        "content": body,
    }]


def _split_verbatim_span(lines):
    """Pull out the one Axios retrospective (see docstring) as an opaque
    block of plain lines, so its own embedded "Month Day, Year:" lines never
    reach the date-header scanner. Returns (before, verbatim, after) line
    lists; `verbatim` is spliced back into the body untouched."""
    start_idx = end_idx = None
    for i, ln in enumerate(lines):
        if start_idx is None and VERBATIM_SPAN_START in ln:
            start_idx = i
        elif start_idx is not None and end_idx is None and VERBATIM_SPAN_END in ln:
            end_idx = i
            break
    if start_idx is None or end_idx is None:
        raise AssertionError(
            "Axios verbatim-span markers not found exactly once - re-check "
            "VERBATIM_SPAN_START/END against the current source text.")
    span = [ln for ln in lines[start_idx:end_idx + 1] if not is_strip_line(ln.strip())]
    return lines[:start_idx], span, lines[end_idx + 1:]


def flush_entry(entries, iso, raw, lines):
    content = "\n".join(lines).strip()
    iso2, note = apply_corrections(iso, raw, content)
    e = {"date": iso2, "raw_date": raw, "content": content}
    if note:
        e["date_note"] = note
    entries.append(e)


def parse_text():
    with open(TEXT_PATH, encoding="utf-8") as f:
        raw_lines = [ln.rstrip("\n") for ln in f.readlines()]

    before, verbatim, after = _split_verbatim_span(raw_lines)
    # Splice the verbatim span back in as a single inert placeholder line;
    # its real text is substituted back in after parsing (see below) so it
    # never gets a chance to match DATE_HEADER_RE.
    placeholder = "\x00VERBATIM_SPAN\x00"
    lines = before + [placeholder] + after

    entries = []
    cur_iso = None
    cur_raw = None
    cur_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped == placeholder:
            cur_lines.append("\n".join(verbatim))
            continue
        m = DATE_HEADER_RE.match(stripped)
        if m:
            month_txt = m.group(1)
            day = int(m.group(2))
            end_day_s = m.group(3)
            year_s = m.group(4)
            rest_of_line = stripped[m.end():]

            if looks_like_article_date(rest_of_line) or looks_like_article_date(stripped):
                if cur_iso is not None and not is_strip_line(stripped):
                    cur_lines.append(line)
                continue

            # A handful of headers drop the year entirely ("April 22 -
            # Global", "April 25 - Global"), always mid-sequence inside an
            # already-dated month, and always followed by the familiar
            # Global/USA case-count tail. Requiring that tail is what stops
            # a mid-sentence PDF line-wrap ("...celebrated at a\nNov. 12
            # gala and have...") from being mistaken for a year-less header,
            # now that the year itself is optional. The year is carried over
            # from the entry currently open; without one yet (can't happen
            # for a real header - the release's first entry is fully dated),
            # this can't be a header at all.
            if year_s is None:
                if cur_iso is None or not re.search(r"\b(?:Global|USA)\b", rest_of_line):
                    if cur_iso is not None and not is_strip_line(stripped):
                        cur_lines.append(line)
                    continue
                year = int(cur_iso[:4])
            else:
                year = int(year_s)

            try:
                month = parse_month(month_txt)
            except KeyError:
                if cur_iso is not None and not is_strip_line(stripped):
                    cur_lines.append(line)
                continue

            if cur_iso is not None:
                flush_entry(entries, cur_iso, cur_raw, cur_lines)

            cur_raw = format_raw_date(month_txt, day, end_day_s, year)
            cur_iso = safe_date(year, month, day).isoformat()
            cur_lines = []
            if rest_of_line.strip():
                cur_lines.append(rest_of_line)
            continue

        if cur_iso is not None and not is_strip_line(stripped):
            cur_lines.append(line)

    if cur_iso is not None:
        flush_entry(entries, cur_iso, cur_raw, cur_lines)

    return entries


def fold_text_order_fragments(entries):
    """Pass 1: fold clippings and same-month backward fragments into the
    preceding entry (same heuristic as reparse_diary.py / reparse_missingyears.py)."""
    merged = []
    for e in entries:
        is_clip = is_article_clipping(e)
        is_frag = (bool(merged)
                   and merged[-1]["date"][:7] == e["date"][:7]
                   and merged[-1]["date"] > e["date"])
        if (is_clip or is_frag) and merged:
            merged[-1]["content"] += "\n" + e["content"]
        else:
            merged.append(e)
    return merged


def fold_exact_date_duplicates(sorted_entries):
    """Pass 2 (runs AFTER sorting): fold any entries that land on the exact
    same date, even across different months - this is what catches an
    article byline's own dateline landing nowhere near its real diary-day
    counterpart in text order (see docstring). Every collision found in this
    release is a byline coinciding with a genuine diary day elsewhere in the
    document, so an exact-date match is folded unconditionally."""
    merged = []
    for e in sorted_entries:
        if merged and merged[-1]["date"] == e["date"]:
            merged[-1]["content"] += "\n" + e["content"]
        else:
            merged.append(e)
    return merged


def post_process(entries):
    entries = [e for e in entries if not is_likely_fake_entry(e)]
    entries = fold_text_order_fragments(entries)
    return entries


def main():
    entries = parse_text()
    entries = post_process(entries)

    dated = sorted(entries, key=lambda e: e["date"])
    dated = fold_exact_date_duplicates(dated)
    front = _analysis_entry()
    real_entries = front + dated
    dates_list = [e["date"] for e in dated]
    date_range = {"start": dates_list[0], "end": dates_list[-1]} if dates_list else {}

    out = {
        "source_file": "2026.10.07_Missing-Pages-Diary_Full-Package.pdf",
        "title": "Tony's Diary -- The Missing Pages (Dec 2021 - May 2022)",
        "released_by": "Chairman Rand Paul",
        "total_entries": len(real_entries),
        "date_range": date_range,
        "entries": real_entries,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("Re-parsed entries: " + str(len(real_entries))
          + " (incl. " + str(len(front)) + " publisher note)")
    print("Date range: " + str(date_range))

    seen = {}
    dups = []
    for i, e in enumerate(dated):
        if e["date"] in seen:
            dups.append((e["date"], seen[e["date"]], i))
        seen[e["date"]] = i
    print("\nDuplicate dates (should be 0): " + str(len(dups)))
    for d, j, i in dups[:30]:
        print("  " + d + " at idx " + str(j) + " and " + str(i))

    bad = []
    for i in range(1, len(dated)):
        if dated[i]["date"] < dated[i - 1]["date"]:
            bad.append((i, dated[i - 1]["date"], dated[i]["date"]))
    print("\nOut-of-sequence (after sort, should be 0): " + str(len(bad)))
    for b in bad[:30]:
        print("  " + str(b))

    months = Counter()
    for e in dated:
        months[e["date"][:7]] += 1
    print("\nEntries per year-month:")
    for ym in sorted(months):
        print("  " + ym + ": " + str(months[ym]))


if __name__ == "__main__":
    main()
