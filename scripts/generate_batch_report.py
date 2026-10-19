#!/usr/bin/env python3
"""Build an HTML page for one test batch from its latest review runs.

Usage:  python3 scripts/generate_batch_report.py [batch]      (default: smoke)

Reads, per flow in flows/<batch>/:
  - the YAML front-matter (name, priority, description, tags, requires)
  - the latest run under reports/review/<batch>/<flow>/ (run.log + Maestro's
    maestro.log) for pass/fail, duration, step timings and the failure reason
  - videos in reports/recordings/<batch>/<flow>[_partN].mp4
and writes two pages — version from app.apk, device from the phone that ran the
tests, date of the latest run:
  reports/FarmerChat_<Batch>_v<version>_<device>_<date>.html          detailed
  reports/FarmerChat_<Batch>_v<version>_<device>_<date>_summary.html  shareable
The summary has no videos or screenshots, so it can go to stakeholders. Long
digit runs (e.g. a typed phone number) are masked in both.
Videos are linked, not embedded, so the page stays small and nothing leaves the
machine.
"""
import glob
import html
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH = sys.argv[1] if len(sys.argv) > 1 else "smoke"
REPORTS = os.path.join(REPO, "reports")
BATCH_LABEL = "".join(w.capitalize() for w in BATCH.split("_"))   # settings_help → SettingsHelp

LINE = re.compile(r"^(\d\d:\d\d:\d\d\.\d{3}) \[[^\]]*\] [^:]*: (.*) (RUNNING|COMPLETED|FAILED|SKIPPED|WARNED)$")


def front_matter(path):
    head = open(path, encoding="utf-8").read().split("\n---\n", 1)[0]
    def meta(key):
        m = re.search(rf"^#\s*{key}:\s*(.+)$", head, re.M)
        return m.group(1).strip() if m else ""
    name = re.search(r'^name:\s*"(.*)"\s*$', head, re.M)
    name = name.group(1).replace('\\"', '"') if name else os.path.basename(path)
    tid, _, title = name.partition(" - ")
    tags = re.findall(r"^\s+-\s+(\S+)\s*$", head.split("tags:", 1)[1], re.M) if "tags:" in head else []
    return {"id": tid, "title": title or name, "priority": meta("priority") or "P1",
            "description": meta("description"), "requires": meta("requires"), "tags": tags,
            "pid": meta("id"), "quarantine": meta("quarantine")}


def mask(text):
    """Hide long digit runs (phone numbers, OTPs typed by sign-up steps)."""
    return re.sub(r"\d{6,}", "••••••", text)


def secs(t):
    return datetime.strptime(t, "%H:%M:%S.%f")


def fmt(sec):
    sec = int(round(sec))
    return f"{sec // 60}m {sec % 60:02d}s" if sec >= 60 else f"{sec}s"


def parse_run(stem):
    """Latest run of a flow → status, duration, top-level steps, failure."""
    d = os.path.join(REPORTS, "review", BATCH, stem)
    logs = sorted(glob.glob(os.path.join(d, ".maestro", "tests", "*", "maestro.log")))
    if not logs:
        return None
    log = logs[-1]
    run_dir = os.path.basename(os.path.dirname(log))
    events = []
    for raw in open(log, encoding="utf-8", errors="replace"):
        m = LINE.match(raw.rstrip("\n"))
        if m:
            events.append(m.groups())
    if not events:
        return None
    # Rebuild the top-level step list: nested commands sit between their
    # parent's RUNNING and its terminal state.
    steps, stack = [], []
    for ts, label, state in events:
        if state == "RUNNING":
            stack.append((ts, label))
            continue
        start = ts
        for i in range(len(stack) - 1, -1, -1):
            if stack[i][1] == label:
                start = stack[i][0]
                del stack[i:]
                break
        if not stack and not label.startswith(("Apply configuration", "Define variables")):
            steps.append({"label": mask(label), "state": state,
                          "dur": (secs(ts) - secs(start)).total_seconds()})
    first, last = secs(events[0][0]), secs(events[-1][0])
    duration = (last - first).total_seconds()

    run_log = os.path.join(d, "run.log")
    text = open(run_log, encoding="utf-8", errors="replace").read() if os.path.exists(run_log) else ""
    failed = any(s["state"] == "FAILED" for s in steps) or bool(re.search(r"\.\.\. FAILED", text))
    failure = None
    if failed:
        # Innermost failing command = the YAML step that failed; the
        # message is Maestro's explanation printed right after it.
        fails = [l for l in text.splitlines() if l.rstrip().endswith("FAILED")]
        step = re.sub(r"\.*\s*FAILED$", "", fails[0].strip()) if fails else "Unknown step"
        msg = ""
        m = re.search(r"\n\n((?:Element not found|Assertion is false|No visible element|.*Exception)[^\n]*)", text)
        if m:
            msg = m.group(1).strip()
        failure = {"step": mask(step), "message": mask(msg)}
    shots = sorted(glob.glob(os.path.join(os.path.dirname(log), "screenshot-❌-*.png")))
    log_text = open(log, encoding="utf-8", errors="replace").read()
    sel = re.search(r"Selected device (\S+)", log_text)
    # Answer latencies logged by helpers/wait_for_answer.yaml, and soft checks
    # (optional asserts labelled "soft check") that didn't hold.
    latency = {}
    for name, ms in re.findall(r"\[ANSWER-LATENCY\] (\w+?)_ms=(\d+)", log_text):
        latency[name] = int(ms)
    warnings = sorted({mask(l) for _, l, st in events if st == "WARNED" and "soft check" in l})
    # Notes the flow printed itself (console.log '[NOTE] …'), e.g. a part of
    # the journey that couldn't be exercised this run. Only real console
    # output counts — the command definitions are logged too, even when
    # their branch is skipped.
    for line in log_text.splitlines():
        if "JsConsole" in line:
            m = re.search(r"\[NOTE\] (.+?)\s*$", line)
            if m:
                warnings.append(mask(m.group(1)))
    dev_file = os.path.join(d, "device.txt")
    saved = tuple((open(dev_file).read().splitlines() + ["", ""])[:2]) if os.path.exists(dev_file) else None
    return {"serial": sel.group(1) if sel else "", "saved_device": saved,
            "status": "FAIL" if failed else "PASS", "duration": duration, "steps": steps,
            "failure": failure, "run": run_dir, "latency": latency, "warnings": warnings,
            "shot": os.path.relpath(shots[-1], REPORTS) if shots else None}


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def app_version():
    """versionName of app.apk via aapt2 from the Android SDK, if available."""
    sdk = os.environ.get("ANDROID_HOME") or os.path.expanduser("~/Library/Android/sdk")
    tools = sorted(glob.glob(os.path.join(sdk, "build-tools", "*", "aapt2"))) or [shutil.which("aapt2") or ""]
    out = sh([tools[-1], "dump", "badging", os.path.join(REPO, "app.apk")]) if tools[-1] else ""
    m = re.search(r"versionName='([^']+)'", out)
    return m.group(1) if m else "unknown"


def device_name(serial, saved=None):
    """Readable model of the device that ran the tests, e.g. 'Vivo1919'.
    Prefers the device.txt saved with the run (manufacturer, model), then adb."""
    maker, model = saved or ("", "")
    if not model and serial:
        maker = sh(["adb", "-s", serial, "shell", "getprop", "ro.product.manufacturer"])
        model = sh(["adb", "-s", serial, "shell", "getprop", "ro.product.model"])
    if not serial and not model:
        return "UnknownDevice"
    if not model:
        return re.sub(r"\W", "", serial)          # device not connected → serial
    name = model if maker.lower() in model.lower() else f"{maker} {model}"
    return "".join(w[:1].upper() + w[1:] for w in re.split(r"[^A-Za-z0-9]+", name) if w)


def videos(stem):
    vids = sorted(glob.glob(os.path.join(REPORTS, "recordings", BATCH, f"{stem}*.mp4")))
    return [os.path.relpath(v, REPORTS) for v in vids
            if re.fullmatch(rf"{re.escape(stem)}(_part\d+)?\.mp4", os.path.basename(v))]


rows = []
for path in sorted(glob.glob(os.path.join(REPO, "flows", BATCH, "TC_*.yaml"))):
    stem = os.path.splitext(os.path.basename(path))[0]
    meta = front_matter(path)
    run = parse_run(stem)
    # A run older than the flow's last edit tested a different version of
    # the test — don't count it as this test's result.
    stale = None
    if run:
        ran_at = datetime.strptime(run["run"][:17], "%Y-%m-%d_%H%M%S").timestamp()
        if os.path.getmtime(path) > ran_at:
            stale, run = run["run"], None
    meta["stale"] = stale
    rows.append({"stem": stem, "file": os.path.relpath(path, REPO), **meta, "run": run, "videos": videos(stem)})

runs = [r["run"] for r in rows if r["run"]]
latest = max((r["run"] for r in runs), default="")             # run dir: YYYY-MM-DD_HHMMSS
run_date = latest[:10] or datetime.now().strftime("%Y-%m-%d")
serials = [r["serial"] for r in runs if r["serial"]]
serial = max(set(serials), key=serials.count) if serials else ""
DEVICE = device_name(serial, next((r["saved_device"] for r in runs
                                   if r["serial"] == serial and r["saved_device"]), None))
VERSION = app_version()
OUT = os.path.join(REPORTS, f"FarmerChat_{BATCH_LABEL}_v{VERSION}_{DEVICE}_{run_date}.html")

total = len(rows)
passed = sum(1 for r in rows if r["run"] and r["run"]["status"] == "PASS")
failed = sum(1 for r in rows if r["run"] and r["run"]["status"] == "FAIL")
quarantined = sum(1 for r in rows if r["quarantine"] and not r["run"])
warned = sum(1 for r in rows if r["run"] and r["run"]["warnings"])
notrun = total - passed - failed - quarantined
total_time = sum(r["run"]["duration"] for r in rows if r["run"])
e = html.escape


def row_html(r, summary=False):
    run = r["run"]
    status = run["status"] if run else ("QUARANTINED" if r["quarantine"] else "NOT RUN")
    cls = {"PASS": "pass", "FAIL": "fail"}.get(status, "skip")
    if summary:
        btns = ""
    elif r["videos"]:
        btns = "".join(
            f'<button class="play" data-src="{e(v)}" data-title="{e(r["id"])} · {e(r["title"])}'
            f'{" · part " + str(i + 1) if len(r["videos"]) > 1 else ""}">▶ '
            f'{"Play" if len(r["videos"]) == 1 else f"Part {i + 1}"}</button>'
            for i, v in enumerate(r["videos"]))
    else:
        btns = '<span class="muted">No video</span>'
    if run and run["failure"]:
        f = run["failure"]
        reason = (f'<div class="reason"><b>Failed step:</b> <code>{e(f["step"])}</code>'
                  + (f'<br><b>Why:</b> {e(f["message"])}' if f["message"] else "")
                  + (f'<br><a href="{e(run["shot"])}" target="_blank">Failure screenshot</a>' if run["shot"] and not summary else "")
                  + "</div>")
    elif run:
        reason = '<span class="muted">—</span>'
    elif r["quarantine"]:
        reason = ""
    elif r["stale"]:
        reason = '<span class="muted">Not run since the test was last changed</span>'
    else:
        reason = '<span class="muted">No run found</span>'
    if r["quarantine"]:
        reason += f'<div class="quar"><b>Quarantined:</b> {e(r["quarantine"])}</div>'
    if run and run["warnings"]:
        reason += "".join(f'<div class="warn">⚠ {e(w)}</div>' for w in run["warnings"])
    lat = ""
    if run and run["latency"]:
        lat = "".join(f'<div class="lat">{e(k.replace("_total", " (incl. clarifications)").replace("_", " "))}: {v / 1000:.1f}s</div>'
                      for k, v in run["latency"].items())
    steps = ""
    if run:
        items = "".join(
            f'<li class="st-{s["state"].lower()}"><span class="sd">{s["dur"]:.1f}s</span>'
            f'<span class="sl">{e(s["label"])}</span><span class="ss">{s["state"].lower()}</span></li>'
            for s in run["steps"])
        steps = f'<details><summary>{len(run["steps"])} steps</summary><ol class="steps">{items}</ol></details>'
    tags = " ".join(f'<span class="tag">{e(t)}</span>' for t in r["tags"] if t not in ("regression", BATCH))
    req = f'<div class="muted small">Requires: <code>{e(r["requires"])}</code></div>' if r["requires"] else ""
    return f"""
<tr class="{cls}">
  <td class="id">{e(r["id"])}<div class="pid">{e(r["pid"])}</div><div class="prio p-{e(r["priority"].lower())}">{e(r["priority"])}</div></td>
  <td><div class="title">{e(r["title"])}</div>
      <div class="desc">{e(r["description"])}</div>
      <div class="meta">{tags} <span class="muted small"><code>{e(r["file"])}</code></span></div>{req}{steps}</td>
  <td><span class="badge {cls}">{e(status)}</span></td>
  <td class="num">{fmt(run["duration"]) if run else "—"}{lat}</td>
  {"" if summary else f"<td>{btns}</td>"}
  <td>{reason}</td>
</tr>"""


def build(summary=False):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FarmerChat {e(BATCH_LABEL)} Report</title>
<style>
:root {{ --bg:#f6f7f5; --card:#fff; --fg:#1b1f1c; --muted:#66706a; --line:#e2e6e1;
  --pass:#1f7a3f; --pass-bg:#e5f4ea; --fail:#b42318; --fail-bg:#fdeceb; --skip:#8a6d00; --skip-bg:#fbf3d5;
  --accent:#0b6b35; --code:#eef1ed; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#111412; --card:#1a1e1b; --fg:#e7ebe8; --muted:#9aa49d; --line:#2b312d;
  --pass:#6fd394; --pass-bg:#173523; --fail:#ff8a80; --fail-bg:#3a1a18; --skip:#e9c94c; --skip-bg:#3a3214;
  --accent:#6fd394; --code:#232924; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }}
main {{ max-width:1200px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:22px; margin:0 0 4px; }}
.sub {{ color:var(--muted); margin:0 0 20px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-bottom:20px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; }}
.card .k {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
.card .v {{ font-size:24px; font-weight:650; }}
.card.pass .v {{ color:var(--pass); }} .card.fail .v {{ color:var(--fail); }}
.wrap {{ background:var(--card); border:1px solid var(--line); border-radius:10px; overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; min-width:900px; }}
th, td {{ text-align:left; vertical-align:top; padding:12px; border-bottom:1px solid var(--line); }}
th {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; background:var(--card); position:sticky; top:0; }}
tr:last-child td {{ border-bottom:0; }}
td.id {{ font-weight:650; white-space:nowrap; }}
.prio {{ font-size:11px; font-weight:600; color:var(--muted); }}
.title {{ font-weight:600; }}
.desc {{ color:var(--muted); font-size:13px; margin:2px 0 6px; max-width:560px; }}
.meta {{ display:flex; flex-wrap:wrap; gap:4px; align-items:center; }}
.tag {{ font-size:11px; padding:1px 7px; border-radius:99px; background:var(--code); }}
.small {{ font-size:12px; }} .muted {{ color:var(--muted); }}
code {{ background:var(--code); padding:1px 5px; border-radius:4px; font-size:12px; }}
.badge {{ font-weight:650; font-size:12px; padding:3px 10px; border-radius:99px; white-space:nowrap; }}
.badge.pass {{ color:var(--pass); background:var(--pass-bg); }}
.badge.fail {{ color:var(--fail); background:var(--fail-bg); }}
.badge.skip {{ color:var(--skip); background:var(--skip-bg); }}
td.num {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
button.play {{ border:1px solid var(--line); background:var(--bg); color:var(--accent); font-weight:600;
  border-radius:8px; padding:6px 10px; cursor:pointer; margin:0 4px 4px 0; white-space:nowrap; }}
button.play:hover {{ border-color:var(--accent); }}
.reason {{ font-size:13px; color:var(--fail); max-width:320px; }}
.reason code {{ color:var(--fg); }}
.pid {{ font-size:11px; font-weight:600; color:var(--accent); white-space:nowrap; }}
.quar {{ font-size:13px; color:var(--skip); max-width:320px; margin-top:4px; }}
.warn {{ font-size:12px; color:var(--skip); margin-top:4px; }}
.lat {{ font-size:11px; color:var(--muted); white-space:nowrap; }}
details {{ margin-top:6px; }} summary {{ cursor:pointer; color:var(--muted); font-size:12px; }}
ol.steps {{ margin:6px 0 0; padding:0; list-style:none; font-size:12px; }}
ol.steps li {{ display:grid; grid-template-columns:52px 1fr auto; gap:8px; padding:2px 0; border-top:1px dashed var(--line); }}
.sd {{ font-variant-numeric:tabular-nums; color:var(--muted); text-align:right; }}
.sl {{ overflow-wrap:anywhere; }} .ss {{ color:var(--muted); }}
li.st-failed .sl, li.st-failed .ss {{ color:var(--fail); font-weight:600; }}
dialog {{ border:0; border-radius:12px; padding:0; background:#000; max-width:min(92vw,520px); width:100%; }}
dialog::backdrop {{ background:rgba(0,0,0,.7); }}
dialog .bar {{ display:flex; justify-content:space-between; align-items:center; gap:8px; padding:8px 12px; color:#fff; background:#111; font-size:13px; }}
dialog .bar button {{ background:none; border:0; color:#fff; font-size:20px; cursor:pointer; }}
dialog video {{ display:block; width:100%; max-height:80vh; background:#000; }}
</style></head>
<body><main>
<h1>{e(BATCH_LABEL)} suite: test report</h1>
<p class="sub">FarmerChat v{e(VERSION)} · {e(DEVICE)} · runs of {e(run_date)} · generated {datetime.now().strftime('%d %b %Y, %H:%M')}{" · summary (videos and screenshots are in the detailed report)" if summary else ""}</p>
<div class="cards">
  <div class="card"><div class="k">Tests</div><div class="v">{total}</div></div>
  <div class="card pass"><div class="k">Passed</div><div class="v">{passed}</div></div>
  <div class="card fail"><div class="k">Failed</div><div class="v">{failed}</div></div>
  <div class="card"><div class="k">With warnings</div><div class="v">{warned}</div></div>
  <div class="card"><div class="k">Quarantined</div><div class="v">{quarantined}</div></div>
  <div class="card"><div class="k">Not run</div><div class="v">{notrun}</div></div>
  <div class="card"><div class="k">Total time</div><div class="v">{fmt(total_time)}</div></div>
</div>
<div class="wrap"><table>
<thead><tr><th>ID</th><th>Test</th><th>Result</th><th>Time</th>{"" if summary else "<th>Video</th>"}<th>Failure reason / notes</th></tr></thead>
<tbody>{''.join(row_html(r, summary) for r in rows)}</tbody></table></div>
</main>
<dialog id="player"><div class="bar"><span id="ptitle"></span><button id="pclose" aria-label="Close">×</button></div>
<video id="pvideo" controls playsinline></video></dialog>
<script>
const dlg = document.getElementById('player'), vid = document.getElementById('pvideo');
document.querySelectorAll('button.play').forEach(b => b.addEventListener('click', () => {{
  document.getElementById('ptitle').textContent = b.dataset.title;
  vid.src = b.dataset.src; dlg.showModal(); vid.play().catch(() => {{}});
}}));
const close = () => {{ vid.pause(); vid.removeAttribute('src'); vid.load(); dlg.close(); }};
document.getElementById('pclose').onclick = close;
dlg.addEventListener('cancel', e => {{ e.preventDefault(); close(); }});
dlg.addEventListener('click', e => {{ if (e.target === dlg) close(); }});
</script>
</body></html>
"""
SUMMARY_OUT = OUT[:-5] + "_summary.html"
open(OUT, "w", encoding="utf-8").write(build())
open(SUMMARY_OUT, "w", encoding="utf-8").write(build(summary=True))
print(f"{OUT}\n{SUMMARY_OUT}\n  {passed} passed, {failed} failed, {quarantined} quarantined, "
      f"{notrun} not run, {fmt(total_time)}")
