# Handling emails, threads and mixed sources

How this app models **non-diary documents** — email messages above all — so that
diary entries, emails, and (later) Twitter/Bluesky threads or exported chat
messages can live on one timeline and be read in order.

Read this before adding a release that contains emails, or before wiring up a
new kind of source.

---

## 1. One document per entry

An entry is a single unit of authorship at a single instant. Never paste a whole
mail thread into one entry:

| Kind | Meaning | Timeline | Card badge |
|---|---|---|---|
| `diary` (default) | A diary day (`March 3, 2016`) | yes | none |
| `email` | One email message, one author, one timestamp | yes | ✉ email |
| `report` | Attached/standalone document with no single author-instant (e.g. the NIAID filovirus overview) | no (sorted last) | 📄 report |
| `prologue` | Release cover sheet / intro with no date header (prequel) | no (sorted first) | — |

**An email entry contains only what its author wrote in that message** — no
quoted history, no forwarded bodies. The messages it answers are separate
entries, reached through reply links (§4). This is what makes "the text written
that day" trustworthy when you cite it.

## 2. Splitting a thread into messages

In a PDF there is no thread metadata, only text. Start a new entry at every:

1. **Outer header** — `From:` … with an RFC2822 date, i.e. a `Date:` line
   matching `^\w{3},\s*\d{1,2}\s+\w{3}\s+\d{4}\s+\d{1,2}:\d{2}`.
   Two stamp styles appear in these releases: RFC2822
   (`Date: Thu, 10 Mar 2016 06:13:36 -0500`) and Outlook
   (`Sent: Wednesday, March 09, 2016 11:41 PM`).
2. **Nested header** — a `From:` block using `Sent:` (a quoted reply inside the
   outer message). It becomes its own entry too.
3. **Inline quote marker** — `On Mar 10, 2016, at 1:29 AM, Fauci, Anthony …
   wrote:` (optionally `>`-prefixed, sometimes wrapped over 2–3 lines). These
   carry no header block, so recover them: the marker supplies the author and
   the instant, the following lines are the body. Flag them in the entry with
   `date_note` = "Recovered from an inline quote (no full header in the
   release)". Without this, chain links would have no target and a message's
   words would silently sit inside someone else's entry.

Stop each message's body at the **next** boundary of any of those three kinds.

Practical rules learned from the Ebola release:

- pypdf sometimes splits a header keyword itself: `Fro` + `m: Lane, Cliff…`,
  `Sub` + `ject: FW: …`. Rejoin for **parsing only** (`_join_header_breaks`) and
  use the same rejoined lines when measuring page offsets.
- Only `From`/`To`/`Cc`/`Bcc` values may continue on following lines; `Subject`,
  `Sent`/`Date` and `Importance` are terminal — the first non-field line after
  them is the body. This is what stops the header block swallowing the body.
- Strip X.500/Exchange DN noise from addresses (`</O=NIH/OU=NIHEXCHANGE/CN=…>`).
- Strip the release's own furniture before parsing (`Released by Chairman Rand
  Paul`, `--- Page N ---`, Bates numbers, `EXCERPT FROM FAUCI'S NOTES`).

## 3. Time zones — the part that breaks chronology

**A reply must never appear to answer a message from its own future.** The naive
stamps in the Ebola release do exactly that: Lane's "Wednesday, March 09, 2016
11:41 PM" quotes Fauci's "Mar 10, 2016, at 1:29 AM".

Rules:

1. **RFC2822 `Date:` headers are authoritative** — they carry the offset
   (`-0500`). Trust them; never re-zone them.
2. **`Sent:` and inline-quote stamps carry no zone.** Default them to
   `America/New_York` (the NIH/NIAID senders' base) and record that the zone was
   *assumed*.
3. **Override the default only with evidence, and write the evidence down.**
   Keep an explicit table at the top of the parser:

   ```python
   ZONE_ASSUMPTIONS = {
       ("2016-03-09", "1911", "Hello from France"):     "Europe/Paris",
       ("2016-03-09", "2341", "Re: Hello from France"): "America/Los_Angeles",
   }
   ```

   | Case | Evidence |
   |---|---|
   | Nelson Michael, Mar 9 19:11 → **CET** | His own subject is literally "Hello from France" |
   | Lane, Mar 9 23:41 → **PT** | His message quotes Fauci's Mar 10 01:29; the diary proves Fauci was in Washington that night (NIH Clinical Center acupuncture, the 260-reporter telebriefing), so Fauci's stamps are ET. For Lane's reply to postdate it his clock must be west of ET — and his very next line is "Just landed in San Francisco" |

   Working: `19:11 CET = 13:11 ET` → `01:29 ET` → `23:41 PT = 02:41 ET (Mar 10)`
   → `06:13 ET`. Monotonic.

4. **Normalise everything to New York time and store both stamps:**
   - `date` / `time` = ET date (`YYYY-MM-DD`) and `HHMM`. ET orders entries,
     groups them on the timeline, and forms the entry key.
   - `raw_date` = human label showing local **and** ET, e.g.
     `23:41 PT Mar 9 → 02:41 ET · Re: Hello from France`, or simply
     `06:13 ET · RE: Hello from France` when the message was already ET.
   - The card's printed header line repeats it, e.g.
     `Sent: Wednesday, March 09, 2016 11:41 PM PT (assumed) → 02:41 ET (Mar 10)`.
5. **Verify monotonicity**: after generating, assert that every `reply_to`
   target is *earlier in ET* than the entry pointing at it. Two messages stamped
   the same minute (`15:58`) are the only permitted tie.
6. Use `zoneinfo` (stdlib), not fixed offsets, so DST is handled — US DST began
   13 Mar 2016, inside this very thread (`-0500` before, `-0400` after).

## 4. Threading: links in both directions

### Upward — what THIS message points at

A new **outer** header starts a thread; the quoted messages below it (nested
headers, inline quotes) are its history, in document order (newest first). Each
message links to the next one down the chain, and the link's kind follows the
subject prefix:

| Subject of this message | Up-link fields | Card footer shows |
|---|---|---|
| starts with `FW:` / `Fwd:` | `forwarded_from` + `forwarded_from_label` | ↪ Forwarding: … |
| anything else (incl. `RE:`, inline quotes) | `reply_to` + `reply_to_label` | ↩ In reply to: … |
| message carries a released document | `attachment_ref` + `attachment_label` | 📎 Attachment: … |

### Downward — what points AT this message

Every up-link is inverted into **arrays** (never a single value):

| Field | Inverse of | Card footer shows |
|---|---|---|
| `replied_by` = `[{key, label}, …]` | `reply_to` | ↩ Replied by: … · … |
| `forwarded_by` = `[{key, label}, …]` | `forwarded_from` | ↪ Forwarded by: … · … |
| `attached_by` = `[{key, label}, …]` | `attachment_ref` | 📎 Referenced by: … |

**Why arrays:** the same email can be picked up later and replied to *and*
forwarded again — several times, in several threads, even from a different
release/source. One entry may legitimately hold two `replied_by` entries and a
`forwarded_by` entry at once; the UI renders them as `· `-separated links.

Two places build these:

1. **The parser** (`link_thread()` in `reparse_ebola.py`) inverts within its own
   release, so the JSON is self-describing for consumers of the raw data.
2. **The app** (`rebuildThreadDownLinks()` in `index.html`, called from
   `loadData`) re-inverts across **all merged sources** at load time. This is
   what makes cross-source links work: a future release (or Twitter source)
   that quotes a 2016 email automatically fills that email's `replied_by` /
   `forwarded_by` with no parser change. It rebuilds from scratch each load
   (JSON-supplied arrays are discarded, never doubled up).

Downward keys are **source-qualified** — `"ebola|2016-03-10|06:13 ET · …"` —
because `date|raw_date` labels could collide across releases; upward keys stay
plain (`date|raw_date`) since a parser only ever links within its own dataset.
`openEntryRef()` accepts both forms (a plain first segment that isn't a source
name is treated as an unqualified key).

`report`/`prologue` entries sit outside threads but can still receive downward
links — the NIAID report is `attached_by` Kurilla's "Ebola report you requested"
email.

Boundaries: `report`/`prologue` entries end/stand outside threads; inline
messages participate like any other message.

## 6. Entry shape

```json
{
  "date": "2016-03-10",
  "time": "0241",
  "kind": "email",
  "raw_date": "23:41 PT Mar 9 → 02:41 ET · Re: Hello from France",
  "content": "From: Lane, Cliff (NIH/NIAID) [E]\n\nTo: …\n\nSubject: …\n\nSent: …\n\n----------\n\nI am guessing the NSC meeting on Ebola vaccine.",
  "reply_to": "2016-03-10|01:29 ET · Fauci (inline quote)",
  "reply_to_label": "2016-03-10 01:29 ET · Fauci (inline quote)",
  "replied_by": [
    { "key": "ebola|2016-03-10|06:13 ET · RE: Hello from France",
      "label": "2016-03-10 06:13 ET · RE: Hello from France" }
  ],
  "forwarded_from": "…", "forwarded_from_label": "…",
  "forwarded_by": [ { "key": "…", "label": "…" } ],
  "date_note": "…",
  "source": "ebola"
}
```

`forwarded_from`/`forwarded_by`/`attachment_ref`/`attached_by` appear only when
relevant (see §4); `replied_by` and friends are always arrays.
`content` is the printable document: one header field per line, a `----------`
separator, then the body. Keeping the header inside `content` (rather than only
in side fields) means **From/To/Subject stay searchable and highlightable**, and
the page map keeps working unchanged. The UI splits on the separator to render
the header block and the body differently.

## 7. Adding an email-bearing release

1. Extract text with page markers: `--- Page N ---`.
2. `reparse_<source>.py`, modelled on `reparse_ebola.py`:
   - strip release furniture; rejoin split header keywords;
   - segment diary days, then every email message, then the report;
   - resolve stamps, apply `ZONE_ASSUMPTIONS`, normalise to ET;
   - build `content` (header block + `----------` + body) and the `reply_to*`
     and `attachment_*` links;
   - write `*_fixed.json`.
3. `clean_<source>_breaks.py` — collapse PDF line wraps (blank lines are the
   paragraph breaks, which is what preserves the email header block).
4. `regen_<source>_page_map.py` — import the parser, emit
   `{"start","end","breaks"}`, assert keys and content equality.
5. Append the steps to `server_based/start_search.sh`, list the files in
   `server_based/README.md`, and copy JSON + page map into `page_based/`.
6. Register the source in `index.html` (`SOURCES`): `json`, `pageMap`, `pdf`,
   `label`, `badge`, `badgeTitle`.
7. Checks: entry counts per kind; ET-sorted order; every `reply_to` target
   earlier in ET; every key present in the page map; page-map assertion passes;
   walk one thread end-to-end in the browser.

## 8. Adding other source types (Twitter/X, Bluesky, Slack/Signal exports…)

The model above is source-agnostic: it only assumes *one authoring instant per
entry* plus *an optional link to an earlier entry*. To add a feed:

- One entry per post/comment, with `kind` (`tweet`, `post`, `message`, …), an
  ET-normalised `date`/`time`, and a `raw_date` that shows local **and** ET when
  the platform exposes another zone.
- Use `reply_to` / `reply_to_label` for reply chains, `attachment_ref` for
  attached media or released documents, and add a `quote_*` pair only if you
  need quote-posts as a distinct relation.
- Add a `SOURCES` entry. If the source has **no page images**, omit `pdf` and
  ship an empty `<source>_page_map.json` (`{}`); clicking those results then
  leaves the current PDF where it is. The background PDF loader, `switchPdfSource()`
  and result selection all skip `pdf`-less sources — no other code change.
- Reuse the key discipline (`date|raw_date`, unique per source) and the
  content-equality page-map step, so hit→page jumps stay exact.

Until a source's own time-zone handling is settled, apply §3 verbatim: explicit
offsets win, otherwise assume ET, override only with written-down evidence, and
always show both stamps.

