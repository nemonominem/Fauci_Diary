#!/usr/bin/env python3
"""
Clean PDF-induced line breaks from the Ebola extract JSON content.

The Ebola PDF hard-wraps text at a character column with NO space glyph at
the wrap point - sometimes mid-word ("Ton" / "y,", "I appr" / "eciate"),
sometimes at a word boundary ("who funded" / "the study"). Presence of a
trailing space proves a boundary only when the PDF kept one (245 lines do),
so decide_wrap() instead asks whether BOTH tokens flanking the wrap are
real words (system dictionary + proper names + frequent repo terms):
both words -> insert a space, either side a fragment -> join directly.
Sentence-ending punctuation, an already-present trailing space, an
uppercase next token and single-letter fragments ("a"/"i" excepted) are
handled first.

The page map (regen_ebola_page_map.py) imports paragraph_ranges()/join_items()
so page offsets are measured over the exact same text the app loads - and the
map build asserts content equality, so the two can never silently drift.

Same heuristic as clean_json_breaks.py otherwise: blank lines and short
":"-headed lines are paragraph breaks.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(HERE, "2026.09.28_Ebola-Doc-Release_Full-Package_fixed.json")
OUT_PATH = os.path.join(HERE, "2026.09.28_Ebola-Doc-Release_Full-Package.json")

WORDSET = None
DICT_PATHS = ("/usr/share/dict/words", "/usr/share/dict/propernames")


def build_wordset():
    """A token counts as a real word if it is in the system dictionary
    (Web2 + proper names) OR frequent in this repo's diary corpora (>=5).
    Fragments of split words ("originat", "eciate", "eting") are in neither;
    frequent domain terms the dictionary lacks ("NIAID", "aerosol") are
    covered by the corpus half."""
    global WORDSET
    if WORDSET is None:
        from collections import Counter
        s = set()
        for path in DICT_PATHS:
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    w = line.strip().lower()
                    if w:
                        s.add(w)
        cnt = Counter()
        for name in ("2026.07.24_Tonys-Diary-Package.json",
                     "2026.07.27_Diary-Prequel-.json"):
            path = os.path.join(HERE, name)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as f:
                for e in json.load(f)["entries"]:
                    for tok in re.findall(r"[A-Za-z']+", e.get("content", "")):
                        cnt[tok.lower()] += 1
        s.update(t for t, c in cnt.items() if c >= 5)
        WORDSET = s
    return WORDSET


def is_word(tok):
    return tok.lower() in build_wordset()


SENT_END_RE = re.compile(r'[.!?:;"\')\]\u201d\u2019]$')


def decide_wrap(prev, nxt):
    """True = insert a space between these two raw lines.

    The PDF wraps at a character column with no space glyph at the wrap, both
    mid-word and at word boundaries, so presence of a space proves nothing.
    A space is inserted only when BOTH tokens flanking the wrap are known
    words (dictionary or frequent in the corpora); a fragment on either side
    means the line broke inside a word and the pieces must be joined:
        "originat" + "ed"      -> originated   (originat is no word)
        "lung" + "pathology"   -> lung pathology (both are words)
        "Ton" + "y,"           -> Tony,        (single-letter next rule)
    """
    if not prev or prev[-1].isspace():
        return False                      # space already present at the wrap
    if SENT_END_RE.search(prev):
        return True                       # sentence ended: next word needs one
    m = re.match(r"\s*([A-Za-z']+)", nxt)
    if not m:
        return True
    ntok = m.group(1)
    if ntok[0].isupper():
        return True                       # proper noun / sentence start
    if len(ntok) == 1:
        return ntok.lower() in ("a", "i") # single letters are fragments
    pm = re.search(r"([A-Za-z']+)$", prev)
    if not pm:
        return True
    ptok = pm.group(1)
    if len(ptok) == 1:
        return ptok.lower() in ("a", "i")
    return is_word(ptok) and is_word(ntok)


def paragraph_ranges(lines):
    """[(start, end)) index ranges of paragraphs.

    Mirrors the original cleaner: a blank line closes a paragraph; a
    short ":"-headed or "PRESS:" line closes the previous paragraph AND opens
    a new one containing itself plus the following lines (so "Newt:" heads the
    block instead of being dropped).
    """
    ranges = []
    start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            if start is not None:
                ranges.append((start, i))
                start = None
        elif s.upper().startswith("PRESS:") or (s.endswith(":") and len(s) < 80):
            if start is not None:
                ranges.append((start, i))
            start = i                      # heading opens its own paragraph
        elif start is None:
            start = i
    if start is not None:
        ranges.append((start, len(lines)))
    return ranges


def join_items(items):
    """Join one paragraph's lines into a single collapsed string.

    items: [(raw_line, page)] (page may be None for the JSON cleaner).
    Returns (text, pages) where pages is a char-aligned page list, or None.
    """
    parts = []
    pages = []
    any_page = any(p is not None for _, p in items)
    prev = ""
    for idx, (line, page) in enumerate(items):
        if idx and decide_wrap(prev, line):
            parts.append(" ")
            if any_page:
                pages.append(prev_page if idx else page)
        parts.append(line)
        if any_page:
            pages.extend([page] * len(line))
        prev = line
        prev_page = page
    raw = "".join(parts)
    # collapse whitespace runs to one space (first char's page wins), then strip
    out, opages = [], []
    i, n = 0, len(raw)
    while i < n:
        if raw[i].isspace():
            j = i
            while j < n and raw[j].isspace():
                j += 1
            out.append(" ")
            if any_page:
                pages_i = pages[i] if i < len(pages) else None
                opages.append(pages_i)
            i = j
        else:
            out.append(raw[i])
            if any_page:
                opages.append(pages[i])
            i += 1
    a, b = 0, len(out)
    while a < b and out[a] == " ":
        a += 1
    while b > a and out[b - 1] == " ":
        b -= 1
    text = "".join(out[a:b])
    return text, (opages[a:b] if any_page else None)


def clean_content(content):
    """Join PDF-wrapped lines; keep paragraph breaks at logical points."""
    lines = content.split("\n")
    paragraphs = []
    for a, b in paragraph_ranges(lines):
        text, _ = join_items([(ln, None) for ln in lines[a:b]])
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def main():
    with open(SRC_PATH, encoding="utf-8") as f:
        data = json.load(f)

    for entry in data.get("entries", []):
        if "content" in entry:
            entry["content"] = clean_content(entry["content"])

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Cleaned %d entries -> %s" % (len(data.get("entries", [])), OUT_PATH))


if __name__ == "__main__":
    main()
