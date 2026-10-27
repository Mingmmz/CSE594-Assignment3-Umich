# Product Inspector — Assignment 3, Part 1

Two study interfaces for genuine/counterfeit product classification, using the **200 frozen study images and AI outputs from Assignment 2**. The trial interface keeps the two-pane approach from Assignment 1. Onboarding uses a single column: instructions first, then participant ID and consent below them.

**Current status:** working local preview. GitHub, Supabase, and Render have not been changed. Deployment and posting the two public links are intentionally deferred until you approve the design.

## Try the preview

From `/Users/mmz/HAI`, run:

```bash
Assignment-3/authenticity_study/scripts/run_local.sh
```

Then open:

- Study entry: <http://127.0.0.1:5001/>
- Without AI: <http://127.0.0.1:5001/without-ai>
- With AI: <http://127.0.0.1:5001/with-ai>
- Researcher view: <http://127.0.0.1:5001/admin>

Local researcher username: `admin`; local password: `local-preview-only` (or your exported `ADMIN_PASSWORD`). This default is **only** set by the local launcher. Production researcher access is disabled unless a password is explicitly configured.

The launcher uses the existing Assignment 1 Python environment if this folder has no `.venv`. To make the project independent:

```bash
cd /Users/mmz/HAI/Assignment-3/authenticity_study
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./scripts/run_local.sh
```

The yellow practice banner identifies local storage. Practice answers go to `data/practice.sqlite3`, which is ignored by Git. They are not sent to Supabase. Browser testing used the participant code `QA-local-preview`; those records are practice data.

## Participant workflow

1. Read the task and purpose sentences, label definitions, and instructions at the top. The participant ID and consent form follows below all instructions; enter a pseudonymous ID, optionally report familiarity, and consent.
2. Pass an easy instruction check. Wrong answers receive corrective feedback and can be retried; attempts are recorded.
3. Complete 10 randomly sampled photos.
4. In **Without AI**, choose a binary answer and confidence (1–5), optionally mark uncertainty or leave a note, and submit once to move directly to the next photo.
5. In **With AI**, first save an independent answer and confidence. Then review the model prediction, calibrated confidence, and Grad-CAM overlay; keep or change the final answer and rate trust (1–5).
6. In With AI, rate final confidence and select at least one required reason for trust or your decision, including “I didn’t change my answer” when appropriate. The reasons and a larger optional note/issue box are always expanded. Optionally mark uncertainty or leave a note. Both conditions allow image-load failures to be reported and skipped separately from classification responses.
7. Answer the mental-effort question (1–7), plus AI usefulness (1–7) in the AI condition, and optionally leave comparative feedback.
8. See confirmation that the study is complete. No completion code is shown or needed. Follow the class schedule before opening the other condition, and reuse the same participant ID.

Submitting a final answer advances directly to the next photo. After the last photo, the final questionnaire opens directly. The new-run choice appears only after the questionnaire has been submitted and the full run is complete. There is no per-photo saved screen, continue button, restart prompt, or header restart button.

A participant can reuse the **same code** for both conditions and for as many additional runs as needed. Each run gets a separate internal session, attempt number, and trial assignment. Earlier responses are retained. Images are drawn from previously unassigned items for that code where possible; after the 200-item pool is exhausted, repeated items are marked with `prior_exposures`.

Refresh resumes the saved stage on the same browser. Unsaved selections and comments are not persisted. Different conditions have separate browser resume tokens. A lost token cannot be recovered using the participant code alone, to avoid exposing another participant's responses. Use the restart option on the completion screen to start another run or switch participants; the prior run remains in the data.

## Study design and submission notes

See [A3-1_STUDY_DESIGN.md](A3-1_STUDY_DESIGN.md) for the rationale, measurements, condition order, repeat-run policy, and remaining submission steps. See [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for exports.

The 6–8 minute estimate (including the required trust reasons) is a design target, not a measured human pilot result. Complete a realistic timed pilot before collection. Reduce `TRIALS_PER_SESSION` before the study if the instructions, trials, and questionnaire take 10 minutes or longer. Keep the same count in both conditions and avoid changing settings during collection.

## Later: Supabase + Render

This project uses the same approach as Assignment 1: **Flask + psycopg → Supabase PostgreSQL**, hosted by **Gunicorn on Render**. AI outputs are served asynchronously from the frozen Assignment 2 files; no PyTorch model server, GPU, Colab session, or new inference is required.

1. Push this folder's contents to the repository you choose. Include `data/study_manifest.json`, `data/stimuli/`, and `schema.sql`; exclude `.env`, `.venv`, practice databases, and caches. Do not push the whole Assignment 2 dataset or model checkpoints.
2. In Supabase, open **Connect → Session pooler** and copy the actual connection URI. For this persistent backend, the session pooler is the IPv4-compatible option. Use its exact host, username, and password; do not guess the pooler host.
3. Configure `DATABASE_URL` and a new strong `ADMIN_PASSWORD` in Render. Set `TRIALS_PER_SESSION=10` and `TRUST_RENDER_PROXY=1` (the Blueprint includes both). The latter trusts Render’s TLS-termination scheme header so HTTPS form requests are validated correctly. Do **not** set `LOCAL_SQLITE_PATH` in production. SSL is required by the database adapter; automatic prepared statements are disabled for pooler compatibility.
4. Create a Render Python web service. If the repository root is this app folder, the supplied `render.yaml` contains the settings. If the repository contains the whole HAI workspace, set Render's Root Directory to `Assignment-3/authenticity_study`; keep build/start commands relative to that directory.

   - Build: `pip install -r requirements.txt`
   - Start: `flask --app app:create_app init-db && gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 60 wsgi:app`
   - Health-check path: `/healthz`

5. Initialization creates the separate **`a3_study` schema** and its `sessions`, `trials`, and `attention_events` tables. It does not change Assignment 1 tables. Tables have RLS enabled and no browser-facing policies. The browser talks only to Flask. You can inspect them in Supabase using the schema selector or SQL Editor.
6. Verify `/healthz` reports `storage: "supabase"`. Complete one pilot in each condition, export the records, and check their contents before inviting participants. Supabase/PostgreSQL and Render deployment have **not** been exercised in this local review.
7. Submit the two public URLs, ending in `/without-ai` and `/with-ai`, to the class spreadsheet yourself. Keep the service available during class.

Render's free service may spin down when idle; confirm its current behavior before the class session. No paid service has been selected or purchased.

Configuration sources: [Render Flask deployment](https://render.com/docs/deploy-flask), [Render health checks](https://render.com/docs/health-checks), [Supabase connection methods](https://supabase.com/docs/guides/database/connecting-to-postgres), [Psycopg pooler settings](https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL).

## Verify the local implementation

From this folder with the environment activated:

```bash
python -m unittest discover -s tests -v
node --check static/app.js
DATABASE_URL='' LOCAL_SQLITE_PATH=data/practice.sqlite3 flask --app app:create_app verify-data
```

Tests use temporary databases and cover both conditions, completion, repeat runs, concurrent starts, no-overwrite retries, resume, authorization, AI access restrictions, image-error skips, pool exhaustion, malformed payloads, protected exports, and spreadsheet formula escaping. They do not connect to Supabase.

For first-time database initialization outside the local launcher:

```bash
flask --app app:create_app init-db
```

Missing DB configuration stops the app. A production database failure never silently switches to SQLite.

## Source and assets

- `app.py`: routes, workflow validation, sampling, measurement logging, protected exports.
- `store.py`, `schema.sql`: transactional storage and separate PostgreSQL schema.
- `templates/`, `static/`: responsive interface; local fonts; no external trackers.
- `data/study_manifest.json`: private reference labels, frozen AI outputs, checksums, and model settings.
- `data/stimuli/`: 200 original photos and 200 unmodified Grad-CAM overlays, copied under opaque names. Originals retain aspect ratio in the interface; Grad-CAM retains its 224×224 model-input coordinates.
- `prepare_study.py`: reproducibly copies only the study split from the adjacent Assignment 2 folder. It is not needed on Render because the packaged assets are already present.
- `render.yaml`, `.env.example`: deployment configuration without secrets.

Do not regenerate or edit the frozen manifest while collecting data. The manifest version includes image checksums, labels, predictions, and model settings. An in-progress session refuses to continue against a changed dataset.

Preview screenshots: [instructions-first onboarding](docs/onboarding-desktop.jpg), [mobile onboarding](docs/onboarding-mobile.jpg), [AI review](docs/ai-review-desktop.jpg), [baseline desktop](docs/baseline-desktop.jpg), [baseline mobile](docs/baseline-mobile.jpg).

## Dataset source audit

Run `python scripts/audit_study.py` while the adjacent Assignment 2 folder is available. The audit confirms an exact match to `data/study.csv`, byte-for-byte matches for all 200 originals and their 200 study Grad-CAM overlays, unchanged AI outputs, zero extra packaged images, and no overlap of trial identities with the train/validation/test split CSVs. See [docs/DATASET_AUDIT.md](docs/DATASET_AUDIT.md).

## Condition indicators

Without AI uses amber and With AI uses blue. One sticky header combines the website name, large condition label, workflow reminder, and Instructions button throughout onboarding, trials, and completion. Explicit condition names identify the condition independently of color. Entry cards use the same colors, and browser-tab titles start with the condition name. Photos and answer controls retain their common styling in both conditions.
