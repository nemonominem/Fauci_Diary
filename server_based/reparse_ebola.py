#!/usr/bin/env python3
"""
Re-parser for the Ebola extract (2026.09.28_Ebola-Doc-Release_Full-Package.pdf).

Same "Month Day, Year \u2013" date-header convention as the other parsers for the
diary part (Mar 3-10, 2016). The trailing material is split into individual
documents instead of one blob:

  * Every email message \u2014 outer headers AND nested quoted replies \u2014 becomes
    its own dated entry (kind="email"). Datetimes are resolved from the two
    header styles present in the release:
        Date: Thu, 10 Mar 2016 06:13:36 -0500          (RFC2822)
        Sent: Wednesday, March 09, 2016 11:41 PM        (Outlook)
    Entry keys are "<iso>|<HH:MM> \u00b7 <subject>", so same-day emails are
    distinct and chronological.
  * The NIAID filovirus aerosol-challenge overview becomes one
    kind="attachment" entry (a document, non-dated, shown under the email it
    was attached to).

pypdf occasionally wraps a header keyword itself ("Fro"+"m: ...",
"Sub"+"ject: ..."); those splits are rejoined for header parsing (the raw
lines stay untouched in the entry content).

Time zones: RFC2822 'Date:' headers carry an explicit offset (authoritative).
Outlook 'Sent:' headers and inline-quote markers carry NO zone, so a zone is
assumed (see ZONE_ASSUMPTIONS). Every timestamp is normalised to New York
time - that is what orders the entries - while the local (as-written) time is
kept alongside it in both the entry label and the printed header block.
"""
import calendar
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None
HERE = os.path.dirname(os.path.abspath(__file__))
TEXT_PATH = os.path.join(HERE, "2026.09.28_Ebola-Doc-Release_Full-Package.txt")
OUT_PATH = os.path.join(HERE, "2026.09.28_Ebola-Doc-Release_Full-Package_fixed.json")
MONTH_MAP = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12}
_month_alts = sorted(MONTH_MAP.keys(), key=len, reverse=True)
MONTH_RE = "(" + "|".join(_month_alts) + ")"
ENDASH = chr(0x2013)
EMDASH = chr(0x2014)
DATE_HEADER_RE = re.compile(r"^\s*" + MONTH_RE + r"\.?\s+(\d{1,2})(?:\s*[-" + ENDASH + r"](\d{1,2}))?\s*[,.]?\s*(\d{4})\s*[-" + ENDASH + EMDASH + r":]?", re.IGNORECASE)
STRIP_PATTERNS = [re.compile(r"^---\s*Page\s+\d+\s*---\s*$"), re.compile(r"^Released by Chairman Rand Paul\s*$"), re.compile(r"^EXCERPT FROM FAUCI'S NOTES\s*$", re.IGNORECASE), re.compile(r"^\d{1,4}\s*$")]
ARTICLE_TIME_HINTS = [re.compile(r"\d{1,2}:\d{2}\s*[ap]\.?m\.?", re.I), re.compile(r"\bAEDT\b")]
HEADER_FIELD_RE = re.compile(r"^(From|To|Cc|Bcc|Subject|Sent|Date|Importance|Attachments)\s*:", re.IGNORECASE)
RFC_DATE_RE = re.compile(r"^Date:\s*\w{3},\s*(\d{1,2})\s+(\w{3})\.?\s+(\d{4})\s+(\d{1,2}):(\d{2})", re.IGNORECASE)
SENT_RE = re.compile(r"^Sent:\s*\w+,\s*(\w+)\.?\s+(\d{1,2}),\s*(\d{4})\s+(\d{1,2}):(\d{2})\s*([AP])\.?M\.?", re.IGNORECASE)
REPORT_RE = re.compile(r"^Overview of the NIAID Filovirus", re.IGNORECASE)
SUBJECT_RE = re.compile(r"^Subject:\s*(.*)$", re.IGNORECASE)

def is_strip_line(line):
    return any(p.match(line) for p in STRIP_PATTERNS)

def strip_furniture(raw_lines):
    """Drop page furniture AND the blank lines that belong to it.

    The OCR text puts the page furniture ("Released by Chairman Rand Paul" /
    "EXCERPT FROM FAUCI'S NOTES" / "--- Page N ---" / the page number) in the
    MIDDLE of a sentence, with blank lines around it:

        ...because we are planning to do
        Released by Chairman Rand Paul
        EXCERPT FROM FAUCI'S NOTES
                                   <- blank
        --- Page 3 ---
        500
        vaccine studies there and use the VSV...

    Stripping only the furniture lines leaves that blank line behind, and a
    blank line is a PARAGRAPH break - so "to do" and "vaccine studies" became
    two paragraphs and the sentence was cut in half mid-clause. Any blank
    line touching a furniture line is furniture too, so remove it as well.
    """
    drop = {i for i, ln in enumerate(raw_lines) if is_strip_line(ln.strip())}
    # iterate a snapshot: this loop grows `drop` with the blank lines it finds
    for i in list(drop):
        for j in (i - 1, i + 1):
            if 0 <= j < len(raw_lines) and not raw_lines[j].strip():
                drop.add(j)
    return [ln for i, ln in enumerate(raw_lines) if i not in drop]
def looks_like_article_date(text):
    return any(p.search(text) for p in ARTICLE_TIME_HINTS)
def parse_month(mt):
    return MONTH_MAP[mt.lower().rstrip(".")]
def safe_date(y, m, d):
    d = min(d, calendar.monthrange(y, m)[1])
    return date(y, m, d).isoformat()
def format_raw_date(mt, day, endd, year):
    base = mt.rstrip(".")
    raw = (base + ". " if (len(base) <= 4 and base.lower() != "may") else base + " ") + str(day)
    if endd:
        raw += "-" + endd
    return raw + ", " + str(year)

INLINE_MARK_START_RE = re.compile(r"^>?\s*On\s+\w{3}\.?\s+\d{1,2},\s*\d{4},?\s+at\s+\d{1,2}:\d{2}\s*[AP]\.?M\.?", re.IGNORECASE)
INLINE_MARK_FULL_RE = re.compile(r"^>?\s*On\s+(\w{3})\.?\s+(\d{1,2}),\s*(\d{4}),?\s+at\s+(\d{1,2}):(\d{2})\s*([AP])\.?M\.?,?\s+(.+?)\s+wrote:?\s*$", re.IGNORECASE)

def _join_header_breaks(lines):
    """Rejoin pypdf splits of the header keyword itself ('Fro'+'m: ...',
    'Sub'+'ject: ...') for PARSING only; content keeps raw lines."""
    out = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if s in ("Fro", "Fro ") and i + 1 < len(lines) and lines[i + 1].strip().startswith("m:"):
            out.append("From:" + lines[i + 1].strip()[2:])
            i += 2
            continue
        if s == "Sub" and i + 1 < len(lines) and lines[i + 1].strip().startswith("ject:"):
            out.append("Subject:" + lines[i + 1].strip()[5:])
            i += 2
            continue
        out.append(lines[i])
        i += 1
    return out

CONT_FIELDS = {"from", "to", "cc", "bcc"}
RFC_OFFSET_RE = re.compile(r"([+-])(\d{2})(\d{2})\s*$")

def _cont_value(lines, start, field_re):
    """Value of a header field, joining wrapped continuation lines (long
    address lists that pypdf wraps over several lines)."""
    m = field_re.match(lines[start].strip())
    if not m:
        return "", start
    val = lines[start].strip()[m.end():].strip()
    j = start + 1
    while j < len(lines):
        s = lines[j].strip()
        if not s or HEADER_FIELD_RE.match(s) or is_strip_line(s):
            break
        val += " " + s
        j += 1
    return re.sub(r"\s+", " ", val).strip(), j - 1

def _clean_addr(v):
    """Drop X.500/Exchange DN noise ('</O=NIH/OU=...>') from a From/To value."""
    if "<" in v and "O=" in v:
        v = v[:v.index("<")].strip()
    return v.strip().strip(",")

def scan_header(lines, i):
    """Parse a From:-led header block. Returns dict with printable fields,
    index of the last header line (body follows), the local stamp (naive),
    and the zone used for it (explicit for RFC 'Date:', assumed otherwise)."""
    if not lines[i].strip().lower().startswith("from:"):
        return None
    fields = []
    subject = None
    printed = None
    local_dt = None
    offset_tz = None
    style = None
    last = i
    j = i
    limit = min(i + 14, len(lines))
    while j < limit:
        s = lines[j].strip()
        if j > i and (s.lower().startswith("from:") or is_strip_line(s)):
            break
        m = HEADER_FIELD_RE.match(s)
        if not m:
            break  # body starts here: header block over
        name = m.group(1)
        key = name.lower()
        if key in CONT_FIELDS:
            val, endj = _cont_value(lines, j, HEADER_FIELD_RE)
        else:
            val, endj = s[m.end():].strip(), j
        if key == "subject":
            subject = val
        elif key in ("date", "sent"):
            printed = val
            md = RFC_DATE_RE.match(s)
            if md:
                day, mon, year, hh, mm = int(md.group(1)), md.group(2), int(md.group(3)), int(md.group(4)), md.group(5)
                try:
                    local_dt = datetime(year, parse_month(mon), day, hh, int(mm))
                except (KeyError, ValueError):
                    local_dt = None
                mo = RFC_OFFSET_RE.search(s)
                if mo and local_dt:
                    sign = 1 if mo.group(1) == "+" else -1
                    off = sign * (int(mo.group(2)) * 60 + int(mo.group(3)))
                    offset_tz = timezone(timedelta(minutes=off))
                    style = "outer"
            else:
                ms = SENT_RE.match(s)
                if ms:
                    mon, day, year, hh, mm, ap = ms.group(1), int(ms.group(2)), int(ms.group(3)), int(ms.group(4)), ms.group(5), ms.group(6).upper()
                    hh = int(hh) % 12 + (12 if ap == "P" else 0)
                    try:
                        local_dt = datetime(year, parse_month(mon), day, hh, int(mm))
                    except (KeyError, ValueError):
                        local_dt = None
                    style = "nested" if style is None else style
        if key in CONT_FIELDS or key == "subject":
            fields.append(("Cc" if key == "cc" else name,
                           _clean_addr(val) if key in CONT_FIELDS else val))
        last = endj
        j = endj + 1
    if local_dt is None:
        return None
    if offset_tz is not None:
        tz_name = "America/New_York" if offset_tz.utcoffset(None) in (timedelta(hours=-5), timedelta(hours=-4)) else "UTC%+d" % (offset_tz.utcoffset(None).total_seconds() // 3600)
        tz_inferred = False
        local_dt = local_dt.replace(tzinfo=offset_tz)
    else:
        key_sub = subject or "(no subject)"
        tz_name = ZONE_ASSUMPTIONS.get((local_dt.date().isoformat(), "%02d%02d" % (local_dt.hour, local_dt.minute), key_sub), NEW_YORK)
        tz_inferred = True
        local_dt = local_dt.replace(tzinfo=_zone(tz_name))
    return {"fields": fields, "header_end": last, "local_dt": local_dt,
            "tz_name": tz_name, "tz_inferred": tz_inferred, "printed": printed or "",
            "subject": subject or "(no subject)", "style": style}


def parse_inline_marker(lines, i):
    """Detect 'On Mar 10, 2016, at 1:29 AM, <author> wrote:' quote markers,
    optionally '>'-prefixed and wrapped over up to 3 lines. Such markers carry
    no zone, so New York is assumed (flagged as such)."""
    s0 = lines[i].strip()
    if not INLINE_MARK_START_RE.match(s0):
        return None
    joined = s0
    span = 1
    while "wrote" not in joined.lower() and span < 3 and i + span < len(lines):
        joined += " " + lines[i + span].strip()
        span += 1
    m = INLINE_MARK_FULL_RE.match(joined)
    if not m:
        return None
    mon, day, year, hh, mm, ap, author = m.groups()
    hh = int(hh) % 12 + (12 if ap.upper() == "P" else 0)
    try:
        local_dt = datetime(int(year), parse_month(mon), int(day), hh, int(mm))
    except (KeyError, ValueError):
        return None
    tz_name = ZONE_ASSUMPTIONS.get((local_dt.date().isoformat(), "%02d%02d" % (hh, int(mm)), None), NEW_YORK)
    return {"local_dt": local_dt.replace(tzinfo=_zone(tz_name)), "tz_name": tz_name,
            "author": re.sub(r"\s*\(.*$", "", author).strip(),
            "span": span, "gt_quoted": s0.startswith(">")}

def _body_lines(lines, start):
    out = list(lines[start:])
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out

NEW_YORK = "America/New_York"

def _zone(name):
    if ZoneInfo is not None:
        return ZoneInfo(name)
    return timezone(timedelta(hours={"America/New_York": -5,
                                     "America/Los_Angeles": -8,
                                     "Europe/Paris": 1}[name]), name)

TZ_ABBR = {"America/New_York": "ET", "America/Los_Angeles": "PT", "Europe/Paris": "CET"}
MONTH_ABBR = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
              7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

# 'Sent:'/'On ... wrote:' stamps carry no zone. Default is New York; overrides
# below are inferred from the document itself and are flagged in the output:
#   * Nelson's subject is literally "Hello from France" -> he wrote from France.
#   * Lane's Mar 9 23:41 message QUOTES Fauci's Mar 10 01:29 message; Fauci is
#     provably in Washington then (diary: NIH Clinical Center acupuncture and
#     the 260-reporter telebriefing on Mar 10), so Fauci's stamps are ET. For
#     Lane's reply to postdate it, Lane's clock must be west of ET - matching
#     his own next line "Just landed in San Francisco" (Pacific time).
ZONE_ASSUMPTIONS = {
    ("2016-03-09", "1911", "Hello from France"): "Europe/Paris",
    ("2016-03-09", "2341", "Re: Hello from France"): "America/Los_Angeles",
}

def _mon_day(dt):
    return "%s %d" % (MONTH_ABBR[dt.month], dt.day)

def _hhmm(dt):
    return "%02d:%02d" % (dt.hour, dt.minute)

def _time_label(local_dt, tz_name, ny_dt):
    """Local (as-written) time first, then the NY-normalised time - the latter
    omitted when the message was already stamped in New York time."""
    lab = _hhmm(local_dt) + " " + TZ_ABBR.get(tz_name, tz_name)
    if tz_name == NEW_YORK:
        return lab
    if local_dt.day != ny_dt.day or local_dt.month != ny_dt.month:
        lab += " " + _mon_day(local_dt)
    return lab + " \u2192 " + _hhmm(ny_dt) + " " + TZ_ABBR[NEW_YORK]

def email_raw_date(local_dt, tz_name, ny_dt, subject):
    return _time_label(local_dt, tz_name, ny_dt) + " \u00b7 " + subject

def inline_raw_date(local_dt, tz_name, ny_dt, author):
    short = author.split(",")[0].strip()
    return _time_label(local_dt, tz_name, ny_dt) + " \u00b7 " + short + " (inline quote)"

SEPARATOR = "----------"

def _sent_line(printed, tz_name, ny_dt, inferred):
    """One line carrying BOTH the local (as-written) stamp and the
    New-York-normalised time; the latter is spelled out only when the message
    was not stamped in Eastern time."""
    ab = TZ_ABBR.get(tz_name, tz_name)
    if tz_name == NEW_YORK:
        return "Sent: " + printed + " (" + ab + (", assumed" if inferred else "") + ")"
    tail = " → " + _hhmm(ny_dt) + " " + TZ_ABBR[NEW_YORK]
    if ny_dt.day != ny_dt.day or True:
        tail += " (" + _mon_day(ny_dt) + ")"
    return ("Sent: " + printed + " " + ab + (" (assumed)" if inferred else "")
            + tail)

def _field_lines(fields):
    """Printable header block: one field per line, a blank line between fields
    so the line-break cleaner keeps each field as its own paragraph."""
    out = []
    for name, val in fields:
        if val:
            out.append(name + ": " + val)
            out.append("")
    return out

def segment_tail(tail_lines):
    """Split tail lines into per-message email entries + the report. Every
    email header (outer 'Date:' AND nested 'Sent:') and every inline
    'On ... wrote:' quote marker starts a new block, so each entry holds only
    the text its author wrote. Entry content = printable header block
    (From/To/Cc/Subject + Sent line), a '----------' separator, then the body.
    Times are normalised to New York time (entry date/time use it)."""
    lines = _join_header_breaks(tail_lines)
    bounds = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if REPORT_RE.match(s):
            bounds.append((i, {"kind": "report"}))
            i += 1
            continue
        hdr = scan_header(lines, i)
        if hdr:
            hdr["kind"] = "email"
            bounds.append((i, hdr))
            i += 1
            continue
        iq = parse_inline_marker(lines, i)
        if iq:
            iq["kind"] = "inline"
            bounds.append((i, iq))
            i += iq["span"]
            continue
        i += 1
    entries = []
    ny_zone = _zone(NEW_YORK)
    for k, (b, meta) in enumerate(bounds):
        end = bounds[k + 1][0] if k + 1 < len(bounds) else len(lines)
        if meta["kind"] == "report":
            body = _body_lines(lines[b:end], 0)
            text_lines = [ln.strip() for ln in body if ln.strip()]
            # Title = the document's own heading (first non-empty line)
            title = text_lines[0][:160] if text_lines else "Attached document"
            entries.append({"date": "report", "kind": "attachment",
                            "doc_type": "report", "title": title,
                            "raw_date": "Report",
                            "content": "\n".join(body).strip()})
            continue
        ny_dt = meta["local_dt"].astimezone(ny_zone)
        if meta["kind"] == "inline":
            body = _body_lines(lines[b + meta["span"]:end], 0)
            if meta.get("gt_quoted"):
                body = [re.sub(r"^>\s?", "", ln) for ln in body if ln.strip() not in (">", "")]
            if not body:
                continue
            head = ["From: " + meta["author"] + " (from an inline quote)", "",
                    _sent_line(meta["local_dt"].strftime("%b %d, %Y %I:%M %p"), meta["tz_name"], ny_dt, True), "",
                    SEPARATOR, ""]
            entries.append({"date": ny_dt.date().isoformat(), "time": _hhmm(ny_dt).replace(":", ""),
                            "kind": "email",
                            "raw_date": inline_raw_date(meta["local_dt"], meta["tz_name"], ny_dt, meta["author"]),
                            "date_note": "Recovered from an inline quote (no full header in the release)",
                            "content": "\n".join(head + [ln for ln in body]).strip()})
            continue
        body = _body_lines(lines[meta["header_end"] + 1:end], 0)
        head = _field_lines(meta["fields"])
        head.append(_sent_line(meta["printed"], meta["tz_name"], ny_dt, meta["tz_inferred"]))
        head += ["", SEPARATOR, ""]
        entries.append({"date": ny_dt.date().isoformat(), "time": _hhmm(ny_dt).replace(":", ""),
                        "kind": "email",
                        "raw_date": email_raw_date(meta["local_dt"], meta["tz_name"], ny_dt, meta["subject"]),
                        "content": "\n".join(head + body).strip(),
                        "_style": meta["style"]})
    return entries

def entry_key(e):
    return e["date"] + "|" + e["raw_date"]

FORWARD_SUBJ_RE = re.compile(r"^(?:fw|fwd)\.?\s*:", re.IGNORECASE)

# ── Attachments ──────────────────────────────────────────────────────────────
# A document that physically follows an email in the release (a report, a memo,
# a spreadsheet...) becomes its own entry with kind="attachment" and a `title`
# (its own heading). WHO it was attached to is NOT decided here: the text still
# has PDF line-wraps at this point, and an announcement in one release may refer
# to a document shipped in another. The app infers the link on cleaned text
# across every merged source (inferAttachments in index.html) and writes
# `attachments` / `attached_to` / `attached_by` there. A parser only has to
# mark document entries with kind="attachment" + title (and may set attached_to
# when the release states the parent outright).


def _ref_subject(entry):
    raw = entry.get("raw_date", "")
    return raw.split(" \u00b7 ", 1)[1] if " \u00b7 " in raw else ""

def link_thread(entries):
    """Wire the thread pointers, both directions.

    A thread starts at an outer (RFC 'Date:') email; the following nested /
    inline messages are its quoted history in document order (newest first),
    so message i refers upward to message i+1:

      * subject starts with FW:/Fwd: -> this message FORWARDED that one
        (up-link stored as forwarded_from)
      * otherwise                    -> it REPLIED to it (reply_to)

    Downward, every reference is inverted into ARRAYS - the same email may be
    replied to and/or forwarded again later, possibly several times, and a
    later release may quote it too (the app re-inverts across all sources):

      replied_by / forwarded_by / attached_by
        = [{key, label}, ...]  (may hold several entries)

    Attachment links are NOT set here: the app resolves them on cleaned text
    across every merged source (see the Attachments note above).
    """
    by_key = {}
    for e in entries:
        k = entry_key(e)
        if k in by_key:  # safety: disambiguate identical keys
            e["raw_date"] += " (2)"
            k = entry_key(e)
        by_key[k] = e
    thread = []
    def flush():
        for a, b in zip(thread, thread[1:]):
            key = entry_key(b)
            label = b["date"] + " " + b["raw_date"]
            if FORWARD_SUBJ_RE.match(_ref_subject(a)):
                a["forwarded_from"] = key
                a["forwarded_from_label"] = label
            else:
                a["reply_to"] = key
                a["reply_to_label"] = label
    for e in entries:
        if e.get("kind") == "attachment":
            flush(); thread = []
            continue
        if e.get("_style") == "outer":
            flush(); thread = [e]
        else:
            thread.append(e)
    flush()
    for e in entries:
        e.pop("_order", None); e.pop("_style", None)
    return entries

def parse_text():
    with open(TEXT_PATH, encoding="utf-8") as f:
        raw_lines = [ln.rstrip("\n") for ln in f.readlines()]
    lines = strip_furniture(raw_lines)
    diary, cur_iso, cur_raw, cur_lines, pre = [], None, None, [], []
    tail = []
    in_tail = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if in_tail:
            tail.append(line)
            continue
        m = DATE_HEADER_RE.match(stripped)
        if m and not looks_like_article_date(stripped):
            mt, day, endd, year = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            try:
                mo = parse_month(mt)
            except KeyError:
                mo = None
            if mo is not None:
                if cur_iso is not None:
                    diary.append({"date": cur_iso, "raw_date": cur_raw, "kind": "diary",
                                  "content": "\n".join(cur_lines).strip()})
                cur_raw = format_raw_date(mt, day, endd, year)
                cur_iso = safe_date(year, mo, day)
                cur_lines = []
                if pre and not diary:
                    cur_lines.extend(pre); pre = []
                rest = stripped[m.end():]
                if rest.strip():
                    cur_lines.append(rest)
                continue
        if cur_iso is not None and (REPORT_RE.match(stripped) or scan_header(lines, idx)):
            # First email/report header: the diary part ends here.
            diary.append({"date": cur_iso, "raw_date": cur_raw, "kind": "diary",
                          "content": "\n".join(cur_lines).strip()})
            cur_iso = None
            in_tail = True
            tail.append(line)
            continue
        if cur_iso is not None:
            cur_lines.append(line)
        else:
            pre.append(line)
    if cur_iso is not None:
        diary.append({"date": cur_iso, "raw_date": cur_raw, "kind": "diary",
                      "content": "\n".join(cur_lines).strip()})
    emails = segment_tail([ln for ln in tail if ln.strip()])
    return diary, emails

def main():
    diary, emails = parse_text()
    diary = [e for e in diary if e["content"].strip()]
    diary.sort(key=lambda e: e["date"])
    link_thread(emails)  # document order in, chain pointers set
    mail = sorted([e for e in emails if e["kind"] == "email"],
                  key=lambda e: (e["date"], e["time"]))  # stable: doc order breaks ties
    report = [e for e in emails if e.get("kind") == "attachment"]
    real = diary + mail + report
    dated = [e["date"] for e in diary + mail]
    out = {"source_file": "2026.09.28_Ebola-Doc-Release_Full-Package.pdf",
           "title": "Fauci Diary Ebola Extract -- Diary, Emails & Filovirus Report, March 2016",
           "released_by": "Chairman Rand Paul",
           "total_entries": len(real),
           "date_range": {"start": min(dated), "end": max(dated)} if dated else {},
           "entries": real}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("entries: %d (diary %d, emails %d, attachments %d)" % (len(real), len(diary), len(mail), len(report)))
    print("date range:", out["date_range"])
    for e in real:
        up = ""
        if e.get("reply_to_label"):
            up = "  <-reply- " + e["reply_to_label"]
        if e.get("forwarded_from_label"):
            up = "  <-fwd- " + e["forwarded_from_label"]
        atts = e.get("attachments") or []
        if atts:
            up += "  [att x%d:%s]" % (len(atts), ",".join(
                "linked" if a.get("resolved") else "tag" for a in atts))
        down = ""
        if e.get("replied_by"):
            down += "  ->replied-by x%d" % len(e["replied_by"])
        if e.get("forwarded_by"):
            down += "  ->fwd-by x%d" % len(e["forwarded_by"])
        if e.get("attached_by"):
            down += "  ->refs x%d" % len(e["attached_by"])
        print("  %-10s %-5s %-44s %5d%s%s" % (e["date"], e.get("time", ""),
              e["raw_date"][:44], len(e["content"]), up, down))
if __name__ == "__main__":
    main()
