# GitHub Pages / static version

Self-contained static files. No Python server is required for hosting.

## Files
- `index.html` — app UI
- `2026.07.24_Tonys-Diary-Package.json` — main diary entries (2019–2022)
- `2026.07.27_Diary-Prequel-.json` — prequel entries (2001–2015)
- `2026.09.28_Ebola-Doc-Release_Full-Package.json` — ebola extract entries (Mar 2016: 8 diary + 19 threaded emails + filovirus report)
- `page_map.json` — date → PDF page (main diary)
- `prequel_page_map.json` — date → PDF page (prequel)
- `ebola_page_map.json` — date → PDF page (ebola extract)
- `diary.pdf` — main diary PDF (~63 MB; Git LFS)
- `diary-prequel.pdf` — prequel PDF (~10 MB; Git LFS)
- `diary-ebola.pdf` — ebola extract PDF, short name (~3 MB), the canonical in-repo copy. The Congressional original filename `2026.09.28_Ebola-Doc-Release_Full-Package.pdf` is recorded in the JSON `source_file` field and in `../server_based/README.md`; its bytes are identical to `diary-ebola.pdf`, so it is not stored here again.

## Standards

Email, thread and time-zone conventions for every source (document kinds,
reply-chain links, ET normalisation with local stamps, page-map rules, and how
to add a new source type): **[`../EMAILS.md`](../EMAILS.md)**.

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
