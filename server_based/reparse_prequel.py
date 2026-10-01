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


FRONT_MATTER_OCR = os.path.join(HERE, "prequel_publisher_analysis.txt")

# Obvious Vision OCR slips in the publisher's analysis (listed, so the
# transcription stays auditable rather than silently "fixed").
ANALYSIS_FIXES = [("publick...", "publicly..."), ("iS a tough", "is a tough")]

SEPARATOR = "-" * 10


def _analysis_entry():
    """Chairman Rand Paul's analysis, printed on p.1 as a scan (no text layer).

    PUBLISHER material, not one of the released documents: its own kind
    ("note"), an author, and no date - so it is never counted as a diary entry
    and never plotted on the timeline.
    """
    if not os.path.exists(FRONT_MATTER_OCR):
        return []
    with open(FRONT_MATTER_OCR, encoding="utf-8") as f:
        text = f.read()
    for wrong, right in ANALYSIS_FIXES:
        text = text.replace(wrong, right)
    lines = [ln.rstrip() for ln in text.split("\n")]
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip().lower().startswith("tony") and "diary" in ln.lower():
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
        "provenance": "Publisher's analysis printed on page 1 of the release "
                      "(a scan, transcribed with macOS Vision OCR). Not one of "
                      "the released documents.",
        "content": body,
    }]


MONTHS_NUM = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_rfc2822(value):
    """RFC2822 date -> aware datetime in UTC (the offset is authoritative)."""
    from datetime import datetime, timedelta, timezone
    m = re.search(r"(?:\w{3},\s*)?(\d{1,2})\s+(\w{3})\w*\s+(\d{4})\s+"
                  r"(\d{2}):(\d{2})(?::(\d{2}))?\s*([+-]\d{4})?", value)
    if not m:
        return None
    day, mon, year, hh, mm, ss, off = m.groups()
    if mon[:3].title() not in MONTHS_NUM:
        return None
    try:
        naive = datetime(int(year), MONTHS_NUM[mon[:3].title()], int(day),
                         int(hh), int(mm), int(ss or 0))
    except ValueError:
        return None
    if off:
        sign = 1 if off[0] == "+" else -1
        delta = timedelta(hours=int(off[1:3]), minutes=int(off[3:5])) * sign
        return (naive - delta).replace(tzinfo=timezone.utc)
    return naive.replace(tzinfo=timezone.utc)


def format_sent_line(dt):
    """(iso date, HHMM, "HH:MM", printable stamp) in New York time."""
    from zoneinfo import ZoneInfo
    ny = dt.astimezone(ZoneInfo("America/New_York"))
    stamp = ny.strftime("%A, %B %d, %Y %I:%M %p %Z")
    stamp = stamp.replace(" EDT", " ET").replace(" EST", " ET")
    return ny.date().isoformat(), ny.strftime("%H%M"), ny.strftime("%H:%M"), stamp


def _cover_email(head):
    """Parse the p.2 cover sheet into an email entry (printable header block)."""
    fields, body_lines = [], []
    raw_header_date = None
    in_body = False
    for line in head.split("\n"):
        stripped = line.strip()
        m = re.match(r"^([A-Za-z-]+):\s*(.*)$", stripped)
        if m and m.group(1).lower() in ("from", "to", "cc", "subject", "date",
                                        "sent", "attachments", "importance"):
            name = m.group(1).lower()
            if name == "date":
                raw_header_date = m.group(2).strip()   # printed once, as "Sent:"
            else:
                fields.append("%s: %s" % (name.capitalize(), m.group(2).strip()))
            in_body = False
            continue
        if not stripped:
            continue
        if not in_body and re.match(r"^</?[A-Za-z0-9=/;,.\s]+>$", stripped):
            continue          # continuation of the From:/To: address-book line
        in_body = True
        body_lines.append(stripped)

    if not any(f.lower().startswith("subject:") for f in fields):
        return None
    dt = parse_rfc2822(raw_header_date) if raw_header_date else None
    if dt is None:
        return None
    iso, hhmm, et_hhmm, printable = format_sent_line(dt)
    subject = next((f.split(":", 1)[1].strip() for f in fields
                    if f.lower().startswith("subject:")), "")
    # Fields are separated by BLANK lines: the cleaner turns each into its own
    # paragraph, which is what the card renders as the printable header block.
    content = ("\n\n".join(fields)
               + "\n\nSent: " + printable
               + "\n\n" + SEPARATOR + "\n\n"
               + "\n\n".join(body_lines)).strip()
    return {
        "date": iso,
        "time": hhmm,
        "kind": "email",
        "raw_date": "%s ET · %s" % (et_hhmm, subject or "(no subject)"),
        "date_note": "Cover email of the prequel; carries the historical record as an attachment",
        "content": content,
    }

def front_matter(lines):
    """The release's front matter, split into what it actually is.

    p.2 is a real released document: an email Fauci sent to himself
    ("Subject: history", 11 Jul 2015) whose attachment is the HISTORICAL RECORD
    OF HIV/AIDS opening on p.3. The old code glued all of it into one
    synthetic "prologue" entry that counted as a diary entry and had no date.
    Now: the cover email, its attachment (linked both ways), and - from p.1 -
    the publisher's analysis as its own "note" box.
    """
    joined = "\n".join(ln.rstrip() for ln in lines)
    marker = re.search(r"^\s*HISTORICAL RECORD OF.*$", joined, re.MULTILINE)
    head = (joined[:marker.start()] if marker else joined).strip()
    tail = (joined[marker.end():] if marker else "").strip()

    entries = _analysis_entry()

    email = _cover_email(head) if head else None
    if email:
        entries.append(email)

    if tail:
        title = "HISTORICAL RECORD OF HIV/AIDS"
        m = re.match(r"^(HISTORICAL RECORD OF[^\n]*)", tail.strip())
        if m:
            title = m.group(1).strip()
        # The record is not a self-contained document: after its heading the
        # text continues under the ordinary date headers, i.e. as the dated
        # entries of this release (26 Jan 2001 - 11 Jul 2015, PDF pp. 3-42).
        # So this box is the attachment MANIFEST - it names the document, says
        # where its text lives, and deliberately does not repeat that text
        # (which would show up twice in every search).
        body = (
            title + "\n\n"
            + "Attachment to the cover email of 11 July 2015 "
            + "(historical_record_of_A.S._Fauci.docx).\n\n"
            + "Its text is the body of this release and is not repeated here: it "
            + "follows as the dated entries below, from 26 January 2001 to "
            + "11 July 2015 (PDF pp. 3-42). Those entries are the searchable text "
            + "of the attachment."
        )
        entry = {
            "date": email["date"] if email else "2015-07-11",
            "kind": "attachment",
            "doc_type": "document",
            "title": title,
            "raw_date": title,
            "date_note": "Attachment manifest - the document's text is the dated entries that follow",
            "content": body,
        }
        if email:                      # primary parent: the cover email
            entry["attached_to"] = email["date"] + "|" + email["raw_date"]
            entry["attached_to_label"] = email["date"] + " " + email["raw_date"]
        entries.append(entry)
    return entries


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
                # First date header — the front matter ends here. It is three
                # different things, not one "prologue" (see front_matter()).
                entries.extend(front_matter(prologue_lines))

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

