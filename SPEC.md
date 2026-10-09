# Mixed-source standards — Fauci Diary (SPEC)

How this app models documents from several releases — diary days, emails,
attachments, publisher notes — so they live on **one timeline** and can be
read in order against each other.

This is the testable companion to `EMAILS.md` (the full specification).
Each rule below names the suite that enforces it: `test_app.mjs` runs the
app's real script against the real data under a DOM shim; `audit_app.py`
checks the markup statically.

---

## 1. One document per entry (`test_app.mjs`: kinds present)

An entry is a single unit of authorship at a single instant. Kinds come
from `KIND_DEFS` in `index.html`; `KIND_ALIASES` maps a parser's spelling
onto them, so a new source needs **no UI change**.

| kind | meaning | card badge |
|---|---|---|
| `diary` (default) | a diary day | none (the common case stays quiet) |
| `email` | one message, one author, one timestamp | kind chip + source badge |
| `attachment` / `report` | a document travelling with a message | indented box under its parent |
| `note` | **publisher material about the release** | release-note box, off the timeline |

**Publisher material is not a document** — same rule as PO_Slack's
`SPEC.md §1`.

## 2. Entry keys (`audit_app.py`: keys unique)

`date|raw_date`, unique per source file. Two notes on the same day keep
distinct `raw_date`s or fold (see §4). Page-map keys and thread-link
targets reuse the same string, so a collision breaks both — the audit
fails the build if any source file repeats a key.

## 3. Page maps (`test_app.mjs`: every entry has a key; offsets ordered)

`{ start, end, breaks: [[charOffset, page]] }` per entry, in a **per-source**
map. Every cleaned entry string is asserted equal to the app JSON's
content for the same key at map-build time, so offsets can never silently
drift. `fix_page_map_offsets.py` clamps afterwards (run last, idempotent).

## 4. Adding a release

1. Copy the PDF into `server_based/` (short name, e.g. `diary-ebola.pdf`;
   the Congressional filename stays in the JSON `source_file` field) and
   `page_based/`.
2. Extract text with `--- Page N ---` markers (PDF-index pages).
3. Write `reparse_<source>.py` + `clean_<source>_breaks.py` +
   `regen_<source>_page_map.py` (imports the parser; asserts content
   equality) + `merge_<source>_duplicates.py` if same-date notes fold.
4. Register it in `index.html` `SOURCES`: `json`, `pageMap`, `pdf`,
   `label`, `badge`, `badgeTitle`. Loading, badges, the PDF switch and
   the filter all read from there.
5. Copy JSON + page map into `page_based/`.
6. Run `node test_app.mjs` and `python3 audit_app.py` in **both** folders.

## 5. On-demand PDF rendering (`test_app.mjs`: renderEntryPdf defined)

`selectResult()` never touches `pdfDoc` directly. It renders through
`renderEntryPdf(source, page)`, which reuses the in-flight PDF promise and
renders once ready — clicking a result always lands on the correct
release + page, even mid-load. (Ported from PO_Slack's email-PDF race fix.)

## 6. Tests

- `node test_app.mjs` (25 checks): data load, kinds, chronology, thread
  integrity, page-map resolution, search rendering, badges, thread chips,
  box-type filter, `renderEntryPdf`, bookmarks (toggle add/remove, payload format).
- `python3 audit_app.py` (57 checks): ids, handlers, CSS classes, tag
  balance, fetched files, every `SOURCES` path, `renderEntryPdf` wiring,
  per-source key uniqueness, bookmarks rail (markup, handlers, persistence,
  format), DRASTIC mark + manual.

## 7. Bookmarks

Entries carry no stored key; the rail computes `source|date|raw_date`
(`diaryBmKey`), unique per source file by the §2 audit. The toggle on every
card adds/removes; Save writes `{format: 'drastic-bookmarks', app, url,
bookmarks[]}` so one file travels between the DRASTIC apps. Opening a diary
bookmark rebuilds the 101-card browse window around it (`diaryBmIndex` +
`buildBrowseResultsAroundIndex`), exactly where a timeline click would land.

## 8. Manual

`help.html` (same shell as PO_Slack's) documents search, boxes, timeline,
PDF, bookmarks, keyboard, the releases, release notes and known limits. The
DRASTIC logo in the header links to it in a new tab.
