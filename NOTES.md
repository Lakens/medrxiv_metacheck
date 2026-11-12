# medrxiv_metacheck: notes for continuing the work

These are the working notes for the people who maintain this project. The description for readers is in `README.md`.

This repository is a copy of `psyarxiv_metacheck` (made on 12 November 2026), with medRxiv as the source instead of PsyArXiv. Everything not listed below works as there; that repository's `NOTES.md` describes it (the report pages and their changes, the page of findings per check, the page of totals, the keys removed before saving, the watching, the publishing, the SURF server and how to deploy to it).

## What is different from psyarxiv_metacheck

- Source: medRxiv's listing service, `https://api.biorxiv.org/details/medrxiv/<first day>/<last day>/<cursor>` (30 preprint versions per page), and `.../details/medrxiv/<DOI>/na/json` for all versions of one preprint. The PDF comes from `https://www.medrxiv.org/content/<DOI>v<version>.full.pdf`. Tested on 12 November 2026: both answer GitHub's computers (run "Try a medRxiv download", `.github/workflows/try_download.yml`, which can go now).
- Names: a preprint version is named by its DOI after the slash with its version: `2026.04.04.26349881v2`. The oldest preprints (2019) have numbers without dots (`19000109v1`). medRxiv uses two DOI prefixes side by side (10.1101, and 10.64898 for newer preprints; in October 2026, 26 of 30 listed versions had 10.64898), so the DOI is stored with each preprint (in the queue, the index and the result). The report folders are found by the pattern `[0-9]*v[0-9]*` (update.py `REPORT_DIRS`, update.yml, pages.yml).
- Dates: medRxiv gives the day a version was posted, not the time. `list_new()` therefore lists the newest day listed again each time, leaving out the preprints already known; medRxiv's list is read at most every 2 minutes. The page of totals shows the day of the week preprints are posted, without the hour.
- Only PDFs: medRxiv gives every preprint as a PDF. Its size is known only after the download; one over 50 MB is skipped.
- Withdrawn: medRxiv marks a withdrawal with a new version of type `WITHDRAWN` (since 2024 its title also starts with "WITHDRAWN:"); the version before it may carry a "Withdrawal Statement" as its summary. Any of the three counts (`withdrawn()`). Checked on March 2023 and September 2024: 17 withdrawals in 2,714 listed versions.
- Licences (Daniel, 12 November 2026): the paper's full text is shown on the report page and stored in `data/papers/` only when its licence allows sharing (`OPEN_LICENCES`: cc_by, cc_by_nc, cc0, cc0_ng). For the others (cc_by_nd, cc_by_nc_nd, cc_no), `withhold_text()` replaces each sentence by its number of words (`words`; both `text` and `formatted`, which repeats the sentence in about 18% of sentences), and keeps of tables and figures only their numbers and places; `text_withheld: true` marks it. Kept: the title, the section headings, the references, the authors and affiliations, the links, the statistics found. In one sample of 30 versions, 15 had a licence that is not open. Still in the results: the sentences metacheck's checks quote (median 4% of a paper's longer sentences, at most 19%, measured on 100 PsyArXiv results), and, rarely, text the converter read as a reference.
- The licence, the medRxiv category and the corresponding author's institution are stored with each preprint (`preprint` in the result).
- Sharing the SURF server with psyarxiv_metacheck: each run sends a job only when the server is idle. After its own job ended, a run waits `REST_SECONDS` (60) before it counts the server as idle again, and a waiting run asks every `POLL_SECONDS` (15), so the two sites take turns. The server is also asked once more just before sending, after the PDF's download. psyarxiv_metacheck's `update.py` needs the same two numbers, or this site rarely gets a turn.
- The minutes of the schedules of `update.yml` and `watch.yml` differ from psyarxiv_metacheck's, so the two sites' runs do not start at the same moment.
- Started on 12 November 2026, after one real check on the SURF server (2026.10.26.26365902v2: 16 modules, no errors). At Daniel's request psyarxiv_metacheck's "Update the reports" and "Watch the runs" were switched off then (Actions tab), so medRxiv has the server to itself for now.
- The browser extension works on `www.medrxiv.org/content/<DOI>` pages.
- Not yet: storing the downloaded PDFs (and, if the SURF server can return them, the repository files) on Daniel's pCloud, `P:\metacheck_downloads\medrxiv`. `scripts/pcloud_login.py` gives the runs access once Daniel has a pCloud app (OAuth); the uploading itself is not written yet.

## How to continue

1. See the page: from the project folder run `python -m http.server 8765`, then open `http://127.0.0.1:8765/`.
2. Try the scheduled run without touching the site: `python scripts/update.py --max 1 --data-dir <a test folder> --site-dir <a test folder>` (copy `fonts/` and `images/` into that test folder first). It sends a real job to the SURF server.

## Open questions

- The page wording (title, intro, headings) is copied from psyarxiv_metacheck with PsyArXiv replaced by medRxiv; Daniel writes the final wording.
- The tally counts every version medRxiv lists once.
