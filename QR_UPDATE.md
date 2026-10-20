# QR scanning and six-digit PIN update

This is an in-place update to the attached application. Existing layouts, role colours, PNG downloads, account passwords and connected clinical workflows are retained. The supplied SQLite database is included byte-for-byte unchanged; migration runs against your configured database on startup or with the included migration command.

## Diagnosis

- Patient identity decoding was followed immediately by an authorized clinical-record request. Correctly denied access looked like failed scanning. Identity scans now create persisted, provider-specific requests, exposing only identity and request metadata until patient approval.
- Provider and emergency URL parsing rejected different origins, including localhost versus a LAN/HTTPS address. Recognized path identifiers now resolve only on the current server; arbitrary scanned hosts are never fetched. Existing insurance identity payloads and legacy patient/insurance URLs are supported without disclosing insurance records.
- Generated QR images had only two border modules. The new four-module white margin improves readability without changing stable identifiers.
- Camera setup did not explicitly guard video readiness or request higher resolution/focus, and gave limited decode feedback. It now waits for ready frames, requests rear camera/HD where supported, attempts continuous focus where supported, throttles decoding, exposes retry/switch/upload/text controls, and distinguishes decoder/permission/authorization errors.
- Navigation/logout referenced `window.QRTools`, while the top-level `const QRTools` did not create that property. The scanner is now explicitly exported for those existing cleanup hooks. Tracks stop after scanning, close, navigation, logout, page hide and backgrounding. Stale camera/image operations are discarded.

## PIN and patient consent

- All four registration roles share masked, confirmed six-digit numeric PIN controls, numeric mobile keyboards, show/hide and inline validation. Backend validation enforces ASCII numeric strings and matching confirmation; leading zeros remain intact.
- PIN hashes use independently salted PBKDF2-HMAC-SHA256 with 600,000 iterations. They are distinct from password hashes. PINs are not stored in browser storage, logged, serialized into responses or embedded in QR codes. Validation responses omit input values.
- Nullable additive user fields preserve legacy accounts. Authenticated setup/change/reset is available through Account PIN. Setup and reset require a fresh account-password check; change also requires the current PIN. Five failed verifications impose a database-persisted 15-minute lockout shared across PIN actions.
- Provider identity scans create pending clinical or prescription requests with explicit scope and expiry. Only the owning patient's authenticated session can approve with the patient's PIN, deny or revoke. Provider sessions cannot submit approval, including with the provider's own PIN.
- Both parties have a QR requests view with manual refresh. Notifications and audit events record requests/decisions without PINs. Approval grants expire on the server and can be revoked through either request or existing grant controls. Assigned-care access and the separate limited emergency access remain intact. Direct non-emergency consent creation also verifies the patient PIN.

See `SETUP_PIN_QR.md` and `TEST_REPORT.md`. Maps were not changed or claimed fixed.
