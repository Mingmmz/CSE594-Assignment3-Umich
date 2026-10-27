# Assignment 3 exports

Exports require researcher authentication at `/admin`. All timestamps are UTC ISO 8601 strings. Session bearer tokens and start request IDs are never exported. `run_id` is a non-authenticating internal identifier used to join exports; it is not displayed to participants. Exported free-text values beginning with spreadsheet formula characters receive a leading apostrophe.

## Sessions CSV

One row per run, including incomplete runs.

| Field | Meaning |
| --- | --- |
| run_id | Stable, non-authenticating internal join key for this run; the existing `PI-…` values are retained for export compatibility and are not shown to participants |
| participant_code / display_code | Normalized, case-insensitive grouping code / originally entered display code |
| condition | `baseline` (without AI) or `ai` (with AI) |
| attempt_no | Starts at 1 for each participant and condition; includes incomplete attempts |
| sequence_no | Starts at 1 across both conditions and all runs for that participant |
| first_condition | Condition entered first by this participant, including incomplete runs |
| status | `attention`, `active`, `survey`, or `completed` |
| completed_rank | Order of completion within participant and condition; blank until completed. Use 1 for the first-completed-run primary analysis |
| task_count / dataset_version | Assigned N / fingerprint of frozen assets, labels, outputs, and model settings |
| familiarity | Optional 1–5 prior authentication familiarity; blank if omitted |
| consent_at / attention_passed_at | Consent/start timestamp / passed instruction-check timestamp |
| attention_failures | Number of incorrect instruction-check submissions |
| workload | Post-task mental effort, 1 (very little) to 7 (very high) |
| usefulness | AI-condition usefulness, 1 (not at all) to 7 (extremely); blank for baseline |
| feedback | Optional post-task comment |
| survey_submitted_at / completed_at | Questionnaire completion timestamps |
| duration_seconds | Consent to questionnaire completion; includes instructions, pauses, and network time |
| storage_mode | `local-practice` or `supabase`; never mix practice and study data |

## Trials CSV

One row per assigned trial, including pending, review, submitted, and skipped trials. Rows include the session grouping/order fields above and the following:

| Field | Meaning |
| --- | --- |
| position / item_id / study_index / brand | Within-run order, opaque item identity, original A2 study index, and brand |
| prior_exposures | Number of earlier assignments of this item to the same code, not a guarantee it was viewed |
| status | `pending`, `review`, `submitted`, or `skipped` |
| ground_truth | A2 dataset reference label: `genuine` or `fake` (UI: Counterfeit) |
| ai_prediction / ai_confidence / calibrated_fake_probability | Frozen A2 model output, provided for both conditions in the researcher export, irrespective of participant exposure |
| initial_label / final_label | With AI: independent answer / submitted final answer. Current Without AI: the single submitted answer is copied to both columns for compatibility; it is not a pair of judgments. Blank when not recorded. Earlier baseline practice records may contain two separate judgments. |
| initial_confidence / final_confidence | 1–5 participant certainty, from not at all to extremely confident |
| uncertain | 1 if the participant marked the final answer as a best guess; 0 otherwise; blank until submitted |
| trust | AI recommendation trust, 1 (not at all) to 5 (completely); blank for baseline |
| reasons / comment | Required AI trust/decision reasons as a JSON array / optional trial note. `unchanged_answer` is valid only if final_label equals initial_label. Earlier practice records may have an empty reason array from the earlier interface. |
| shown_prediction / shown_confidence / shown_gradcam | Exact AI outputs released in the review stage; blank in baseline and before reveal |
| viewed_at | First server delivery of this trial state |
| image_ready_at | Browser's first acknowledgement of loaded product image |
| initial_submitted_at | With AI: independent answer saved and becomes immutable. Current Without AI: single-submission timestamp, equal to submitted_at. Earlier saved baseline answers retain their original timestamp. |
| ai_revealed_at | Server release of AI information; blank in baseline |
| ai_assets_ready_at | Browser acknowledgement after Grad-CAM loads; distinct from the release timestamp |
| submitted_at | Final answer submission or technical skip timestamp |
| initial_correct / final_correct | 0 or 1 against the reference label, blank if the corresponding answer is absent |
| changed_answer | With AI: 0/1 final versus independent answer; blank without final answer. Current Without AI: always 0 because it records one judgment; do not interpret this as observed reconsideration behavior. |
| initial_ai_agreement / final_ai_agreement | 0/1 agreement with the frozen AI prediction; blank if answer absent |
| initial_seconds | image_ready_at → initial_submitted_at |
| review_seconds | With AI: initial_submitted_at → submitted_at, including AI loading, review, trust rating, notes, and pauses. Blank for the current single-submission baseline. Earlier baseline practice records that used review retain their elapsed interval. |
| total_seconds | image_ready_at → submitted_at |
| skip_reason | `image_load_error` or `heatmap_load_error`; blank otherwise |

Compute accuracy from `status = submitted`, not from skipped or unsubmitted rows. For the primary analysis also require `session_status = completed` and `completed_rank = 1`. Match participant codes across conditions; report participants with only one completed condition separately. Use participant-level summaries for paired comparisons rather than treating every trial as an independent participant.

## Attention CSV

One row per submitted instruction-check response: `run_id`, `answer`, `passed` (0/1), and `created_at`. Incorrect responses are retained even after a successful retry. The first successful attempt transitions the run to its photo trials.
