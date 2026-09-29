#!/usr/bin/env python3
"""
Re-parser for the Ebola extract (2026.09.28_Ebola-Doc-Release_Full-Package.pdf).
Same date-header convention as the prequel parser; trailing emails + report
become one synthetic appendix entry (mirrors the prequel prologue approach).
"""
import calendar
import json
import os
import re
from collections import Counter
from datetime import date
HERE = os.path.dirname(os.path.abspath(__file__))
TEXT_PATH = os.path.join(HERE, "2026.09.28_Ebola-Doc-Release_Full-Package.txt")
OUT_PATH = os.path.join(HERE, "2026.09.28_Ebola-Doc-Release_Full-Package_fixed.json")
MONTH_MAP = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12}
_month_alts = sorted(MONTH_MAP.keys(), key=len, reverse=True)
MONTH_RE = "(" + "|".join(_month_alts) + ")"
ENDASH = chr(0x2013)
EMDASH = chr(0x2014)
DATE_HEADER_RE = re.compile(r"^\s*" + MONTH_RE + r"\.?\s+" + r"(\d{1,2})" + r"(?:\s*[-" + ENDASH + r"](\d{1,2}))?" + r"\s*[,.]?\s*" + r"(\d{4})" + r"\s*[-" + ENDASH + EMDASH + r":]?", re.IGNORECASE)
STRIP_PATTERNS = [re.compile(r"^---\s*Page\s+\d+\s*---\s*$"), re.compile(r"^Released by Chairman Rand Paul\s*$"), re.compile(r"^EXCERPT FROM FAUCI'S NOTES\s*$", re.IGNORECASE), re.compile(r"^\d{1,4}\s*$")]
ARTICLE_TIME_HINTS = [re.compile(r"\d{1,2}:\d{2}\s*[ap]\.?m\.?", re.I), re.compile(r"\d{1,2}:\d{2}\s*(?:GMT|UTC|AEDT|EST|EDT|CST|PST|PDT)", re.I), re.compile(r"\|\s*\d{1,2}:\d{2}", re.I), re.compile(r"\bAEDT\b"), re.compile(r"\d{1,2}\s*[AP]M\s+PT", re.I), re.compile(r"\bUpdated\b", re.I)]
def is_strip_line(line):
    return any(p.match(line) for p in STRIP_PATTERNS)
def looks_like_article_date(text):
    return any(p.search(text) for p in ARTICLE_TIME_HINTS)
def parse_month(mt):
    return MONTH_MAP[mt.lower().rstrip(".")]
def safe_date(y, m, d):
    import calendar as _cal
    d = min(d, _cal.monthrange(y, m)[1])
    return date(y, m, d).isoformat()
def format_raw_date(mt, day, endd, year):
    base = mt.rstrip(".")
    raw = (base + ". " if (len(base) <= 4 and base.lower() != "may") else base + " ") + str(day)
    if endd:
        raw += "-" + endd
    return raw + ", " + str(year)
def parse_text():
    with open(TEXT_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    entries, cur_iso, cur_raw, cur_lines, pre = [], None, None, [], []
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        m = DATE_HEADER_RE.match(stripped)
        if m:
            mt, day, endd, year = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            rest = stripped[m.end():]
            if looks_like_article_date(rest) or looks_like_article_date(stripped):
                if cur_iso is not None and not is_strip_line(stripped):
                    cur_lines.append(line)
                continue
            try:
                mo = parse_month(mt)
            except KeyError:
                if cur_iso is not None and not is_strip_line(stripped):
                    cur_lines.append(line)
                continue
            if cur_iso is not None:
                entries.append({"date": cur_iso, "raw_date": cur_raw, "content": "\n".join(cur_lines).strip()})
            cur_raw = format_raw_date(mt, day, endd, year)
            cur_iso = safe_date(year, mo, day)
            cur_lines = []
            if pre and not entries:
                cur_lines.extend(pre); pre = []
            if rest.strip():
                cur_lines.append(rest)
        else:
            if cur_iso is not None and not is_strip_line(stripped):
                cur_lines.append(line)
            elif cur_iso is None and not is_strip_line(stripped):
                pre.append(line)
    if cur_iso is not None:
        diary, app = split_appendix("\n".join(cur_lines).strip())
        entries.append({"date": cur_iso, "raw_date": cur_raw, "content": diary})
        if app:
            entries.append({"date": "appendix", "raw_date": "Appendix", "content": app})
    return entries
def split_appendix(content):
    lines = content.split("\n")
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.lower().startswith("from:") and "fauci, anthony" in s.lower():
            d, a = "\n".join(lines[:i]).strip(), "\n".join(lines[i:]).strip()
            if d and a:
                return d, a
    for i, ln in enumerate(lines):
        if ln.strip().lower().startswith("from:"):
            d, a = "\n".join(lines[:i]).strip(), "\n".join(lines[i:]).strip()
            if d and a:
                return d, a
    for i, ln in enumerate(lines):
        if ln.strip().lower().startswith("overview of the niaid filovirus"):
            d, a = "\n".join(lines[:i]).strip(), "\n".join(lines[i:]).strip()
            if d and a:
                return d, a
    return content, ""
def main():
    entries = [e for e in parse_text() if e["content"].strip()]
    appx = [e for e in entries if e["date"] == "appendix"]
    dated = sorted([e for e in entries if e["date"] != "appendix"], key=lambda e: e["date"])
    real = dated + appx
    dl = [e["date"] for e in dated]
    out = {"source_file": "2026.09.28_Ebola-Doc-Release_Full-Package.pdf", "title": "Fauci Diary Ebola Extract -- Zika / Filovirus Notes, March 2016", "released_by": "Chairman Rand Paul", "total_entries": len(real), "date_range": {"start": dl[0], "end": dl[-1]} if dl else {}, "entries": real}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"entries: {len(real)} (dated {len(dated)}, appendix {len(appx)})")
    print("range:", out["date_range"])
    for e in real:
        print(f"  {e['date']} | {e['raw_date']} | {len(e['content'])} chars")
if __name__ == "__main__":
    main()
