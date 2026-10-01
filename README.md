# Fauci Diary Search

Searchable web app for Dr. Anthony Fauci's diary (Congressional release by Chairman Rand Paul).

## Coverage

| Release | Period | Entries | PDF pages |
|---|---|---|---|
| **Prequel** — Historical Record of HIV/AIDS | Jan 2001 – Jul 2015 | 1,135 | 465 |
| **Ebola extract** — Zika / filovirus diary notes + threaded emails + NIAID report | Mar 3–22, 2016 | 28 (8 diary + 19 emails + report) | 26 |
| **Main Diary** — Tony's Diary Package | Dec 2019 – Dec 2022 | 853 | 1,141 |
| **Combined** | Jan 2001 – Dec 2022 | 2,016 | 1,632 |

All three releases are merged into a single searchable timeline. The PDF viewer
automatically switches to the correct source PDF when you click a result.

## Mixed sources: emails, threads, time zones

Emails are first-class entries, not appendix blobs: each message is its own
dated card holding only what its author wrote, linked to the message it answers,
with timestamps normalised to New York time (local time shown alongside).

Attachments are handled on both sides: a document released with a message gets
its own box directly under that message, and an attachment only *announced* in
the text shows as an 📎 chip - an active link when the document is in the
releases, a dimmed "not in these releases" tag otherwise. The toolbar's **Box
types** button ticks which kinds of box are listed (diary, email, attachment,
and room for SMS, social, Slack, WhatsApp), so diaries, emails, attachments and
feeds form one true multi-media timeline.

**→ [`EMAILS.md`](EMAILS.md)** is the specification — document kinds, thread
splitting, zone rules and evidence table, entry shape, and the recipe for adding
new releases or new source types (Twitter/Bluesky threads, Slack/Signal exports)
to the same timeline. Read it before adding anything mail- or feed-shaped.

## Canonical home (important)

**This repository is the sole home of the diary app and its data.**

- All PDF, OCR text, JSON, page maps, and scripts live **inside this repo** (`server_based/` and/or `page_based/`).
- Do **not** symlink to or depend on DataWarehouse / DataWharehouse (or any path outside this project).
- Do **not** put working copies of the diary app under `.../DRASTIC/external_processed/congressional` or similar warehouse trees.
- Paths in scripts must stay relative to the folder they live in (`HERE = …/server_based`).

## Structure

| Folder | Purpose |
|---|---|
| `server_based/` | Local version — run `bash start_search.sh` to serve on port 8765. Local `diary.pdf` + reparse/clean/page-map scripts. |
| `page_based/` | Static GitHub Pages version — self-contained, includes the PDF. |

Email/thread/timezone conventions for the data model: [`EMAILS.md`](EMAILS.md).

## Data

- **Source PDFs**: stored locally as `diary.pdf` (1,141 pp, ~63 MB), `diary-prequel.pdf` (465 pp, ~10 MB), and `diary-ebola.pdf` (26 pp, ~3 MB; short name for `2026.09.28_Ebola-Doc-Release_Full-Package.pdf`)
- **Parsed JSON**: 853 main-diary entries + 1,135 prequel entries + 28 ebola entries (2,016 total), each with date, raw_date, content, and source tag. Content has PDF line-breaks cleaned for reading.
- **Page Maps**: each entry mapped to its PDF content-start page (separate maps per release)

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
