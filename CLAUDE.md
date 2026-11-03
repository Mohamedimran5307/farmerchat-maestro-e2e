# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A [Maestro](https://maestro.mobile.dev/) UI test suite for the **FarmerChat** Android app
(`appId` = `org.digitalgreen.farmer.chat`). There is no application code here — only declarative
YAML flows, reusable sub-flows, and one bash runner (`run_tests.sh`) that orchestrates Maestro + adb and generates HTML/JSON reports.

## Test layout & conventions

- **`flows/<batch>/TC_NN_*.yaml`** — the live suite, split into batches that run in this order, with
  **one gapless TC number sequence across all of them**:

  | Batch folder | IDs | Scope |
  |---|---|---|
  | `flows/smoke/` | TC01–TC08 | **Smoke suite** — must-pass core journeys run first on every build: fresh install, agentic clarification, typed Q→A, feed card, gallery photo, weather/location, account lifecycle, listen |
  | `flows/core/` | TC09–TC20 | Secondary positive flows: full feed scroll, voice, Settings sign-up, share, camera, profile cards, language, sign-up entry screens |
  | `flows/settings_help/` | TC21–TC25 | Settings and Help screens |
  | `flows/first_launch/` | TC26–TC31 | Location interstitial, location permission persists / denied, and first-launch legal links |
  | `flows/offline/` | TC32–TC35 | No-internet / airplane-mode error + retry |

  Suite terms: **Smoke** = the `smoke` batch (if it fails, reject the build); the other batches are
  functional suites; **Regression** = every batch together (all flows carry the `regression` tag).
  `run_tests.sh` lists these folders in `BATCH_DIRS` and globs `TC_[0-9]*_*.yaml` in each, so adding a
  flow to an existing batch needs no runner change. Keep numbers unique and gapless across batches
  (renumber later batches if you insert or delete one). Every flow also carries its batch name as a tag.
- Filename `TC_05_…` maps to CLI/report id `TC05` (underscore dropped) — **display order only**.
  Each flow also has a **permanent id** (`# id: FC-<AREA>-NN`) that never changes when tests are
  renumbered or moved; reports show it and the runner accepts it as a filter. Never reuse one.
  The suite charters, test checklist, quarantine policy and reporting rules are in
  `docs/TEST_STRATEGY.md` — follow them when adding or changing a flow.
- **`helpers/`** — reusable sub-flows invoked via `runFlow: ../../helpers/<name>.yaml`. Most tests
  start with `launchApp` + `runFlow: ../../helpers/complete_onboarding.yaml`. `complete_onboarding.yaml`
  is **idempotent** — it short-circuits if already on `home_screen` and tolerates legacy onboarding
  screens, so a flow can rerun without a clean app state. Prefer reusing helpers over inlining
  onboarding/sign-up/permission steps.

### Front-matter contract (parsed by `run_tests.sh`)

Above the `---` separator, flows carry both real Maestro keys and comment-encoded metadata the
runner scrapes for reporting and gating:

```yaml
appId: ${APP_ID}
name: "TC02 - Typed Question → Answer → Follow-up → Back to Home"
# id: FC-CHAT-01        # permanent id — never changes, never reused
# priority: P0          # P0/P1/P2 — defaults to P1 if absent
# description: ...      # one line; falls back to name minus "TC## - " prefix
# requires: PHONE_NUMBER,OTP_CODE   # see below
# quarantine: <reason + bug>        # skip (with reason) unless RUN_QUARANTINED=1
tags:
  - home
  - regression
```

- **`# requires:`** gates execution on env vars. Comma-separated; each entry is either `KEY`
  (must be non-empty and not an unresolved `${KEY}`) or `KEY=VALUE` (must equal). If any fails the
  test is **skipped with a yellow warning**, not run-and-failed. Sign-up flows use
  `# requires: PHONE_NUMBER,OTP_CODE`; the TTS test uses `# requires: LANGUAGE_CODE=en`.
- Always use `${APP_ID}` for `appId` (project convention — do not hardcode the package).
- Tags in use: `regression` (on all), the batch name (`smoke`, `core`, `settings_help`,
  `first_launch`, `offline`), plus area tags `home`, `chat`, `settings`, `auth`, `onboarding`,
  `navigation`, `legal`, `help`, `error`, `camera`.

## Configuration & secrets

- **`config/env.yaml`** — committed non-secret defaults (`APP_ID`, `LANGUAGE`, `LANGUAGE_CODE`,
  `USER_NAME`, `SHORT_NAME`, `WAIT_TIMEOUT`, `AGENTIC`, and placeholder phone/OTP).
- **`config/env.local.yaml`** — gitignored; holds real secrets (`PHONE_NUMBER`, `OTP_CODE`).
  Keys here **override** `env.yaml`. Copy from `config/env.local.example.yaml`. Without it,
  sign-up tests are skipped via their `# requires:` guards.
- `run_tests.sh` loads `env.yaml` then `env.local.yaml`, exports each key, and passes them all to
  Maestro as `--env KEY=VALUE`. The flows reference them as `${VAR}`.

## Running tests

`run_tests.sh` is the **single test runner** — used both locally and in CI (Maestro driver
management, retry with video capture, debug-output dirs, JSON+HTML report, optional Google Drive
upload). Run from repo root:

```bash
./run_tests.sh "Imran"                 # tester name; runs all discovered TCs
./run_tests.sh "Imran" TC01            # single test (id, not filename)
./run_tests.sh "Imran" TC01,TC03       # comma-separated subset
./run_tests.sh "Imran" @smoke          # every flow tagged `smoke` (any tag works)
./run_tests.sh "Imran" @smoke,TC12     # tags and ids can be mixed
./run_tests.sh "Imran" FC-CHAT-01      # permanent id
RUN_QUARANTINED=1 ./run_tests.sh "Imran" @smoke   # include quarantined flows
```

- Each test gets **up to 3 attempts** (`MAX_RETRIES=2`). Before every attempt it `am force-stop`s the
  app and **wipes its data** (`run-as … rm -rf shared_prefs files cache databases`), so each test
  starts signed out on the language screen. This is deliberate (clean state per test) and only works
  on debuggable APKs — on a release build the wipe silently does nothing and state carries over, so
  onboarding stays idempotent and sign-up flows still call `helpers/ensure_signed_out.yaml`
  (directly or via `full_signup.yaml`). A language screen on every launch is this wipe, not an app bug.
- Before each attempt it also closes a leftover Files picker, goes to the phone's Home screen and
  starts the screen recording, so every video starts from the launcher → splash. Once per run it
  pushes `test_assets/crop_disease.jpg` to the device as `Pictures/farmerchat_test_tomato.jpg`; the
  gallery flow picks that image so a run never uploads a personal photo.
- Run a single flow directly with Maestro (bypassing the runner) — env flags are required because
  flows use `${...}` interpolation:

```bash
maestro --device emulator-5554 test flows/smoke/TC_02_type_question_ai_response.yaml \
  -e APP_ID=org.digitalgreen.farmer.chat -e LANGUAGE_CODE=en -e USER_NAME="Test Farmer"
```

### Notes

- **Offline-network tests are self-contained.** TC_32/TC_33 (global no-internet error + retry),
  TC_34 (chat send offline → inline error + retry), and TC_35 (chat history offline → error + retry)
  each toggle the radio in-flow via `setAirplaneMode: enabled/disabled` and drive their own
  recovery — no manual network toggling and no required run order. (These were previously
  `_setup`/`_assert`/`_recovery` triplets; now consolidated into one flow apiece.)

## App binary & CI

- **Branch / build:** work happens on `farmerchat-4.1.7-nov2026` (renamed from `apk-rewrite-jun2026`
  on 3 Nov 2026); `app.apk` there is the 4.1.7 stage debug build of 2 Nov 2026. CI only runs for
  `main` (push / PR), so merge via a PR to get CI on these changes.
- **`app.apk`** is tracked via **git LFS** (`.gitattributes`). Note `.gitignore` also lists `*.apk`,
  but the committed binary is the LFS object — CI does `git lfs pull` then `adb install -r app.apk`.
- CI: `.github/workflows/maestro-tests.yml` runs on a **self-hosted macOS ARM64** runner (push/PR to
  `main`, daily cron, manual dispatch). It boots an emulator, grants permissions, disables animations,
  `adb forward tcp:7001`, then runs `./run_tests.sh "CI"`. The Post Summary step parses the
  `reports/FarmerChat_*_Test_Report_*.json` summary block for the pass/fail counts.

## When editing flows

- Re-inspect the live screen hierarchy before targeting elements — prefer stable resource `id`s
  (e.g. `home_screen`, `language_item_${LANGUAGE_CODE}`, `chat_suggested_questions`) over text,
  which varies by language. Use the Maestro MCP tools (`list_devices` → `inspect_screen` → `run`)
  to validate against a running emulator.
- AI answers: after sending (or opening a card/weather chat) use `helpers/wait_for_answer.yaml`. It
  watches the loader (`chat_loading`, "Getting your …") **without scrolling** (whatever arrives — a chip card or the
  answer — lands in view top-first), taps chips where they land, and scrolls down only once a
  finished answer is there. It completes on the Share/Listen row or the suggestions, and fails on the
  inline error (`chat_retry_btn`), on the "Sorry, I had a problem just now" failure reply (it looks
  like a normal answer; `chat_ai_message_error`, plus its wording until that tag has been seen), and
  on an answer without real text. There is **no answer-time limit**: a
  single UI sample says nothing about performance (measure latency in the backend); a hang still
  fails, because the waits time out.
- After an answer, chat tests assert the **Share button** only: a `scrollUntilVisible` to it,
  then an explicit `assertVisible` with a readable label. What the agent posts **after** the
  answer (confirmation cards such as save crop / gender, late clarifications) and the
  **follow-up questions** (`chat_suggested_questions`) belong to **FC-CHAT-01 (TC03) only**: it
  sets `output.handleFollowUps = true` before `wait_for_answer`, asserts the follow-up questions
  and taps one via `helpers/followup_via_suggestion.yaml`. No other test sets the flag — each
  extra agent turn costs time and saves data to the account.
- Chat tests check **functionality only** — every turn completes, and the answer shows its Share
  button. The user's own bubbles (`chat_user_message`) are **not**
  asserted: the tag is unreliable in 4.1.7 (listed for the developer). Never assert what the AI says (crop, relevance, place names): that's covered by
  the separate evals project.
- **Tags only:** when a check fails because a testTag is missing or drops out, don't work around it
  in the flow (no switching to text) — list it with the evidence in `TESTTAG_REQUESTS_CRITICAL.md`
  for the developer.
- Guard optional/OEM-specific UI (permission dialogs, "Try again" error screens) with
  `runFlow: { when: { visible: ... } }` blocks, as `complete_onboarding.yaml` does. When several
  fallback tiers could all match, set an `output.*` flag in the first tier that fires and gate the
  later ones on it (see the `composer_*.yaml` helpers) so one tap doesn't trigger twice.

### Agentic builds (4.1.7+)

The chat may ask clarification chips before answering (location, photo, crop, growth stage) and
show confirmation chips after it (save crop, gender) instead of suggestions. `AGENTIC: true` in
`config/env.yaml` marks an agentic APK (enables FC-AGENT-01, which *requires* a clarification);
set it false for a non-agentic APK. Always wait for
answers with `helpers/wait_for_answer.yaml` (handles both build types; taps the first chip of any
clarification before the answer (`chat_clarification_option_0`) — except the photo card
(`chat_clarification_card_photo`), where it's "Continue without photo"
(`chat_clarification_option_skip`). A pending card is the one whose option still shows its
number: answered cards keep their tags but show a tick on the chosen option. A confirmation card
that comes **before** the answer ("Please Confirm", 2 Nov build) blocks it, so it's answered the same
way (`chat_confirmation_option_0`). The agent's turns are awaited
between taps, nothing is asserted while it's working). Only with `output.handleFollowUps` (TC03)
does it also answer a confirmation after the answer (first chip, found by
`chat_confirmation_option_0`) and wait for the suggestions, which come after any confirmation card
at the end of the chat; never type a follow-up. Each Maestro check on an absent element costs ~3.5s here, so keep
`runFlow when` / optional checks to a minimum. Details in `docs/TEST_STRATEGY.md` §3a. Test APKs come from fc-compose
`feature/dev-v2.5-mux-video` until a dedicated Maestro testTags branch exists.

### 4.1.x UI pitfalls (learned on device)

- **Composer** (`[Camera] [field] [Voice/Send]`): the `composer_*.yaml` helpers use its tags
  (`composer_text_field`, `composer_send_button`, `composer_photo_button`, `composer_voice_button`)
  and fall back to older ids / its labels only if a tag is missing. Its border animates forever, so `waitForAnimationToEnd` always runs to its limit and taps wait to
  settle: use `waitToSettleTimeoutMs: 500` on taps and wait for a concrete element instead.
- **The hamburger/weather buttons float over the feed** and the header text stays in the hierarchy
  behind the cards, so none of them indicate scroll position. FC-FEED-01/02 use the first card's question
  (copied at launch) as the top marker and `helpers/feed_fingerprint.yaml` to detect the feed end.
- **Swipe the feed along the left margin** (`2%` x): a centre swipe lands on the crops card's own
  scrollable list. Very fast swipes register as taps; long drags at the top trigger pull-to-refresh,
  which reorders the feed.
- **`centerElement: true` times out near the end of a list** (the element can't reach the middle);
  use `centerElement: false` for chat action rows and the top/bottom of the feed.
- `copyTextFrom` / `below` / `above` return the **first match in hierarchy order**, not the nearest.
- The answer's Share/Listen row intermittently drops out of the accessibility tree (Listen missing,
  Share shrunk) — an app bug still present in 4.1.7, seen when the chat updates after the answer
  (confirmation cards, more turns). FC-TTS-01 (Listen) was quarantined for it, ran again after
  passing 3/3 on 30 Oct, and is **quarantined again (2 Nov build)**: the Listen node collapses to
  34 px even with no chat update after the answer, and it passed 1 of 3.
  The same bug also collapses suggestion rows, drops the Listen state tags and, during loading,
  the `chat_user_message` tag (details in `TESTTAG_REQUESTS_CRITICAL.md`).
- **Settings → Sign Up** shows the account-benefits screen (Skip) only to a user who has asked
  fewer than 3 questions; after that it opens the phone-number screen (`auth_screen`) directly.
  Expected behaviour. The count survives the runner's data wipe (likely kept per device on the
  server), so sign-up flows must accept both screens (TC20, TC11 do).
- **Voice (FC-VOICE-01 / TC10):** the test doesn't speak, but room noise can be transcribed and sent
  as a question. Both outcomes pass: transcribed → `wait_for_answer` + Share; nothing heard → Retry.
- Some devices (e.g. Vivo) open the **Files** picker for the gallery, others the Photo picker; FC-PHOTO-01
  handles both. OPPO/ColorOS has no `screenrecord`, so it can't record video.
