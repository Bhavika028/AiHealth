# Registration implementation and verification

Tested 16 October 2026. The supplied application, FastAPI/SQLAlchemy backend and existing vanilla JavaScript frontend were retained. No database schema change was needed: registration already stores current_medications and the existing idempotent clinical projection creates PATIENT_REPORTED medication records with the full instruction dictionary. No parallel medication system was added.

## Implemented behaviour

- Patients: Account details, Personal details, Medical background, Insurance, Security and review (five steps).
- Doctors, hospitals and pharmacies: Account details, role-specific profile/location, Security and review (three steps).
- Only the current step is visible. Values remain in form memory during navigation. Current-step validation focuses the first invalid control; native hidden-field validation cannot block other roles or steps.
- Percentage counts previously completed steps that still validate, divided by the role's step count. Filling fields alone does not complete a step. Optional and conditional hidden fields are excluded from required counts; successful creation is the only path that sets 100%.
- Explicit medication Yes/No; numbered structured cards; positive integer frequency 1–24 (the existing API limit); food instructions; optional dose and additional instructions. Yes requires at least one complete card. Duplicate names generate review warnings rather than silently discarding entries.
- Increasing the medicine count retains existing cards. To decrease it, remove specific cards, avoiding silent truncation of entries. Switching to No retains cards in memory but submits an empty list.
- Review is grouped by section with Edit actions. Password and PIN values are excluded. Hidden insurance policy values are excluded from both review and payload when insurance is off.
- Submission locks controls and rejects a second submission while saving. Server failures retain values and display an inline alert.
- The existing active-medication table and Doctor's Note now also display the patient-reported reason and additional instructions. Existing frequency amendments preserve the original instruction dictionary, including food, disease/reason and additional instructions. Replacement food prepopulation continues through the existing medFields function.

## Browser-verified — PASS

Command (from project root):

```sh
BROWSER_EXECUTABLE=/tmp/chromium BROWSER_ARGS='["--no-sandbox","--disable-dev-shm-usage"]' node tests/browser_registration.cjs
```

Use your installed Chromium path or omit BROWSER_EXECUTABLE when Playwright browsers are installed. Tests use temporary isolated SQLite databases and block external HTTPS resources.

Actual headless Chromium UI interactions at 1440x1000 and 390x844 verified:

- Successful patient, doctor, hospital and pharmacy registration; also a patient submitting No medicines.
- Empty required fields rejected, Back preserves account values, Edit preserves medication entries, final review contains the entered medicines and food instructions but no password/PIN values.
- Initial patient required count is 0 of 5. Validating Account advances overall progress to 20%. Security review remains below 100% before creation.
- Explicit medication answer required; Yes/No/Yes retains cards; adding and removing a third card retains the first two; invalid zero frequency rejected; duplicate medicine names flagged.
- Insurance-off hides policy details from review. Optional profile fields do not block progression.
- Two synchronous final form submissions produce exactly one POST. An existing-email response (HTTP 400 in this application) displays an error and preserves the PIN and account fields. No draft/password/PIN localStorage key is created.
- Mobile review fits the viewport without horizontal page overflow. Mobile review screenshot visually inspected; screenshots are internal test artifacts, not packaged deliverables.
- Registration medicines appear in actual doctor encounter and Doctor's Note. Existing After food is prepopulated for frequency changes. Frequency change, replacement, additional medication, draft save/restore, finalization, hospital referral, receiving-hospital confirmation, notifications, patient record download and pharmacy dispensing complete through the interface.
- Patient active prescriptions show the revised medicines after finalization. A No-medicines patient starts with an empty Doctor's Note list and can receive multiple new medicines.
- No JavaScript page errors.

Additional regression command:

```sh
BROWSER_EXECUTABLE=/tmp/chromium node tests/browser_secure_qr.cjs
```

PASS: all four role colours remain distinct; four-role PIN registration including leading zero, mismatch and Show/Hide; QR downloads decode using the bundled decoder; image upload, blank-image handling, text scanning, simulated live camera scanning, camera-denied/unavailable messages, track cleanup on close/navigation/logout, separate-session patient approval/revocation, consent and emergency routing, cross-device URLs, PIN setup/change/reset, desktop/mobile dashboard widths; no JavaScript page errors.

The camera run uses a generated video as Chromium's fake camera input. It is not a physical-camera test.

## Backend-only — PASS

```sh
python -m pytest tests -q --disable-warnings
```

Result: 5 passed, 655 deprecation warnings, 8.81 seconds.

Coverage includes clinical journeys, migration preservation/idempotency, PIN/access lifecycle, atomic visit finalization and appointment/dispensing rules. The visit regression was extended to assert that registration additional instructions survive projection and a finalized frequency amendment; registration medicines create no prescription orders and projecting them again leaves exactly two medications.

The supplied pulsesync.db was compared by SHA-256 with the input ZIP and is byte-for-byte unchanged. No test users or test uploads are included in the delivered project.

## Known legacy test and unverified checks

- A separate exploratory `python -m pytest -q` run from the enclosing workspace found an existing failure in `test_jwt_and_map.py::test_full_flow`: its old registration fixture omits mandatory pin and confirm_pin and receives HTTP 422. The five maintained tests above pass. PIN validation was not weakened to accommodate this outdated fixture.
- Physical webcams, real mobile hardware, screen-reader announcements and a full keyboard-only journey were not manually tested. Labels, live status/error regions, visible focus styling and first-invalid focus are implemented.
- Production PostgreSQL, external map services and external AI services were not exercised. Browser runs use isolated SQLite and blocked external requests.
- Network-outage error handling is implemented but the browser failure-retention test specifically uses the application's duplicate-email HTTP 400 response.
- A same-form rapid double submit is browser-verified. Cross-device/concurrent account-creation races and load testing are outside this run.

## Preservation

Authentication, QR, camera scanning, consent, emergency access, consultation drafts, prescriptions, referrals, appointments, original records and original backend source/schema remain in place. Functional browser regressions cover the connected flows described above; this is not a claim that every existing screen was manually reviewed.
