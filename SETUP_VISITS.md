# Run the fixed project

Run all commands from the extracted `AiHealth-main` directory, not its parent.
The existing Python/FastAPI, SQLAlchemy, PostgreSQL/SQLite and plain JavaScript stack is retained. No frontend build or npm install is needed to run the app.

## Windows 11 (Command Prompt)

```bat
cd C:\path\to\AiHealth-main
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe migrations\20261016_consultation_decisions.py
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 and hard refresh once with Ctrl+F5. Use this address consistently. First-party JS/CSS URLs are versioned to avoid loading an old interface against the new API.

## macOS / Linux

```bash
cd /path/to/AiHealth-main
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python migrations/20261016_consultation_decisions.py
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## Existing installation / database

Stop the old server. Back up your working directory, `.env`, database and `uploads` directory. Copy this release's source files over the existing installation while retaining your own `.env`, database and uploaded documents. Do not replace your live database with the database included in this ZIP. The bundled `pulsesync.db` is the original attachment's database, unchanged byte-for-byte.

Use the same `DATABASE_URL` and JWT secret as your existing installation. With no `DATABASE_URL`, the app uses `sqlite:///./pulsesync.db` relative to the current working directory. Do not accidentally launch from a different directory and create another database.

For an existing PostgreSQL installation, retain its working `.env` configuration and run the same migration command. The migration uses SQLAlchemy's dialect-aware metadata and existing additive initializer. PostgreSQL execution was not available in this verification environment; test against a backup/staging database before applying to a deployed PostgreSQL instance.

The migration adds:

- Nullable JSON `medications.instructions` (old rows are backfilled from their recorded prescription or patient-reported medication data when accessed).
- `consultation_plans`: one versioned draft/final decision document per consultation.
- `outpatient_appointments`: an outpatient request linked uniquely to its referral, with preferred/scheduled time and hospital response.

It does not drop tables or delete medical/dispensing records. It can be run repeatedly. Startup also calls the additive initializer. SQLite's existing automatic pre-migration backup behavior remains, but make your own backup for each upgrade.

## Use the corrected workflow

1. Register the receiving hospital, pharmacy and doctor using their existing role forms and six-digit PIN fields.
2. Register a patient. Under Current medication, choose Yes, enter a count, generate rows and fill medicine, disease/reason, frequency and food instructions.
3. As the patient, use Appointments / Follow-ups to submit intake to the doctor. This creates the existing legitimate assigned-care relationship. Consent/QR access is also retained; scanning identification alone grants no access.
4. As the doctor, open Queue, open the encounter, then choose the prominent Doctor’s Note action in its header. You can enter decisions before completion.
5. Prepare one or more frequency/replacement/addition decisions. The frequency action never asks for a dispensing quantity. Addition/replacement quantities are optional: blank means instructions only; entering a quantity explicitly creates an order for the existing dispensing workflow. A selected pharmacy requires an explicit quantity.
6. Prepare a referral using actual facility search, or enter an external destination. Location and distance availability are stated. Review the clinical summary yourself.
7. Save draft to retain work. Reopen Doctor’s Note to restore it. Review check-up shows old/proposed instructions and warnings. Finalize check-up saves all connected changes together.
8. As the patient, open Medical History and choose View complete check-up record beside the finalized consultation. Download is a self-contained HTML document. Print opens a printable page; choose Save as PDF in the browser's print dialog if wanted. External destinations also have separate referral-letter print/download actions and appear in Referrals.
9. As the receiving hospital, open Outpatient appointments and confirm, reschedule or decline the request. Confirmation/rescheduling requires an explicit time. Patient and referring doctor receive notifications.
10. As the pharmacy, use the existing authorized prescription queue and inventory/dispensing flow. Food instructions are displayed. Instructions-only records cannot be dispensed as refill orders.

## Tests

Python tests use isolated temporary databases, not your working database:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q --disable-warnings
```

Browser tests require Node plus Playwright and Chromium (test tooling only; this does not change the application stack):

```bat
npm install --no-save playwright
npx playwright install chromium
node tests\browser_visit.cjs
node tests\browser_secure_qr.cjs
node tests\browser_smoke.cjs
```

Run the browser scripts sequentially; each starts and stops its own local server and isolated database. The scripts accept `BROWSER_EXECUTABLE`; the visit/smoke scripts also accept `BROWSER_ARGS` as a JSON array for an existing Chromium installation. The QR suite additionally requires `ffmpeg` for its simulated camera feed. On Linux replace backslashes in these commands with slashes.
