# Fauci Diary Search

Searchable web app for Dr. Anthony Fauci's diary (Congressional release, Dec 2019 – Dec 2022, 860 entries).

## Structure

| Folder | Purpose |
|---|---|
| `server_based/` | Local version — run `bash start_search.sh` to serve on port 8765. Includes local `diary.pdf` plus reparse/clean/page-map scripts. |
| `page_based/` | Static GitHub Pages version — self-contained, includes the PDF. |

## Data

- **Source PDF**: 1,141 pages, ~63 MB (Congressional release by Chairman Rand Paul)
- **Parsed JSON**: 860 diary entries, each with date, raw_date, content, and optional date_note (typo corrections). Content has PDF line-breaks cleaned for reading.
- **Page Map**: Each entry mapped to its PDF content-start page (863 mapped keys)

## How to use

### Local (server_based)
```bash
cd server_based
bash start_search.sh
# Opens http://localhost:8765
```

### GitHub Pages (page_based)
Push `page_based/` to a GitHub Pages-enabled repo. The 63 MB PDF is tracked via Git LFS.

## Search tips

- `word1 word2` — AND  
- `word1|word2` — OR  
- `lab*` — wildcard  
- `(regex)` — JavaScript regex when special characters are present  
- `"exact phrase"` — quoted phrase  

Click **?** in the header for the full help popup. Use HIT Prev/Next to step through matches inside an entry. Toggle Landscape / Portrait layout with the header button.
