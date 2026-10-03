#!/usr/bin/env python3
"""
Regenerate page_map for the Ebola extract (2026.09.28_Ebola-Doc-Release_Full-Package).

Imports the parser so the segmentation, entry keys and content structure can
never drift from reparse_ebola.py. Each entry maps to the PDF page of its
content start, plus a [charOffset, page] break list used to follow search hits
across pages. Every cleaned entry string is asserted equal to the app JSON's
content for the same key, which guarantees the offsets stay valid.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import reparse_ebola as R  # noqa: E402
import clean_ebola_breaks as CB  # noqa: E402

TEXT_PATH = os.path.join(HERE, "2026.09.28_Ebola-Doc-Release_Full-Package.txt")
JSON_PATH = os.path.join(HERE, "2026.09.28_Ebola-Doc-Release_Full-Package.json")
OUT_PATH = os.path.join(HERE, "ebola_page_map.json")

PAGE_MARKER_RE = re.compile(r"^---\s*Page\s+(\d+)\s*---\s*$")

def clean_with_pages(line_pages):
    """Same text as clean_ebola_breaks.clean_content (shared paragraph/join
    logic), with the PDF page tracked for every output character."""
    texts = [t for t, _ in line_pages]
    para_texts = []
    para_pages = []
    for a, b in CB.paragraph_ranges(texts):
        text, pages = CB.join_items(line_pages[a:b])
        if not text:
            continue
        para_texts.append(text)
        para_pages.append(pages)
    out, out_pages = [], []
    for i, (text, pages) in enumerate(zip(para_texts, para_pages)):
        if i:
            out.append("\n\n")
            out_pages.extend([pages[0] if pages else 1] * 2)
        out.append(text)
        out_pages.extend(pages if pages else [1] * len(text))
    cleaned = "".join(out)
    breaks, prev = [], None
    for i, p in enumerate(out_pages):
        if p != prev:
            breaks.append([i, p])
            prev = p
    start = breaks[0][1] if breaks else 1
    end = breaks[-1][1] if breaks else start
    return cleaned, breaks, start, end

def read_pairs():
    """(line, pdf page) for every non-boilerplate line."""
    with open(TEXT_PATH, encoding="utf-8") as f:
        raw = [ln.rstrip("\n") for ln in f.readlines()]
    # Must mirror R.strip_furniture(): a blank line touching page furniture is
    # furniture too. Keeping it here would make the map's text disagree with the
    # text reparse_ebola.py produced, which build_page_map() asserts below.
    drop_blank = set()
    for i, ln in enumerate(raw):
        if ln.strip():
            continue
        neigh = [raw[j] for j in (i - 1, i + 1) if 0 <= j < len(raw)]
        if any(R.is_strip_line(n.strip()) for n in neigh):
            drop_blank.add(i)
    pairs, page = [], 1
    for i, ln in enumerate(raw):
        m = PAGE_MARKER_RE.match(ln.strip())
        if m:
            page = int(m.group(1)); continue
        if R.is_strip_line(ln.strip()):
            continue
        if i in drop_blank:
            continue
        pairs.append((ln, page))
    return pairs

def build_page_map():
    pairs = read_pairs()
    texts = [t for t, _ in pairs]
    blocks = []          # (key, [(line, page), ...])
    cur_key, cur_lines, pre = None, [], []
    tail_pairs = None
    for i, (t, p) in enumerate(pairs):
        s = t.strip()
        m = R.DATE_HEADER_RE.match(s)
        if m and not R.looks_like_article_date(s):
            mt, day, endd, year = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            try:
                mo = R.parse_month(mt)
            except KeyError:
                mo = None
            if mo is not None:
                if cur_key is not None:
                    blocks.append((cur_key, cur_lines))
                cur_key = (R.safe_date(year, mo, day) + "|" + R.format_raw_date(mt, day, endd, year))
                cur_lines = pre if (pre and not blocks) else []
                pre = []
                rest = s[m.end():]
                if rest.strip():
                    cur_lines.append((rest, p))
                continue
        if cur_key is not None and (R.REPORT_RE.match(s) or R.scan_header(texts, i)):
            blocks.append((cur_key, cur_lines))
            cur_key = None
            tail_pairs = pairs[i:]
            break
        if cur_key is not None:
            cur_lines.append((t, p))
        else:
            pre.append((t, p))
    if cur_key is not None:
        blocks.append((cur_key, cur_lines))
    if tail_pairs is None:
        tail_pairs = []

    # ── Tail: per-message emails + report, same structure as the parser ──
    def join_pairs(pairs):
        """Same header-keyword rejoin as R._join_header_breaks, keeping the
        first line's page (asserted equal to the parser's joined lines below)."""
        out, i = [], 0
        while i < len(pairs):
            t, p = pairs[i]
            s = t.strip()
            if s in ("Fro", "Fro ") and i + 1 < len(pairs) and pairs[i + 1][0].strip().startswith("m:"):
                out.append(("From:" + pairs[i + 1][0].strip()[2:], p)); i += 2; continue
            if s == "Sub" and i + 1 < len(pairs) and pairs[i + 1][0].strip().startswith("ject:"):
                out.append(("Subject:" + pairs[i + 1][0].strip()[5:], p)); i += 2; continue
            out.append((t, p)); i += 1
        return out

    joined_pairs = join_pairs([(t, p) for t, p in tail_pairs if t.strip()])
    assert [t for t, _ in joined_pairs] == R._join_header_breaks([t for t, _ in joined_pairs]),         "header rejoin disagrees with the parser"
    jtexts = [t for t, _ in joined_pairs]

    bounds = []
    i = 0
    while i < len(joined_pairs):
        s = jtexts[i].strip()
        if R.REPORT_RE.match(s):
            bounds.append((i, {"kind": "report"})); i += 1; continue
        hdr = R.scan_header(jtexts, i)
        if hdr:
            hdr["kind"] = "email"; bounds.append((i, hdr)); i += 1; continue
        iq = R.parse_inline_marker(jtexts, i)
        if iq:
            iq["kind"] = "inline"; bounds.append((i, iq)); i += iq["span"]; continue
        i += 1

    ny = R._zone(R.NEW_YORK)
    for b, (start, meta) in enumerate(bounds):
        end = bounds[b + 1][0] if b + 1 < len(bounds) else len(joined_pairs)
        page_of_head = joined_pairs[start][1]
        if meta["kind"] == "report":
            blocks.append(("report|Report", joined_pairs[start:end]))
            continue
        ny_dt = meta["local_dt"].astimezone(ny)
        if meta["kind"] == "inline":
            body_pairs = list(joined_pairs[start + meta["span"]:end])
            if meta.get("gt_quoted"):
                body_pairs = [(re.sub(r"^>\s?", "", ln), p) for ln, p in body_pairs
                              if ln.strip() not in (">", "")]
            if not R._body_lines([t for t, _ in body_pairs], 0):
                continue
            head = ["From: " + meta["author"] + " (from an inline quote)", "",
                    R._sent_line(meta["local_dt"].strftime("%b %d, %Y %I:%M %p"), meta["tz_name"], ny_dt, True),
                    "", R.SEPARATOR, ""]
            key = ny_dt.date().isoformat() + "|" + R.inline_raw_date(meta["local_dt"], meta["tz_name"], ny_dt, meta["author"])
            blocks.append((key, [(h, page_of_head) for h in head] + body_pairs))
            continue
        head = R._field_lines(meta["fields"])
        head.append(R._sent_line(meta["printed"], meta["tz_name"], ny_dt, meta["tz_inferred"]))
        head += ["", R.SEPARATOR, ""]
        key = ny_dt.date().isoformat() + "|" + R.email_raw_date(meta["local_dt"], meta["tz_name"], ny_dt, meta["subject"])
        lines = [(h, page_of_head) for h in head] + [(ln, p) for ln, p in joined_pairs[meta["header_end"] + 1:end]]
        blocks.append((key, lines))

    # ── Clean, then verify offsets are meaningful + content matches the app JSON ──
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    by_key = {e["date"] + "|" + e["raw_date"]: e["content"] for e in data["entries"]}
    out = {}
    for key, lp in blocks:
        cleaned, breaks, start, end = clean_with_pages(lp)
        if key not in by_key:
            raise SystemExit("page_map key not in JSON: " + key)
        if cleaned != by_key[key]:
            raise SystemExit("content mismatch for %s\n--- map ---\n%r\n--- json ---\n%r"
                             % (key, cleaned[:400], by_key[key][:400]))
        out[key] = {"start": start, "end": end, "breaks": breaks}
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
    for k in sorted(page_map):
        v = page_map[k]
        print("  %-58s p.%d-%d" % (k[:58], v["start"], v["end"]))

if __name__ == "__main__":
    main()
