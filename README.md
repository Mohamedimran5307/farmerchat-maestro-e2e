# FarmerChat Maestro Automation (End-to-End)

Automated UI tests for the **FarmerChat** Android app (`org.digitalgreen.farmer.chat`), written in
[Maestro](https://maestro.mobile.dev/). The repo holds no app code: only YAML test flows, reusable
sub-flows, and one bash runner that drives Maestro + adb and produces HTML/JSON reports with a video
of every test.

- **35 tests** (TC01–TC35) in 5 batches, grouped into three suites:

  | Suite | What it runs | When | Typical time (one phone) |
  |---|---|---|---|
  | **Smoke** | `smoke` batch, TC01–TC08 | Every new build. If it fails, reject the build. | ~15 min |
  | **Functional** | `core`, `settings_help`, `first_launch`, `offline`, TC09–TC35 | When testing features | ~37 min |
  | **Regression** | Every batch | Before a release | ~52 min |

- Tests check **functionality only**: screens open, every chat turn completes, and the answer shows
  its Share button. What the AI says is checked in the separate evals project.
- Elements are found by their **test tags**, not by wording, so tests work in any app language.
  Missing tags are listed for the developer in `TESTTAG_REQUESTS_CRITICAL.md`.

### Current status (3 Nov 2026)
| | |
|---|---|
| Branch | `farmerchat-4.1.7-nov2026` (renamed from `apk-rewrite-jun2026`) |
| App under test | FarmerChat 4.1.7 stage debug build of 2 Nov 2026 (`app.apk`, agentic) |
| Smoke | 7/7 passed on the first attempt, 14m 44s; TC08 quarantined |
| Functional | 27/27 passed, 36m 45s; 26 on the first attempt (TC10 needed a retry) |
| Quarantined | TC08 (FC-TTS-01): app bug, the Listen button collapses in the accessibility tree |
| Waiting on the developer | Tags on the Terms/Privacy page, the FAQ page, the photo in the user's message and two voice states; the Listen bug (all in `TESTTAG_REQUESTS_CRITICAL.md`) |

---

## 1. Setup (one time)

### Prerequisites
| Tool | Check | Notes |
|---|---|---|
| macOS with Homebrew | `brew --version` | |
| Java 17+ | `java -version` | Needed by Maestro |
| Maestro CLI 2.x | `maestro --version` | `curl -Ls "https://get.maestro.mobile.dev" \| bash` |
| Android platform tools (adb) | `adb version` | `brew install --cask android-platform-tools` |
| Git LFS | `git lfs version` | The test APK is stored in LFS |
| An Android phone (or emulator) | `adb devices` | USB debugging on, screen unlocked |

### Steps
1. **Get the code and the APK**
   ```bash
   git clone -b farmerchat-4.1.7-nov2026 https://github.com/Mohamedimran5307/farmerchat-maestro-e2e.git
   cd farmerchat-maestro-e2e
   git lfs pull
   ```
2. **Install the app on the phone.** The APK must be a **debuggable** build: the runner wipes the
   app's data before every test, and that only works on debuggable builds.
   ```bash
   adb install -r app.apk
   ```
3. **Add the secrets** (needed for the sign-up tests):
   ```bash
   cp config/env.local.example.yaml config/env.local.yaml
   ```
   Fill in `PHONE_NUMBER`, `NEW_PHONE_NUMBER` and `OTP_CODE`. The file is gitignored; never commit it.
   - `PHONE_NUMBER`: the main test account, used by every test that signs in.
   - `NEW_PHONE_NUMBER`: one fixed account that is only used to *see* the profile cards
     (TC14/TC15). It must differ from `PHONE_NUMBER`.
   - The stage backend allows only **2 different phone numbers per device**, though each one can
     sign in any number of times. Don't sign up with new or random numbers.
   - Without `env.local.yaml`, the sign-up tests are **skipped** with a warning, not failed.
4. **Check the phone is ready:** `adb devices` lists it as `device`, the screen is unlocked, and
   Wi-Fi is on.

### Configuration
`config/env.yaml` (committed defaults) is loaded first, then `config/env.local.yaml` (secrets), which
overrides it. Every key is passed to Maestro as `--env KEY=VALUE`.

| Key | File | Meaning |
|---|---|---|
| `APP_ID` | env.yaml | App package |
| `LANGUAGE`, `LANGUAGE_CODE` | env.yaml | App language chosen at onboarding (`en`) |
| `USER_NAME`, `SHORT_NAME` | env.yaml | Display name used by tests |
| `WAIT_TIMEOUT` | env.yaml | Default wait (ms) |
| `AGENTIC` | env.yaml | `true` for agentic builds (4.1.7+), which may ask clarification chips |
| `PHONE_NUMBER`, `NEW_PHONE_NUMBER`, `OTP_CODE` | env.local.yaml | Test accounts (secret) |

---

## 2. Running tests

Always run from the repo root. The first argument is the tester's name, which appears in the
report. Add `SKIP_DRIVE_UPLOAD=1` to keep the report local (otherwise it is uploaded to Google Drive).

### A suite
```bash
SKIP_DRIVE_UPLOAD=1 ./run_tests.sh "Imran" @smoke
```
```bash
SKIP_DRIVE_UPLOAD=1 ./run_tests.sh "Imran" @functional
```
```bash
SKIP_DRIVE_UPLOAD=1 ./run_tests.sh "Imran"
```
`@smoke` is TC01–TC08, `@functional` is every batch except smoke, and no filter runs the full
regression.

### One batch
```bash
SKIP_DRIVE_UPLOAD=1 ./run_tests.sh "Imran" @core
```
Batches: `@smoke`, `@core`, `@settings_help`, `@first_launch`, `@offline`. Any tag works the same way,
for example `@chat` or `@auth`.

### One test, or a few
```bash
SKIP_DRIVE_UPLOAD=1 ./run_tests.sh "Imran" TC17
```
```bash
SKIP_DRIVE_UPLOAD=1 ./run_tests.sh "Imran" FC-NAV-02
```
```bash
SKIP_DRIVE_UPLOAD=1 ./run_tests.sh "Imran" TC16,TC17,@offline
```
Use the TC number (`TC17`, not the file name) or the permanent id (`FC-NAV-02`). Ids, numbers and
tags can be mixed, separated by commas.

### Runner options (environment variables)
| Variable | Effect |
|---|---|
| `SKIP_DRIVE_UPLOAD=1` | Keep the report local; no Google Drive upload |
| `MAESTRO_DEVICE=<serial>` | Pick the phone when several are connected (default: the first in `adb devices`) |
| `RUN_QUARANTINED=1` | Also run quarantined tests (normally skipped and shown with their reason) |
| `RECORD_DISABLED=1` | Don't record videos |

```bash
RUN_QUARANTINED=1 SKIP_DRIVE_UPLOAD=1 MAESTRO_DEVICE=b0dab239 ./run_tests.sh "Imran" @smoke
```

### Running one flow straight with Maestro (debugging only)
This skips the runner, so there's no data wipe, retry, video or report. The `-e` values are required
because flows use `${...}` variables.
```bash
maestro --device <serial> test flows/core/TC_17_drawer_home_navigation.yaml -e APP_ID=org.digitalgreen.farmer.chat -e LANGUAGE_CODE=en -e USER_NAME="Test Farmer"
```

### What the runner does for each test
1. Force-stops the app and **wipes its data**, so every test starts as a fresh install on the
   language screen.
2. Makes sure the Maestro driver is running on the phone.
3. Goes to the phone's home screen and starts the screen recording. Smoke videos start from the home
   screen; functional videos start when the app launches.
4. Runs the flow. If it fails, it retries, **up to 3 attempts** in all.
5. Once per run it copies `test_assets/crop_disease.jpg` to the phone, so the gallery test never
   uploads a personal photo.

### Reports
- `reports/FarmerChat_<Suite>_Test_Report_<date>.html` plus a matching `.json`.
  `<Suite>` is `Smoke`, `Functional`, `Regression`, the batch name, or `Selected` for a custom
  filter. A second run on the same day with the same suite **overwrites** that day's report.
- `reports/logs_<date>_<time>/`: per-attempt logs, Maestro debug output (screenshots on failure),
  and one `.mp4` per attempt. The HTML report links to these videos.
- `reports/` is gitignored.

### In CI (GitHub Actions)
`.github/workflows/maestro-tests.yml` runs on the self-hosted Mac runner, using the phone plugged
into it (or an emulator if none is attached).

| Trigger | Suite |
|---|---|
| Pull request or push to `main` | Smoke (~15 min) |
| Every night at 02:00 IST | Full regression (~52 min) |
| **Actions → FarmerChat Maestro Tests → Run workflow** | Pick the branch and the suite (smoke, functional or regression; default smoke) |

- Only one run at a time; later runs wait. Don't use the phone while a run is going.
- **Every run's report is published** (any branch, any trigger) at
  **https://mohamedimran5307.github.io/farmerchat-maestro-e2e/**: one row per run, and each run keeps
  its own link (`…/runs/<run>-<suite>/`) to share. The link is also on the run's summary page.
- The site is **public**, so it gets the HTML + JSON report only. Videos and debug logs (which
  contain the test phone numbers) stay in the run's **Artifacts** on GitHub:
  `FarmerChat-report-<n>` (HTML/JSON) and `FarmerChat-report-full-<n>` (with videos).
- Sign-up tests use the repo secrets `PHONE_NUMBER`, `NEW_PHONE_NUMBER` and `OTP_CODE`.

---

## 3. Project structure
```
.
├── run_tests.sh              # The test runner (local and CI)
├── config/
│   ├── env.yaml              # Committed defaults
│   ├── env.local.example.yaml
│   └── env.local.yaml        # Your secrets (gitignored)
├── flows/                    # The tests, one folder per batch, run in this order
│   ├── smoke/                # TC01–TC08
│   ├── core/                 # TC09–TC20
│   ├── settings_help/        # TC21–TC25
│   ├── first_launch/         # TC26–TC31
│   └── offline/              # TC32–TC35
├── helpers/                  # Reusable sub-flows (runFlow: ../../helpers/<name>.yaml)
│   ├── complete_onboarding.yaml   # Launch → language screen → home (safe to rerun)
│   ├── wait_for_answer.yaml       # Waits for an AI answer, taps clarification chips, checks it completed
│   ├── followup_via_suggestion.yaml
│   ├── full_signup.yaml / ensure_signed_out.yaml
│   ├── open_drawer.yaml / navigate_to_*.yaml
│   ├── composer_*.yaml            # Text field, Send, Camera, Voice on the chat bar
│   └── …
├── test_assets/crop_disease.jpg   # Image used by the gallery photo test
├── docs/TEST_STRATEGY.md     # Suite charters, test checklist, quarantine and reporting rules
├── CLAUDE.md                 # Detailed conventions and known app pitfalls
├── TESTTAG_REQUESTS_CRITICAL.md   # Missing test tags and app bugs for the developer (not committed)
├── app.apk                   # App under test (git LFS)
└── reports/                  # Generated reports and videos (gitignored)
```

---

## 4. Test list
`TC` numbers are display order only and can change when tests are added or removed. The
**permanent id** (`FC-…`) never changes, so use it in bug reports.

| Batch | TC | Permanent id | Test | Priority | Needs |
|---|---|---|---|---|---|
| `smoke` | TC01 | FC-ONB-01 | Fresh Install: Language → Home → Feed Loads | P0 | |
| `smoke` | TC02 | FC-AGENT-01 | Agentic: Vague Question → Clarification → Answer | P0 | `AGENTIC=true` |
| `smoke` | TC03 | FC-CHAT-01 | Typed Question → Answer → Follow-up → Back to Home | P0 | |
| `smoke` | TC04 | FC-FEED-01 | First Feed Card → Ask Now → Answer | P0 | |
| `smoke` | TC05 | FC-PHOTO-01 | Photo Question from Gallery → AI Response | P0 | |
| `smoke` | TC06 | FC-LOC-01 | Weather → Share Location (granted) → Answer | P0 | |
| `smoke` | TC07 | FC-AUTH-01 | Account Lifecycle: Sign Up → History → Log Out | P0 | sign-in |
| `smoke` | TC08 | FC-TTS-01 | Listen to AI Response (TTS Playback) | P0 | ⏸ quarantined (Listen accessibility bug) |
| `core` | TC09 | FC-FEED-02 | Home Feed Full Scroll → Back to First Card → Chat | P1 | |
| `core` | TC10 | FC-VOICE-01 | Voice Input: Overlay → Send → Answer or Retry | P2 | |
| `core` | TC11 | FC-AUTH-02 | Full Sign Up via Settings (Phone + OTP → Signed In) | P0 | sign-in |
| `core` | TC12 | FC-CHAT-02 | Share AI Response via System Chooser | P1 | |
| `core` | TC13 | FC-PHOTO-02 | Photo Question from Camera → AI Response | P2 | |
| `core` | TC14 | FC-PROF-01 | Gender Card Shows for a New Account | P1 | card account |
| `core` | TC15 | FC-PROF-02 | Crops Card Shows for a New Account | P1 | card account |
| `core` | TC16 | FC-NAV-01 | Drawer: Change Language | P2 | `LANGUAGE_CODE=en` |
| `core` | TC17 | FC-NAV-02 | Side Menu Home Returns From Help Screen | P2 | |
| `core` | TC18 | FC-AUTH-03 | Drawer → Sign Up: Phone-Input Screen | P1 | sign-in |
| `core` | TC19 | FC-AUTH-04 | Settings → Sign Up: Phone-Input Screen | P1 | sign-in |
| `core` | TC20 | FC-AUTH-05 | Settings → Sign Up → Skip / Close Returns to Settings | P2 | sign-in |
| `settings_help` | TC21 | FC-SET-01 | Settings: Toggle Display Mode (Day / Night / Auto) | P2 | |
| `settings_help` | TC22 | FC-SET-02 | Settings: Update Display Name | P2 | |
| `settings_help` | TC23 | FC-HELP-01 | Help: FAQ Opens and Expands Answers | P2 | |
| `settings_help` | TC24 | FC-HELP-02 | Help: Open Terms of Use | P2 | |
| `settings_help` | TC25 | FC-HELP-03 | Help: Open Privacy Policy | P2 | |
| `first_launch` | TC26 | FC-LOC-02 | Weather: Skip Share Location → Continue Without Location → Answer | P2 | |
| `first_launch` | TC27 | FC-LEGAL-01 | First-Launch: Open Terms of Use from Language Screen | P2 | |
| `first_launch` | TC28 | FC-LEGAL-02 | First-Launch: Open Privacy Policy from Language Screen | P2 | |
| `first_launch` | TC29 | FC-LEGAL-03 | First-Launch: Open and Close Both Legal Documents | P2 | |
| `first_launch` | TC30 | FC-LOC-03 | Location Permission Persists After Grant (across a restart) | P1 | |
| `first_launch` | TC31 | FC-LOC-04 | Location Denied → Continue Without Location → Answer | P1 | |
| `offline` | TC32 | FC-ERR-01 | Returning User Cold Starts Offline → Cached Home | P2 | |
| `offline` | TC33 | FC-ERR-02 | No-Internet Error: Retry Recovers to Language Screen | P2 | |
| `offline` | TC34 | FC-ERR-03 | Chat Offline: Inline Error + Retry Recovers | P2 | |
| `offline` | TC35 | FC-ERR-04 | Chat History Offline: Error + Retry Loads History | P2 | sign-in |

- **sign-in** needs `PHONE_NUMBER` and `OTP_CODE`; **card account** needs `NEW_PHONE_NUMBER`.
- Tests whose requirements aren't met are skipped with a warning, not failed.
- The offline tests switch airplane mode on and off themselves, and always turn it back off at the
  end, even if they fail.

---

## 5. Writing or changing a test
- Put it in the right batch folder as `TC_NN_<what_it_does>.yaml`. Keep TC numbers gapless across
  batches, and give it a new permanent id (`# id: FC-<AREA>-NN`) that is never reused.
- The front-matter (above `---`) is read by the runner:
  ```yaml
  appId: ${APP_ID}
  name: "TC17 - Side Menu Home Returns From Help Screen"
  # id: FC-NAV-02
  # priority: P2                       # P0 / P1 / P2 (default P1)
  # description: One line shown in the report.
  # requires: PHONE_NUMBER,OTP_CODE    # optional: skip unless these are set
  # quarantine: <reason + bug>         # optional: skip with this reason
  tags:
    - navigation
    - regression
    - core                             # its batch name
  ```
- Start with `launchApp` and `runFlow: ../../helpers/complete_onboarding.yaml`.
- **Check navigation in three steps:** the target screen arrived (its tag), the previous screen is
  gone, and the target's key content is there.
- **Use tags (`id:`), not text.** If a tag is missing, don't work around it; add it to
  `TESTTAG_REQUESTS_CRITICAL.md` for the developer.
- **For AI answers,** use `helpers/wait_for_answer.yaml`, then assert the Share button. Only TC03
  handles the cards after an answer (save crop / gender) and the follow-up questions.
- Run the new test 3 times with video before committing it.

The full rules are in `docs/TEST_STRATEGY.md` and `CLAUDE.md`.

---

## 6. Troubleshooting
| Symptom | Cause / fix |
|---|---|
| Tests fail in under 5s with `UNAVAILABLE` / `tcp:7001: closed` | The Maestro driver dropped. The runner restarts it before the next attempt; if a whole run is affected, unplug and replug the phone and run again. |
| The language list never loads; every test fails at onboarding | The phone is offline. Check Wi-Fi: an airplane-mode toggle can leave Wi-Fi off on some phones. |
| Sign-up tests are skipped | `config/env.local.yaml` is missing or has empty values. |
| "Send via SMS" does nothing at sign-up | The device has hit the 2-numbers limit. Use only `PHONE_NUMBER` and `NEW_PHONE_NUMBER`. |
| Videos are missing | `RECORD_DISABLED=1` was set, or the phone blocks screen recording (OPPO / ColorOS). |
| Tests stop with the phone locked | Unlock the phone. Keep it unlocked and on charge during runs. |
| `adb: device '<serial>' not found` in a log | The USB connection dropped for a moment; the retry usually passes. Use a good cable and keep the phone plugged in. |
| TC08 (Listen) is skipped | It's quarantined until the app's Listen accessibility bug is fixed; `RUN_QUARANTINED=1` runs it. |
