# Fauci Diary Search

Searchable web app for Dr. Anthony Fauci's diary (Congressional release, Dec 2019 – Dec 2022, 860 entries).

## Structure

| Folder | Purpose |
|---|---|
| `server_based/` | Local version — run `bash start_search.sh` to serve on port 8765. Uses a symlink to the original PDF. |
| `page_based/` | Static GitHub Pages version — self-contained, includes the PDF. |

## Data

- **Source PDF**: 1,141 pages, 63 MB (Congressional release by Chairman Rand Paul)
- **Parsed JSON**: 860 diary entries, each with date, raw_date, content, and optional date_note (typo corrections)
- **Page Map**: Each entry mapped to its PDF page number (855/860 mapped)

## How to use

### Local (server_based)
```bash
cd server_based
bash start_search.sh
# Opens http://localhost:8765
```

### GitHub Pages (page_based)
Push `page_based/` to a GitHub Pages-enabled repo. The 63 MB PDF is tracked via Git LFS.
