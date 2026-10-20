> Latest consultation repair: start with [SETUP_VISITS.md](SETUP_VISITS.md). Root causes, changed files and verified/unverified checks are in [TEST_REPORT.md](TEST_REPORT.md).

> **Current QR/PIN update:** Start with [SETUP_PIN_QR.md](SETUP_PIN_QR.md). See [QR_UPDATE.md](QR_UPDATE.md) for changes and [TEST_REPORT.md](TEST_REPORT.md) for verification. Run the additive migration; keep your existing database and configuration.

> QR download, camera scanning and role colour update: see [QR_UPDATE.md](QR_UPDATE.md) for usage, camera setup and verification.

# PulseSync / HealthFlow — connected care demo

This updates the supplied project in place. It retains Python/FastAPI, SQLAlchemy, SQLite or PostgreSQL, the existing adaptive intake and multilingual symptom parser, QR generation, and vanilla HTML/CSS/JavaScript. The authenticated portal now uses a restrained clinical interface with separate patient, doctor, hospital, and pharmacy workflows.

## Run on Windows 11 with VS Code / PowerShell

1. Install Python 3.10 or newer (3.12 recommended). Enable “Add Python to PATH”.
2. Extract the ZIP. Open the `AiHealth-main` folder in VS Code. This is the folder containing `requirements.txt` and `run_app.bat`.
3. Open Terminal → New Terminal and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m backend.manage init
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

4. Wait for “Application startup complete”. Open http://127.0.0.1:8000 . API documentation is at http://127.0.0.1:8000/docs .
5. Keep the terminal open. Stop with Ctrl+C. To restart, run the final command again.

Alternatively, double-click `run_app.bat`. It creates the virtual environment if needed, installs requirements, and runs the server. `start.bat` also calls it. Virtual-environment activation is not required, avoiding PowerShell execution-policy issues.

No Node, npm, PostgreSQL installation, cloud account, or AI API key is needed for the local demo. Installation requires internet; stored clinical records work without map or AI services.

## Database and migration

- The original uploaded `pulsesync.db` is retained unchanged in this ZIP. New registrations and clinical records persist in that database after startup.
- First startup creates `pulsesync.db.pre-healthflow.bak` before applying additive migrations. Existing tables and rows are preserved. New clinical tables and columns are added; no seed command runs automatically.
- Startup migrations are idempotent. To apply them explicitly: `python -m backend.manage init`.
- To start an empty demo **without deleting the supplied database**, set `DATABASE_URL=sqlite:///./healthflow-demo.db` in `.env`. The new file is created automatically. Register accounts yourself; no sample patients or hospitals are inserted.
- For PostgreSQL, create an empty database and put your own URL in `.env`; use the same initialization command. Configured PostgreSQL connection failures stop startup instead of silently switching databases. PostgreSQL was not available for execution testing in this environment.
- Runtime schema is defined by `backend/models.py` and `backend/workflow_models.py`. `db/schema.sql` is a generated PostgreSQL reference. The older Prisma file and seed scripts are historical references, not runtime migrations. Do not run them against the updated demo.

### Existing hospital accounts

The old application never stored hospital ownership, so existing hospital accounts cannot safely be associated by guessing the first hospital. Newly registered accounts link correctly automatically. For an existing account, use explicit local recovery:

```powershell
.\.venv\Scripts\python.exe -m backend.manage list-hospitals
.\.venv\Scripts\python.exe -m backend.manage link-hospital --email "admin@example.com" --hospital-id "the-listed-hospital-id"
```

Existing password hashes remain usable. Legacy accounts with no password require local recovery, rather than accepting the first password supplied at login:

```powershell
.\.venv\Scripts\python.exe -m backend.manage set-password --email "existing@example.com"
```

## Demo journey

1. Register a patient, a clinic doctor, a hospital, a pharmacy, and a specialist doctor. Use separate browser profiles or sign out to switch roles. Providers become available immediately; no license approval or external verification is required.
2. During hospital registration, enter address and coordinates, use current location, or click the map. Manual coordinates work when maps fail. Update coordinates later in provider settings. Address-only facilities appear with distance unavailable.
3. Patient → Nearby Care: find the registered hospital. Patient → Appointments: select the doctor, enter symptoms, and submit the adaptive intake.
4. Doctor → Queue → Open encounter: start review, record diagnosis certainty and vitals with units and measurement times, then complete the consultation. Draft records do not appear as finalized history.
5. Doctor → Issue prescription: select a registered pharmacy. Enter dosage, frequency, duration, and dispensing quantity. Review any allergy / duplicate-medicine warning. Replacement prescriptions can mark the old medication changed with a reason.
6. Pharmacy → Inventory: add the exact medicine name and stock. Prescriptions → Dispense: stock is deducted atomically, and patient notifications and dispensing history are recorded. Medication course state remains separate from dispensing state.
7. Doctor → Refer to hospital: select the registered hospital, reason, specialty, and priority.
8. Hospital → Incoming Referrals: receive, accept, and mark the patient arrived.
9. Hospital → Doctors: create a one-hour invitation. The specialist doctor pastes it in Clinic settings. Hospital → Incoming Referrals → Specialist encounter: assign that doctor. The doctor records and completes the specialist encounter in their own consultation view.
10. Hospital → Admissions: select the authorized patient, available bed, and responsible clinician. Include the specialist consultation ID and referral ID to retain the encounter link. Discharge with a summary; the bed enters CLEANING. Beds / Wards → Mark available only after cleaning.
11. Hospital → Incoming Referrals → Complete: record the outcome. The referring doctor sees it.
12. Doctor → Open encounter → Schedule a follow-up. Patient sees it in Appointments and can start a linked follow-up intake.
13. Patient → Medical History: see consultation, diagnostic certainty, vitals, medication, referral, specialist, admission, discharge, and follow-up events. Documents supports previous-record upload and system prescription / referral / discharge records; “View / print” uses the browser print dialog.
14. Patient → Generate history summary: a configured model produces an unreviewed AI summary with source references. Without a model, an explicitly labelled factual record digest is stored instead. Underlying records remain accessible in both cases.
15. Patient → Consent & QR: issue a provider-specific clinical or prescription grant, or an expiring limited emergency QR. Revoke it at any time. The identification QR alone grants no clinical access. Patient → Access log shows important accesses and changes.

## Authorization and records

Patients access their own records; doctors access assigned patients or current clinical consent; hospitals access their own operations and authorized referrals/patients; pharmacies see assigned or consented dispensing information and necessary allergies. Hospital administrators cannot diagnose or finalize an assigned clinician's encounter. Backend checks enforce these rules independently of navigation.

Clinical corrections preserve before/after values, editor, reason, and timestamp. Records are corrected or marked entered in error rather than deleted. Patient-reported conditions and allergies remain labelled separately from clinician records. Profile confirmation timestamps, notifications, and upload provenance are persisted. Medication end dates and due follow-ups are evaluated on portal access; notifications do not depend on a background worker. No email/SMS service is implied.

The local application creates a private `.jwt-secret` when `JWT_SECRET` is omitted. Keep that file for sessions to survive restarts; it is excluded from the ZIP and git. Signing out revokes that session token. Document downloads require authorization; uploads accept PDF, PNG, JPEG, or UTF-8 text up to 10 MB and are stored outside public static files.

## Optional AI and maps

Use `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL` in `.env` for an OpenAI-compatible chat-completions endpoint. Keys stay on the backend. The prompt uses only stored facts, preserves diagnostic certainty, and requests uncertainty. AI results remain unreviewed until a clinician reviews them. The older current-consultation summarizer and multilingual parser are deterministic assistance, not an external model.

Leaflet and OpenStreetMap are optional. Set `ENABLE_EXTERNAL_MAPS=false` to skip external facility lookup. Database hospitals/pharmacies and manual coordinates remain functional. Distance uses coordinates, not inferred addresses; no geocoding is fabricated. Map-listed ratings and verification are not invented. Labs, document OCR, external approvals, and email/SMS are outside this pass.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q -W ignore
```

Tests use isolated temporary SQLite databases and document directories. They cover the complete registered-account journey, cross-account restrictions, dispensing, referral continuity, admission/discharge, duplicate/concurrent bed allocation, medication completion, document permissions, record corrections, consent expiry/revocation, optional AI failure, session revocation, and persistence after login.

Current redesign verification includes real Chromium navigation, forms and responsive checks with external map assets blocked. See `TEST_REPORT.md` for exact coverage and limits. Windows launcher execution remains unverified.


## Information-rich portal redesign (15 October 2026)

The existing FastAPI, SQLAlchemy, PostgreSQL/SQLite support, authentication and clinical workflows remain in place. No new frontend build step is needed. Start the application with the existing instructions above; use a hard refresh after replacing files.

- All four roles now open on a database-backed overview, with clickable metrics, contextual shortcuts, care updates and collapsible sections.
- Patient overview combines follow-ups, active medicines, prescriptions, allergy information, chronological care events, documents, profile confirmation and registered-care shortcuts. Emergency QR opens the temporary-access form with emergency scope selected; creating the QR still requires an explicit submission.
- Doctor overview combines open cases, recorded urgency, active consultations, completed encounters, follow-ups and referral states. The encounter workspace retains its forms and safety checks, with section navigation and visible allergy/medication context.
- Hospital overview combines incoming referral actions, admissions, bed states, actual ward occupancy, discharges, affiliated clinicians and specialist encounters. All records remain scoped to the authenticated hospital.
- Pharmacy overview combines authorized prescriptions, dispensing status, stock attention, restocking and inventory states. The backend whitelist adds only the prescription issue timestamp; clinical history and notes remain unavailable to pharmacy accounts.
- Medical history includes month groups, encounter links, exact related prescription/referral/document dialogs, source labels, expandable details, search, event type, date ranges, and summary/detail modes. Existing draft exclusion is preserved.
- Shared tables provide text filtering, sortable column headers and ten-row pagination. Long tables scroll within their own region. Date columns sort their displayed text; this is not a guaranteed chronological sort across months. Data is fetched from existing endpoints, so pagination is client-side.
- Numeric vital trends require two or more numeric readings with the same measurement name and unit. Text blood-pressure readings are shown as recorded rather than forced into an invalid scalar chart. Every trend also has readable values.
- Shared navigation includes a collapsible sidebar, page search, breadcrumbs, header notifications, keyboard focus states, skeletons and per-account last-page restoration. On mobile, the navigation button toggles the compact navigation region.
- Registration includes keyboard role selection, section shortcuts, manual coordinates, map fallback, and explicit ICU/general bed counts. Providers remain immediately active.

### Frontend files

`app.js` retains authentication and registration. `workflow.js` retains the existing care operations, API client and forms. `ui.js` contains shared table, timeline, trend and navigation components. `dashboards.js` composes the four role dashboards from authorized existing endpoints. `portal.css` provides the responsive visual system. No backend framework or schema replacement is required.

### Optional browser checks

Install Node.js and Python dependencies first, then from the project folder:

```powershell
npm install --no-save playwright
npx playwright install chromium
node tests/browser_smoke.cjs
```

The script starts a separate local server on port 8123, uses temporary test accounts, a temporary SQLite database and a temporary upload directory, and removes its temporary data when finished. It does not modify the supplied database. If a browser binary is already installed elsewhere, set `BROWSER_EXECUTABLE` to that executable. `BROWSER_ARGS` optionally accepts a JSON array of launch flags. The test requires `python` on PATH. Screenshots are disabled by default; `QA_SCREENSHOTS=1` captures temporary screenshots for inspection only.

The ZIP preserves the database bytes supplied in the uploaded project. It contains no accounts or database records generated during this verification. Keep your existing `.env`, private JWT secret and uploaded documents when applying the updated source to an existing installation; never overwrite your current database with the ZIP's database if your installation has newer records.
