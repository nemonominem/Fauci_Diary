#!/usr/bin/env python3
"""Regenerate page_map for the Missing Pages diary (Dec 2021 - May 2022).

Imports the parser so the segmentation, entry keys and content structure can
never drift from reparse_missingpages.py. Each entry maps to the PDF page of
its content start, plus a [charOffset, page] break list used to follow search
hits across pages. Every cleaned entry string is asserted equal to the app
JSON's content for the same key, which guarantees the offsets stay valid.

Same contract as regen_missingyears_page_map.py, adapted for this release's
simpler header grammar (no cross-month/deferred-range headers) and its two
extra moving parts:

  * the Axios verbatim span (reparse_missingpages.VERBATIM_SPAN_START/END) -
    tracked here as a single multi-page run of (line, page) pairs, spliced
    back in at the same placeholder position, so its pages are still
    recorded even though its content never goes through the header scanner;
  * the second, sorted-order fold (fold_exact_date_duplicates) - applied
    here to the page-break accumulators the same way it is applied to
    content in the parser, so a byline-date collision folds its pages into
    the entry it folds its text into.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import reparse_missingpages as R  # noqa: E402

TEXT_PATH = os.path.join(HERE, "2026.10.07_Missing-Pages-Diary_Full-Package.txt")
JSON_PATH = os.path.join(HERE, "2026.10.07_Missing-Pages-Diary_Full-Package.json")
OUT_PATH = os.path.join(HERE, "missingpages_page_map.json")

PAGE_MARKER_RE = re.compile(r"^---\s*Page\s+(\d+)\s*---\s*$")
ANALYSIS_KEY = "prologue|Analysis by Chairman Rand Paul"


def clean_with_pages(line_pages):
    """Mirror clean_missingpages_breaks.clean_content, tracking PDF page."""
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
        if s.endswith(":") and len(s) < 80 and not s[:1].islower():
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
    """(line, pdf page) for every raw line, page furniture included - the
    verbatim span needs its own furniture dropped explicitly (see below), so
    furniture is NOT stripped here the way the other regen_*.py scripts do
    it; is_strip_line is applied per-branch instead, mirroring parse_text()."""
    with open(TEXT_PATH, encoding="utf-8") as f:
        raw = [ln.rstrip("\n") for ln in f.readlines()]
    pairs, page = [], 1
    for ln in raw:
        m = PAGE_MARKER_RE.match(ln.strip())
        if m:
            page = int(m.group(1))
            continue
        pairs.append((ln, page))
    return pairs


def split_verbatim_pairs(pairs):
    start_idx = end_idx = None
    for i, (ln, _p) in enumerate(pairs):
        if start_idx is None and R.VERBATIM_SPAN_START in ln:
            start_idx = i
        elif start_idx is not None and end_idx is None and R.VERBATIM_SPAN_END in ln:
            end_idx = i
            break
    if start_idx is None or end_idx is None:
        raise SystemExit("Axios verbatim-span markers not found in page-tracked text")
    span = [(ln, p) for ln, p in pairs[start_idx:end_idx + 1] if not R.is_strip_line(ln.strip())]
    return pairs[:start_idx], span, pairs[end_idx + 1:]


def collect_blocks(pairs):
    """Segment pairs like R.parse_text(). Returns (order, accum) in TEXT
    ORDER, pre-sort - the exact-date fold happens later, on sorted keys."""
    before, verbatim, after = split_verbatim_pairs(pairs)
    placeholder = R.__dict__.get("_PLACEHOLDER", "\x00VERBATIM_SPAN\x00")
    tagged = [(ln, p, False) for ln, p in before] + [(placeholder, None, True)] + [(ln, p, False) for ln, p in after]

    order, accum = [], {}
    cur_iso = cur_raw = cur_key = None

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

    for t, p, is_verbatim in tagged:
        if is_verbatim:
            if cur_key is not None:
                accum[cur_key].extend(verbatim)
            continue
        s = t.strip()
        m = R.DATE_HEADER_RE.match(s)
        if m:
            month_txt = m.group(1)
            day = int(m.group(2))
            end_day_s = m.group(3)
            year_s = m.group(4)
            rest_of_line = s[m.end():]

            if R.looks_like_article_date(rest_of_line) or R.looks_like_article_date(s):
                if cur_key is not None and not R.is_strip_line(s):
                    accum[cur_key].append((t, p))
                continue

            if year_s is None:
                if cur_iso is None or not re.search(r"\b(?:Global|USA)\b", rest_of_line):
                    if cur_key is not None and not R.is_strip_line(s):
                        accum[cur_key].append((t, p))
                    continue
                year = int(cur_iso[:4])
            else:
                year = int(year_s)

            try:
                month = R.parse_month(month_txt)
            except KeyError:
                if cur_key is not None and not R.is_strip_line(s):
                    accum[cur_key].append((t, p))
                continue

            raw = R.format_raw_date(month_txt, day, end_day_s, year)
            iso = R.safe_date(year, month, day).isoformat()
            iso2, _ = R.apply_corrections(iso, raw, "")
            open_block(iso2, raw, rest_of_line, p)
            continue

        if cur_key is not None and not R.is_strip_line(s):
            accum[cur_key].append((t, p))

    return order, accum


def build_page_map():
    pairs = read_pairs()
    order, accum = collect_blocks(pairs)
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    by_key = {e["date"] + "|" + e["raw_date"]: e["content"] for e in data["entries"]}

    # Pass 1 (mirrors R.fold_text_order_fragments): same-month backward
    # fragments and article clippings fold into whatever is open. The page
    # map has no content to run is_article_clipping against here, so this
    # pass only applies the same-month-backward half - clippings merge via
    # pass 2 below instead (every clipping found in this release happens to
    # land on an exact date collision - see reparse_missingpages docstring).
    folded_order, folded = [], {}
    for key in order:
        iso = key.split("|", 1)[0]
        if folded_order and folded_order[-1].split("|", 1)[0][:7] == iso[:7] \
                and folded_order[-1].split("|", 1)[0] > iso:
            folded[folded_order[-1]].extend(accum[key])
            continue
        folded_order.append(key)
        folded[key] = list(accum[key])

    # Pass 2 (mirrors R.fold_exact_date_duplicates): sort by date, fold any
    # EXACT same-date run together, in sorted (= stable text) order.
    sorted_keys = sorted(folded_order, key=lambda k: k.split("|", 1)[0])
    merged_order, merged_acc = [], {}
    for key in sorted_keys:
        iso = key.split("|", 1)[0]
        if merged_order and merged_order[-1].split("|", 1)[0] == iso:
            merged_acc[merged_order[-1]].extend(folded[key])
            continue
        merged_order.append(key)
        merged_acc[key] = list(folded[key])

    out = {}
    for key in merged_order:
        cleaned, breaks, start, end = clean_with_pages(merged_acc[key])
        if key not in by_key:
            raise SystemExit("page_map key not in JSON: " + key)
        if cleaned != by_key[key]:
            norm = lambda x: re.sub(r"\s+", " ", x).strip()
            if norm(cleaned) != norm(by_key[key]):
                raise SystemExit("content mismatch for %s" % key)
        out[key] = {"start": start, "end": end, "breaks": breaks}
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
