# Assignment 3, Part 1 — Study design and implementation

## Study question and hypothesis

Does AI assistance improve non-experts' ability to distinguish genuine from counterfeit products in photographs? The prediction carried forward from Assignment 2 is **human–AI joint performance > AI-only performance > human-only performance**. This is a hypothesis to test, not a result from human data.

The task uses the 200-image study split already held out in Assignment 2: 100 genuine and 100 counterfeit products from Adidas, Gucci, Louis Vuitton, Nike, and Puma. The frozen EfficientNet-B0 seed-42 model supplies its prediction, calibrated confidence, and predicted-class Grad-CAM overlay. Full-image inference is used; the abandoned ROI-fusion method is not introduced.

## Conditions

**Without AI:** inspect a product image → choose an answer and confidence → submit once to save the response and move directly to the next photo. Optional uncertainty and notes are on the same form. No AI outputs are delivered to this condition's participant session.

**With AI:** inspect the same type of product image → record an independent answer and confidence → view the frozen AI prediction, calibrated confidence, and Grad-CAM → keep or change the answer → record final confidence and trust in the specific AI recommendation. At least one reason for trust or the decision is required; comments remain optional. “I didn’t change my answer” is available only when the final answer matches the independent answer.

Both conditions use the same photo presentation, label definitions, confidence scales, trial count, uncertainty option, and post-task mental-effort question. With AI adds a second decision stage, model information, per-trial trust, and an overall usefulness question. Because these extra interactions take time, elapsed time is interpreted as whole-workflow efficiency rather than a pure measure of visual judgment speed.

In With AI, the independent-answer stage preserves each participant's unaided judgment before AI exposure. That answer remains fixed once saved; final selections can be changed before submission. Without AI records a single judgment per photo, with no review stage. For export compatibility, that one response populates both initial and final columns; these are not two separate baseline judgments. Existing practice records from the earlier two-stage baseline are retained and should be separated from the current protocol when analyzing data.

## Trial count and randomization

Each run contains **N = 10** random photos sampled without replacement from the frozen 200-item pool. Sampling does not select for AI correctness, confidence, brand, or label. Individual 10-image samples need not have balanced labels even though the full pool is balanced.

Target duration: approximately 1–2 minutes of instructions and onboarding, 4–5 minutes for photo trials, and under a minute for final questions (about 6–8 minutes per condition). This is an estimate. Run a human pilot and reduce N equally in both conditions if total time reaches 10 minutes. Do not impose an artificial speed cutoff or claim the automated QA is a human timing pilot.

When a participant takes another condition or repeats a run, the server prefers items not already assigned to that participant code. The two conditions therefore usually use different randomly sampled images from the same pool. This reduces image-specific recall but introduces item variation; report that limitation when analyzing a small sample. Once the pool is exhausted, repeats are permitted and prior assignment counts are logged.

Classmates follow the course's condition-order procedure: some complete Without AI first and others With AI first. The app does not claim to assign balanced condition order. It records first condition and session order so actual counterbalancing and order effects can be checked. Participants use the same pseudonymous code in both conditions.

## Measures and why they matter

| Measure | Operationalization | Rationale |
| --- | --- | --- |
| Task performance | Initial and final accuracy against the dataset reference label; counterfeit precision, recall, F1, and balanced accuracy can be computed from trial exports | Tests whether assistance improves decisions and whether it changes false alarms versus missed counterfeits. For small samples, report counts and denominators; single-class samples make some metrics undefined. |
| Decision confidence | Required 1–5 confidence once in Without AI; before and after AI assistance in With AI | Tests whether AI changes certainty as well as correctness, including confidence on errors. An explicit uncertainty flag identifies best guesses. |
| Efficiency | Server timestamps for first image acknowledgement, independent answer, AI reveal/asset acknowledgement, final answer, and run completion | Captures decision and review time. Distinguishes image loading from the initial timer and records the longer assisted workflow. |
| Mental effort | Required post-task question: “How much mental effort did this task require?”; 1 = very little, 7 = very high | Compares perceived workload across conditions. A tool may improve accuracy while increasing effort. This is a single self-report item, not the full NASA-TLX. |
| AI trust | Required 1–5 trust rating for each recommendation, with required reasons | Allows trust to be related to AI correctness, confidence, heatmap relevance, and answer changes. Only applies to the AI condition. |
| Perceived usefulness | Required AI-condition overall usefulness rating, 1–7 | Records whether participants found the assistance helpful, independently of accuracy. |
| Qualitative experience | Optional trial notes and final feedback; participants who have tried both are prompted to compare them | Helps explain confusing images, perceived benefits, and frustrations. |

The required additional measurement is met by the comparable confidence, mental-effort, and timing measures. Trust and usefulness provide further evidence about how people use AI assistance.

Timing begins when the browser acknowledges the original image loading. AI assets have a separate acknowledgement. Server timestamps may include network latency, time in another tab, breaks, or time spent rereading instructions; the application does not claim to measure active attention. Use medians, inspect outliers, and report this limitation.

## Attention, usability, and data quality

Before the photos, participants answer which information they should use: the photo and, when applicable, AI assistance supplied in this interface. Outside searches and random answers are the other choices. This is deliberately easy. Incorrect choices receive corrective feedback and another attempt; every attempt is recorded. No participant is automatically terminated for one error. Any analysis exclusion rule should be set before inspecting condition outcomes; do not treat one corrected answer as automatic grounds for exclusion.

Onboarding presents one sentence stating the classification task and one sentence explaining the importance of human–AI collaboration, followed by instructions in a prominent single-column card. Participant ID entry and consent appear below all instructions, rather than alongside them. The interface includes concise opening instructions, accessible definitions and examples, a permanent Instructions button, a prominent reminder to reuse the same participant ID or nickname in both conditions, explicit consent and privacy information, mutually exclusive labels, required but unselected confidence scales, an optional uncertainty marker, comments, progress, image zoom, direct progression from each submitted photo to the next, and a new-run choice only after the final questionnaire. Participants are not asked to keep or enter a completion code. Trust reasons and a larger note/issue box are expanded rather than hidden in toggles. AI-condition callouts explain what differs and how people can check the model’s evidence and override mistakes. They explicitly explain that the frozen model does not retrain from these responses. Keyboard navigation and a single-column mobile layout are supported.

Technical image failures can be skipped with an explicit reason. Such trials retain their record and appear as `skipped`; they are not coded as incorrect classifications. Do not replace them silently after seeing outcomes. Report the usable trial count.

AI information is released by the backend only after the independent answer has been recorded. Original and heatmap routes require the session token and verify the trial belongs to the current run. Reference labels and source filenames are not served through static routes or participant JSON. No correctness feedback is shown during a run.

## Repeat runs and analysis unit

The previous implementation allocated tasks by participant ID. The new implementation allocates them by a distinct session ID. A participant code is a grouping variable, not a one-run restriction. Each new session has its own condition-specific attempt number and overall sequence number. All past responses remain available.

Primary analysis should use the **first completed run in each condition for each participant**, exported as `completed_rank = 1`. Pair the two conditions by `participant_code` and aggregate outcomes at participant level; repeat attempts are not additional independent people. Keep later completed runs for a separately reported sensitivity analysis. Incomplete runs, attention failures, image skips, prior exposure, and order are retained so exclusions and deviations can be described.

The admin dashboard counts unique completed participants separately from completed runs. The course asks for at least five participants in each condition; repeating one person's run does not meet that requirement.

## A3-1 submission preparation

Implementation and local practice are ready for review. Remaining steps after the design is approved:

- Run a realistic timed human pilot and confirm N keeps each condition below 10 minutes, including instructions.
- Push the app folder to the selected GitHub repository and deploy the supplied Flask service on Render with a Supabase connection.
- Verify a real Supabase-backed run and all three CSV exports. Ensure no practice SQLite file is deployed as study storage.
- Put the deployed `/without-ai` and `/with-ai` links and required study information into the shared class spreadsheet. This document does not claim those links have been posted.
- Follow the class condition-order procedure and collect at least five distinct participants in each condition. Keep the app available throughout class.

The requirement sheet gives A3-1 as November 12, 2026 at 10:00 am, while calling that date Tuesday. November 12, 2026 is Thursday; verify the intended class date with the course announcement before scheduling collection.

## Reference materials used

- `../HAI FA 26 Assignment 3 instruction.pdf`: A3-1 requirements and submission process.
- `../FA26 Assignment 1 Summary.pdf`: clear instructions, privacy, attention checks, uncertainty, confidence, accessibility, and workflow feedback.
- `../../Assignment-2/Assignment 2.pdf` and the frozen study CSVs/Grad-CAM files: task, hypotheses, independent-then-assisted workflow, and model outputs.
- `../../Assignment-1/emotion_labeler/`: two-pane UI and the original Flask/Supabase deployment pattern.
