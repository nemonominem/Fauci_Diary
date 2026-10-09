#!/usr/bin/env python3
"""Regenerate page_map for the Missing Years diary (2015-2019).

Imports the parser so the segmentation, entry keys and content structure
can never drift from reparse_missingyears.py. Each entry maps to the PDF
page of its content start, plus a [charOffset, page] break list used to
follow search hits across pages. Every cleaned entry string is asserted
equal to the app JSON's content for the same key, which guarantees the
offsets stay valid.

Same contract as regen_ebola_page_map.py, adapted for a diary-only
release: segmentation mirrors parse_text() (DATE_HEADER_RE +
CROSS_MONTH_RE + deferred RANGE_NO_YEAR_RE + post_process), the
publisher note maps to PDF page 1 like the prequel's analysis, and
duplicate-date entries reuse the merge rule (later folds into first).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import reparse_missingyears as R  # noqa: E402

TEXT_PATH = os.path.join(HERE, "2026.10.6_Fauci-Diary-Release-Missing-Years_Full-Package.txt")
JSON_PATH = os.path.join(HERE, "2026.10.6_Fauci-Diary-Release-Missing-Years_Full-Package.json")
OUT_PATH = os.path.join(HERE, "missingyears_page_map.json")

PAGE_MARKER_RE = re.compile(r"^---\s*Page\s+(\d+)\s*---\s*$")
ANALYSIS_KEY = "prologue|Analysis by Chairman Rand Paul"
def clean_with_pages(line_pages):
    """Mirror clean_missingyears_breaks.clean_content, tracking PDF page."""
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
    parts = []
    char_pages = []
    for pi, para in enumerate(paragraphs):
        if pi:
            parts.append("\n\n")
            char_pages.extend([para[0][1], para[0][1]])
        first = True
        for text, page in para:
            if not first:
                parts.append(" ")
                char_pages.append(page)
            t = re.sub(r"\s+", " ", text).strip()
            parts.append(t)
            char_pages.extend([page] * len(t))
            first = False
    cleaned = "".join(parts)
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


def read_pairs():
    """(line, pdf page) for every non-furniture line."""
    with open(TEXT_PATH, encoding="utf-8") as f:
        raw = [ln.rstrip("\n") for ln in f.readlines()]
    pairs, page = [], 1
    for ln in raw:
        m = PAGE_MARKER_RE.match(ln.strip())
        if m:
            page = int(m.group(1))
            continue
        if R.is_strip_line(ln.strip()):
            continue
        pairs.append((ln, page))
    return pairs
def collect_blocks(pairs):
    """Segment pairs like R.parse_text. Returns (order, accum).

    accum maps the PRE-correction key to [(line, page)]. Duplicate-date
    entries share one accum list (the merge rule folds later same-date
    content into the first).
    """
    order, accum = [], {}
    cur_iso = cur_raw = cur_key = None
    pending = None

    def open_block(iso, raw, rest, page):
        nonlocal cur_iso, cur_raw, cur_key
        key = iso + "|" + raw
        cur_iso, cur_raw = iso, raw
        if key in accum:
            cur_key = key
        else:
            accum[key] = []
            order.append(key)
            cur_key = key
        if rest and rest.strip():
            accum[cur_key].append((rest, page))

    def commit_pending(next_iso):
        nonlocal pending, cur_iso, cur_raw, cur_key
        if pending is None:
            return
        month = R.parse_month(pending["month_txt"])
        year = None
        if cur_iso is not None:
            year = int(cur_iso[:4])
        if year is None and next_iso is not None:
            n = next_iso.split("-")
            if int(n[1]) == month and pending["d1"] <= int(n[2]):
                year = int(n[0])
        if year is None and next_iso is not None:
            year = int(next_iso[:4])
        if year is None:
            if cur_key is not None:
                accum[cur_key].extend(pending["lines"])
            pending = None
            return
        raw = R.format_raw_date(pending["month_txt"], pending["d1"], str(pending["d2"]), year)
        iso = R.safe_date(year, month, pending["d1"]).isoformat()
        iso2, _ = R.apply_corrections(iso, raw, "")
        open_block(iso2, raw, None, pending["page"])
        accum[cur_key].extend(pending["lines"])
        pending = None

    for t, p in pairs:
        s = t.strip()
        n = R.normalise_header(s)
        m = R.DATE_HEADER_RE.match(n)
        if m:
            if R.looks_like_article_date(n):
                if cur_key is not None:
                    accum[cur_key].append((t, p))
                continue
            try:
                mo = R.parse_month(m.group(1))
            except KeyError:
                if cur_key is not None:
                    accum[cur_key].append((t, p))
                continue
            ys = m.group(4)
            yr = int(ys[:4]) if len(ys) == 5 else int(ys)
            iso = R.safe_date(yr, mo, int(m.group(2))).isoformat()
            commit_pending(iso)
            raw = R.format_raw_date(m.group(1), int(m.group(2)), m.group(3), ys)
            iso2, _ = R.apply_corrections(iso, raw, "")
            open_block(iso2, raw, n[m.end():], p)
            continue
        cm = R.CROSS_MONTH_RE.match(s)
        if cm:
            try:
                m1 = R.parse_month(cm.group(1))
                m2 = R.parse_month(cm.group(3))
            except KeyError:
                if cur_key is not None:
                    accum[cur_key].append((t, p))
                continue
            yr = int(cm.group(5))
            start_year = yr - 1 if m2 < m1 else yr
            iso = R.safe_date(start_year, m1, int(cm.group(2))).isoformat()
            commit_pending(iso)
            raw = R.format_cross_month_raw(cm.group(1), int(cm.group(2)), cm.group(3), int(cm.group(4)), start_year)
            open_block(iso, raw, s[cm.end():], p)
            continue
        rm = R.RANGE_NO_YEAR_RE.match(n)
        if rm and not R.looks_like_article_date(n):
            if pending is not None and cur_key is not None:
                accum[cur_key].extend(pending["lines"])
            pending = {"month_txt": rm.group(1), "d1": int(rm.group(2)),
                       "d2": int(rm.group(3)), "lines": [], "page": p}
            rest = n[rm.end():]
            if rest.strip():
                pending["lines"].append((rest, p))
            cur_iso = cur_raw = cur_key = None
            continue
        if pending is not None:
            pending["lines"].append((t, p))
        elif cur_key is not None:
            accum[cur_key].append((t, p))
    commit_pending(None)
    return order, accum


def build_page_map():
    pairs = read_pairs()
    order, accum = collect_blocks(pairs)
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # The merge step (merge_missingyears_duplicates.py) folds later
    # same-DATE entries into the first, keyed by date. Fold the same way
    # here so the assert compares merged text to merged text.
    by_date = {}
    for e in data["entries"]:
        if e["date"] in by_date:
            by_date[e["date"]] += "\n\n" + e["content"]
        else:
            by_date[e["date"]] = e["content"]
    by_key = {}
    for e in data["entries"]:
        k = e["date"] + "|" + e["raw_date"]
        if k not in by_key:
            by_key[k] = by_date[e["date"]]
    # Mirror R.post_process: same-year-month backward fragments fold into
    # the running block (their pages belong to that entry).
    folded_order, folded = [], {}
    for key in order:
        iso = key.split("|", 1)[0]
        if folded_order and folded_order[-1].split("|", 1)[0][:7] == iso[:7] \
                and folded_order[-1].split("|", 1)[0] > iso:
            folded[folded_order[-1]].extend(accum[key])
            continue
        folded_order.append(key)
        folded[key] = list(accum[key])
    # Merge rule (merge_missingyears_duplicates.py): later same-DATE
    # entries fold into the first, whatever their raw_date. Fold the page
    # blocks the same way so multi-block dates get one entry with the
    # pages of all their blocks.
    # Merge rule (merge_missingyears_duplicates.py): EVERY later same-DATE
    # entry folds into the FIRST, wherever it sits in the file (first_by_date
    # dict, not adjacency). Same here: the first key keeps its raw_date and
    # gains the pages of all later same-date blocks, joined with a blank
    # line (a paragraph break after cleaning).
    merged_order, merged_acc, first_key = [], {}, {}
    for key in folded_order:
        iso = key.split("|", 1)[0]
        if iso in first_key:
            fk = first_key[iso]
            merged_acc[fk].append(("", merged_acc[fk][-1][1]))
            merged_acc[fk].extend(folded[key])
            continue
        first_key[iso] = key
        merged_order.append(key)
        merged_acc[key] = list(folded[key])
    out = {}
    for key in merged_order:
        accum[key] = merged_acc[key]
    for key in merged_order:
        cleaned, breaks, start, end = clean_with_pages(accum[key])
        iso, raw = key.split("|", 1)
        corr, _ = R.apply_corrections(iso, raw, "")
        out_key = corr + "|" + raw
        if out_key not in by_key:
            raise SystemExit("page_map key not in JSON: " + out_key)
        if cleaned != by_key[out_key]:
            norm = lambda x: re.sub(r"\s+", " ", x).strip()
            if norm(cleaned) != norm(by_key[out_key]):
                raise SystemExit("content mismatch for %s" % out_key)
        out[out_key] = {"start": start, "end": end, "breaks": breaks}
    out[ANALYSIS_KEY] = {"start": 1, "end": 1, "breaks": [[0, 1]]}
    if ANALYSIS_KEY not in by_key:
        raise SystemExit("publisher note missing from JSON")
    missing = [k for k in by_key if k not in out]
    if missing:
        raise SystemExit("JSON entries with no page map: %s" % missing)
    return out


def main():
    page_map = build_page_map()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(page_map, f, ensure_ascii=False, indent=2)
    multi = sum(1 for v in page_map.values() if v.get("end", v.get("start")) > v.get("start", 0))
    print("Wrote %d entries to %s (%d multi-page)" % (len(page_map), OUT_PATH, multi))


if __name__ == "__main__":
    main()
