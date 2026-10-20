# FarmerChat UI automation: test strategy

How this suite is organised, what each suite promises, and the rules a test has to meet before it
joins. Read this before adding or changing a flow.

## 1. Suites and their charters

| Suite | Folder / tag | Purpose | Time budget | Exit criterion | When it runs |
|---|---|---|---|---|---|
| **Smoke** | `flows/smoke/`, `smoke` | Is this build worth testing? The must-pass core journeys only. | ≤ 10 min | **100% pass**, or the build is rejected | Every new build, first |
| **Core** | `flows/core/`, `core` | Secondary positive flows and alternate entry points | ≤ 30 min | ≥ 95% pass; every failure triaged | Every build that passes smoke |
| **Settings & Help** | `flows/settings_help/` | Settings, Help, legal screens | ≤ 10 min | ≥ 95% pass | Every build that passes smoke |
| **First launch** | `flows/first_launch/` | Interstitials and first-launch legal links (clear state) | ≤ 10 min | ≥ 95% pass | Every build that passes smoke |
| **Offline** | `flows/offline/` | Negative paths: no internet, inline errors, retry | ≤ 15 min | ≥ 95% pass | Nightly and before release |
| **Regression** | all folders, `regression` | Everything above together | — | Release sign-off | Nightly and before release |

Run a suite with `./run_tests.sh "<name>" @smoke` (any batch tag works).

### What belongs in smoke

A smoke test is a **positive, end-to-end user journey that a release can't ship without**, and it
must be fast and deterministic. Current smoke suite:

| ID | Journey |
|---|---|
| FC-ONB-01 | Fresh install → language → home → feed loads |
| FC-AGENT-01 | Agentic: vague question → clarification **required** → answer (agentic builds only) |
| FC-CHAT-01 | Typed question → answer → follow-up → back to home |
| FC-FEED-01 | First feed card → Ask Now → answer |
| FC-PHOTO-01 | Gallery photo → answer |
| FC-LOC-01 | Weather → share location (clean state, every grant step required) → answer |
| FC-AUTH-01 | Sign up → history → log out → still logged out after relaunch |
| FC-TTS-01 | Listen to an answer (**quarantined**: Share/Listen accessibility bug, still in 4.1.7) |

Not smoke: negative and error paths, alternate entry points to a journey already covered,
exhaustive UI checks (such as scrolling the whole feed), and anything flaky.

## 2. Test IDs

- **Permanent ID** (`# id: FC-<AREA>-NN`) identifies a test for its whole life. It never changes
  when a test is renumbered or moves to another batch. Use it in bug reports, trend comparisons and
  conversations. Areas: ONB, CHAT, FEED, PHOTO, LOC, AUTH, TTS, VOICE, PROF, NAV, SET, HELP, LEGAL, ERR.
- **TC number** (`TC_NN_` in the filename) is only the run and display order: gapless across batches
  in batch order. Renumber freely; never reuse a permanent ID.
- Both work as runner filters: `./run_tests.sh "Imran" FC-CHAT-01` or `TC02`.

## 3. Checklist for every test

A flow is ready to merge only if all of these hold:

1. **One purpose.** The name and `# description:` say exactly what is verified.
2. **Explicit preconditions.** It sets up its own state (`clearState`, `ensure_signed_out`,
   `permissions:`) instead of relying on what an earlier test left behind. It must pass when run on
   its own.
3. **Outcome checks, not "a screen appeared".** When a chat already holds an answer (a
   follow-up turn), wait for the earlier answer's action row to leave the screen before waiting
   for the new one, so the old row can't pass the check. Don't anchor checks to the question
   text: long answers scroll it off screen, and Maestro can only anchor to visible elements. For AI answers use `helpers/wait_for_answer.yaml`:
   it records when the answer text finished (timing only), requires the suggestions (they come
   from a separate follow-up request), fails on the inline error, and fails if the complete
   answer took longer than `ANSWER_SLA_MS`.
4. **Unique test data.** Anything later looked up (history entries, names) carries a run-unique
   value, so an older run's data can't produce a false pass.
5. **Stable selectors.** Use testTag ids. Text or content-desc is allowed only with a comment and a
   matching request in `TESTTAG_REQUESTS*.md`.
6. **No blind waits.** No `waitForAnimationToEnd` on screens that animate continuously, no fixed
   sleeps. Wait for a concrete element.
7. **Soft checks are labelled and short.** (Chat tests don't check AI wording at all — see §3a.) For other optional UI, use `extendedWaitUntil` with
   `timeout: 3000`, `optional: true` and a `label` containing "soft check". A plain optional
   `assertVisible` idles about 20s before giving up. It shows as a warning in the report, never as
   a failure. Only on-screen text counts, so a warning means "check the video".
8. **Within the suite's time budget**, and verified once on a device with video before merging.

## 3a. Agentic and non-agentic builds

Builds from 4.1.7 on can be **agentic**: before answering, the chat may ask clarifications as
numbered chips (location, photo, crop, growth stage), and after answering it may show
confirmation chips (save crop to profile, gender) instead of the "You can also ask" suggestions.
Non-agentic builds answer directly and end with suggestions. **Every test must pass on both**:

- Send questions and wait with `helpers/wait_for_answer.yaml`. Rule: **always tap the first chip** — except the photo clarification ("Add one clear photo"), where it's always the **3rd chip** ("Continue without one" / "Continue without photo" by text, else `chat_clarification_option_2`) —
  for a clarification before the answer (the location card's first chip is "Give permission", and
  the Android prompt is then granted) and for a confirmation after it (found by `chat_confirmation_option_0`, so a suggestion row is never
  mistaken for one; late cards after the answer are handled until the suggestions show). The answer counts as complete once
  the Share/Listen row or the suggestions show.
- **Functional checks only.** These tests prove the chat *works*, not that the AI is right: what
  an answer, card or suggestion says (relevance, crop consistency, language) is covered by the
  separate evals project (LLM judges). Never assert on AI wording here.
- **Wait for the response, then assert.** Nothing is asserted while the agent is working: tap
  through any clarification / confirmation chips, wait for the final response, then assert the
  answer, then the follow-up questions and the Share button. The user's own bubbles
  (`chat_user_message`) are not asserted — the tag is unreliable in 4.1.7 (it drops out even on
  visible bubbles); it's listed for the developer.
- **Every turn must complete:** an answer counts as complete once the Share/Listen row or the
  suggestions show, it has real text, no Retry button, and it isn't the failure reply ("Sorry, I
  had a problem just now. Please ask your question again." — looks like a normal answer, so it is
  caught by its wording), within `ANSWER_SLA_MS`.
- **Follow-ups:** after any confirmation, scroll to the end; the suggestions appear there. Use
  `helpers/followup_via_suggestion.yaml` (tap the first, wait until the earlier suggestions leave the
  screen so the old answer can't pass for the new one, then check the new answer). The follow-up
  questions are **mandatory** after every answer: none shown is an app bug (hard failure).
- Don't require suggestions. A follow-up runs only when the answer offers suggestions (tap the
  first one); otherwise it's skipped, never typed.
- **Watch first, scroll later.** While the app shows "Getting your answer… / location…", don't
  scroll: whatever arrives (a clarification card or the answer) lands in view top-first, because the
  app doesn't follow the answer down. Act on a card where it lands (option 1 below its "Choose one"
  title); scroll down only once a finished answer is there, to reach its action row / suggestions.
- Keep conditional checks to a minimum: each check on an absent element costs about 3.5s, because
  FarmerChat's animations never let the screen settle.
- The report logs per answer how many clarifications were answered, and both the answer-only time
  (the SLA figure) and the total including clarification rounds. Anything a test couldn't exercise
  (e.g. no follow-up offered) is logged as `[NOTE]` and shown as a warning.
- FC-AGENT-01 (`# requires: AGENTIC=true`) is the positive check that the agent clarifies at all;
  every other test merely tolerates clarifications.
- Cards, chips, the loader and the failure reply have no testTags yet (requested in
  `TESTTAG_REQUESTS_CRITICAL.md`); until then the text fallbacks are English-only.

## 4. Flaky tests and quarantine

- The runner retries a failed test up to 2 more times. A test that passes **only on a retry is
  flaky**, not passed; the report counts it separately (flake rate).
- A test that is flaky **twice in a week**, or that fails because of a known app bug, is
  quarantined: add `# quarantine: <reason + bug link>` to its front-matter. The runner skips it
  and shows the reason; `RUN_QUARANTINED=1` runs it anyway.
- Every quarantine has an owner and is reviewed weekly. Remove it once the bug is fixed and the
  test passes 3 runs in a row.
- Never quarantine a smoke test silently. A quarantined smoke journey is a known release risk.

## 5. Devices

| Role | Device | Notes |
|---|---|---|
| CI (every build) | Emulator, Pixel API 31+ | Fast, clean, can record video |
| Low-end physical | OPPO CPH2127 (Android 12, ColorOS) | No `screenrecord`, so no video |
| Mid-range physical | Vivo 1919 (Android 12) | Files picker for the gallery; video works |
| Recent Android | One Android 14/15 phone (to add) | Photo picker, newer permission UI |

Run smoke on CI for every build, and the full regression on at least one physical device nightly
and before release.

## 6. Test data and accounts

- Sign-up uses the dedicated test number and OTP in `config/env.local.yaml`, never a personal one.
- Shared-account data (chat history) builds up across runs. Tests must use run-unique data (rule 4).
- The gallery test image (`test_assets/crop_disease.jpg`) is pushed by the runner, so no personal
  photo is ever uploaded.

## 7. Reporting

There is **one** report: every run of `run_tests.sh` writes
`reports/FarmerChat_TestReport_<tester>_<date>.html` (and the same data as JSON for CI). It stays
local, because the videos it links to show test credentials being typed.

The report shows the device and the date, plus per test: its result (passed, flaky — passed only on
a retry, or failed), a one-line description, the reason and screenshot for every failed attempt,
the videos and the answer latency.

**Triage every failure into one category** and record it next to the failure:

| Category | Meaning | Action |
|---|---|---|
| App bug | The app misbehaves | File a bug, link it; quarantine only if it blocks the suite |
| Test bug | The test is wrong or brittle | Fix the flow before the next run |
| Environment | Device, network, driver, lock screen, OTP service | Fix the setup, rerun |

## 8. Review process

1. **New or changed test:** run it alone on a device with video and get a reviewer's approval (one
   test at a time).
2. **Approved tests:** run the whole batch unattended. Review only failures, flaky tests and a
   sample of passes.
3. **New build:** smoke first. Run the other batches only if smoke passes.
