# Status: Fauci_Diary

## Standing rule

**The diary lives only in this repo.** Move work *away* from DataWarehouse / DataWharehouse. No symlinks or absolute paths outside `Fauci_Diary`.

## Done
- Merged congressional working copy into `server_based/` + `page_based/`
- Dual timeline UI, collapse, PDF jump-from-result, static load error messages
- `server_based/diary.pdf` is a **local file** (not a DataWarehouse symlink)
- Scripts (`reparse_diary.py`, etc.) use paths relative to `server_based/`
- Misplaced diary app files removed from `DataWharehouse/.../congressional` (processed folder)
- **Prequel added**: 2026.07.27_Diary-Prequel-.pdf processed (1,135 entries, Jan 2001 – Jul 2015) with dedicated parse/clean/page-map scripts
- **Web app merged**: both releases combined into one searchable timeline (1,988 entries); PDF viewer auto-switches between the two source PDFs
- Pushed to `origin/main`

## Optional later
- If any leftover diary *source* copies remain under DataWarehouse for other archives, treat this repo as authoritative for the search app.
