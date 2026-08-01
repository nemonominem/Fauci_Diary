# GitHub Pages / static version

Self-contained static files. No Python server is required for hosting.

## Files
- `index.html` — app UI
- `2026.07.24_Tonys-Diary-Package.json` — main diary entries (2019–2022)
- `2026.07.27_Diary-Prequel-.json` — prequel entries (2001–2015)
- `page_map.json` — date → PDF page (main diary)
- `prequel_page_map.json` — date → PDF page (prequel)
- `diary.pdf` — main diary PDF (~63 MB; Git LFS)
- `diary-prequel.pdf` — prequel PDF (~10 MB; Git LFS)

## Important: do not open `index.html` as a file

Browsers block `fetch()` of local JSON/PDF under `file://`, which produces
**“Failed to fetch”**. That is not a request to run `serve.py` — `serve.py`
belongs to the **server_based** variant only.

### Option A — any static HTTP server (local preview)
```bash
cd page_based
python3 -m http.server 8080
# open http://localhost:8080
```

### Option B — GitHub Pages
Push this folder’s contents to a Pages-enabled branch/repo. Prefer Git LFS for the PDF:
```bash
git lfs track "diary.pdf"
```

### Option C — full local app with pipeline scripts
Use `../server_based` and `bash start_search.sh` (also includes a local `diary.pdf`).
