"""Add one CI run's report to the report site (the gh-pages checkout).

The site is public. Each run gets runs/<run>-<suite>/ with the runner's HTML
report (index.html), its JSON (report.json) and the videos the report plays.
Videos of tests that type the test phone number / OTP are not published:
their player is replaced by a note (the video stays in the run's artifacts).
The newest runs keep their videos, up to KEEP_VIDEO_RUNS runs and
VIDEO_BUDGET_MB in all (GitHub Pages sites are capped at 1 GB); older runs
keep their report page. Debug logs are never published. Finally the index page
listing every run is rebuilt.

Environment: RUN, SUITE, BRANCH, TRIGGER, RUN_URL, BUNDLE (the downloaded
full report bundle), SITE (gh-pages checkout), FLOWS (repo root holding
flows/ and helpers/), KEEP_VIDEO_RUNS (default 10), VIDEO_BUDGET_MB
(default 500).
"""
import glob
import html
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone

ENV = os.environ
RUN, SUITE = ENV["RUN"], ENV["SUITE"]
BUNDLE, SITE, FLOWS = ENV["BUNDLE"], ENV["SITE"], ENV.get("FLOWS", ".")
KEEP_VIDEO_RUNS = int(ENV.get("KEEP_VIDEO_RUNS", "10"))
VIDEO_BUDGET = int(ENV.get("VIDEO_BUDGET_MB", "500")) * 1024 * 1024

VIDEO_TAG = re.compile(r'<video[^>]*\bsrc="([^"]+\.mp4)"[^>]*>\s*</video>')
NOTE = ('<div style="max-width:320px;padding:8px;border:1px dashed #bbb;'
        'border-radius:4px;font-size:12px;color:#555">{}</div>')
PRIVATE_NOTE = NOTE.format("Video not published (shows the test phone number). "
                           "It's in the run's Artifacts on GitHub.")
PRUNED_NOTE = NOTE.format("Video no longer kept (only the most recent runs keep "
                          "their videos). It may still be in the run's Artifacts on GitHub.")


def private_tests():
    """File prefixes (TC_07_account_lifecycle_) of flows that type the test
    phone number or OTP, directly or through full_signup.yaml."""
    typing = re.compile(r"full_signup\.yaml|inputText:.*\$\{(PHONE_NUMBER|NEW_PHONE_NUMBER|OTP_CODE)\}")
    prefixes = []
    for path in glob.glob(os.path.join(FLOWS, "flows", "*", "TC_*.yaml")):
        if typing.search(open(path, encoding="utf-8").read()):
            prefixes.append(os.path.basename(path)[:-len(".yaml")] + "_")
    return prefixes


def add_run():
    folder = os.path.join(SITE, "runs", f"{RUN}-{SUITE}")
    os.makedirs(folder, exist_ok=True)
    reports = sorted(glob.glob(os.path.join(BUNDLE, "FarmerChat_*_Test_Report_*.html")))
    summary = {}
    if not reports:
        open(os.path.join(folder, "index.html"), "w").write(
            f"<h1>No report for run #{RUN}</h1><p>The run ended before a report was written.</p>")
    else:
        page = open(reports[-1], encoding="utf-8").read()
        private = private_tests()

        def video(match):
            src = match.group(1)
            name = os.path.basename(src)
            if any(name.startswith(p) for p in private):
                return PRIVATE_NOTE
            source = os.path.join(BUNDLE, src)
            if not os.path.exists(source):
                return match.group(0)
            os.makedirs(os.path.join(folder, os.path.dirname(src)), exist_ok=True)
            shutil.copy(source, os.path.join(folder, src))
            return match.group(0)

        page = VIDEO_TAG.sub(video, page)
        open(os.path.join(folder, "index.html"), "w", encoding="utf-8").write(page)
        js = reports[-1][:-len(".html")] + ".json"
        if os.path.exists(js):
            shutil.copy(js, os.path.join(folder, "report.json"))
            summary = json.load(open(js)).get("summary", {})

    ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    json.dump({
        "run": int(RUN), "suite": SUITE, "branch": ENV.get("BRANCH", ""),
        "trigger": ENV.get("TRIGGER", ""), "url": ENV.get("RUN_URL", ""),
        "date": ist.strftime("%d %b %Y, %H:%M IST"), "summary": summary,
    }, open(os.path.join(folder, "meta.json"), "w"))


def load_runs():
    runs = []
    for meta in glob.glob(os.path.join(SITE, "runs", "*", "meta.json")):
        d = json.load(open(meta))
        d["dir"] = os.path.dirname(meta)
        runs.append(d)
    return sorted(runs, key=lambda d: d["run"], reverse=True)


def prune_videos(runs):
    """Newest first, runs keep their videos until KEEP_VIDEO_RUNS runs or the
    size budget is reached (the newest run always keeps its own). Older runs
    keep their page; their videos are removed."""
    used = 0
    for i, d in enumerate(runs):
        videos = glob.glob(os.path.join(d["dir"], "**", "*.mp4"), recursive=True)
        size = sum(os.path.getsize(v) for v in videos)
        if i == 0 or (i < KEEP_VIDEO_RUNS and used + size <= VIDEO_BUDGET):
            used += size
            continue
        if not videos:
            continue
        for v in videos:
            os.remove(v)
        index = os.path.join(d["dir"], "index.html")
        page = open(index, encoding="utf-8").read()
        open(index, "w", encoding="utf-8").write(VIDEO_TAG.sub(PRUNED_NOTE, page))


def write_index(runs):
    e = html.escape
    rows = []
    for d in runs:
        s = d.get("summary") or {}
        if s:
            failed = s.get("failed", 0)
            result = f"{s.get('passed', 0)}/{s.get('total', 0)} passed" + (f", {failed} failed" if failed else "")
            colour = "#b42318" if failed else "#067647"
        else:
            result, colour = "no report", "#667085"
        path = os.path.basename(d["dir"])
        rows.append(
            f"<tr><td><a href='runs/{e(path)}/'>#{d['run']}</a></td><td>{e(d['date'])}</td>"
            f"<td>{e(d['suite'])}</td><td>{e(d['branch'])}</td><td>{e(d['trigger'])}</td>"
            f"<td style='color:{colour}'>{e(result)}</td><td><a href='{e(d['url'])}'>run</a></td></tr>")
    open(os.path.join(SITE, "index.html"), "w").write(
        "<!doctype html><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>FarmerChat test reports</title>"
        "<style>body{font-family:system-ui,sans-serif;margin:24px;color:#101828}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{text-align:left;padding:8px;border-bottom:1px solid #eaecf0}"
        "th{background:#f9fafb}</style>"
        "<h1>FarmerChat test reports</h1>"
        "<p>One row per CI run, newest first. The most recent runs keep their videos; "
        "videos that show the test phone number, and all debug logs, are only in each run's "
        "Artifacts on GitHub (link in the last column).</p>"
        "<table><tr><th>Run</th><th>Date</th><th>Suite</th><th>Branch</th>"
        "<th>Trigger</th><th>Result</th><th>GitHub</th></tr>" + "".join(rows) + "</table>")


add_run()
runs = load_runs()
prune_videos(runs)
write_index(runs)
