/**
 * PulseSync AI - Frontend Application Logic
 * Secured with JWT Authentication, HTML5 Geolocation, Leaflet OpenStreetMap Radar, and Multi-Roles.
 */

const API_BASE = "";
let currentLanguage = "en";
let currentComplaint = "Blood Pressure";

// Authenticated State
let currentUser = null;
let currentToken = null;
let selectedAuthRole = "PATIENT";
let authMode = "login"; // 'login' or 'register'

// Real-World Map State
let medicalLeafletMap = null;
let userLocationMarker = null;
let pharmacyMapMarkers = [];
let userCurrentCoords = null; // { lat, lng }
let allLoadedPharmacies = [];
let currentMapFilterMode = "all"; // 'all' or 'online'

// =============================================================================
// 1. INITIALIZATION & JWT SESSION CONTROLLER
// =============================================================================

document.addEventListener("DOMContentLoaded", async () => {
    // Check saved JWT session
    const savedToken = localStorage.getItem("pulsesync_jwt_token") || localStorage.getItem("pulsesync_token");
    const savedUser = localStorage.getItem("pulsesync_user");

    if (savedToken) {
        try {
            currentToken = savedToken;
            // Verify session with server
            const verifyRes = await fetch(`${API_BASE}/api/auth/me`, {
                headers: { "Authorization": `Bearer ${currentToken}` }
            });

            if (verifyRes.ok) {
                const verifyData = await verifyRes.json();
                currentUser = verifyData.user;
                localStorage.setItem("pulsesync_user", JSON.stringify(currentUser));
                showDashboardView(currentUser);
            } else {
                // Token expired or invalid - clear stale session
                localStorage.removeItem("pulsesync_jwt_token");
                localStorage.removeItem("pulsesync_token");
                localStorage.removeItem("pulsesync_user");
                currentUser = null;
                currentToken = null;
                showAuthPortalView();
            }
        } catch (e) {
            console.error("Session restoration error:", e);
            localStorage.removeItem("pulsesync_jwt_token");
            localStorage.removeItem("pulsesync_token");
            localStorage.removeItem("pulsesync_user");
            showAuthPortalView();
        }
    } else {
        showAuthPortalView();
    }


});

function showAuthPortalView() {
    const authView = document.getElementById("auth-portal-page-view");
    const mainApp = document.getElementById("main-app-container");
    if (authView) authView.style.display = "flex";
    if (mainApp) mainApp.style.display = "none";
}

function showDashboardView(user) {
    document.getElementById('auth-portal-page-view').style.display='none';
    document.getElementById('main-app-container').style.display='block';
    HF.mount(user);
}

async function logout() {
    PinAccess.close();
    window.QRTools?.close();
    try {
        if (currentToken) {
            await fetch(`${API_BASE}/api/auth/logout`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${currentToken}` }
            });
        }
    } catch (e) {}

    localStorage.removeItem("pulsesync_jwt_token");
    localStorage.removeItem("pulsesync_token");
    localStorage.removeItem("pulsesync_user");
    currentUser = null;
    currentToken = null;
    setAuthMode("login");
    showAuthPortalView();
    showToast("Logged out successfully.", "info");
}

// =============================================================================
// 2. AUTHENTICATION & ROLE SELECTION HANDLERS
// =============================================================================

function selectAuthRole(role) {
    selectedAuthRole = role;
    document.getElementById("auth-portal-page-view").dataset.role = role;

    // Update Role Card UI
    document.querySelectorAll(".auth-role-card").forEach(card => {
        card.classList.toggle("active", card.getAttribute("data-role") === role);
        card.setAttribute("aria-pressed", card.getAttribute("data-role") === role);
    });

    // Update Role Specific Registration Sections
    document.querySelectorAll(".role-specific-section").forEach(sec => sec.style.display = "none");

    const loginText = document.getElementById("login-submit-text");
    const regText = document.getElementById("register-submit-text");

    if (role === "PATIENT") {
        const sec = document.getElementById("role-fields-patient");
        if (sec) sec.style.display = "block";
        document.getElementById("lbl-reg-name").textContent = "Patient Full Name";
        document.getElementById("auth-login-email").placeholder = "Enter your registered email";
        if (loginText) loginText.textContent = " Sign In to Patient Dashboard";
        if (regText) regText.textContent = " Register Patient & Generate Medical QR";
    } else if (role === "DOCTOR") {
        const sec = document.getElementById("role-fields-doctor");
        if (sec) sec.style.display = "block";
        document.getElementById("lbl-reg-name").textContent = "Doctor Full Name";
        document.getElementById("auth-login-email").placeholder = "Enter your registered doctor email";
        if (loginText) loginText.textContent = " Sign In to Doctor Clinic Dashboard";
        if (regText) regText.textContent = " Register Doctor & Generate Clinic QR";
    } else if (role === "HOSPITAL_ADMIN" || role === "HOSPITAL") {
        const sec = document.getElementById("role-fields-hospital");
        if (sec) sec.style.display = "block";
        document.getElementById("lbl-reg-name").textContent = "Hospital Administrator Name";
        document.getElementById("auth-login-email").placeholder = "Enter your registered hospital email";
        if (loginText) loginText.textContent = " Sign In to Hospital Dashboard";
        if (regText) regText.textContent = " Register Hospital & Generate Admission QR";
    } else if (role === "PHARMACY") {
        const sec = document.getElementById("role-fields-pharmacy");
        if (sec) sec.style.display = "block";
        document.getElementById("lbl-reg-name").textContent = "Pharmacist In-Charge Name";
        document.getElementById("auth-login-email").placeholder = "Enter your registered pharmacy email";
        if (loginText) loginText.textContent = " Sign In to Medical Store Dashboard";
        if (regText) regText.textContent = " Register Medical Store & Generate Store QR";
    }
    window.Registration?.roleChanged();
}

function setAuthMode(mode) {
    authMode = mode;

    document.getElementById("btn-auth-mode-login").classList.toggle("active", mode === "login");
    document.getElementById("btn-auth-mode-register").classList.toggle("active", mode === "register");

    const loginForm = document.getElementById("auth-login-form");
    const regForm = document.getElementById("auth-register-form");

    if (loginForm) loginForm.style.display = (mode === "login") ? "block" : "none";
    if (regForm) regForm.style.display = (mode === "register") ? "block" : "none";

    selectAuthRole(selectedAuthRole);
}

function toggleInsuranceFields(hasInsurance) {
    const detailsBlock = document.getElementById("patient-insurance-details-block");
    const noInsPrompt = document.getElementById("no-insurance-doc-prompt");

    if (detailsBlock) detailsBlock.style.display = hasInsurance ? "grid" : "none";
    if (noInsPrompt) noInsPrompt.style.display = hasInsurance ? "none" : "block";
}

function detectRegistrationLocation() {
    const statusElem = document.getElementById("reg-location-status");
    if (!navigator.geolocation) {
        if (statusElem) statusElem.textContent = "Geolocation is not supported by this browser.";
        return;
    }

    if (statusElem) statusElem.textContent = "Detecting live GPS coordinates...";

    navigator.geolocation.getCurrentPosition(
        (pos) => {
            const lat = pos.coords.latitude;
            const lng = pos.coords.longitude;
            document.getElementById("reg-lat").value = lat;
            document.getElementById("reg-lng").value = lng;
            if (statusElem) statusElem.textContent = ` Live GPS Captured: (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
            showToast("Live coordinates detected for registration.", "success");
        },
        (err) => {
            if (statusElem) statusElem.textContent = "GPS permission denied or unavailable. You can still register.";
            showToast("Could not detect location: " + err.message, "info");
        },
        { enableHighAccuracy: true, timeout: 8000 }
    );
}

async function handleLoginSubmit(event) {
    if (event) event.preventDefault();
    const email = document.getElementById("auth-login-email").value.trim();
    const password = document.getElementById("auth-login-password").value;

    if (!email) {
        showToast("Please enter your registered email.", "emergency");
        return;
    }
    if (!password) {
        showToast("Please enter your password.", "emergency");
        return;
    }

    try {
        document.getElementById("login-submit-button").disabled=true;
        showToast("Signing in…", "info");
        const res = await fetch(`${API_BASE}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password, role: selectedAuthRole })
        });

        let data;
        const text = await res.text();
        try {
            data = JSON.parse(text);
        } catch (_) {
            data = { success: false, detail: text || `HTTP ${res.status} Error` };
        }

        if (res.ok && data.success) {
            currentToken = data.access_token;
            currentUser = data.user;
            localStorage.setItem("pulsesync_jwt_token", currentToken);
            localStorage.setItem("pulsesync_token", currentToken);
            localStorage.setItem("pulsesync_user", JSON.stringify(currentUser));

            showDashboardView(currentUser);
            showToast(`Welcome back, ${currentUser.name}!`, "success");
        } else {
            showToast(data.detail || "Sign-in failed. Please check credentials or register first.", "emergency");
        }
    } catch (err) {
        console.error("Login error:", err);
        showToast("Error connecting to backend authentication server.", "emergency");
    } finally { document.getElementById("login-submit-button").disabled=false; }
}

async function handleRegisterSubmit(event) {
    if (event) event.preventDefault();
    if (window.Registration && !Registration.beforeSubmit()) return;
    
    const name = document.getElementById("reg-name").value.trim();
    const email = document.getElementById("reg-email").value.trim();
    const phone = document.getElementById("reg-phone").value.trim();
    const password = document.getElementById("reg-password").value;
    const confirmPassword = document.getElementById("reg-confirm-password").value;

    if (!name || !email) {
        showToast("Please enter your full name and email.", "emergency");
        return;
    }

    if (!password || password.length < 4) {
        showToast("Password must be at least 4 characters long.", "emergency");
        return;
    }

    if (password !== confirmPassword) {
        showToast("Passwords do not match. Please re-enter.", "emergency");
        return;
    }

    const pin = document.getElementById('reg-pin').value;
    const confirm_pin = document.getElementById('reg-confirm-pin').value;
    if (!PinAccess.validateRegistration()) return;
    const regLat = document.getElementById("reg-lat").value === "" ? null : Number(document.getElementById("reg-lat").value);
    const regLng = document.getElementById("reg-lng").value === "" ? null : Number(document.getElementById("reg-lng").value);

    let payload = {
        pin, confirm_pin,
        role: selectedAuthRole,
        name,
        email,
        phone: phone || "",
        password: password,
        preferred_language: currentLanguage,
        latitude: regLat,
        longitude: regLng
    };

    let registrationMeds=[];
    try { if(selectedAuthRole === "PATIENT") registrationMeds=readRegistrationMeds(); } catch(err) { showToast(err.message,"emergency"); return; }
    if (selectedAuthRole === "PATIENT") {
        const age = parseInt(document.getElementById("reg-pat-age").value) || 30;
        const gender = document.getElementById("reg-pat-gender").value;
        const blood_group = document.getElementById("reg-pat-blood").value;
        const city = document.getElementById("reg-pat-city").value.trim();
        const aadhaar = document.getElementById("reg-pat-aadhaar").value.trim();
        const pan = document.getElementById("reg-pat-pan").value.trim();
        const allergies = document.getElementById("reg-pat-allergies").value.split(",").map(s => s.trim()).filter(Boolean);
        const conditions = document.getElementById("reg-pat-conditions").value.split(",").map(s => s.trim()).filter(Boolean);
        const has_insurance = document.getElementById("reg-pat-has-insurance").checked;
        const ins_provider = document.getElementById("reg-pat-ins-provider").value.trim();
        const ins_policy = document.getElementById("reg-pat-ins-policy").value.trim();
        const ins_claimed = document.getElementById("reg-pat-ins-claimed").value === "true";

        payload = {
            ...payload,
            age,
            gender,
            blood_group,
            city,
            address: document.getElementById("reg-pat-address").value.trim() || city,
            aadhaar_card_no: aadhaar,
            pan_card_no: pan,
            allergies,
            existing_conditions: conditions,
            current_medications: registrationMeds,
            has_insurance,
            insurance_provider: has_insurance ? ins_provider : "",
            insurance_policy_no: has_insurance ? ins_policy : "",
            insurance_claimed: has_insurance && ins_claimed
        };
    } else if (selectedAuthRole === "DOCTOR") {
        payload = {
            ...payload,
            specialization: document.getElementById("reg-doc-spec").value.trim() || "General Physician",
            education: document.getElementById("reg-doc-edu").value.trim() || "MBBS",
            license_no: document.getElementById("reg-doc-license").value.trim(),
            clinic_name: document.getElementById("reg-doc-clinic-name").value.trim(),
            clinic_address: document.getElementById("reg-doc-clinic-addr").value.trim(),
            patients_checked_count: parseInt(document.getElementById("reg-doc-checked-count").value) || 0
        };
    } else if (selectedAuthRole === "HOSPITAL_ADMIN" || selectedAuthRole === "HOSPITAL") {
        payload = {
            ...payload,
            hospital_name: document.getElementById("reg-hosp-name").value.trim(),
            registration_no: document.getElementById("reg-hosp-reg").value.trim(),
            emergency_phone: document.getElementById("reg-hosp-phone").value.trim(),
            city: document.getElementById("reg-hosp-city").value.trim(),
            address: document.getElementById("reg-provider-address").value.trim() || document.getElementById("reg-hosp-city").value.trim(),
            total_doctors: parseInt(document.getElementById("reg-hosp-docs").value) || 10,
            total_wards: parseInt(document.getElementById("reg-hosp-wards").value) || 4,
            total_icu_beds: parseInt(document.getElementById("reg-hosp-icu-beds").value) || 0,
            total_general_beds: Number(document.getElementById("reg-hosp-general-beds").value) || 0,
            treatments: document.getElementById("reg-hosp-treatments").value.split(",").map(s => s.trim()).filter(Boolean)
        };
    } else if (selectedAuthRole === "PHARMACY") {
        payload = {
            ...payload,
            store_name: document.getElementById("reg-pharm-store-name").value.trim() || `${name}'s Medical Store`,
            pharmacist_name: document.getElementById("reg-pharm-pharmacist").value.trim() || name,
            drug_license_no: document.getElementById("reg-pharm-license").value.trim(),
            address: document.getElementById("reg-pharm-address").value.trim()
        };
    }

    try {
        document.getElementById("register-submit-button").disabled=true;
        showToast("Creating account...", "info");
        const res = await fetch(`${API_BASE}/api/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        let data;
        const text = await res.text();
        try {
            data = JSON.parse(text);
        } catch (_) {
            data = { success: false, detail: text || `HTTP ${res.status} Error` };
        }

        if (res.ok && data.success) {
            currentToken = data.access_token;
            currentUser = data.user;
            localStorage.setItem("pulsesync_jwt_token", currentToken);
            localStorage.setItem("pulsesync_token", currentToken);
            localStorage.setItem("pulsesync_user", JSON.stringify(currentUser));

            window.Registration?.success();
            document.getElementById('auth-register-form').reset();
            showDashboardView(currentUser);
            showToast(`Profile registered successfully for ${currentUser.name}!`, "success");
        } else {
            Registration.failure(typeof data.detail === "string" ? data.detail : "Registration failed. Check your details and try again.");
        }
    } catch (err) {
        console.error("Register error:", err);
        Registration.failure("Cannot reach the server. Your entries are retained; please try again.");
    } finally { document.getElementById("register-submit-button").disabled=false; window.Registration?.settled(); }
}

// =============================================================================
// 3. DASHBOARD HYDRATION
// =============================================================================

function showToast(msg, type = "info") {
    const banner = document.getElementById("toast-banner");
    const msgElem = document.getElementById("toast-msg");
    if (!banner || !msgElem) return;

    msgElem.textContent = msg;
    banner.className = `toast-banner show ${type}`;

    setTimeout(() => {
        banner.classList.remove("show");
    }, 3500);
}

function registrationMedRows(){ Registration.resizeMedicines(); }
function readRegistrationMeds(){ return Registration.medicines(); }
