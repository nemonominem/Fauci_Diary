#!/usr/bin/env python3
"""
Re-parser for the Missing Years release (2026.10.6_Fauci-Diary-Release-Missing-Years_Full-Package.pdf).

Fills the diary gap Jul 2015 - Dec 2019: bates 467-669 continue the prequel
(stops ~Jul 8, 2015) and run into the main diary (starts Dec 30, 2019).

Same "Month Day, Year -" date-header convention as the main/prequel
releases, so the core regex, strip patterns, article-date guard and
post-process rules are shared with reparse_diary.py / reparse_prequel.py.
Differences this parser accounts for:

  * Front matter: p.1 is the publisher's cover + analysis - a SCAN with no
    text layer, transcribed with macOS Vision OCR (ocr_image.swift) into
    missingyears_publisher_analysis.txt. Like the prequel's p.1 analysis it
    is publisher material, not a released document: it becomes a
    kind="note" entry with a synthetic date ("prologue") that sorts first
    and stays off the timeline (see EMAILS.md section 1).
  * Cross-month ranges: "Dec. 27 - Jan. 3, 2016" and
    "August 30 - September 3, 2018" name the month on both sides of the
    dash. Same-month ranges ("July 18-21, 2015") are handled by the shared
    regex; cross-month ones are matched by CROSS_MONTH_RE and anchored to
    the FIRST month's date (entry starts Dec 27 / Aug 30).
  * Same-month ranges without a year ("Feb. 15-17 - ...", "April 4 - 5,
    2016 -" has one): the year is inferred from the following entry when
    the block is chronological, else from the preceding entry. The block
    kind cannot be decided until the NEXT header is parsed, so range
    candidates are deferred (pending_range) instead of opened immediately.
  * Inline pasted emails (Bono Dec 2015 thread, Frieden Mar 2016 Zika
    thread, Sesno/McDonough/Haynes/Kousa thank-you notes ...): these are
    quoted INSIDE diary prose ("See below:", "I have copied below ..."),
    not a forwarded-mail dump like the Ebola release. Per the main diary's
    precedent they stay inside the diary entry - they are NOT split into
    email entries (one-document-per-entry applies when the release ships a
    message as a document; a pasted quote inside prose is part of that prose).
  * Year typos: "Feb. 14, 2018" sits inside the Feb-2019 sequence;
    "Nov. 4, 20915" sits between Nov 2 / Nov 5, 2015.
  * Redacted pages: a few pages carry nothing but the release footer; they
    contribute no lines and must not create entries.
"""

import calendar
import json
import os
import re
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT_PATH = os.path.join(HERE, "2026.10.6_Fauci-Diary-Release-Missing-Years_Full-Package.txt")
OUT_PATH = os.path.join(HERE, "2026.10.6_Fauci-Diary-Release-Missing-Years_Full-Package_fixed.json")

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
# Tolerances beyond the shared pattern (all attested in this release):
#   * no space after the month dot ("Nov.13, 2015", "Dec.21, 2015",
#     "Jan.21, 2017"), comma instead of dot ("Jan, 24, 2018");
#   * spaces around the range dash ("July 18- 21, 2015",
#     "Sept. 3 - 6, 2015", "April 4 - 5, 2016");
#   * weekday in parens ("Dec. 13 (Sunday), 2015").
DATE_HEADER_RE = re.compile(
    r"^\s*" + MONTH_RE + r"[.,]?\s*"
    + r"(\d{1,2})"
    + r"(?:\s*[-" + ENDASH + r"]\s*(\d{1,2}))?"
    + r"(?:\s*\(\w+\))?"
    + r"\s*[,.]?\s*"
    + r"(\d{4,5})"
    + r"\s*[-" + ENDASH + EMDASH + r":]?",
    re.IGNORECASE,
)

# Rare one-off header shapes, normalised before DATE_HEADER_RE runs:
#   * "Oct. 2,3,4,5, 2015" -> "Oct. 2, 2015" (multi-day list, starts Oct 2)
#   * "July 11 and 12, 2017" -> "July 11, 2017"
#   * "March 12 through 24, 2018" -> "March 12-24, 2018"
MONTH_NC = "(?:" + "|".join(_month_alts) + ")"  # non-capturing month (normalise_* only)

# The OCR/text layer drops the month's first letter once ("Pct. 25-26, 2018"
# for "Oct."); repair before matching so the header is not lost.
MONTH_TYPO_RE = re.compile(r"^\s*Pct\.", re.IGNORECASE)
# Day with a trailing dot instead of a comma ("Dec 16. 2017").
DAY_DOT_RE = re.compile(r"^(\s*" + MONTH_NC + r"[.,]?\s*\d{1,2})\.(\s*\d{4})", re.IGNORECASE)
LIST_DAYS_RE = re.compile(r"^(\s*" + MONTH_NC + r"[.,]?\s*\d{1,2})((?:,\d{1,2})+)(.*)$", re.IGNORECASE)
AND_DAYS_RE = re.compile(r"^(\s*" + MONTH_NC + r"[.,]?\s*\d{1,2})\s+and\s+\d{1,2}(.*)$", re.IGNORECASE)
THROUGH_DAYS_RE = re.compile(r"^(\s*" + MONTH_NC + r"[.,]?\s*\d{1,2})\s+through\s+(\d{1,2})(.*)$", re.IGNORECASE)


def normalise_header(stripped):
    stripped = MONTH_TYPO_RE.sub("Oct.", stripped, count=1)
    stripped = DAY_DOT_RE.sub(r"\1,\2", stripped, count=1)
    m = LIST_DAYS_RE.match(stripped)
    if m:
        return m.group(1) + m.group(3)
    m = AND_DAYS_RE.match(stripped)
    if m:
        return m.group(1) + m.group(2)
    m = THROUGH_DAYS_RE.match(stripped)
    if m:
        return m.group(1) + "-" + m.group(2) + m.group(3)
    return stripped

# Cross-month range: "Dec. 27 - Jan. 3, 2016". groups: 1=m1 2=d1 3=m2 4=d2 5=yr
CROSS_MONTH_RE = re.compile(
    r"^\s*" + MONTH_RE + r"\.?\s+(\d{1,2})"
    + r"\s*[-" + ENDASH + r"]\s*"
    + MONTH_RE + r"\.?\s+(\d{1,2})"
    + r"\s*[,.]?\s*(\d{4})"
    + r"\s*[-" + ENDASH + EMDASH + r":]?",
    re.IGNORECASE,
)

# Same-month range with NO year: "Feb. 15-17 - Quick trip ...".
# groups: 1=month, 2=start day, 3=end day. Year is deferred (see parse_text).
RANGE_NO_YEAR_RE = re.compile(
    r"^\s*" + MONTH_RE + r"[.,]?\s*(\d{1,2})"
    + r"\s*[-" + ENDASH + r"]\s*(\d{1,2})\.?"
    + r"\s*[-" + ENDASH + EMDASH + r":]",
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
    re.compile(r"^[\u2022\-\*]?\s*Statements and Releases", re.I),
    re.compile(r"^ALEX WONG|^BRIAN SMIALOWSKI|^Getty", re.I),
    re.compile(r"^Based on COVID-19 data,? Dr\. Fauci", re.I),
    re.compile(r"^Following up on the regular briefings he", re.I),
    re.compile(r"^During my time as Vice President", re.I),
    re.compile(r"^for a religious institution", re.I),
    re.compile(r"^CNN'?s Drew Griffin", re.I),
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
    """Apply known source-typo corrections. Listed, not silent."""
    note = None
    # Year typo: sits in the Feb-2019 sequence (neighbours Feb 13 / Feb 15,
    # 2019) and its content (Ebola RCT in DRC, Plan to End HIV rollout)
    # matches Feb 2019, not Feb 2018.
    if raw_date == "Feb. 14, 2018":
        iso_date = "2019-02-14"
        note = "Source year typo (2018->2019) corrected based on sequence/context."
    # Bates typo: printed "Nov. 4, 20915" (neighbours Nov 2 / Nov 5, 2015).
    if raw_date == "Nov. 4, 20915":
        iso_date = "2015-11-04"
        note = "Source year typo (20915->2015) corrected based on sequence/context."
    # Content-dated entries: printed year is wrong, neighbours + content agree.
    # "May 3, 2015" briefs Zika at PAHO between May 2 / May 5, 2016 entries;
    # Zika PHEIC work did not exist in May 2015.
    if raw_date == "May 3, 2015":
        iso_date = "2016-05-03"
        note = "Source year typo (2015->2016) corrected based on sequence/context."
    # "April 4, 2016" (CDC/Zika MMWR findings) sits between Apr 3 / Apr 5, 2017.
    if raw_date == "April 4, 2016":
        iso_date = "2017-04-04"
        note = "Source year typo (2016->2017) corrected based on sequence/context."
    # "May 22, 2017" (Universal Influenza Vaccine pitch to Page org) sits
    # between May 18 / May 24, 2018 entries in the May-2018 sequence.
    if raw_date == "May 22, 2017":
        iso_date = "2018-05-22"
        note = "Source year typo (2017->2018) corrected based on sequence/context."
    # "Feb. 15, 2018" (Azar war-room press briefing, VE data) is the eve of
    # the corrected Feb. 14, 2019 entry - same briefing, same week.
    if raw_date == "Feb. 15, 2018":
        iso_date = "2019-02-15"
        note = "Source year typo (2018->2019) corrected based on sequence/context."
    return iso_date, note


def format_raw_date(month_txt, day, end_day_s, year):
    base = month_txt.rstrip(".")
    if len(base) <= 4 and base.lower() != "may":
        raw = base + ". " + str(day)
    else:
        raw = base + " " + str(day)
    if end_day_s:
        raw += "-" + end_day_s
    raw += ", " + str(year).strip()
    return raw


def format_cross_month_raw(m1_txt, d1, m2_txt, d2, year):
    b1 = m1_txt.rstrip(".")
    b2 = m2_txt.rstrip(".")
    r1 = (b1 + ". " + str(d1)) if (len(b1) <= 4 and b1.lower() != "may") else (b1 + " " + str(d1))
    r2 = (b2 + ". " + str(d2)) if (len(b2) <= 4 and b2.lower() != "may") else (b2 + " " + str(d2))
    return "%s - %s, %s" % (r1, r2, year)


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


ANALYSIS_OCR = os.path.join(HERE, "missingyears_publisher_analysis.txt")
ANALYSIS_FIXES = [(chr(84)+chr(104)+chr(101)+chr(32)+chr(77)+chr(105)+chr(115)+chr(115)+chr(105)+chr(110)+chr(103)+chr(32)+chr(84)+chr(101)+chr(97)+chr(114)+chr(115), chr(84)+chr(104)+chr(101)+chr(32)+chr(77)+chr(105)+chr(115)+chr(115)+chr(105)+chr(110)+chr(103)+chr(32)+chr(89)+chr(101)+chr(97)+chr(114)+chr(115)+chr(58)+chr(32)+chr(50)+chr(48)+chr(49)+chr(53)+chr(45)+chr(50)+chr(48)+chr(49)+chr(57))]


def _analysis_entry():
    """Chairman Rand Paul's cover + analysis, printed on p.1 as a scan.

    PUBLISHER material, not one of the released documents: its own kind
    ("note"), an author, and no date - so it is never counted as a diary
    entry and never plotted on the timeline (see EMAILS.md section 1 and
    reparse_prequel._analysis_entry).
    """
    if not os.path.exists(ANALYSIS_OCR):
        return []
    with open(ANALYSIS_OCR, encoding="utf-8") as f:
        text = f.read()
    for wrong, right in ANALYSIS_FIXES:
        text = text.replace(wrong, right)
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


def flush_entry(entries, iso, raw, lines):
    content = "\n".join(lines).strip()
    iso2, note = apply_corrections(iso, raw, content)
    e = {"date": iso2, "raw_date": raw, "content": content}
    if note:
        e["date_note"] = note
    entries.append(e)

def parse_text():
    with open(TEXT_PATH, encoding="utf-8") as f:
        lines = f.readlines()

    entries = []
    cur_iso = None
    cur_raw = None
    cur_lines = []
    # A same-month range header without a year ("Feb. 15-17 - ..."): the
    # year comes from a NEIGHBOUR entry and the block kind (real entry vs
    # date-less continuation fragment) is decided only once the next dated
    # header is known. So the block is held aside until then.
    pending_range = None  # dict(month_txt, d1, d2, lines)

    def abandon_pending():
        nonlocal pending_range
        if pending_range is not None:
            # A continuation fragment, not an entry: its lines belong to the
            # current entry (or are dropped if there is none yet).
            if cur_iso is not None:
                cur_lines.extend(pending_range["lines"])
            pending_range = None

    def commit_pending(next_iso):
        """Resolve a deferred year-less range against the NEXT entry's date.

        The range takes the next entry's year when the block is chronological
        with it (same month, earlier day), else the current entry's year.
        """
        nonlocal pending_range, cur_iso, cur_raw, cur_lines
        if pending_range is None:
            return
        pr = pending_range
        pending_range = None
        month = parse_month(pr["month_txt"])
        year = None
        if cur_iso is not None:
            year = int(cur_iso[:4])
        if year is None and next_iso is not None:
            ny, nm, nd = int(next_iso[:4]), int(next_iso[5:7]), int(next_iso[8:10])
            if nm == month and pr["d1"] <= nd:
                year = ny
        if year is None and next_iso is not None:
            year = int(next_iso[:4])
        if year is None:
            if cur_iso is not None:
                cur_lines.extend(pr["lines"])
            return
        if cur_iso is not None:
            flush_entry(entries, cur_iso, cur_raw, cur_lines)
        cur_raw = format_raw_date(pr["month_txt"], pr["d1"], str(pr["d2"]), year)
        cur_iso = safe_date(year, month, pr["d1"]).isoformat()
        cur_lines = list(pr["lines"])

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = normalise_header(line.strip())
        m = DATE_HEADER_RE.match(stripped)
        if m:
            month_txt = m.group(1)
            day = int(m.group(2))
            end_day_s = m.group(3)
            year_s = m.group(4)
            year = int(year_s[:4]) if len(year_s) == 5 else int(year_s)
            rest_of_line = stripped[m.end():]

            if looks_like_article_date(rest_of_line) or looks_like_article_date(stripped):
                if cur_iso is not None and not is_strip_line(stripped):
                    cur_lines.append(line)
                elif pending_range is not None:
                    pending_range["lines"].append(line)
                continue

            try:
                month = parse_month(month_txt)
            except KeyError:
                if cur_iso is not None and not is_strip_line(stripped):
                    cur_lines.append(line)
                elif pending_range is not None:
                    pending_range["lines"].append(line)
                continue

            cand_iso = safe_date(year, month, day).isoformat()
            commit_pending(cand_iso)
            if cur_iso is not None:
                flush_entry(entries, cur_iso, cur_raw, cur_lines)

            cur_raw = format_raw_date(month_txt, day, end_day_s, year_s)
            cur_iso = cand_iso
            cur_lines = []
            if rest_of_line.strip():
                cur_lines.append(rest_of_line)
            continue

        cm = CROSS_MONTH_RE.match(stripped)
        if cm:
            m1_txt, d1 = cm.group(1), int(cm.group(2))
            m2_txt, d2, year = cm.group(3), int(cm.group(4)), int(cm.group(5))
            rest_of_line = stripped[cm.end():]
            try:
                m1 = parse_month(m1_txt)
            except KeyError:
                if cur_iso is not None and not is_strip_line(stripped):
                    cur_lines.append(line)
                elif pending_range is not None:
                    pending_range["lines"].append(line)
                continue
            try:
                m2 = parse_month(m2_txt)
            except KeyError:
                m2 = None
            # The printed year belongs to the END month ("Dec. 27 - Jan. 3,
            # 2016" starts Dec 27, 2015). Same-year ranges ("August 30 -
            # September 3, 2018") are unaffected: start year == end year.
            start_year = year - 1 if (m2 is not None and m2 < m1) else year
            cand_iso = safe_date(start_year, m1, d1).isoformat()
            commit_pending(cand_iso)
            if cur_iso is not None:
                flush_entry(entries, cur_iso, cur_raw, cur_lines)
            # Anchored to the FIRST month: the entry starts Dec 27 / Aug 30.
            cur_raw = format_cross_month_raw(m1_txt, d1, m2_txt, d2, start_year)
            cur_iso = cand_iso
            cur_lines = []
            if rest_of_line.strip():
                cur_lines.append(rest_of_line)
            continue

        rm = RANGE_NO_YEAR_RE.match(stripped)
        if rm and not looks_like_article_date(stripped):
            # Defer: year and entry-vs-fragment both need the next header.
            abandon_pending()
            if cur_iso is not None:
                flush_entry(entries, cur_iso, cur_raw, cur_lines)
                cur_iso, cur_raw, cur_lines = None, None, []
            rest_of_line = stripped[rm.end():]
            pending_range = {
                "month_txt": rm.group(1), "d1": int(rm.group(2)),
                "d2": int(rm.group(3)), "lines": [],
            }
            if rest_of_line.strip():
                pending_range["lines"].append(rest_of_line)
            continue

        if pending_range is not None:
            if not is_strip_line(stripped):
                pending_range["lines"].append(line)
        elif cur_iso is not None and not is_strip_line(stripped):
            cur_lines.append(line)

    commit_pending(None)
    if cur_iso is not None:
        flush_entry(entries, cur_iso, cur_raw, cur_lines)

    return entries


def post_process(entries):
    """Filter fakes, fold continuation fragments into the running entry.

    The main diary's 60-day backward-jump merge is deliberately NOT applied:
    this release contains content-dated entries whose printed year is wrong
    (see apply_corrections) plus retrospective blocks (Oct. 13-15 before
    Oct. 14), so a backward jump is evidence of a typo, not of an embedded
    article. Folding those would chain-merge the whole timeline into one
    entry. Only same-year-month neighbours fold (a date-less continuation
    fragment), plus pasted-article openers.
    """
    entries = [e for e in entries if not is_likely_fake_entry(e)]
    merged = []
    for e in entries:
        is_clip = is_article_clipping(e)
        is_frag = bool(merged) and merged[-1]["date"][:7] == e["date"][:7]             and merged[-1]["date"] > e["date"]
        if (is_clip or is_frag) and merged:
            merged[-1]["content"] += "\n" + e["content"]
        else:
            merged.append(e)
    return merged


def main():
    entries = parse_text()
    entries = post_process(entries)

    dated = sorted(entries, key=lambda e: e["date"])
    front = _analysis_entry()
    real_entries = front + dated
    dates_list = [e["date"] for e in dated]
    date_range = {"start": dates_list[0], "end": dates_list[-1]} if dates_list else {}

    out = {
        "source_file": "2026.10.6_Fauci-Diary-Release-Missing-Years_Full-Package.pdf",
        "title": "Tony's Diary -- The Missing Years (2015-2019)",
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

    print("\nText-order backward jumps >60d (possible typos/fragments):")
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
    print("\nEntries per year-month:")
    for ym in sorted(months):
        print("  " + ym + ": " + str(months[ym]))


if __name__ == "__main__":
    main()
