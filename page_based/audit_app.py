#!/usr/bin/env python3
"""
Static integrity audit of index.html.

The DOM shim in the test harness can run the app's logic, but it cannot tell
you that a getElementById names an element that no longer exists, that an id is
duplicated, or that an onclick calls a function nobody defined. Those are the
failures that survive every functional test and then blow up in the browser, so
they are checked directly against the markup.

Usage: python3 audit_app.py
"""
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "index.html")

with open(HTML, encoding="utf-8") as f:
    src = f.read()

# `src` is the whole file; `body` is only the inline script. Markup checks read
# `src`, script checks read `body`.
body = src.split("<script>")[-1]
body = body.split("</script>")[0]

problems = []
notes = []


def check(cond, msg):
    if cond:
        notes.append("ok   " + msg)
    else:
        problems.append("FAIL " + msg)


# ── ids ─────────────────────────────────────────────────────────────────────
ids = re.findall(r'\sid="([^"]+)"', src)
dupes = [i for i, c in Counter(ids).items() if c > 1]
check(not dupes, "no duplicate ids" + (" (dupes: %s)" % dupes if dupes else ""))

# ids the script reaches for. Only literals: getElementById('result-' + i)
# builds an id at runtime and must not be read as the literal "result-".
used_ids = set()
for m in re.finditer(r"getElementById\(\s*'([^']+)'\s*(\+|,|\))", body):
    if m.group(2) in ("+", ","):     # concatenated -> runtime id
        continue
    used_ids.add(m.group(1))
missing = sorted(used_ids - set(ids) - {"kindFilterPanel"})  # created by JS
check(not missing, "every getElementById target exists" +
      (" (missing: %s)" % missing if missing else ""))

# ids the markup binds through onclick=
onclick_ids = set(re.findall(r'onclick="([A-Za-z_$][\w$]*)\(', src))
defined = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", body))
defined |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function", body))
missing_fn = sorted(f for f in onclick_ids if f not in defined)
check(not missing_fn, "every inline onclick handler is defined" +
      (" (missing: %s)" % missing_fn if missing_fn else ""))

# ── classes ─────────────────────────────────────────────────────────────────
css = src.split("<style>")[-1].split("</style>")[0]
css_classes = set(re.findall(r"\.([A-Za-z][\w-]*)", css))
js_classes = set()
def add_tokens(chunk):
    # The script builds class attributes by concatenation, e.g.
    #   class="entry-kind k-' + kind + '"  ->  k-email
    # so everything from the first quote on is a runtime fragment, not a class.
    chunk = re.split(r"['\"\`]", chunk)[0]
    for tok in chunk.split():
        # a trailing hyphen means the markup is a fragment being concatenated
        # ("class=\"... k-' + kind") -- the real class only exists at runtime
        if tok.endswith("-"):
            continue
        if re.fullmatch(r"[a-zA-Z][\w-]*", tok):
            js_classes.add(tok)
for m in re.findall(r'class="([^"]*)"', body):
    add_tokens(m)
for m in re.findall(r"classList\.(?:add|toggle|contains|remove)\(\s*'([^']+)'", body):
    add_tokens(m)
# closest('.result-content') / ('#resultsPanel, .foo') -> bare class tokens only
for m in re.findall(r'closest\(\s*[\'"]([^\'"]+)[\'"]', body):
    for sel in m.split(','):
        sel = sel.strip()
        if sel.startswith('.') and re.fullmatch(r"\.[\w-]+", sel):
            add_tokens(sel[1:])
undefined = sorted(c for c in js_classes if c not in css_classes)
check(not undefined, "every class used by the script exists in the CSS" +
      (" (missing: %s)" % undefined if undefined else ""))

# ── tag balance ─────────────────────────────────────────────────────────────
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
# Scan markup only: <script> and <style> bodies contain '<' inside strings
# (help text, generated HTML), which would look like unbalanced tags.
markup = re.sub(r"<script>[\s\S]*?</script>", "<script></script>", src)
markup = re.sub(r"<style>[\s\S]*?</style>", "<style></style>", markup)
stack = []
for m in re.finditer(r"<(/?)([a-zA-Z][\w-]*)([^>]*?)(/?)>", markup):
    closing, tag, attrs, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
    if tag in VOID or selfclose:
        continue
    if closing:
        if stack and stack[-1][0] == tag:
            stack.pop()
        else:
            problems.append("FAIL unbalanced </%s> (open: %s)" % (tag, [t for t, _ in stack[-3:]]))
            if stack:
                stack.pop()
    else:
        stack.append((tag, m.start()))
check(not stack, "HTML tags balance" +
      (" (unclosed: %s)" % [t for t, _ in stack] if stack else ""))

# ── data files the app fetches must exist ───────────────────────────────────
fetched = set(re.findall(r"fetch\(\s*'([^']+)'", body))
absent = sorted(f for f in fetched if not os.path.exists(os.path.join(HERE, f)))
check(not absent, "every fetched data file exists" + (" (missing: %s)" % absent if absent else ""))

# ── sources ─────────────────────────────────────────────────────────────────
src_block = re.search(r"const SOURCES = \{(.*?)\n\};", body, re.S)
check(bool(src_block), "SOURCES block found")
if src_block:
    for sid, chunk in re.findall(r"(\n  '?[\w-]+'?): \{(.*?)\n  \}", src_block.group(1), re.S):
        for field in ("json", "pageMap"):
            m = re.search(field + r":\s*'([^']+)'", chunk)
            if m:
                check(os.path.exists(os.path.join(HERE, m.group(1))),
                      "SOURCES.%s.%s -> %s exists" % (sid.strip("'").strip(), field, m.group(1)))
        m = re.search(r"pdf:\s*'([^']+)'", chunk)
        if m:
            check(os.path.exists(os.path.join(HERE, m.group(1))),
                  "SOURCES.%s.pdf -> %s exists" % (sid.strip("'").strip(), m.group(1)))


# -- the on-demand PDF fix (ported from PO_Slack) --
check("async function renderEntryPdf(" in body, "renderEntryPdf() is defined")
check("renderEntryPdf(src, page)" in body,
      "selectResult() renders through renderEntryPdf()")
# -- entry key discipline: date|raw_date unique per source file --
import json as _json
try:
    _sids = []
    if src_block:
        for _sid, _chunk in re.findall(r"(\n  '?[\w-]+'?): \{(.*?)\n  \}", src_block.group(1), re.S):
            _sids.append(_sid.strip("'"))
    for _sid in _sids:
        _m = re.search(r"\n  '?" + re.escape(_sid) + r"'?: \{(.*?)\n  \}", src_block.group(1), re.S)
        _jm = re.search(r"json:\s*'([^']+)'", _m.group(1)) if _m else None
        if not _jm:
            continue
        _data = _json.load(open(os.path.join(HERE, _jm.group(1)), encoding="utf-8"))
        _keys = [_e["date"] + "|" + _e["raw_date"] for _e in _data["entries"]]
        _dupes = [_k for _k, _c in Counter(_keys).items() if _c > 1]
        check(not _dupes, "SOURCES.%s entry keys unique (%d entries)" % (_sid, len(_keys)))
except Exception as _ex:
    problems.append("FAIL entry key check crashed: %s" % _ex)

# -- bookmarks rail --
check('id="bmRail"' in src, "bookmarks rail is in the markup")
check('id="bmList"' in src, "bookmarks list is in the markup")
check('id="bmUp"' in src and 'id="bmDown"' in src,
      "bookmarks list has both scroll arrows")
check('id="bmFile"' in src, "bookmarks file input is in the markup")
check("data-bm-toggle" in body, "every result box gets a bookmark toggle")
check(re.search(r'<div class="content-area">' , src) and '<div class="bm-rail"' in src.split('<div class="content-area">')[1][:2000],
      "bookmarks rail sits inside .content-area (so it follows the layout flip)")
for _fn in ("toggleBookmark", "isBookmarked", "removeBookmark", "openBookmark",
           "renderBookmarks", "bookmarksPayload", "loadBookmarksFile",
           "initBookmarks", "toggleBmRail", "bmScrollBy", "syncBmScrollBtns",
           "diaryBmKey", "diaryBmIndex", "openEntryByBmKey"):
    check(("function %s(" % _fn) in body, "%s() is defined" % _fn)
check("localStorage" in body, "bookmarks persist in localStorage")
check("format: 'drastic-bookmarks'" in body, "the bookmark file names its format")

# -- the DRASTIC mark and the manual --
check('class="header-brand"' in src, "the DRASTIC mark has a home in the header")
check("drastic-logo.png" in src, "the DRASTIC logo is referenced")
check(os.path.exists(os.path.join(HERE, "drastic-logo.png")), "the DRASTIC logo file exists")
check('href="help.html"' in src, "the logo links to the manual")
check(os.path.exists(os.path.join(HERE, "help.html")), "help.html exists")

# -- the manual page itself --
HELP = os.path.join(HERE, "help.html")
if os.path.exists(HELP):
    hp = open(HELP, encoding="utf-8").read()
    check(hp.count("<html") == 1 and "</html>" in hp, "help.html is a whole document")
    for term, why in (("search", "searching"), ("Bookmarks", "bookmarks"),
                      ("timeline", "the timeline"), ("Keyboard", "the keyboard"),
                      ("Release notes", "release notes"),
                      ("Known limits", "the limits")):
        check(term in hp, "the manual covers %s" % why)
    check("drastic-logo.png" in hp, "the manual carries the DRASTIC mark")
    check('href="index.html"' in hp, "the manual links back to the app")
print("\n".join(notes))
if problems:
    print()
    print("\n".join(problems))
print("\n%d checks passed, %d failed" % (len(notes), len(problems)))
sys.exit(1 if problems else 0)