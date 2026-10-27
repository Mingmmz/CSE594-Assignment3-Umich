# Local verification — October 26, 2026

Current flow: Without AI records one answer and confidence per photo; a single submission saves the answer, optional uncertainty, and notes, then opens the next photo directly. With AI retains independent judgment followed by AI review and final judgment. After the last submitted photo, the questionnaire opens directly. There is no per-photo saved screen, Continue button, or restart prompt. Participants see no completion code. The option to start another run appears after the full study and questionnaire are complete.

- Eleven backend integration tests pass, covering the single-submission baseline, saved notes and uncertainty, last-photo transition, duplicate submissions, legacy baseline resume, matching condition instructions, both conditions, repeat runs, concurrent starts, session isolation, AI gates, technical skips, exhausted item pools, attention checks, protected exports, HTTPS proxy origin validation, and required/consistent trust reasons. Completed participant API state does not include a completion code.
- Browser: one Without AI submission advanced Photo 2 directly to Photo 3; refresh resumed Photo 3. No two-step indicator or AI fields appeared, and optional uncertainty and notes were available on the single form. With AI still progressed from independent judgment to AI review on the same photo, with trust and final submission controls. No browser script errors were observed. Screenshot: `baseline-single-submit.jpg`.
- Current baseline exports copy the single response into both initial and final fields for compatibility; the two timestamps match and `review_seconds` is blank. Legacy baseline practice records retain their saved initial responses and timestamps. No schema migration or historical-record rewrite was required.
- JavaScript syntax validation passes.
- Dataset audit: exactly 200 study originals and their 200 Grad-CAM overlays; 400 byte matches to Assignment 2 study sources, zero extra packaged stimuli, unchanged AI outputs, and no trial-identity overlap with training/validation/development-test splits. See DATASET_AUDIT.md.
- Browser: confirmed final submission of Photo 1 advances directly to Photo 2. The removed intermediate screen does not exist in the DOM, and no restart choice is visible during the trial.
- Browser: the updated completion screen displays saved-study confirmation and the participant ID reminder, with no completion code, and retains the option for a new full run.
- Prior browser checks verified full 10-photo flows in both conditions, image zoom, reload/resume, required trust reasons, the unchanged-answer option, expanded comments, and desktop/mobile layouts. The 390 px mobile layout had no horizontal overflow.
- Researcher CSV exports retain existing internal run identifiers for compatibility; these are not shown to participants. Existing records are preserved.

Remaining verification: timed human pilot, Supabase/PostgreSQL connectivity and data writes, Render deployment, and the deployed HTTPS URLs. These remain deferred for local design review. No Supabase or Render resources were changed.

## Instructions-first onboarding

- Both condition pages render successfully with the task sentence and purpose sentence before the instructions, followed by the participant ID, consent, and Begin control. Each input ID is unique.
- In the browser at 1360×1000, the With AI participant-entry card begins below the entire instruction card (entry top 1340 px, instruction bottom 1314 px), in the same column.
- At 390×844, the same ordering holds and document width equals viewport width, with no horizontal overflow.
- The detailed instructions dialog opens and closes correctly from the revised onboarding page.
- Screenshots: onboarding-desktop.jpg and onboarding-mobile.jpg. This revision changes presentation and instructions; it does not change sampling, storage, or trial submission behavior.

## Unified study header — October 26, 2026

- Combined the brand, condition label, workflow reminder, and Instructions button into one sticky header. Removed the separate condition banner and its duplicate emblem. Without AI remains amber; With AI remains blue.
- Browser checks at 1360, 820, and 390 px confirm no horizontal overflow. Labels are 30 px on desktop and 25 px on mobile. Desktop uses one row; mobile uses two rows within the same continuous header.
- Confirmed the header stays at viewport top after scrolling, Instructions opens and closes, and the home page retains its normal header. Checked both conditions without submitting study responses.
- Saved current previews as `unified-header-without-ai.jpg`, `unified-header-with-ai.jpg`, and `unified-header-mobile.jpg`.

## Previous condition banner — October 25, 2026 (superseded above)

- Added an amber Without AI banner and a blue With AI banner, with explicit condition names, distinct icons, and a brief workflow reminder. The banner is outside the individual workflow panels so it remains present throughout the study.
- Labels are 30 px on desktop and 25 px at the 390 px mobile breakpoint. Both desktop condition pages render with exactly one banner and unique element IDs.
- Browser checks confirm the banner remains at viewport top (0 px) after scrolling. Both mobile conditions have a document width of 390 px for a 390 px viewport, without horizontal overflow.
- Calculated banner text contrast: 7.34:1 for Without AI and 6.93:1 for With AI. Condition names and icons provide identification without color alone.
- The home-page cards use the matching amber/blue colors; browser-tab titles begin with With AI or Without AI.
- No trial content, answer-control colors, sampling, or measurement behavior was changed.
- Screenshots: condition-without-ai.jpg, condition-with-ai.jpg, and condition-mobile.jpg.
