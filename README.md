# FarmerChat Maestro Automation Framework

Automated UI test suite for the **FarmerChat** Android app (`org.digitalgreen.farmer.chat`)
using [Maestro](https://maestro.mobile.dev/).

## Project Structure

```
Maestro_automation_FarmerChat_End_to_End_Flow/
├── config/
│   ├── env.yaml                  # Committed non-secret defaults (APP_ID, LANGUAGE, …)
│   ├── env.local.example.yaml    # Template for secrets — copy to env.local.yaml
│   └── env.local.yaml            # Gitignored secrets (PHONE_NUMBER, OTP_CODE); overrides env.yaml
├── flows/
│   ├── smoke/                    # Batch 1: TC01–TC08 — smoke suite (must-pass core journeys)
│   ├── core/                     # Batch 2: TC09–TC22 — secondary positive flows
│   ├── settings_help/            # Batch 3: TC23–TC27
│   ├── first_launch/             # Batch 4: TC28–TC33
│   ├── offline/                  # Batch 5: TC34–TC37 (airplane-mode error + retry)
│   └── onboarding/               # Legacy flows — NOT run by the runners
├── helpers/                      # Reusable sub-flows invoked via runFlow:
│   ├── launch_app.yaml
│   ├── launch_app_fresh.yaml
│   ├── complete_onboarding.yaml  # Idempotent: skips onboarding if already on home
│   ├── full_signup.yaml
│   ├── grant_location.yaml
│   ├── dismiss_system_popup.yaml
│   ├── ensure_signed_out.yaml    # Logs out first if a previous test left the user signed in
│   ├── composer_*.yaml           # Focus / Send / Camera / Voice on the composer bar
│   ├── grant_runtime_permission.yaml
│   ├── feed_fingerprint.yaml     # Detects the end of the home feed (no end-of-feed marker needed)
│   └── navigate_to_*.yaml
├── run_tests.sh                  # The test runner (driver mgmt, retry, video, reports) — used locally and in CI
├── scripts/
│   ├── run_failed.sh             # Re-run only previously failed TCs
│   └── report_style.css          # HTML report styling
├── device-farm/                  # Run the suite on a physical USB device
├── test_assets/crop_disease.jpg  # Gallery test image (pushed to the device by the runner)
├── TESTTAG_REQUESTS.md           # testTag / accessibility requests for the app team
├── app.apk                       # App under test (tracked via git LFS)
├── reports/                      # Generated HTML/JSON reports (gitignored)
└── README.md
```

## Prerequisites

- Maestro CLI installed (`~/.maestro/bin/maestro`)
- Android emulator or device running (Pixel 7 Pro / API 31+ recommended)
- FarmerChat app installed — `adb install -r app.apk` (run `git lfs pull` first)

## Configuration & secrets

- `config/env.yaml` holds committed defaults and is loaded first.
- `config/env.local.yaml` (gitignored) holds real secrets and **overrides** `env.yaml`.
  Copy `config/env.local.example.yaml` to `config/env.local.yaml` and fill in `PHONE_NUMBER`
  and `OTP_CODE`. Without it, sign-up tests are **skipped** (see `# requires:` below), not failed.

| Variable      | Source     | Description                          |
|---------------|------------|--------------------------------------|
| APP_ID        | env.yaml   | App package name                     |
| LANGUAGE      | env.yaml   | Display language (e.g. English (Kenya)) |
| LANGUAGE_CODE | env.yaml   | Language id used in element ids (`en`) |
| USER_NAME     | env.yaml   | Onboarding display name              |
| SHORT_NAME    | env.yaml   | Avatar initials                      |
| WAIT_TIMEOUT  | env.yaml   | Max wait (ms)                        |
| PHONE_NUMBER  | env.local  | Sign-up phone number (secret)        |
| OTP_CODE      | env.local  | Sign-up OTP (secret)                 |

## Running tests

`run_tests.sh` is the single entry point for running the suite — locally and in CI. It discovers
every `flows/<batch>/TC_NN_*.yaml` (batches in order: smoke, core, settings_help, first_launch,
offline), loads env config, retries each test up to 3 times, captures video + debug output, and
generates an HTML/JSON report under `reports/`. It does not clear app state between tests; it relies
on the idempotent `complete_onboarding.yaml` helper, and sign-up tests log out first via
`ensure_signed_out.yaml`. Each video starts from the phone's home screen, and the gallery test image
is pushed to the device once per run so no personal photo is ever uploaded.

```bash
./run_tests.sh "Imran"            # tester name; run the whole suite
./run_tests.sh "Imran" TC01       # single test by ID (not filename)
./run_tests.sh "Imran" TC01,TC03  # comma-separated subset
./run_tests.sh "Imran" @smoke     # one batch (or any tag); mix with ids: @smoke,TC13
```

### Run a single flow directly with Maestro

Flows interpolate `${...}` variables, so env flags are required:

```bash
maestro --device emulator-5554 test flows/smoke/TC_01_weather_widget_location.yaml \
  -e APP_ID=org.digitalgreen.farmer.chat -e LANGUAGE_CODE=en -e USER_NAME="Test Farmer"
```

## Flow conventions

Each flow's front-matter (above `---`) carries Maestro keys plus comment-encoded metadata that
`run_tests.sh` scrapes:

```yaml
appId: ${APP_ID}                              # always use ${APP_ID}, never hardcode
name: "TC01 - Location-Based Personalization via Weather Widget"
# priority: P0                                # P0/P1/P2 (defaults to P1)
# description: ...                            # one line, used in reports
# requires: PHONE_NUMBER,OTP_CODE             # gate execution on env vars (see below)
tags:
  - home
  - regression
```

- **`# requires:`** — comma-separated env-var gates. `KEY` requires a non-empty resolved value;
  `KEY=VALUE` requires equality. If any entry fails, the test is **skipped with a warning** rather
  than run-and-failed (cleaner signal than an OTP timeout 30s into a sign-up flow).
- File `TC_05_…` maps to report/CLI id **`TC05`** (underscore dropped, leading zero stripped).
- Most tests start with `launchApp` + `runFlow: ../../helpers/complete_onboarding.yaml`. Reuse
  helpers rather than inlining onboarding, sign-up, or permission handling.

## Test coverage

Tests are grouped into batches (one folder each) and numbered **TC01–TC37** in batch order (display order only — the permanent `FC-…` id is what
identifies a test across builds). Every
test is tagged with its batch name, its functional area, and `regression`.

- **Smoke** (`smoke`, TC01–TC08): must-pass core flows, run first on every new build. If smoke fails,
  the build is rejected before the rest is run.
- **Functional batches** (`core`, `settings_help`, `first_launch`, `offline`): deeper coverage,
  including the negative/error cases in `offline`.
- **Regression**: all batches together, run before a release.

Every run of `run_tests.sh` writes **one** report: `reports/FarmerChat_<Suite>_Test_Report_<date>.html` (e.g. `FarmerChat_Smoke_Test_Report_20Oct2026.html`)
(plus the same data as JSON). See `docs/TEST_STRATEGY.md` for the suite charters and rules.

| Batch | TC | Permanent ID | Test | Priority |
|---|---|---|---|---|
| `smoke` | TC01 | FC-ONB-01 | Fresh Install: Language → Home → Feed Loads | P0 |
| `smoke` | TC02 | FC-AGENT-01 | Agentic: Vague Question → Clarification → Answer | P0 |
| `smoke` | TC03 | FC-CHAT-01 | Typed Question → Answer → Follow-up → Back to Home | P0 |
| `smoke` | TC04 | FC-FEED-01 | First Feed Card → Ask Now → Answer | P0 |
| `smoke` | TC05 | FC-PHOTO-01 | Photo Question from Gallery → AI Response | P0 |
| `smoke` | TC06 | FC-LOC-01 | Weather → Share Location (granted) → Answer | P0 |
| `smoke` | TC07 | FC-AUTH-01 | Account Lifecycle: Sign Up → History → Log Out | P0 |
| `smoke` | TC08 | FC-TTS-01 | Listen to AI Response (TTS Playback) *(quarantined)* | P0 |
| `core` | TC09 | FC-FEED-02 | Home Feed Full Scroll → Back to First Card → Chat | P1 |
| `core` | TC10 | FC-VOICE-01 | Speak Button Opens Voice-Input Overlay | P2 |
| `core` | TC11 | FC-AUTH-02 | Full Sign Up via Settings (Phone + OTP → Signed In) | P0 |
| `core` | TC12 | FC-CHAT-02 | Share AI Response via System Chooser | P1 |
| `core` | TC13 | FC-CHAT-03 | Save AI Response Shows Confirmation | P2 |
| `core` | TC14 | FC-PHOTO-02 | Photo Question from Camera → AI Response | P2 |
| `core` | TC15 | FC-PROF-01 | Gender Card Renders After Sign-Up + Location | P1 |
| `core` | TC16 | FC-PROF-02 | Crops Card Renders After Sign-Up + Location | P1 |
| `core` | TC17 | FC-PROF-03 | Answer Gender Profile-Prompt Card | P2 |
| `core` | TC18 | FC-NAV-01 | Drawer: Change Language | P2 |
| `core` | TC19 | FC-NAV-02 | Drawer "Home" Returns From Help Screen | P2 |
| `core` | TC20 | FC-AUTH-03 | Drawer → Sign Up: Phone-Input Screen | P1 |
| `core` | TC21 | FC-AUTH-04 | Settings → Sign Up: Phone-Input Screen | P1 |
| `core` | TC22 | FC-AUTH-05 | Settings → Sign Up → Skip Returns to Settings | P2 |
| `settings_help` | TC23 | FC-SET-01 | Settings: Toggle Display Mode (Day / Night / Auto) | P2 |
| `settings_help` | TC24 | FC-SET-02 | Settings: Update Display Name | P2 |
| `settings_help` | TC25 | FC-HELP-01 | Help: FAQ Accordion Expands With Answer | P2 |
| `settings_help` | TC26 | FC-HELP-02 | Help: Open Terms of Use | P2 |
| `settings_help` | TC27 | FC-HELP-03 | Help: Open Privacy Policy | P2 |
| `first_launch` | TC28 | FC-LOC-02 | Location Interstitial: Skip Returns to Home | P2 |
| `first_launch` | TC29 | FC-LEGAL-01 | First-Launch: Open Terms of Use from Language Screen | P2 |
| `first_launch` | TC30 | FC-LEGAL-02 | First-Launch: Verify Privacy Policy Link in Language-Screen Legal Text | P2 |
| `first_launch` | TC31 | FC-LEGAL-03 | First-Launch: Verify Both Legal Links in Language-Screen Legal Text | P2 |
| `first_launch` | TC32 | FC-LOC-03 | Location Permission Persists After Grant | P1 |
| `first_launch` | TC33 | FC-LOC-04 | Location Denied → Continue Without Location → Answer | P1 |
| `offline` | TC34 | FC-ERR-01 | No-Internet Error Screen Asserts on Cold Start | P2 |
| `offline` | TC35 | FC-ERR-02 | No-Internet Error: Retry Recovers to Language Screen | P2 |
| `offline` | TC36 | FC-ERR-03 | Chat Offline: Inline Error + Retry Recovers | P2 |
| `offline` | TC37 | FC-ERR-04 | Chat History Offline: Error + Retry Loads History | P2 |

> The offline-network tests (TC34–TC37) are self-contained: each toggles the radio in-flow via
> `setAirplaneMode` and drives its own retry/recovery — no manual network toggling, no required order.

## Reports

`run_tests.sh` writes `reports/FarmerChat_<Suite>_Test_Report_<date>.html` and a matching `.json`
summary, plus a `reports/logs_<date>_<time>/` directory with per-attempt logs, debug output, and
(when capture succeeds) per-attempt video. `reports/` is gitignored.

## Physical device testing

See `device-farm/` (`bash device-farm/setup.sh` then `bash device-farm/run.sh`) to run the suite
on a USB-connected Android device and auto-push results.
