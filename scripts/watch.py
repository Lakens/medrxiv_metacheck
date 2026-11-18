# Watches the runs that make the reports, and opens one GitHub issue for each
# kind of problem (a module error, preprints that failed for one reason, keys
# removed from results, a stopped run). A later case of the same kind becomes
# a comment on that issue while it is open; GitHub emails the repository's
# owner about each new issue and comment. Closing an issue means the problem
# is addressed: its cases are not reported again, and a new case of the same
# kind after that opens a new issue that links the earlier one. An issue about
# the runs themselves (switched off, stopped, no new report) is closed by the
# script when the problem is over. Run every six hours by
# .github/workflows/watch.yml; uses the gh program for GitHub.
#
#   python scripts/watch.py [--dry-run]   (--dry-run: print, change nothing)
#
# Kinds of problems:
#   - the workflow "Update the reports" is switched off, its last run failed,
#     no run has ended for STOPPED_HOURS, or a run has gone on longer than
#     its 180 minutes allow
#   - no new report for QUIET_HOURS
#   - a module that failed (traffic light "fail") in a stored report, one kind
#     per module and error message, one case per preprint
#   - preprints listed as failed in data/state.json (their job failed twice,
#     or GitHub refused the result), and new checks with the current
#     Metacheck that failed twice (rerun_failed; the earlier report stays),
#     one kind per reason
#   - keys removed from a result (the authors may want to know)
# What each issue reported is kept in the issue itself, in a line the issue
# page does not show. The single issue "Problems with the runs" of the earlier
# version of this script is kept as a record of what was reported before.

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

# ── This site ────────────────────────────────────────────────────────────────
REPO = os.environ.get("GITHUB_REPOSITORY", "Lakens/medrxiv_metacheck")
SITE = "https://lakens.github.io/medrxiv_metacheck/"
AGENT = "medrxiv_metacheck watch"


def preprint_link(osf_id, state):
    # the preprint's page on medRxiv, where its DOI is known
    dois = state.get("failed_doi") or {}
    if osf_id not in dois:
        return osf_id
    return f"[{osf_id}](https://www.medrxiv.org/content/{dois[osf_id]}v{osf_id.rpartition('v')[2]})"


def site_failures(state):
    # [(kind, title, case, text)] for the preprints this site lists as failed,
    # and for the new checks with the current Metacheck that failed (the
    # earlier report stays)
    out = []
    for osf_id, why in sorted((state.get("failed") or {}).items()):
        k = error_kind(why)
        out.append((f"failed:{k}", f"Preprints that failed and are not tried again: {k}",
                    osf_id, f"{preprint_link(osf_id, state)}: {why}"))
    for osf_id, why in sorted((state.get("rerun_failed") or {}).items()):
        k = error_kind(why)
        out.append((f"rerun-failed:{k}", f"New checks with the current Metacheck that failed: {k}",
                    osf_id, f"[{osf_id}]({SITE}{osf_id}/) (its earlier report stays): {why}"))
    return out
# ─────────────────────────────────────────────────────────────────────────────

SERVER = "https://metacheckserve.metacheck.src.surf-hosted.nl/api"
LABEL = "watch"
STOPPED_HOURS = 3
QUIET_HOURS = 24
LONG_RUN_HOURS = 4          # update.yml stops a run after 180 minutes
MARK = re.compile(r"<!-- watch (\{.*?\}) -->", re.S)              # one issue per kind
OLD_MARK = re.compile(r"<!-- watch-state (.*?) -->", re.S)        # the earlier single issue
KNOWN_MARK = re.compile(r"<!-- watch-known (.*?) -->", re.S)      # what it had reported
MAX_BODY = 60000                                                  # GitHub allows 65,536


def gh(*args, data=None):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", input=data)
    if r.returncode:
        raise RuntimeError(f"gh {' '.join(args[:2])}: {r.stderr.strip()}")
    return r.stdout


def api(path):
    return json.loads(gh("api", f"repos/{REPO}/{path}"))


def when(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def ago(t, now):
    h = (now - t).total_seconds() / 3600
    return f"{h:.0f} hours ago" if h >= 2 else f"{h * 60:.0f} minutes ago"


def short(t):
    return t.strftime("%Y-%m-%d %H:%M UTC")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def fingerprint(*parts):
    # a short fingerprint, which can stand in the hidden line whatever the
    # text contains
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def server():
    try:
        req = urllib.request.Request(f"{SERVER}/health", headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=30) as r:
            h = json.load(r)
        return (f"the server answers (Metacheck {h.get('metacheck_version')}; "
                f"{h.get('jobs_running')} running, {h.get('jobs_waiting')} waiting)")
    except Exception as e:
        return f"**the server does not answer** ({type(e).__name__})"


def error_kind(msg):
    # the error message without what differs from paper to paper (quoted
    # text, numbers, file names), so one bug gives one kind
    msg = re.sub(r"\s+", " ", msg or "the module failed").strip()
    msg = re.sub(r"(['\"`]).*?\1", "'…'", msg)
    msg = re.sub(r"\d+(?:\.\d+)?", "N", msg)
    return msg[:300]


def code(text):
    # text shown as code in the issue, on one line
    text = re.sub(r"\s+", " ", text).replace("`", "'")
    return f"`{text}`"


def run_problems(now, data_dir):
    # [(kind, title, case, text)] about the update runs; these issues are
    # closed by the script when the problem is over
    out = []
    wf = api("actions/workflows/update.yml")
    if wf["state"] != "active":
        out.append(("run:switched-off", 'The workflow "Update the reports" is switched off', "switched-off",
                    f'Its state is {wf["state"]}, so no run starts. Switch it on in the Actions tab '
                    '("..." menu, "Enable workflow").'))
    runs = api("actions/workflows/update.yml/runs?per_page=10")["workflow_runs"]
    going = [r for r in runs if r["status"] in ("in_progress", "queued", "waiting")]
    done = [r for r in runs if r["status"] == "completed"]
    for r in going:
        if now - when(r["run_started_at"]) > dt.timedelta(hours=LONG_RUN_HOURS):
            out.append(("run:long", "A run goes on longer than its 180 minutes allow", str(r["id"]),
                        f"[A run]({r['html_url']}) has been going since {short(when(r['run_started_at']))}."))
    last = done[0] if done else None
    if last and last["conclusion"] not in ("success", "cancelled", "skipped"):
        out.append(("run:failed", "The last update run failed", str(last["id"]),
                    f"[The last run]({last['html_url']}), which ended {short(when(last['updated_at']))}, "
                    f"ended with \"{last['conclusion']}\". A failed run does not start the next one; "
                    "GitHub's hourly timetable may restart them."))
    if not going and last and now - when(last["updated_at"]) > dt.timedelta(hours=STOPPED_HOURS):
        out.append(("run:none", "No update run is going", str(last["id"]),
                    f"No run is going, and the last one ended {ago(when(last['updated_at']), now)} "
                    f"({short(when(last['updated_at']))})."))
    index = load(os.path.join(data_dir, "index.json"), {"papers": []})["papers"]
    state = load(os.path.join(data_dir, "state.json"), {})
    newest = max((when(p["checked"]) for p in index if p.get("checked")), default=None)
    if newest and now - newest > dt.timedelta(hours=QUIET_HOURS):
        out.append(("run:quiet", f"No new report for {QUIET_HOURS} hours", newest.isoformat(),
                    f"No new report for {ago(newest, now)} (the last was made {short(newest)}). "
                    f"{len(state.get('queue', []))} preprints are waiting; {server()}."))
    return out


INNER = re.compile(r"^(Running the module \S+ produced errors: )+")


def module_failures(data_dir):
    # [(kind, title, case, text)]: one kind per error, one case per preprint.
    # A module that runs another fails with that one's error ("Running the
    # module 'codebook_check' produced errors: Running the module 'data_check'
    # produced errors: ..."), so the error is taken without those openings and
    # one bug is one kind, whichever modules it stopped
    index = load(os.path.join(data_dir, "index.json"), {"papers": []})["papers"]
    out = []
    for p in index:
        failed = [k for k, light in (p.get("lights") or {}).items() if light == "fail"]
        if not failed:
            continue
        rec = load(os.path.join(data_dir, "papers", p["id"] + ".json"), {})
        reports = {e.get("module"): e.get("report") for e in rec.get("errors") or []}
        by_error = {}
        for mod in failed:
            msg = reports.get(mod) or (rec.get("modules", {}).get(mod) or {}).get("report") or ""
            inner = INNER.sub("", re.sub(r"\s+", " ", msg).strip())
            by_error.setdefault(error_kind(inner), (inner, []))[1].append(mod)
        for k, (inner, mods) in by_error.items():
            out.append((f"module:{k}", f"Modules fail: {k[:150]}", p["id"],
                        f"[{p['id']}]({SITE}{p['id']}/), {', '.join(sorted(mods))} "
                        f"(Metacheck {rec.get('metacheck_version') or '?'}): {code(inner[:500])}"))
    return out


def keys_removed(data_dir):
    out = []
    for path in sorted(glob.glob(os.path.join(data_dir, "papers", "*.json"))):
        with open(path, encoding="utf-8") as f:
            head = f.read(200000)         # keys_removed stands near the top
        m = re.search(r'"keys_removed": (\{[^}]*\})', head)
        if m and m.group(1) != "{}":
            osf_id = os.path.basename(path)[:-5]
            out.append(("keys", "Keys were removed from results (the authors may want to know)", osf_id,
                        f"[{osf_id}]({SITE}{osf_id}/): {json.loads(m.group(1))}"))
    return out


def problems_now(data_dir, now):
    # {kind: {"title", "auto", "cases": {case: text}}}
    state = load(os.path.join(data_dir, "state.json"), {})
    found = (run_problems(now, data_dir) + module_failures(data_dir) + site_failures(state)
             + keys_removed(data_dir))
    kinds = {}
    for kind, title, case, text in found:
        k = kinds.setdefault(kind, {"title": title, "auto": kind.startswith("run:"), "cases": {}})
        k["cases"][case] = text
    return kinds


def issue_body(title, intro, cases, auto, kind_fp, case_fps, earlier=None):
    lines = [intro, ""]
    if earlier:
        lines += [f"This kind of problem was reported before in #{earlier}, which was closed.", ""]
    shown, size = [], 0
    for t in cases:
        if size > MAX_BODY - 2000:
            shown.append(f"… and {len(cases) - len(shown)} more (see the comments)")
            break
        shown.append(f"- {t}")
        size += len(t)
    lines += shown + [""]
    lines += ["_Opened by `scripts/watch.py` (workflow \"Watch the runs\"). "
              + ("It closes this issue when the problem is over._" if auto else
                 "Close this issue when the problem is addressed: its cases are not reported again, "
                 "and a new case of this kind after that opens a new issue._")]
    hidden = json.dumps({"kind": kind_fp, "auto": auto, "cases": sorted(case_fps)})
    return "\n".join(lines) + f"\n\n<!-- watch {hidden} -->\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--dry-run", action="store_true", help="print what would be done; change nothing")
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    kinds = problems_now(args.data_dir, now)

    issues = json.loads(gh("issue", "list", "-R", REPO, "--label", LABEL, "--state", "all",
                           "--limit", "1000", "--json", "number,state,title,body"))
    reported = {}      # kind fingerprint -> case fingerprints in any issue of it
    open_issue = {}    # kind fingerprint -> its open issue
    latest = {}        # kind fingerprint -> number of its latest issue
    known = set()      # case fingerprints the earlier single issue had reported
    legacy = None
    for iss in sorted(issues, key=lambda i: i["number"]):
        m = MARK.search(iss["body"] or "")
        if m:
            meta = json.loads(m.group(1))
            reported.setdefault(meta["kind"], set()).update(meta["cases"])
            latest[meta["kind"]] = iss["number"]
            if iss["state"] == "OPEN":
                open_issue[meta["kind"]] = dict(iss, meta=meta)
        elif OLD_MARK.search(iss["body"] or "") or KNOWN_MARK.search(iss["body"] or ""):
            legacy = iss
            km = KNOWN_MARK.search(iss["body"])
            if km:
                known.update(json.loads(km.group(1)))

    actions = []
    # The first run after the change: every problem the earlier single issue
    # lists now counts as reported, and it says so; closing it is left to you
    if legacy and not KNOWN_MARK.search(legacy["body"]):
        all_cases = sorted(fingerprint(kind, case) for kind, k in kinds.items() for case in k["cases"])
        known.update(all_cases)
        note = ("\n\n**This issue is no longer kept up to date.** `scripts/watch.py` now opens one issue "
                "for each kind of problem. Everything listed here counts as reported and will not come "
                "back as a new issue; close this issue when you like.\n")
        body = OLD_MARK.sub("", legacy["body"]).rstrip() + note + f"\n<!-- watch-known {json.dumps(all_cases)} -->\n"
        actions.append(("edit", str(legacy["number"]), body,
                        f"#{legacy['number']}: marked {len(all_cases)} current cases as reported"))

    for kind, k in sorted(kinds.items()):
        kind_fp = fingerprint(kind)
        cases = {fingerprint(kind, c): t for c, t in k["cases"].items()}
        seen = reported.get(kind_fp, set()) | known
        new = {fp: t for fp, t in cases.items() if fp not in seen}
        if not new:
            continue
        if kind_fp in open_issue:
            iss = open_issue[kind_fp]
            all_fps = set(iss["meta"]["cases"]) | set(new)
            body = MARK.sub(f"<!-- watch {json.dumps(dict(iss['meta'], cases=sorted(all_fps)))} -->", iss["body"])
            actions.append(("comment", str(iss["number"]), "New:\n\n" + "\n".join(f"- {t}" for t in new.values()),
                            f"#{iss['number']} ({k['title']}): {len(new)} new case(s)"))
            actions.append(("edit", str(iss["number"]), body, None))
        else:
            earlier = latest.get(kind_fp)
            intro = (f"**{k['title']}**" if k["auto"] else
                     f"**{k['title']}** ({len(new)} case{'s' if len(new) != 1 else ''})")
            body = issue_body(k["title"], intro, list(new.values()), k["auto"], kind_fp, new.keys(), earlier)
            title = k["title"] if len(k["title"]) <= 200 else k["title"][:197] + "…"
            actions.append(("create", title, body, f"new issue: {title} ({len(new)} case(s))"))

    # an issue about the runs whose problem is over is closed
    for kind_fp, iss in open_issue.items():
        if iss["meta"].get("auto") and kind_fp not in {fingerprint(kd) for kd in kinds}:
            actions.append(("close", str(iss["number"]), "The problem is over.", f"#{iss['number']}: closed, over"))

    if args.dry_run:
        for what, target, text, label in actions:
            if label:
                print(f"- {label}")
        for what, target, text, label in actions:
            if what == "create":
                print(f"\n===== would open: {target}\n{text}")
        if not actions:
            print("Nothing new.")
        return
    for what, target, text, label in actions:
        if what == "create":
            try:
                gh("label", "create", LABEL, "-R", REPO, "--description", "Kept by scripts/watch.py",
                   "--color", "B60205")
            except RuntimeError:
                pass                                    # it exists already
            gh("issue", "create", "-R", REPO, "--title", target, "--label", LABEL, "--body-file", "-", data=text)
        elif what == "comment":
            gh("issue", "comment", target, "-R", REPO, "--body-file", "-", data=text)
        elif what == "edit":
            gh("issue", "edit", target, "-R", REPO, "--body-file", "-", data=text)
        elif what == "close":
            gh("issue", "close", target, "-R", REPO, "--comment", text)
        if label:
            print(label)
    if not actions:
        print("Nothing new.")


if __name__ == "__main__":
    sys.exit(main())
