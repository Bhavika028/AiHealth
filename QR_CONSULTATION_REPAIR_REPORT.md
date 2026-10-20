# QR-to-consultation authorization repair (19 October 2026)

## Working base
`PulseSync_HealthFlow_SECURITY_PROGRESS(1).zip` (existing project preserved).

## Cause
`HF.scanResult()` silently submitted a consent request and returned a status string rather than presenting explicit identification and approval controls. The consultation POST path only used `patient_access()`, which accepts broader clinical grants and did not bind an approved patient/doctor request to the new visit. Existing consultation lists could also show fields from unapproved records.

## Changes
- `frontend/workflow.js`: QR identity recognition now fetches only a minimal authenticated identity card, shows **Request Consultation Access**, enables separate refresh/status, and exposes **Start Consultation** only for a server-approved request. The patient PIN is never requested in doctor UI. Fixed identification QR type to `identity` to match existing backend.
- `backend/routers/qr_engine.py`: authenticated minimal patient identity endpoint, with no records/PIN.
- `backend/workflow_models.py`: additive `consultation_authorizations` join table; does not alter prior consultations or existing records.
- `backend/routers/workflow.py`: doctor-created consultations require a specific approved access request. Approval is matched to the logged-in doctor and patient; the request can be used for only one newly created consultation. Unapproved doctor queue entries return limited scheduling data rather than clinical details.
- `backend/security.py`: checks linked approval for Doctor's Note and consultation resource actions; revoked/expired approvals are denied. Historical visits do not imply consent. Legacy patient-issued PIN-protected clinical grants still work for previously created encounters.
- `tests/test_qr_consultation_authorization.py`: two independently authenticated doctor/patient sessions, cross-patient and wrong-provider rejection, wrong PIN, correct PIN, approve, start, double-use, revoke, deny, expire and historical access checks.

## Verified
- `python -m pytest -q tests/test_qr_consultation_authorization.py tests/test_pin_access.py tests/test_visit.py`: **3 passed**.
- `node --check frontend/workflow.js`: **passed**.
- `python -m pytest -q` yielded **6 passed, 1 failed**. The remaining migration test depends on a `pulsesync.db` fixture that is **not included in the supplied ZIP**; no real patient database was invented or overwritten. See `tests/test_migration.py`.

## Limitations
- Automated Python API tests exercised separate authenticated sessions and the backend authorization lifecycle. Actual camera scanning in a live browser was **not** executed on this host; user should verify device camera permissions and the live interaction locally.
- Requests/authorization last for the configured lifetime; a revoked or expired grant prevents subsequent doctor record access and edits. A new request is necessary for a new QR-initiated consultation.
- This is a prototype security repair, not a claim of regulatory certification or production-ready healthcare security.

## Windows startup (CMD)
Open CMD inside `AiHealth-main` after extraction:
```
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
copy .env.example .env
python -m backend.manage init
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Visit http://127.0.0.1:8000/ and hard-refresh (Ctrl+F5). On later launches: activate `.venv`, then rerun the `uvicorn` command. The `init` routine is additive; back up an existing database before running migrations, and avoid running against production without review.

Test from the same project directory:
```
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/test_qr_consultation_authorization.py tests/test_pin_access.py tests/test_visit.py
```
