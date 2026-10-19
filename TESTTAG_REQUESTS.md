# FarmerChat — testTag requests for UI automation

**Build inspected:** 4.1.1 (versionCode 106), `org.digitalgreen.farmer.chat`, FC-Stage debug
(`5th_app-stage-debug_latest.apk`, md5 `421d3544721eda6d3111f887a8e66e78`)
**Device:** Vivo V2431, Android 15 · **Inspected:** 6 Aug 2026 · **Method:** `uiautomator` hierarchy dump per screen

The Maestro suite targets elements by Compose `testTag` (surfaced as `resource-id` via
`testTagsAsResourceId`). Anything without a tag has to be matched by visible text or
screen coordinates — both of which break under a language change or a layout tweak, and
are the main source of flaky tests.

This doc lists only what is **missing or wrong**. Screens not mentioned are correctly tagged.

> **Update — 15 Oct 2026, build 4.1.5 (versionCode 113)**, re-checked on an OPPO CPH2127
> (Android 12) and a Vivo 1919 (Android 12) while running the smoke suite:
> - The composer **still** exposes no testTags (P0 below is unchanged).
> - **New P0:** the answer's Share/Listen row intermittently drops out of the accessibility tree
>   (section below). It blocks FC-TTS-01 (Listen, now quarantined) on some runs and affects TalkBack users too.
> - **Chat history question answered:** it is back in the drawer as *Past Advice* + **See all**;
>   `drawer_see_all_btn`, `chat_history_screen` and `chat_history_list` are all present.

---

## P0 — Blocking: the composer has no testTags at all

The composer is the app's primary input surface. It renders on **both the home screen and the
chat screen**, and since the composer flag was enabled it has **replaced** the old
`primary_input_photo_btn` / `primary_input_speak_btn` / `primary_input_type_btn` trio.

None of its four controls carry a `resource-id`:

| Control | Current selector (all we have) | Requested testTag | Observed bounds |
|---|---|---|---|
| Camera button | `content-desc="Camera"` | `composer_photo_button` | `[38,1408][128,1498]` |
| Text field | **nothing** — only the placeholder string "Ask about your farm..." | `composer_text_field` | `[139,1408][581,1498]` |
| Voice button | `content-desc="Voice"` | `composer_voice_button` | `[592,1408][682,1498]` |
| Send button | `content-desc="Send"` | `composer_send_button` | replaces Voice once text is entered |

**These four tag names already exist as string constants in the APK** — they are present in
`classes*.dex` but never applied to the rendered nodes. So this should be a small change:
attach the constants you already defined.

Composer behaviour we depend on (please keep stable): with the field empty the row is
`[Camera] [field] [Voice]`; once text is entered the camera hides and Voice becomes Send.

The text field is the highest priority of the four — it currently has **no stable selector
whatsoever**, since the placeholder text is localised.

---

## P1 — Home location chip has no tag

The chip reading `"Bengaluru Urban - Change"` at `[137,349][584,439]` is clickable but has
**neither a `resource-id` nor a `content-desc`**. It opens the system location permission dialog.

**Requested:** `home_location_chip` (and, if the "Change" area is separately tappable,
`home_location_change_btn`).

---

## P1 — Dead tag constants: wire them up or delete them

These four exist in the DEX but are **never rendered on any screen**. They look like a
half-finished rename and actively mislead anyone writing tests against the build:

```
settings_auth_button      settings_location_row
settings_name_row         settings_phone_row
```

The Settings screen actually renders `settings_btn_auth` and `settings_name_edit_row`.
Either apply the new names or remove the unused constants — please don't leave both.

The Settings rows that are currently **untagged** and would be useful to us:

| Row | Visible text | Requested testTag |
|---|---|---|
| Location row | "Location" / "Bengaluru Urban (approximate)" | `settings_location_row` |
| Phone row | "Your phone" | `settings_phone_row` |

---

## P0 (new in 4.1.5) — Share/Listen row drops out of the accessibility tree

After an AI answer finishes streaming, the action row is drawn correctly on screen (Share and
Listen chips with labels), but the accessibility tree that Maestro — and TalkBack — read is wrong
for long stretches:

| Expected (seen on some runs) | Observed most of the time |
|---|---|
| `chat_share_btn` ~300px wide with child text "Share" | `chat_share_btn` 90px wide, **no** "Share" text |
| `chat_listen_btn` ~280px wide with child icon desc "Listen" + text "Listen" | `chat_listen_btn` **missing entirely**, or present but 15px tall |

It persisted while the screen sat idle for over a minute and across several small scrolls; on a
few runs the tree was correct from the start. When it is correct, the Listen states read as
expected (Listen → "Loading..." → icon desc "Pause" → icon desc "Play").

Likely the same root cause as the 9-pixel Share/Save hit boxes below — the row's semantics/bounds
aren't updated after it re-lays out. Please check the action row's `Modifier.semantics` /
`clearAndSetSemantics` usage and make sure the chips' semantics nodes are invalidated when the
row changes size.

## P2 — Likely layout bug: 9-pixel tap targets

On the chat response actions, two of the three buttons have a **9px-tall** hit box while the
third is a normal 90px:

| Element | Bounds | Height |
|---|---|---|
| `chat_listen_btn` | `[38,634][248,724]` | 90px |
| `chat_share_btn` | `[256,670][465,679]` | **9px** |
| `chat_save_btn` | `[473,670][682,679]` | **9px** |

The tags are correct — the hit area is not. This will make Share/Save taps unreliable for
both automation and real users on smaller screens.

---

## ~~Question — where does chat history live now?~~ (answered in 4.1.5)

**Resolved:** 4.1.5 shows chat history in the drawer under *Past Advice*, with a **See all** button
(`drawer_see_all_btn`) that opens `chat_history_screen` / `chat_history_list`. they're used by FC-AUTH-01
(account lifecycle) and FC-ERR-04 (offline variant). Original question kept below for context.


Our suite had two tests (`TC_21_chat_history_screen`, `TC_32_chat_history_retry_assert` at the time)
targeting `chat_history_screen`, `chat_history_list` and `drawer_see_all_button`.

In 4.1.1 we could not find **any** entry point to chat history: the drawer contains only
Home / Language / Settings / Help & Support / Sign up, and no `history`, `see_all`, `recent`
or `saved` id appears in any screen dump we captured.

Has the feature been removed, or moved somewhere we haven't found? If it's gone we will
retire those two tests; if it moved, please point us at the entry point and its tag.

---

## Not a request — informational

Correctly tagged, no action needed. Listed so you know what automation now depends on:

- **New in 4.1.1, we'll adopt these:** `language_chooser_all_languages_chip`,
  `auth_country_code_btn`, `suggested_card_ask_btn`, `help_faq_item_0..4`, `help_list_faqs`,
  `chat_photo_input_sheet`, `chat_photo_input_camera_btn`, `chat_photo_input_gallery_btn`
- **Renamed since our last APK — our side to fix, not yours:** `faqs-en` → `help_list_faqs`,
  `faq-01-en` → `help_faq_item_0`
- Fully tagged screens verified this pass: drawer, settings, language chooser, help,
  sign-up/auth entry, chat response actions, photo input sheet

## Two notes on test environment

1. **The composer is behind a remote flag.** The same APK (identical md5) showed the old
   Photo/Speak/Type trio in the morning and the composer in the afternoon. Automation cannot
   assert a stable UI while the flag can flip mid-run — we need either a pinned value for
   test builds or a documented way to force it.
2. **The Plotline "New Terms" bottom sheet blocks the app on launch** and its `Read Terms` /
   `Accept` buttons have no ids. Being removed as a Plotline event, so no code change
   requested — but any future Plotline interstitial will break every test the same way.
   Please keep test accounts out of Plotline campaign targeting.
