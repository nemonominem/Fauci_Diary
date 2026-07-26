# Server-based version

Requires Python 3. The PDF is a symlink to the original in `DataWharehouse/`.

## Quick start
```bash
bash start_search.sh
# Or manually:
# python3 serve.py
```

Then open http://localhost:8765

`start_search.sh` regenerates `page_map.json` and cleans JSON line breaks before serving.

## Data pipeline (optional rebuild)
```bash
# 1. Re-parse OCR text → fixed JSON (date headers, typo notes)
python3 reparse_diary.py

# 2. Collapse PDF hard line-breaks in entry content
python3 clean_json_breaks.py

# 3. Rebuild page map (content start page heuristic)
python3 regen_page_map.py
```

| File | Role |
|---|---|
| `2026.07.24_Tonys-Diary-Package.txt` | OCR source text |
| `2026.07.24_Tonys-Diary-Package_fixed.json` | Parsed entries (pre-clean) |
| `2026.07.24_Tonys-Diary-Package.json` | App load file (cleaned content) |
| `page_map.json` | date\|raw_date → PDF page |
| `diary.pdf` | Symlink to original PDF |
