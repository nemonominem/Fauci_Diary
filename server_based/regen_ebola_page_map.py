#!/usr/bin/env python3
"""
Regenerate page_map for the Ebola extract (2026.09.28_Ebola-Doc-Release_Full-Package).

Mirrors reparse_ebola.py segmentation exactly (diary date-headers, per-message
email blocks incl. inline-quote recovery, filovirus report), but tracks the PDF
page of every line so each entry gets content-start page + per-page breaks.
Entry keys ("date|raw_date") are verified against the parsed JSON.
"""
import json
import re
import os
import calendar
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT_PATH = os.path.join(HERE, "2026.09.28_Ebola-Doc-Release_Full-Package.txt")
JSON_PATH = os.path.join(HERE, "2026.09.28_Ebola-Doc-Release_Full-Package.json")
OUT_PATH = os.path.join(HERE, "ebola_page_map.json")

MONTH_MAP = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12}
_month_alts = sorted(MONTH_MAP.keys(), key=len, reverse=True)
MONTH_RE = "(" + "|".join(_month_alts) + ")"
ENDASH = chr(0x2013)
EMDASH = chr(0x2014)
DATE_HEADER_RE = re.compile(r"^\s*" + MONTH_RE + r"\.?\s+(\d{1,2})(?:\s*[-" + ENDASH + r"](\d{1,2}))?\s*[,.]?\s*(\d{4})\s*[-" + ENDASH + EMDASH + r":]?", re.IGNORECASE)
STRIP_PATTERNS = [re.compile(r"^---\s*Page\s+\d+\s*---\s*$"), re.compile(r"^Released by Chairman Rand Paul\s*$"), re.compile(r"^EXCERPT FROM FAUCI'S NOTES\s*$", re.IGNORECASE), re.compile(r"^\d{1,4}\s*$")]
ARTICLE_TIME_HINTS = [re.compile(r"\d{1,2}:\d{2}\s*[ap]\.?m\.?", re.I), re.compile(r"\bAEDT\b")]
PAGE_MARKER_RE = re.compile(r"^---\s*Page\s+(\d+)\s*---\s*$")
HEADER_FIELD_RE = re.compile(r"^(From|To|Cc|Bcc|Subject|Sent|Date|Importance|Attachments)\s*:", re.IGNORECASE)
RFC_DATE_RE = re.compile(r"^Date:\s*\w{3},\s*(\d{1,2})\s+(\w{3})\.?\s+(\d{4})\s+(\d{1,2}):(\d{2})", re.IGNORECASE)
SENT_RE = re.compile(r"^Sent:\s*\w+,\s*(\w+)\.?\s+(\d{1,2}),\s*(\d{4})\s+(\d{1,2}):(\d{2})\s*([AP])\.?M\.?", re.IGNORECASE)
REPORT_RE = re.compile(r"^Overview of the NIAID Filovirus", re.IGNORECASE)
SUBJECT_RE = re.compile(r"^Subject:\s*(.*)$", re.IGNORECASE)
INLINE_MARK_START_RE = re.compile(r"^>?\s*On\s+\w{3}\.?\s+\d{1,2},\s*\d{4},?\s+at\s+\d{1,2}:\d{2}\s*[AP]\.?M\.?", re.IGNORECASE)
INLINE_MARK_FULL_RE = re.compile(r"^>?\s*On\s+(\w{3})\.?\s+(\d{1,2}),\s*(\d{4}),?\s+at\s+(\d{1,2}):(\d{2})\s*([AP])\.?M\.?,?\s+(.+?)\s+wrote:?\s*$", re.IGNORECASE)

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
def email_raw_date(hhmm, subject):
    return hhmm[:2] + ":" + hhmm[2:] + " \u00b7 " + subject
def inline_raw_date(hhmm, author):
    short = author.split(",")[0].strip()
    return hhmm[:2] + ":" + hhmm[2:] + " \u00b7 " + short + " (inline quote)"

def _join_header_breaks_pairs(pairs):
    """Same header-keyword rejoin as reparse_ebola, keeping first page."""
    out = []
    i = 0
    while i < len(pairs):
        t, p = pairs[i]
        s = t.strip()
        if s in ("Fro", "Fro ") and i + 1 < len(pairs) and pairs[i + 1][0].strip().startswith("m:"):
            out.append(("From:" + pairs[i + 1][0].strip()[2:], p)); i += 2; continue
        if s == "Sub" and i + 1 < len(pairs) and pairs[i + 1][0].strip().startswith("ject:"):
            out.append(("Subject:" + pairs[i + 1][0].strip()[5:], p)); i += 2; continue
        out.append((t, p)); i += 1
    return out

def parse_email_header(texts, i):
    """Identical logic to reparse_ebola.parse_email_header."""
    if not texts[i].strip().lower().startswith("from:"):
        return None
    subject = None
    date_iso = hhmm = style = None
    for j in range(i, min(i + 12, len(texts))):
        s = texts[j].strip()
        if j > i:
            sl = s.lower()
            if sl.startswith("from:") or sl.startswith("importance:") or is_strip_line(s):
                break
        if subject is None and SUBJECT_RE.match(s):
            subject = SUBJECT_RE.match(s).group(1).strip()
        if subject is not None and date_iso is not None:
            break
        md = RFC_DATE_RE.match(s)
        if md and date_iso is None:
            day, mon, year, hh, mm = int(md.group(1)), md.group(2), int(md.group(3)), int(md.group(4)), md.group(5)
            try:
                date_iso = safe_date(year, parse_month(mon), day)
                hhmm = "%02d%02d" % (hh, int(mm)); style = "outer"
            except KeyError:
                return None
            continue
        ms = SENT_RE.match(s)
        if ms and date_iso is None:
            mon, day, year, hh, mm, ap = ms.group(1), int(ms.group(2)), int(ms.group(3)), int(ms.group(4)), ms.group(5), ms.group(6).upper()
            hh = int(hh) % 12 + (12 if ap == "P" else 0)
            try:
                date_iso = safe_date(year, parse_month(mon), day)
                hhmm = "%02d%02d" % (hh, int(mm)); style = "nested"
            except KeyError:
                return None
            continue
    if date_iso is None:
        return None
    return {"date": date_iso, "hhmm": hhmm, "subject": subject or "(no subject)", "style": style}

def parse_inline_marker(texts, i):
    s0 = texts[i].strip()
    if not INLINE_MARK_START_RE.match(s0):
        return None
    joined = s0
    span = 1
    while "wrote" not in joined.lower() and span < 3 and i + span < len(texts):
        joined += " " + texts[i + span].strip()
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
    author = re.sub(r"\s*\(.*$", "", author).strip()
    return {"date": iso, "hhmm": "%02d%02d" % (hh, int(mm)), "author": author,
            "span": span, "gt_quoted": s0.startswith(">")}

def clean_with_pages(line_pages):
    """Mirror clean_ebola_breaks.clean_content while tracking PDF page."""
    paragraphs = []
    current = []
    def flush():
        nonlocal current
        if current:
            paragraphs.append(current); current = []
    for line, page in line_pages:
        s = line.strip()
        if not s:
            flush(); continue
        if s.upper().startswith("PRESS:"):
            flush(); current.append((s, page)); continue
        if s.endswith(":") and len(s) < 80:
            flush(); current.append((s, page)); continue
        current.append((s, page))
    flush()
    cleaned_parts, char_pages = [], []
    for pi, para in enumerate(paragraphs):
        if pi:
            cleaned_parts.append("\n\n")
            char_pages.extend([para[0][1], para[0][1]])
        first = True
        for text, page in para:
            if not first:
                cleaned_parts.append(" "); char_pages.append(page)
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
            breaks.append([i, p]); prev = p
    start = breaks[0][1] if breaks else 1
    end = breaks[-1][1] if breaks else start
    return cleaned, breaks, start, end

def build_page_map():
    with open(TEXT_PATH, encoding="utf-8") as f:
        raw = [ln.rstrip("\n") for ln in f.readlines()]
    # page attribution on raw lines (markers included), then drop strip lines
    pairs = []
    page = 1
    for ln in raw:
        m = PAGE_MARKER_RE.match(ln.strip())
        if m:
            page = int(m.group(1)); continue
        if is_strip_line(ln.strip()):
            continue
        pairs.append((ln, page))

    texts = [t for t, _ in pairs]
    page_map = {}

    # ── Diary entries (date headers) until the first email/report ──
    cur_key, cur_pairs, pre = None, [], []
    tail_start = None
    for i, (t, p) in enumerate(pairs):
        s = t.strip()
        m = DATE_HEADER_RE.match(s)
        if m and not looks_like_article_date(s):
            mt, day, endd, year = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            try:
                mo = parse_month(mt)
            except KeyError:
                mo = None
            if mo is not None:
                if cur_key is not None:
                    page_map[cur_key] = cur_pairs
                iso = safe_date(year, mo, day)
                cur_key = iso + "|" + format_raw_date(mt, day, endd, year)
                cur_pairs = []
                if pre and not page_map:
                    cur_pairs.extend(pre); pre = []
                rest = s[m.end():]
                if rest.strip():
                    cur_pairs.append((rest, p))
                continue
        if cur_key is not None and (REPORT_RE.match(s) or parse_email_header(texts, i)):
            page_map[cur_key] = cur_pairs
            cur_key = None
            tail_start = i
            break
        if cur_key is not None:
            cur_pairs.append((t, p))
        else:
            pre.append((t, p))
    if cur_key is not None:
        page_map[cur_key] = cur_pairs

    # ── Tail: per-message email blocks + report (mirrors segment_tail) ──
    tail_pairs = [(t, p) for t, p in pairs[tail_start:] if t.strip()]
    tail_pairs = _join_header_breaks_pairs(tail_pairs)
    ttexts = [t for t, _ in tail_pairs]
    bounds = []
    i = 0
    while i < len(tail_pairs):
        s = ttexts[i].strip()
        if REPORT_RE.match(s):
            bounds.append((i, {"kind": "report"})); i += 1; continue
        hdr = parse_email_header(ttexts, i)
        if hdr:
            hdr["kind"] = "email"; bounds.append((i, hdr)); i += 1; continue
        iq = parse_inline_marker(ttexts, i)
        if iq:
            iq["kind"] = "inline"; bounds.append((i, iq)); i += iq["span"]; continue
        i += 1
    for k, (b, meta) in enumerate(bounds):
        start = b + (meta.get("span", 1) if meta["kind"] == "inline" else 0)
        end = bounds[k + 1][0] if k + 1 < len(bounds) else len(tail_pairs)
        bp = tail_pairs[start:end]
        if meta["kind"] == "inline" and meta.get("gt_quoted"):
            bp = [(re.sub(r"^>\s?", "", t), p) for t, p in bp if t.strip() not in (">", "")]
        if not bp:
            continue
        if meta["kind"] == "report":
            key = "report|Report"
        elif meta["kind"] == "inline":
            key = meta["date"] + "|" + inline_raw_date(meta["hhmm"], meta["author"])
        else:
            key = meta["date"] + "|" + email_raw_date(meta["hhmm"], meta["subject"])
        page_map[key] = bp

    # ── Clean + verify against the JSON entry keys ──
    out = {}
    for key, lp in page_map.items():
        cleaned, breaks, start, end = clean_with_pages(lp)
        out[key] = {"start": start, "end": end, "breaks": breaks}
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    json_keys = [e["date"] + "|" + e["raw_date"] for e in data["entries"]]
    missing = [k for k in json_keys if k not in out]
    extra = [k for k in out if k not in json_keys]
    if missing or extra:
        raise SystemExit("KEY MISMATCH vs JSON\n missing: %s\n extra: %s" % (missing, extra))
    return out

def main():
    page_map = build_page_map()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(page_map, f, ensure_ascii=False, indent=2)
    multi = sum(1 for v in page_map.values() if v.get("end", v.get("start")) > v.get("start", 0))
    print("Wrote %d entries to %s (%d multi-page)" % (len(page_map), OUT_PATH, multi))
    for k in sorted(page_map):
        v = page_map[k]
        print("  %-70s p.%d-%d breaks=%d" % (k[:70], v["start"], v["end"], len(v["breaks"])))

if __name__ == "__main__":
    main()
