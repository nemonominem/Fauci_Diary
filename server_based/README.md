# Server-based version

Requires Python 3. **Self-contained** — local `diary.pdf` and data files only (no DataWarehouse paths or symlinks).

## Quick start
```bash
bash start_search.sh
# Or manually:
# python3 serve.py
```

Then open http://localhost:8765

`start_search.sh` regenerates `page_map.json` and cleans JSON line breaks before serving.

## Data pipeline (optional rebuild)

### Main diary (2019–2022)
```bash
python3 reparse_diary.py        # OCR text → fixed JSON
python3 clean_json_breaks.py    # collapse PDF line-breaks
python3 regen_page_map.py       # rebuild page map
```

### Prequel (2001–2015)
```bash
python3 reparse_prequel.py          # OCR text → fixed JSON
python3 clean_prequel_breaks.py     # collapse PDF line-breaks
python3 merge_prequel_duplicates.py # merge same-date entries
python3 regen_prequel_page_map.py   # rebuild page map
python3 fix_page_map_offsets.py      # clamp/validate every page map (run LAST)

# Pages that ship as scans with no text layer (prequel p.1 = the publisher's
# analysis) are transcribed once with macOS Vision and kept as text:
swiftc -O ocr_image.swift -o /tmp/ocr_vision
python3 -c "import pypdf;open('/tmp/p1.png','wb').write(pypdf.PdfReader('diary-prequel.pdf').pages[0].images[0].data)"
/tmp/ocr_vision /tmp/p1.png prequel_publisher_analysis.txt
```

### Ebola extract (Mar 2016)
```bash
python3 reparse_ebola.py          # OCR text → fixed JSON (8 diary + 19 threaded emails + the report)
python3 clean_ebola_breaks.py     # collapse PDF line-breaks
python3 regen_ebola_page_map.py   # rebuild page map (imports the parser; asserts content equality)
```

### After ANY page-map or content change (all releases)
```bash
python3 fix_page_map_offsets.py   # clamp/verify all three maps against the loaded text
```
Run it last. A page map records where an entry's content crosses a page
boundary (`breaks: [[charOffset, page], …]`), so an offset that points past the
end of the content sends a search hit to a page the entry does not even reach —
this happens when the OCR block swallowed material the parser correctly drops
(pasted press articles, web boilerplate, a repeated date header). The script
drops those breaks, keeps offsets increasing and pages non-decreasing,
recomputes `start`/`end`, drops orphan keys and prints any entry left unmapped.
It is idempotent; run it even when nothing changed, as a regression check.

> Emails, mail threads and their time-zone handling (local stamp + New York
> normalisation, reply-chain links, printable header block) are specified in
> **[`../EMAILS.md`](../EMAILS.md)** — follow it for any new release that
> contains emails, or when adding a new kind of source.

| File | Role |
|---|---|
| `2026.07.24_Tonys-Diary-Package.txt` | Main diary OCR source text |
| `2026.07.24_Tonys-Diary-Package_fixed.json` | Main diary parsed entries (pre-clean) |
| `2026.07.24_Tonys-Diary-Package.json` | Main diary app load file (cleaned) |
| `page_map.json` | Main diary: date\|raw_date → PDF page |
| `fix_page_map_offsets.py` | Clamps/verifies every page map against the loaded text (run last) |
| `diary.pdf` | Local copy of the main Congressional PDF |
| `2026.07.27_Diary-Prequel-.txt` | Prequel OCR source text |
| `2026.07.27_Diary-Prequel-_fixed.json` | Prequel parsed entries (pre-clean) |
| `2026.07.27_Diary-Prequel-.json` | Prequel app load file (cleaned) |
| `prequel_page_map.json` | Prequel: date\|raw_date → PDF page |
| `prequel_publisher_analysis.txt` | Vision OCR of the prequel's p.1 scan (the publisher's analysis); read by `reparse_prequel.py` |
| `ocr_image.swift` | macOS Vision OCR for scan-only pages (reading order + two-column blocks + paragraph gaps) |
| `merge_prequel_duplicates.py` | Folds same-date **diary** entries only; never merges an email/attachment/note |
| `diary-prequel.pdf` | Local copy of the prequel Congressional PDF |
| `2026.09.28_Ebola-Doc-Release_Full-Package.txt` | Ebola extract OCR source text |
| `2026.09.28_Ebola-Doc-Release_Full-Package_fixed.json` | Ebola parsed entries (pre-clean) |
| `2026.09.28_Ebola-Doc-Release_Full-Package.json` | Ebola app load file (cleaned) |
| `ebola_page_map.json` | Ebola: date\|raw_date → PDF page |
| `diary-ebola.pdf` | Local copy of the Ebola Congressional PDF (short name) |
