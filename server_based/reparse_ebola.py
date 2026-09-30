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
  * The NIAID filovirus aerosol-challenge overview becomes one "report"
    entry (kind="report", non-dated, sorted last).

pypdf occasionally wraps a header keyword itself ("Fro"+"m: ...",
"Sub"+"ject: ..."); those splits are rejoined for header parsing (the raw
lines stay untouched in the entry content).
"""
import calendar
import json
import os
import re
from datetime import date
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

def _field_value(lines, start, name_re):
    m = name_re.match(lines[start].strip())
    if not m:
        return "", start
    val = m.group(1).strip()
    j = start + 1
    while j < len(lines):
        s = lines[j].strip()
        if not s or HEADER_FIELD_RE.match(s) or is_strip_line(s):
            break
        val += " " + s
        j += 1
    return re.sub(r"\s+", " ", val).strip(), j - 1

def parse_email_header(lines, i):
    """If lines[i] starts an email header block (From: + Sent:/RFC Date:),
    return dict(date, hhmm, subject, style) else None. Scans the whole block:
    nested (Outlook) headers put 'Sent:' BEFORE 'Subject:', so an early return
    on the datetime line would lose the subject."""
    if not lines[i].strip().lower().startswith("from:"):
        return None
    subject = None
    date_iso = hhmm = style = None
    for j in range(i, min(i + 12, len(lines))):
        s = lines[j].strip()
        if j > i:
            sl = s.lower()
            if sl.startswith("from:") or sl.startswith("importance:") or is_strip_line(s):
                break
        if subject is None and SUBJECT_RE.match(s):
            subject = SUBJECT_RE.match(s).group(1).strip()  # single line; subjects never wrap here
        if subject is not None and date_iso is not None:
            break
        md = RFC_DATE_RE.match(s)
        if md and date_iso is None:
            day, mon, year, hh, mm = int(md.group(1)), md.group(2), int(md.group(3)), int(md.group(4)), md.group(5)
            try:
                date_iso = safe_date(year, parse_month(mon), day)
                hhmm = "%02d%02d" % (hh, int(mm))
                style = "outer"
            except KeyError:
                return None
            continue
        ms = SENT_RE.match(s)
        if ms and date_iso is None:
            mon, day, year, hh, mm, ap = ms.group(1), int(ms.group(2)), int(ms.group(3)), int(ms.group(4)), ms.group(5), ms.group(6).upper()
            hh = int(hh) % 12 + (12 if ap == "P" else 0)
            try:
                date_iso = safe_date(year, parse_month(mon), day)
                hhmm = "%02d%02d" % (hh, int(mm))
                style = "nested"
            except KeyError:
                return None
            continue
    if date_iso is None:
        return None
    return {"date": date_iso, "hhmm": hhmm, "subject": subject or "(no subject)", "style": style}

def parse_inline_marker(lines, i):
    """Detect 'On Mar 10, 2016, at 1:29 AM, <author> wrote:' quote markers,
    optionally '>'-prefixed and wrapped over up to 3 lines.
    Returns dict(date, hhmm, author, span, gt_quoted) or None."""
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
        iso = safe_date(int(year), parse_month(mon), int(day))
    except KeyError:
        return None
    author = re.sub(r"\s*\(.*$", "", author).strip()  # drop (NIH/NIAID)... suffix
    return {"date": iso, "hhmm": "%02d%02d" % (hh, int(mm)), "author": author,
            "span": span, "gt_quoted": s0.startswith(">")}

def email_raw_date(hhmm, subject):
    return hhmm[:2] + ":" + hhmm[2:] + " \u00b7 " + subject

def inline_raw_date(hhmm, author):
    short = author.split(",")[0].strip()
    return hhmm[:2] + ":" + hhmm[2:] + " \u00b7 " + short + " (inline quote)"

def segment_tail(tail_lines):
    """Split tail lines into per-message email entries + the report.
    Every email header (outer 'Date:' AND nested 'Sent:') and every inline
    'On ... wrote:' quote marker starts a new block, so each entry holds only
    the text its author actually wrote."""
    lines = _join_header_breaks(tail_lines)
    blocks = []  # (start, end, meta, kind)
    bounds = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if REPORT_RE.match(s):
            bounds.append((i, {"kind": "report"}))
            i += 1
            continue
        hdr = parse_email_header(lines, i)
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
    for k, (b, meta) in enumerate(bounds):
        start = b + (meta.get("span", 1) if meta["kind"] == "inline" else 0)
        end = bounds[k + 1][0] if k + 1 < len(bounds) else len(lines)
        content_lines = lines[start:end]
        if meta["kind"] == "inline" and meta.get("gt_quoted"):
            content_lines = [re.sub(r"^>\s?", "", ln) for ln in content_lines
                             if ln.strip() not in (">", "")]
        content = "\n".join(content_lines).strip()
        if meta["kind"] == "report":
            entries.append({"date": "report", "kind": "report", "raw_date": "Report", "content": content})
        elif meta["kind"] == "inline":
            entries.append({"date": meta["date"], "time": meta["hhmm"], "kind": "email",
                            "raw_date": inline_raw_date(meta["hhmm"], meta["author"]),
                            "date_note": "Recovered from an inline quote (no full header in the release)",
                            "content": content, "_order": k})
        else:
            entries.append({"date": meta["date"], "time": meta["hhmm"], "kind": "email",
                            "raw_date": email_raw_date(meta["hhmm"], meta["subject"]),
                            "content": content, "_order": k, "_style": meta["style"]})
    return entries

def entry_key(e):
    return e["date"] + "|" + e["raw_date"]

def link_thread(entries):
    """Wire reply-chain pointers. A thread starts at an outer (RFC 'Date:')
    email; following nested/inline messages are its quoted history in
    document order. Each entry points at the next one down the chain."""
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
            a["reply_to"] = entry_key(b)
            a["reply_to_label"] = b["date"] + " " + b["raw_date"]
    for e in entries:
        if e["kind"] == "report":
            flush(); thread = []
            continue
        if e.get("_style") == "outer":
            flush(); thread = [e]
        else:
            thread.append(e)
    flush()
    # The Kurilla 'Ebola report you requested' email attached the report.
    for e in entries:
        if e["kind"] == "email" and e["raw_date"].endswith("Ebola report you requested") and e.get("_style") == "nested":
            e["attachment_ref"] = "report|Report"
            e["attachment_label"] = "NIAID Filovirus Aerosol-Challenge Report (pp. 21-24)"
    for e in entries:
        e.pop("_order", None); e.pop("_style", None)
    return entries

def parse_text():
    with open(TEXT_PATH, encoding="utf-8") as f:
        raw_lines = [ln.rstrip("\n") for ln in f.readlines()]
    lines = [ln for ln in raw_lines if not is_strip_line(ln.strip())]
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
        if cur_iso is not None and (REPORT_RE.match(stripped) or parse_email_header(lines, idx)):
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
    report = [e for e in emails if e["kind"] == "report"]
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
    print("entries: %d (diary %d, emails %d, report %d)" % (len(real), len(diary), len(mail), len(report)))
    print("date range:", out["date_range"])
    for e in real:
        link = " -> " + e["reply_to_label"] if e.get("reply_to_label") else ""
        att = " [att: report]" if e.get("attachment_ref") else ""
        print("  %-10s %-5s %-48s %5d chars%s%s" % (e["date"], e.get("time", ""),
              e["raw_date"][:48], len(e["content"]), link, att))
if __name__ == "__main__":
    main()
