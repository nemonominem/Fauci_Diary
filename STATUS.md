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
- **Ebola extract added**: 2026.09.28_Ebola-Doc-Release_Full-Package.pdf processed (8 diary entries Mar 3–10, 2016 + 19 email entries + NIAID filovirus report) with dedicated parse/clean/page-map scripts (`reparse_ebola.py`, `clean_ebola_breaks.py`, `regen_ebola_page_map.py`); app serves short-name `diary-ebola.pdf`
- **Ebola emails threaded**: every email (outer + nested + inline-quoted) is its own dated entry; cards show only that message's own text, from a printable header block (From/To/Cc/Subject + Sent) separated by a rule from the body, and link ↩ to the replied-to/forwarded entry down the chain; the report is linked as attachment of the Kurilla "Ebola report you requested" email
- **Ebola time zones normalised**: RFC2822 `Date:` headers are authoritative; zone-less `Sent:`/inline stamps default to ET with documented per-message overrides (Nelson wrote from France → CET; Lane's Mar 9 23:41 must postdate Fauci's ET 01:29 Mar 10, matching "Just landed in San Francisco" → PT). Every card shows local time plus the ET-normalised time, and ET orders the timeline
- **Thread links bidirectional**: up-links (`reply_to`, or `forwarded_from` when the subject is `FW:`/`Fwd:`, plus `attachment_ref`) and downward **arrays** (`replied_by`, `forwarded_by`, `attached_by`) — an email can be replied to and/or forwarded again later, possibly several times and from another source. The parser inverts within its release; the app re-inverts across all merged sources at load (`rebuildThreadDownLinks`), with source-qualified keys
- **Mixed-source standards documented**: `EMAILS.md` specifies document kinds, thread splitting, time-zone rules with the evidence table, entry shape, page-map key discipline, and recipes for adding new releases or new source types (feeds/chat exports)
- **Web app merged (3 sources)**: all releases combined into one searchable timeline (2,016 entries); PDF viewer auto-switches between the three source PDFs (Ebola badge; on-demand PDF load; report sorted last; synthetic entries excluded from timeline)
- **Entry boxes scroll + expand**: each result card's text box has its own always-visible slim scrollbar (`overscroll-behavior: contain`, so wheeling inside it no longer drags the results list); a `⤢ Full text` button (shown only when the text overflows) removes the height cap, and an italic "↕ scroll inside this box for more text" hint appears while content remains below
- **PDF line-wrap joins fixed**: `clean_ebola_breaks.py` now decides a wrap by asking whether **both** flanking tokens are real words — system dictionary (Web2 + proper names) plus terms frequent in the two diary corpora — instead of corpus frequency alone; "Tony", "Cliff", "vulnerability", "lung pathology" and "assumption" join correctly, and no word is wrongly split
- Pushed to `origin/main`

## Optional later
- If any leftover diary *source* copies remain under DataWarehouse for other archives, treat this repo as authoritative for the search app.
