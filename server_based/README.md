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
```

| File | Role |
|---|---|
| `2026.07.24_Tonys-Diary-Package.txt` | Main diary OCR source text |
| `2026.07.24_Tonys-Diary-Package_fixed.json` | Main diary parsed entries (pre-clean) |
| `2026.07.24_Tonys-Diary-Package.json` | Main diary app load file (cleaned) |
| `page_map.json` | Main diary: date\|raw_date → PDF page |
| `diary.pdf` | Local copy of the main Congressional PDF |
| `2026.07.27_Diary-Prequel-.txt` | Prequel OCR source text |
| `2026.07.27_Diary-Prequel-_fixed.json` | Prequel parsed entries (pre-clean) |
| `2026.07.27_Diary-Prequel-.json` | Prequel app load file (cleaned) |
| `prequel_page_map.json` | Prequel: date\|raw_date → PDF page |
| `diary-prequel.pdf` | Local copy of the prequel Congressional PDF |
