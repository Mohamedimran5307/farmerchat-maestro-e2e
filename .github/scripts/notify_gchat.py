"""Post one CI run's result to a Google Chat space (incoming webhook).

Reads the run's report.json from the report site (written by
publish_report.py) and posts a short text message: result, suite,
branch, trigger, the failed tests (if any) and the link to the run's
report page. Only that public link is posted — never logs or test data.
Does nothing when GCHAT_WEBHOOK_URL is empty (the secret isn't set).

Environment: GCHAT_WEBHOOK_URL, RUN, SUITE, BRANCH, TRIGGER, RUN_URL,
REPORT_URL, SITE (gh-pages checkout). DRY_RUN=1 prints the message only.
"""
import json
import os
import sys
import urllib.request

ENV = os.environ
URL = ENV.get("GCHAT_WEBHOOK_URL", "").strip()
RUN, SUITE = ENV["RUN"], ENV["SUITE"]
DRY = ENV.get("DRY_RUN") == "1"

if not URL and not DRY:
    print("GCHAT_WEBHOOK_URL not set - nothing posted")
    sys.exit(0)

report = {}
path = os.path.join(ENV["SITE"], "runs", f"{RUN}-{SUITE}", "report.json")
if os.path.exists(path):
    report = json.load(open(path, encoding="utf-8"))
s = report.get("summary") or {}

if not s:
    head = f"⚠️ FarmerChat {SUITE} run #{RUN}: no report (the run ended before one was written)"
else:
    failed = s.get("failed", 0)
    first = s.get("first_attempt_passed", 0)
    result = f"{s.get('passed', 0)}/{s.get('total', 0)} passed"
    result += f", {failed} failed" if failed else ""
    result += f" ({first} on the first attempt)" if s.get("passed") else ""
    head = f"{'❌' if failed else '✅'} FarmerChat {SUITE} run #{RUN}: {result}"

lines = [f"*{head}*",
         f"Branch: {ENV.get('BRANCH', '')} · Trigger: {ENV.get('TRIGGER', '')}"]
if report.get("appVersion"):
    lines.append(f"App: {report['appVersion']}")
bad = [t for t in report.get("testCases", []) if t.get("status") == "FAILED"]
if bad:
    lines.append("Failed: " + ", ".join(f"{t.get('tc')} {t.get('name', '')}" for t in bad))
if s.get("quarantined"):
    lines.append(f"Quarantined (not run): {s['quarantined']}")
lines.append(f"<{ENV['REPORT_URL']}|Report with videos> · <{ENV.get('RUN_URL', '')}|GitHub run>")
text = "\n".join(lines)

if DRY:
    print(text)
    sys.exit(0)

req = urllib.request.Request(URL, data=json.dumps({"text": text}).encode(),
                             headers={"Content-Type": "application/json; charset=UTF-8"})
try:
    urllib.request.urlopen(req, timeout=30).read()
    print("Posted to Google Chat")
except Exception as e:  # a failed post must not fail the run
    print(f"Google Chat post failed: {e}")
