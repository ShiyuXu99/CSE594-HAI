# Assignment III — Facial Expression Study

## Study links

- `/prototype`: prototype with synchronous AI inference, a predicted label and confidence.
- `/baseline`: baseline without AI output.
- `/admin`: authenticated read-only dashboard, participant details and CSV exports.
- `/health`: application availability check.

Both versions use 20 images sampled from the fixed 200-image Assignment II dataset (five per category, shuffled). Images assigned in one condition are excluded from the other for the same participant. A user name is required and can only be registered by one participant (case-insensitive). Use the same user name and browser for both conditions. A generated UUID is the primary key. The same browser preserves that UUID across conditions; names do not link identities. Class scheduling controls condition order, which timestamps record.

Both conditions ask for a 1–5 confidence rating after each image answer. The rating is saved with the answer as `trial_confidence` and included in the trial export. Earlier trials have no per-image rating.

A single attention check is randomly placed after image 1–19 and saved, so refreshing does not move it. Failed attempts are recorded and may be retried. The check is separate from the 20 scored images. The final questionnaire asks Mental Demand (adapted from the NASA-TLX item) on a 1–5 scale, plus an optional comment. Analyze these separately, not as a NASA-TLX total. Earlier sessions retain their original seven-point scale and previously completed checks.

## Synchronous AI

After the current image loads, the browser calls `/api/ai/predict`. The server executes the model on that image at request time. No label or confidence is read from the stored Assignment II prediction columns. The model is loaded once per worker and shared by threads. Inference errors show a retry option and do not fall back to stored predictions.

`model/emotion.onnx` is an inference export of Assignment II’s finalfacialemotionmodel.keras, with no retraining or quantization. Preprocessing is unchanged: Pillow grayscale, 48×48 resize with its default filter, float32/255, original output indices [0,3,5,6], renormalized across angry/happy/sad/surprise. `model/validation.json` records hashes and verification against all 200 original labels/confidence scores. `tools/export_model.py` can rebuild and verify it using TensorFlow 2.20.0, tf2onnx, onnx and the runtime dependencies, with Assignment II available alongside this directory. The original license is retained.

The UI shows the label, rounded confidence percentage and a meter labeled Less certain → More certain. Higher means the model is more certain, not a calibrated probability that it is correct. The unscored homepage example is illustrative and uses an image outside the 200 study images.

Each inference request is logged in `a3.inference_events` with request ID, image/session IDs, success/failure, requested/generated timestamps, predicted label, exact confidence, all four scores, model hash/version and inference latency. After rendering, the browser posts a display receipt to `/api/ai/displayed`. The final answer must reference a confirmed displayed inference ID. Refresh/retry produces a new real inference event. Unacknowledged outputs remain distinguishable from outputs confirmed displayed. Baseline never calls inference or receives model outputs. Earlier offline predictions remain marked asynchronous; display receipts start with this version.

## Local setup

Use Python 3.12:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure the existing Supabase Session pooler connection and a stable SECRET_KEY. For a fresh database run `python init_db.py`; for an existing database run `python migrate_db.py`. Only `a3` objects are created/updated. Original assignments and existing responses remain unchanged. RLS is enabled; only the trusted backend database role accesses study tables.

```sh
gunicorn wsgi:app --workers 1 --threads 4 --timeout 120 --bind 127.0.0.1:5003
```

`wsgi.py` loads and warms the CPU model before accepting requests. Deployment runtime uses ONNX Runtime, not TensorFlow.

## Temporary testing

`ALLOW_RETEST=true` shows Restart test in both versions. This clears only the browser participant ID and generates a fresh UUID on the next start; it does not erase responses or sign out admin. There is no IP-based participant limit. Disable this flag and restart before formal collection. Keep testing responses distinguishable from actual participant data.

## Admin and export

Configure ADMIN_USERNAME and ADMIN_PASSWORD_HASH (a Werkzeug password hash) in the server environment. A local ignored admin-credentials.txt may contain the initial credentials. Do not commit credentials. Sign-in expires after one hour and password-hash rotation invalidates existing sessions. POST requests require CSRF tokens. A shared database-backed limit blocks further login attempts after eight failures within 15 minutes.

The dashboard supports name/ID search, condition/status filters and pagination. Participant detail shows condition order, image answers, correctness, active/elapsed time, reference AI outputs, actual displayed outputs/confidence/source, check attempts, questionnaires/comments and all real-time AI events. Sessions, trials, checks and inference events can be downloaded as CSV after sign-in. Exports escape spreadsheet formula prefixes. The panel cannot edit or delete records.

`python export_data.py` also exports sessions, trials and inference events privately into the ignored exports directory.

Response-time definitions: shown_at is first server delivery; submitted_at is answer storage; active_ms is visible-browser time since the image loaded on the current page visit, including AI wait and expression-guide time, resetting on refresh. Inference latency is logged separately. Server elapsed time includes absences. Summarize per participant, distinguish trial counts from participant counts, and report incomplete-session exclusions. The five-to-eight-minute estimate requires a pilot.

## Deployment

Use a separate Render Python web service for Assignment III. The supplied render.yaml uses the free plan, one worker and four threads. Keep the existing Assignment I service separate. Configure DB_*, SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD_HASH and RENDER=true through Render environment variables. ALLOW_RETEST remains enabled for this testing deployment. Free instances can sleep when idle; classroom cold-start behavior still needs checking.

When creating the service from repository root, build with `cd 'Assignment III' && pip install -r requirements.txt` and start with `cd 'Assignment III' && gunicorn wsgi:app --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT`. Set PYTHON_VERSION=3.12.12. Run the explicit database migration before accepting participants.

## Verification

- `python tests/test_study.py`: in-memory database adapter and stub model for workflow/privacy/idempotency checks, including inference/display gating.
- `python tests/test_live_admin.py`: opt-in real PostgreSQL/model integration checks; migrations and test responses run in a transaction and roll back.
- Model export validation checks all 200 labels and scores. Logs distinguish synchronous output from existing asynchronous rows.

The Assignment II hypothesis/report is not included; check the final presentation against it before formal collection. To evaluate the contribution of confidence alone requires a separate label-only condition; this two-condition study measures the complete AI assistance design.
