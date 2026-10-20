# Run this updated existing project

The original FastAPI, SQLAlchemy, SQLite/PostgreSQL and plain JavaScript stack remains in place. No rebuild or database replacement is needed.

## Windows 11

1. Extract the ZIP. Open `AiHealth-main` in VS Code, then open a terminal there.
2. Create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell activation is blocked, use Command Prompt and `.venv\Scripts\activate.bat`, or run `.venv\Scripts\python.exe` directly for the commands below.
3. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
4. Keep your existing `.env`, `DATABASE_URL`, `JWT_SECRET`, database and uploaded-document directory. No live secrets are distributed in this ZIP. For a fresh local demo, omit `DATABASE_URL` to use the included original `pulsesync.db`. Do not run seed/reset scripts over your working database.
5. Back up your working database, then run the additive migration:
   ```powershell
   python migrations/20261016_pin_requests.py
   ```
   Startup also applies this idempotent migration. It adds nullable PIN columns and a request table. Existing accounts retain their passwords and identities, with no PIN assigned. SQLite initialization also creates the existing pre-migration backup if one is absent. For PostgreSQL, take your normal database backup first. Never run `db/schema.sql` against an existing database; it is an empty-database reference.
6. Start the server:
   ```powershell
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
7. Open `http://localhost:8000`. Existing users are prompted for authenticated PIN setup. Account PIN in the top bar provides setup, change and forgotten-PIN reset. Setup/reset require your account password again; change requires both the current PIN and account password. Password login remains unchanged. A forgotten account password uses the existing trusted local-operator recovery command (`python -m backend.manage set-password --email ...`), not a public PIN bypass.

## QR sharing demonstration with two sessions

1. Register patient and provider accounts with a six-digit PIN and matching confirmation. Leading zeros are retained. Use a separate browser profile/private window for the patient and provider, because tabs in the same profile share the app's existing login storage.
2. Patient: My QR → Download QR (PNG).
3. Provider: Scan QR → live camera, image upload, or paste the identity text. Scanning identifies the patient and creates a pending 30-minute provider request; it does not disclose medical history.
4. Patient: QR requests → review provider name, role, scope and expiry → enter the patient's own PIN → Approve access. Deny needs no PIN. The provider never enters a patient PIN.
5. Provider: QR requests → Refresh status. Approved doctors/hospitals can use existing patient/history workflows; pharmacies receive prescription scope only. An approved request grants access immediately on the server; no token needs to be copied between people.
6. Patient: QR requests → Revoke, or Consent & QR → Revoke the grant. Both views reflect the effective status. Expiry is checked on every server access, without needing a browser timer. Refresh the list to display the latest status.
7. Existing assigned-care permissions continue independently of QR grants: revoking a QR grant does not remove a legitimate consultation/referral/admission relationship. Emergency QR access remains a separate, limited-profile bearer-token workflow. Existing direct clinical/prescription consent grants now also require the patient's PIN; emergency grant creation retains its separate workflow.

## Camera and cross-device use

- Cameras require HTTPS or localhost. A phone visiting `http://192.168...:8000` will generally not be allowed to open its camera. Serve the same backend through a trusted HTTPS endpoint/certificate, or use image upload/text. Never disable browser security to enable a camera.
- `localhost` on a phone points to that phone, not your laptop. Open the app at the laptop's reachable LAN address for uploads/text, or its HTTPS address for live camera scanning. On Windows, allow the server port on your private network if needed.
- New patient identity payloads are independent of hostnames. Known legacy patient/insurance/provider/emergency URL paths are parsed as identifiers and looked up on the currently signed-in server. The scanned hostname is never fetched, and your bearer token is never sent there. Unknown hosts do not establish trust: a matching record/grant must exist locally and normal authorization still applies. Wrong-server IDs fail safely. Unknown paths, URL credentials, query strings and fragments are rejected.
- Keep the whole code and its white border visible, hold steady, avoid glare, and try greater distance if it cannot focus. Generated PNGs now use a four-module white margin. The bundled jsQR decoder works offline; maps and existing external styles retain their previous dependencies.
- Scan again / Start camera restarts after failure or denial. Camera selection appears after permission is granted. Closing, navigation, logout and hiding the page stop tracks; return to the scanner and restart if needed.
- Five failed PIN/password verifications in PIN actions lock that account's PIN actions for 15 minutes, persisted in the database. A valid PIN/reset cannot bypass an active lock. No public reset link or email delivery was added; forgotten PIN reset requires an authenticated session plus fresh password proof.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Browser tests additionally require Node.js, Playwright/Chromium and ffmpeg on PATH:

```powershell
npm install --no-save playwright
npx playwright install chromium
node tests/browser_secure_qr.cjs
node tests/browser_smoke.cjs
```

`BROWSER_EXECUTABLE` may select an installed Chromium binary. The QR suite uses Chromium's simulated camera with real generated video frames, not a physical camera. All test actors and data use isolated temporary databases. See `TEST_REPORT.md` for exact verified scope and limitations.
