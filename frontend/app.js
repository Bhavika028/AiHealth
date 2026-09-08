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
            } else if (savedUser) {
                currentUser = JSON.parse(savedUser);
                showDashboardView(currentUser);
            } else {
                showAuthPortalView();
            }
        } catch (e) {
            console.error("Session restoration error:", e);
            showAuthPortalView();
        }
    } else {
        showAuthPortalView();
    }

    // Initialize complaint branch
    await loadComplaintBranch(currentComplaint);
    
    // Automatically initialize map
    setTimeout(() => {
        initMedicalStoresMap();
    }, 400);
});

function showAuthPortalView() {
    const authView = document.getElementById("auth-portal-page-view");
    const mainApp = document.getElementById("main-app-container");
    if (authView) authView.style.display = "flex";
    if (mainApp) mainApp.style.display = "none";
}

function showDashboardView(user) {
    const authView = document.getElementById("auth-portal-page-view");
    const mainApp = document.getElementById("main-app-container");
    if (authView) authView.style.display = "none";
    if (mainApp) mainApp.style.display = "block";

    applyAuthenticatedSession(user);

    // Invalidate map size once container is visible
    setTimeout(() => {
        if (medicalLeafletMap) medicalLeafletMap.invalidateSize();
    }, 300);
}

async function logout() {
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
    showAuthPortalView();
    showToast("Logged out successfully.", "info");
}

// =============================================================================
// 2. AUTHENTICATION & ROLE SELECTION HANDLERS
// =============================================================================

function selectAuthRole(role) {
    selectedAuthRole = role;

    // Update Role Card UI
    document.querySelectorAll(".auth-role-card").forEach(card => {
        card.classList.toggle("active", card.getAttribute("data-role") === role);
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
        if (loginText) loginText.textContent = "🔐 Sign In to Patient Dashboard";
        if (regText) regText.textContent = "✨ Register Patient & Generate Medical QR";
    } else if (role === "DOCTOR") {
        const sec = document.getElementById("role-fields-doctor");
        if (sec) sec.style.display = "block";
        document.getElementById("lbl-reg-name").textContent = "Doctor Full Name";
        document.getElementById("auth-login-email").placeholder = "Enter your registered doctor email";
        if (loginText) loginText.textContent = "🩺 Sign In to Doctor Clinic Dashboard";
        if (regText) regText.textContent = "✨ Register Doctor & Generate Clinic QR";
    } else if (role === "HOSPITAL_ADMIN" || role === "HOSPITAL") {
        const sec = document.getElementById("role-fields-hospital");
        if (sec) sec.style.display = "block";
        document.getElementById("lbl-reg-name").textContent = "Hospital Administrator Name";
        document.getElementById("auth-login-email").placeholder = "Enter your registered hospital email";
        if (loginText) loginText.textContent = "🏥 Sign In to Hospital Dashboard";
        if (regText) regText.textContent = "✨ Register Hospital & Generate Admission QR";
    } else if (role === "PHARMACY") {
        const sec = document.getElementById("role-fields-pharmacy");
        if (sec) sec.style.display = "block";
        document.getElementById("lbl-reg-name").textContent = "Pharmacist In-Charge Name";
        document.getElementById("auth-login-email").placeholder = "Enter your registered pharmacy email";
        if (loginText) loginText.textContent = "💊 Sign In to Medical Store Dashboard";
        if (regText) regText.textContent = "✨ Register Medical Store & Generate Store QR";
    }
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
            if (statusElem) statusElem.textContent = `✅ Live GPS Captured: (${lat.toFixed(4)}, ${lng.toFixed(4)})`;
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
        showToast("Authenticating & verifying JWT...", "info");
        const res = await fetch(`${API_BASE}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password, role: selectedAuthRole })
        });

        const data = await res.json();
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
    }
}

async function handleRegisterSubmit(event) {
    if (event) event.preventDefault();
    
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

    const regLat = parseFloat(document.getElementById("reg-lat").value) || null;
    const regLng = parseFloat(document.getElementById("reg-lng").value) || null;

    let payload = {
        role: selectedAuthRole,
        name,
        email,
        phone: phone || "",
        password: password,
        preferred_language: currentLanguage,
        latitude: regLat,
        longitude: regLng
    };

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
            address: city,
            aadhaar_card_no: aadhaar,
            pan_card_no: pan,
            allergies,
            existing_conditions: conditions,
            has_insurance,
            insurance_provider: ins_provider,
            insurance_policy_no: ins_policy,
            insurance_claimed: ins_claimed
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
            address: document.getElementById("reg-hosp-city").value.trim(),
            total_doctors: parseInt(document.getElementById("reg-hosp-docs").value) || 10,
            total_wards: parseInt(document.getElementById("reg-hosp-wards").value) || 4,
            total_icu_beds: parseInt(document.getElementById("reg-hosp-icu-beds").value) || 10,
            total_general_beds: 50,
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
        showToast("Registering account & generating signed JWT pass...", "info");
        const res = await fetch(`${API_BASE}/api/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok && data.success) {
            currentToken = data.access_token;
            currentUser = data.user;
            localStorage.setItem("pulsesync_jwt_token", currentToken);
            localStorage.setItem("pulsesync_token", currentToken);
            localStorage.setItem("pulsesync_user", JSON.stringify(currentUser));

            showDashboardView(currentUser);
            showToast(`Profile registered successfully for ${currentUser.name}!`, "success");
        } else {
            showToast(data.detail || "Registration failed. Please check your inputs.", "emergency");
        }
    } catch (err) {
        console.error("Register error:", err);
        showToast("Error communicating with server.", "emergency");
    }
}

// =============================================================================
// 3. DASHBOARD HYDRATION
// =============================================================================

function applyAuthenticatedSession(user) {
    if (!user) return;

    // Update Header
    const headerName = document.getElementById("current-user-display-name");
    const headerRole = document.getElementById("current-user-role-display");
    const headerAvatar = document.getElementById("active-user-avatar-icon");

    if (headerName) headerName.textContent = user.name;

    const role = (user.role || "PATIENT").toUpperCase();
    if (headerRole) {
        if (role === "PATIENT") headerRole.textContent = `Patient (${user.gender || 'User'}, ${user.blood_group || 'O+'})`;
        else if (role === "DOCTOR") headerRole.textContent = `Doctor (${user.specialization || 'Clinical'})`;
        else if (role === "HOSPITAL_ADMIN" || role === "HOSPITAL") headerRole.textContent = "Hospital Administrator";
        else if (role === "PHARMACY") headerRole.textContent = "Medical Store";
    }

    if (headerAvatar) {
        if (role === "PATIENT") headerAvatar.textContent = "👤";
        else if (role === "DOCTOR") headerAvatar.textContent = "🩺";
        else if (role === "HOSPITAL_ADMIN" || role === "HOSPITAL") headerAvatar.textContent = "🏥";
        else if (role === "PHARMACY") headerAvatar.textContent = "💊";
    }

    // STRICT ROLE-BASED TAB VISIBILITY (Hide other role tabs so a patient never sees doctor/hospital/pharmacy management)
    const tabPatient = document.getElementById("tab-patient");
    const tabDoctor = document.getElementById("tab-doctor");
    const tabHospital = document.getElementById("tab-hospital");
    const tabPharmacy = document.getElementById("tab-pharmacy");
    const tabIcu = document.getElementById("tab-icu");

    if (tabPatient) tabPatient.style.display = (role === "PATIENT") ? "inline-flex" : "none";
    if (tabDoctor) tabDoctor.style.display = (role === "DOCTOR") ? "inline-flex" : "none";
    if (tabHospital) tabHospital.style.display = (role === "HOSPITAL_ADMIN" || role === "HOSPITAL") ? "inline-flex" : "none";
    if (tabPharmacy) tabPharmacy.style.display = (role === "PHARMACY") ? "inline-flex" : "none";
    if (tabIcu) tabIcu.style.display = (role === "PATIENT" || role === "DOCTOR") ? "inline-flex" : "none";

    // ONLY HYDRATE THE CURRENT USER'S AUTHENTIC ROLE DASHBOARD
    if (role === "PATIENT") {
        hydratePatientDashboard(user);
        switchView("patient");
    } else if (role === "DOCTOR") {
        hydrateDoctorDashboard(user);
        switchView("doctor");
    } else if (role === "HOSPITAL_ADMIN" || role === "HOSPITAL") {
        hydrateHospitalDashboard(user);
        switchView("hospital");
    } else if (role === "PHARMACY") {
        hydratePharmacyDashboard(user);
        switchView("pharmacy");
    }

    // If patient or has coordinates, load live map
    if (role === "PATIENT") {
        if (user.latitude && user.longitude) {
            userCurrentCoords = { lat: user.latitude, lng: user.longitude };
            loadNearbyMedicalStores(user.latitude, user.longitude);
        } else {
            requestUserLiveLocation();
        }
    }
}

// Hydrate Patient Dashboard
async function hydratePatientDashboard(user) {
    const patId = user.patient_id || user.id;

    const pName = document.getElementById("pat-view-name");
    const pAge = document.getElementById("pat-view-age");
    const pGender = document.getElementById("pat-view-gender");
    const pBlood = document.getElementById("pat-view-blood");
    const pPhone = document.getElementById("pat-view-phone");
    const pEmail = document.getElementById("pat-view-email");
    const pLoc = document.getElementById("pat-view-location");
    const pAllergies = document.getElementById("pat-view-allergies");
    const pConds = document.getElementById("pat-view-conditions");
    const pAadhaar = document.getElementById("pat-view-aadhaar");
    const pPan = document.getElementById("pat-view-pan");

    if (pName) pName.textContent = user.name || "Patient Profile";
    if (pAge) pAge.textContent = user.age || "-";
    if (pGender) pGender.textContent = user.gender || "-";
    if (pBlood) pBlood.textContent = user.blood_group ? `${user.blood_group} Group` : "Blood Group";
    if (pPhone) pPhone.textContent = user.phone || "-";
    if (pEmail) pEmail.textContent = user.email || "-";
    if (pLoc) pLoc.textContent = user.city ? `${user.address || user.city}` : "Location";

    const allergiesList = user.allergies && user.allergies.length ? user.allergies.join(", ") : "None Recorded";
    const conditionsList = user.existing_conditions && user.existing_conditions.length ? user.existing_conditions.join(", ") : "None Recorded";

    if (pAllergies) pAllergies.textContent = allergiesList;
    if (pConds) pConds.textContent = conditionsList;
    if (pAadhaar) pAadhaar.textContent = user.aadhaar_card_no || "Not Specified";
    if (pPan) pPan.textContent = user.pan_card_no || "Not Specified";

    // Insurance status
    const claimTag = document.getElementById("pat-ins-claim-tag");
    const policyDisp = document.getElementById("pat-ins-policy-display");
    const insBadge = document.getElementById("pat-insurance-badge");

    if (user.has_insurance) {
        if (claimTag) {
            claimTag.className = user.insurance_claimed ? "ins-status-tag claimed-yes" : "ins-status-tag claimed-no";
            claimTag.textContent = user.insurance_claimed ? "Insurance Claimed: YES" : "Insurance: ACTIVE";
        }
        if (policyDisp) policyDisp.textContent = `Provider: ${user.insurance_provider || 'Health Insurance'} | Policy: ${user.insurance_policy_no || 'ACTIVE-POLICY'}`;
        if (insBadge) insBadge.textContent = "● Cashless Active";
    } else {
        if (claimTag) {
            claimTag.className = "ins-status-tag claimed-no";
            claimTag.textContent = "Direct / Ayushman Bharat Subsidy";
        }
        if (policyDisp) policyDisp.textContent = "Identity linked for Ayushman Bharat PM-JAY Benefits";
        if (insBadge) insBadge.textContent = "● Govt Healthcare Pass";
    }

    // Load Patient QR Codes
    try {
        const resProf = await fetch(`${API_BASE}/api/qr/generate/${patId}/PROFILE_INTAKE`);
        const dataProf = await resProf.json();
        if (dataProf.success && dataProf.qr_image_base64) {
            const imgProf = document.getElementById("pat-profile-qr-img");
            if (imgProf) imgProf.src = dataProf.qr_image_base64;
        }

        const resIns = await fetch(`${API_BASE}/api/qr/generate/${patId}/INSURANCE_CLAIM`);
        const dataIns = await resIns.json();
        if (dataIns.success && dataIns.qr_image_base64) {
            const imgIns = document.getElementById("pat-insurance-qr-img");
            if (imgIns) imgIns.src = dataIns.qr_image_base64;
        }
    } catch (e) {}
}

// Hydrate Doctor Dashboard
async function hydrateDoctorDashboard(user) {
    const docId = user.doctor_id || user.id;

    const dName = document.getElementById("doc-view-name");
    const dSpec = document.getElementById("doc-view-spec");
    const dEdu = document.getElementById("doc-view-edu");
    const dLic = document.getElementById("doc-view-license");
    const dClinic = document.getElementById("doc-view-clinic");
    const dCount = document.getElementById("doc-checked-counter");

    if (dName) dName.textContent = user.name || "Doctor Profile";
    if (dSpec) dSpec.textContent = user.specialization || "Physician & Clinical Specialist";
    if (dEdu) dEdu.textContent = user.education ? `🎓 ${user.education}` : "🎓 Certified Practitioner";
    if (dLic) dLic.textContent = user.license_no || "Registered";
    if (dClinic) dClinic.textContent = user.clinic_name || "Healthcare Clinic";
    if (dCount) dCount.textContent = user.patients_checked_count || 0;

    try {
        const resDocQr = await fetch(`${API_BASE}/api/qr/doctor/${docId}`);
        const dataDocQr = await resDocQr.json();
        if (dataDocQr.success && dataDocQr.qr_image_base64) {
            const imgDoc = document.getElementById("doc-official-qr-img");
            if (imgDoc) imgDoc.src = dataDocQr.qr_image_base64;
        }
    } catch (e) {}

    await loadDoctorQueue(docId);
}

// Hydrate Hospital Dashboard
async function hydrateHospitalDashboard(user) {
    const hospId = user.hospital_id || user.id;

    const hName = document.getElementById("hosp-view-name");
    const hReg = document.getElementById("hosp-view-reg");
    const hPhone = document.getElementById("hosp-view-phone");
    const hLoc = document.getElementById("hosp-view-location");
    const hDocs = document.getElementById("hosp-docs-counter");
    const hWards = document.getElementById("hosp-wards-counter");

    if (hName) hName.textContent = user.hospital_name || user.name || "Multiservice Hospital";
    if (hReg) hReg.textContent = user.registration_no || "Certified Facility";
    if (hPhone) hPhone.textContent = user.emergency_phone || user.phone || "+91-11-2894000";
    if (hLoc) hLoc.textContent = user.address ? `${user.address}, ${user.city || ''}` : "Institutional Medical Area";
    if (hDocs) hDocs.textContent = user.total_doctors || 12;
    if (hWards) hWards.textContent = user.total_wards || 4;

    try {
        const resHospQr = await fetch(`${API_BASE}/api/qr/hospital/${hospId}`);
        const dataHospQr = await resHospQr.json();
        if (dataHospQr.success && dataHospQr.qr_image_base64) {
            const imgHosp = document.getElementById("hosp-official-qr-img");
            if (imgHosp) imgHosp.src = dataHospQr.qr_image_base64;
        }
    } catch (e) {}

    await loadHospitalBeds();
}

// Hydrate Pharmacy Dashboard
async function hydratePharmacyDashboard(user) {
    const pharmId = user.pharmacy_id || user.id;

    const pName = document.getElementById("pharm-view-name");
    const pPharm = document.getElementById("pharm-view-pharmacist");
    const pLic = document.getElementById("pharm-view-license");
    const pAddr = document.getElementById("pharm-view-address");

    if (pName) pName.textContent = user.store_name || user.name || "Medical Store & Pharmacy";
    if (pPharm) pPharm.textContent = user.pharmacist_name || user.name || "Registered Pharmacist";
    if (pLic) pLic.textContent = user.license_no || "Licensed";
    if (pAddr) pAddr.textContent = user.address || "Medical Complex";

    try {
        const resPharmQr = await fetch(`${API_BASE}/api/qr/pharmacy/${pharmId}`);
        const dataPharmQr = await resPharmQr.json();
        if (dataPharmQr.success && dataPharmQr.qr_image_base64) {
            const imgPharm = document.getElementById("pharm-official-qr-img");
            if (imgPharm) imgPharm.src = dataPharmQr.qr_image_base64;
        }
    } catch (e) {}

    await loadPharmacyQueueAndInventory();
}

// =============================================================================
// 4. NAVIGATION VIEW SWITCHER
// =============================================================================

function switchUserDefaultView() {
    if (!currentUser) return;
    const role = (currentUser.role || "PATIENT").toUpperCase();
    if (role === "PATIENT") switchView("patient");
    else if (role === "DOCTOR") switchView("doctor");
    else if (role === "HOSPITAL_ADMIN" || role === "HOSPITAL") switchView("hospital");
    else if (role === "PHARMACY") switchView("pharmacy");
}

function switchView(viewName) {
    const role = currentUser ? (currentUser.role || "PATIENT").toUpperCase() : "PATIENT";
    
    // Strict Role-Based View Guard
    if (role === "PATIENT" && viewName !== "patient" && viewName !== "icu") {
        viewName = "patient";
    } else if (role === "DOCTOR" && viewName !== "doctor" && viewName !== "icu") {
        viewName = "doctor";
    } else if ((role === "HOSPITAL_ADMIN" || role === "HOSPITAL") && viewName !== "hospital") {
        viewName = "hospital";
    } else if (role === "PHARMACY" && viewName !== "pharmacy") {
        viewName = "pharmacy";
    }

    document.querySelectorAll(".view-panel").forEach(panel => panel.classList.remove("active"));
    document.querySelectorAll(".nav-tab").forEach(tab => tab.classList.remove("active"));

    const targetPanel = document.getElementById(`view-${viewName}`);
    const targetTab = document.getElementById(`tab-${viewName}`);

    if (targetPanel) targetPanel.classList.add("active");
    if (targetTab) targetTab.classList.add("active");

    if (viewName === "patient") {
        setTimeout(() => {
            if (medicalLeafletMap) medicalLeafletMap.invalidateSize();
        }, 200);
    }
    if (viewName === "hospital" && (role === "HOSPITAL_ADMIN" || role === "HOSPITAL")) loadHospitalBeds();
    if (viewName === "pharmacy" && role === "PHARMACY") loadPharmacyQueueAndInventory();
    if (viewName === "doctor" && role === "DOCTOR") loadDoctorQueue();
    if (viewName === "icu") loadIcuTransferScreen();
}

// =============================================================================
// 5. OLA-STYLE REAL-WORLD MEDICAL STORES MAP & GEOLOCATION
// =============================================================================

function initMedicalStoresMap() {
    const mapElement = document.getElementById("medical-stores-leaflet-map");
    if (!mapElement || medicalLeafletMap) return;

    // Default center (India/New Delhi or global center until GPS activates)
    const defaultLat = 28.6139;
    const defaultLng = 77.2090;

    medicalLeafletMap = L.map("medical-stores-leaflet-map", {
        center: [defaultLat, defaultLng],
        zoom: 13,
        zoomControl: true
    });

    // OpenStreetMap tiles (100% free, no API key required)
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(medicalLeafletMap);

    // Initial search
    loadNearbyMedicalStores(defaultLat, defaultLng);
}

function requestUserLiveLocation() {
    const statusSub = document.getElementById("map-status-sub");
    const statusPill = document.getElementById("map-live-status-pill");

    if (!navigator.geolocation) {
        showToast("Geolocation is not supported by your browser.", "emergency");
        return;
    }

    if (statusSub) statusSub.textContent = "📍 Requesting live GPS coordinates from device...";
    if (statusPill) statusPill.textContent = "Acquiring GPS...";

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            userCurrentCoords = { lat, lng };

            if (statusSub) statusSub.textContent = `📍 Live GPS Active: (${lat.toFixed(4)}, ${lng.toFixed(4)}) - Finding local pharmacies`;
            if (statusPill) statusPill.textContent = "GPS Live & Accurate";

            // Pan map
            if (medicalLeafletMap) {
                medicalLeafletMap.setView([lat, lng], 14);

                // Add or update live radar marker
                if (userLocationMarker) {
                    userLocationMarker.setLatLng([lat, lng]);
                } else {
                    const userIcon = L.divIcon({
                        className: 'user-live-pin',
                        iconSize: [20, 20],
                        iconAnchor: [10, 10]
                    });
                    userLocationMarker = L.marker([lat, lng], { icon: userIcon })
                        .addTo(medicalLeafletMap)
                        .bindPopup("<b>📍 Your Live Location</b><br>Searching medical stores in this radius.")
                        .openPopup();
                }
            }

            showToast("Live GPS location locked! Fetching real medical stores...", "success");
            await loadNearbyMedicalStores(lat, lng);
        },
        (err) => {
            console.warn("GPS error:", err);
            if (statusSub) statusSub.textContent = "⚠️ GPS permission prompt was declined or unavailable. Showing regional medical stores.";
            if (statusPill) statusPill.textContent = "GPS Offline";
            showToast("GPS location permission required for exact live coordinates.", "info");
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
}

async function loadNearbyMedicalStores(lat, lng, query = "") {
    try {
        let url = `${API_BASE}/api/clinical/pharmacies/nearby?radius_km=10.0`;
        if (lat && lng) url += `&lat=${lat}&lng=${lng}`;
        if (query) url += `&search_query=${encodeURIComponent(query)}`;

        const res = await fetch(url);
        const data = await res.json();
        allLoadedPharmacies = data.pharmacies || [];

        renderPharmaciesOnMap(allLoadedPharmacies);
        renderPharmacyListCards(allLoadedPharmacies);

        const counter = document.getElementById("stores-count-badge");
        if (counter) counter.textContent = `${allLoadedPharmacies.length} Real Facilities`;
    } catch (err) {
        console.error("Error loading real nearby facilities:", err);
    }
}

function getFilteredFacilities(facilities) {
    if (currentMapFilterMode === "pharmacy") {
        return facilities.filter(p => p.facility_type === "pharmacy");
    } else if (currentMapFilterMode === "hospital") {
        return facilities.filter(p => p.facility_type === "hospital" || p.facility_type === "clinic");
    } else if (currentMapFilterMode === "registered" || currentMapFilterMode === "online") {
        return facilities.filter(p => p.is_registered || p.is_online);
    }
    return facilities;
}

function renderPharmaciesOnMap(pharmacies) {
    if (!medicalLeafletMap) return;

    // Clear existing markers
    pharmacyMapMarkers.forEach(m => medicalLeafletMap.removeLayer(m));
    pharmacyMapMarkers = [];

    const visibleItems = getFilteredFacilities(pharmacies);

    visibleItems.forEach(p => {
        if (!p.latitude || !p.longitude) return;

        const isOnline = p.is_online;
        const isRegistered = p.is_registered;
        const fType = p.facility_type || (isRegistered ? "pharmacy" : "hospital");
        const iconSymbol = fType === "hospital" ? "🏥" : (fType === "clinic" ? "🩺" : "💊");

        const markerHtml = `
            <div class="pharmacy-map-pin ${fType === 'hospital' ? 'hospital-pin' : ''} ${isOnline ? 'online-store' : ''}">
                ${iconSymbol}
            </div>
        `;

        const customIcon = L.divIcon({
            className: 'custom-pharm-icon',
            html: markerHtml,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });

        const popupContent = `
            <div style="font-family:sans-serif; min-width:180px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <strong style="color:#0f172a; font-size:0.9rem;">${p.name}</strong>
                </div>
                <div style="font-size:0.75rem; color:${fType === 'hospital' ? '#dc2626' : '#059669'}; font-weight:700; margin-bottom:4px;">
                    ${p.type_label || (fType === 'hospital' ? '🏥 Real Hospital' : '💊 Verified Chemist')}
                </div>
                <p style="font-size:0.75rem; color:#64748b; margin:2px 0;">📍 ${p.distance} | ${p.address}</p>
                <p style="font-size:0.75rem; color:#0369a1; margin:2px 0;">📞 ${p.phone}</p>
                <div style="margin-top:6px; display:flex; gap:4px;">
                    <a href="https://www.google.com/maps/dir/?api=1&destination=${p.latitude},${p.longitude}" target="_blank" style="background:#0f172a; color:white; font-size:0.7rem; padding:3px 8px; border-radius:4px; text-decoration:none;">🗺️ Navigate</a>
                    <button onclick="showToast('Calling ${p.name.replace(/'/g, '')} at ${p.phone}...', 'info')" style="background:#059669; color:white; border:none; font-size:0.7rem; padding:3px 8px; border-radius:4px; cursor:pointer;">📞 Call</button>
                </div>
            </div>
        `;

        const marker = L.marker([p.latitude, p.longitude], { icon: customIcon })
            .addTo(medicalLeafletMap)
            .bindPopup(popupContent);

        pharmacyMapMarkers.push(marker);
    });
}

function renderPharmacyListCards(pharmacies) {
    const grid = document.getElementById("nearby-pharmacies-grid");
    if (!grid) return;

    const filtered = getFilteredFacilities(pharmacies);

    if (filtered.length === 0) {
        grid.innerHTML = `
            <div style="grid-column:1/-1; text-align:center; padding:2rem; color:#64748b;">
                No facilities found matching the current filter. Try selecting <strong>"All Facilities"</strong> or click <strong>"Locate My Live GPS"</strong>.
            </div>
        `;
        return;
    }

    grid.innerHTML = "";
    filtered.forEach(p => {
        const card = document.createElement("div");
        card.className = `pharmacy-card-real ${p.is_registered ? 'is-registered-active' : ''}`;

        const isHosp = p.facility_type === "hospital";
        const isClinic = p.facility_type === "clinic";
        const tagColor = isHosp ? '#dc2626' : (isClinic ? '#7c3aed' : (p.is_online ? '#059669' : '#0369a1'));
        const badgeLabel = p.type_label || (isHosp ? "🏥 Real Hospital" : (isClinic ? "🩺 Real Clinic" : (p.is_registered ? "🟢 Registered Store" : "💊 Verified Chemist")));

        const medsList = (p.availableMeds || []).slice(0, 3).map(m => `<span style="background:#f1f5f9; padding:2px 6px; border-radius:4px; font-size:0.72rem; color:#334155;">${m}</span>`).join(" ");

        card.innerHTML = `
            <div>
                <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:0.5rem;">
                    <div>
                        <strong style="font-size:0.92rem; color:#0f172a;">${p.name}</strong>
                        <div style="font-size:0.74rem; color:${tagColor}; font-weight:700; margin-top:2px;">
                            ${badgeLabel}
                        </div>
                    </div>
                    <span style="background:#ecfdf5; color:#047857; font-size:0.75rem; font-weight:800; padding:2px 8px; border-radius:9999px;">
                        ${p.distance}
                    </span>
                </div>
                
                <p style="font-size:0.78rem; color:#64748b; margin:0.4rem 0;">📍 ${p.address}</p>
                <p style="font-size:0.78rem; color:#0f766e;">📞 ${p.phone} | ⭐ ${p.rating} / 5.0</p>
                
                <div style="margin-top:0.4rem; display:flex; gap:0.3rem; flex-wrap:wrap;">
                    ${medsList}
                </div>
            </div>

            <div style="display:flex; gap:0.5rem; margin-top:0.85rem; border-top:1px solid #f1f5f9; padding-top:0.6rem;">
                <button type="button" class="btn-xs-outline" style="flex:1;" onclick="focusStoreOnMap(${p.latitude}, ${p.longitude})">
                    📍 Focus on Map
                </button>
                <a href="https://www.google.com/maps/dir/?api=1&destination=${p.latitude},${p.longitude}" target="_blank" class="btn-xs-outline" style="text-decoration:none; text-align:center; flex:1; background:#0f172a; color:white; border-color:#0f172a;">
                    🗺️ Directions
                </a>
            </div>
        `;
        grid.appendChild(card);
    });
}

function focusStoreOnMap(lat, lng) {
    if (medicalLeafletMap && lat && lng) {
        medicalLeafletMap.setView([lat, lng], 16);
        const matched = pharmacyMapMarkers.find(m => {
            const pos = m.getLatLng();
            return Math.abs(pos.lat - lat) < 0.0001 && Math.abs(pos.lng - lng) < 0.0001;
        });
        if (matched) matched.openPopup();
    }
}

function filterMapStoresMode(mode) {
    currentMapFilterMode = mode;
    const btnAll = document.getElementById("btn-filter-all");
    const btnPharm = document.getElementById("btn-filter-pharmacy");
    const btnHosp = document.getElementById("btn-filter-hospital");
    const btnReg = document.getElementById("btn-filter-online");

    if (btnAll) btnAll.classList.toggle("active", mode === "all");
    if (btnPharm) btnPharm.classList.toggle("active", mode === "pharmacy");
    if (btnHosp) btnHosp.classList.toggle("active", mode === "hospital");
    if (btnReg) btnReg.classList.toggle("active", mode === "registered" || mode === "online");

    renderPharmaciesOnMap(allLoadedPharmacies);
    renderPharmacyListCards(allLoadedPharmacies);
}

let searchDebounceTimer = null;
function handleMapSearchInput(query) {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(async () => {
        const q = query.trim();
        if (userCurrentCoords) {
            await loadNearbyMedicalStores(userCurrentCoords.lat, userCurrentCoords.lng, q);
        } else {
            await loadNearbyMedicalStores(null, null, q);
        }
    }, 400);
}

// =============================================================================
// 6. INTAKE QUESTIONNAIRE ENGINE
// =============================================================================

async function selectComplaint(complaintName) {
    currentComplaint = complaintName;
    document.getElementById("intake-q1-complaint").value = complaintName;

    document.querySelectorAll(".complaint-chip").forEach(chip => {
        chip.classList.toggle("active", chip.textContent.includes(complaintName));
    });

    await loadComplaintBranch(complaintName);
}

async function loadComplaintBranch(complaintKey) {
    try {
        const res = await fetch(`${API_BASE}/api/intake/branch/${encodeURIComponent(complaintKey)}`);
        const data = await res.json();

        const titleElem = document.getElementById("branch-title");
        if (titleElem) titleElem.textContent = `Section B: ${data.title || complaintKey + ' Branch'}`;

        const container = document.getElementById("branch-questions-list");
        if (!container) return;

        container.innerHTML = "";
        (data.questions || []).forEach(q => {
            const qDiv = document.createElement("div");
            qDiv.className = "form-group branch-q-item";

            let inputHtml = "";
            if (q.type === "select") {
                const optionsHtml = (q.options || []).map(opt => `<option value="${opt}">${opt}</option>`).join("");
                inputHtml = `<select id="branch_q_${q.id}" class="form-control">${optionsHtml}</select>`;
            } else if (q.type === "boolean") {
                inputHtml = `
                    <select id="branch_q_${q.id}" class="form-control">
                        <option value="true">Yes</option>
                        <option value="false" selected>No</option>
                    </select>`;
            } else {
                inputHtml = `<input type="text" id="branch_q_${q.id}" class="form-control" placeholder="${q.placeholder || ''}">`;
            }

            qDiv.innerHTML = `<label style="font-weight:700;">${q.label}</label>${inputHtml}`;
            container.appendChild(qDiv);
        });
    } catch (err) {
        console.warn("Branch load notice:", err);
    }
}

async function handleIntakeSubmit(event) {
    event.preventDefault();

    const patId = (currentUser && (currentUser.patient_id || currentUser.id)) ? (currentUser.patient_id || currentUser.id) : "pat_user";
    const complaint = document.getElementById("intake-q1-complaint").value;
    const durVal = parseInt(document.getElementById("intake-q2-val").value) || 1;
    const durUnit = document.getElementById("intake-q2-unit").value;
    const severity = document.getElementById("intake-q3-severity").value;
    const isFirstVisit = document.getElementById("intake-q4-first-visit").value === "true";
    const medTaken = document.getElementById("intake-q5-taken").value === "true";
    const medDetails = document.getElementById("intake-q5-details").value;

    const warningSigns = [];
    document.querySelectorAll("input[name='warning_sign']:checked").forEach(cb => warningSigns.push(cb.value));

    const vitalBp = document.getElementById("intake-vital-bp").value;
    const vitalPulse = parseInt(document.getElementById("intake-vital-pulse").value) || 80;
    const vitalTemp = document.getElementById("intake-vital-temp").value;
    const vitalSpo2 = parseInt(document.getElementById("intake-vital-spo2").value) || 98;

    const payload = {
        patient_id: patId,
        q1_chief_complaint: complaint,
        q2_duration_value: durVal,
        q2_duration_unit: durUnit,
        q3_severity: severity,
        q4_is_first_visit: isFirstVisit,
        q5_taken_any_medication: medTaken,
        q5_medication_details: medDetails,
        q9_warning_symptoms: warningSigns,
        vital_bp: vitalBp,
        vital_pulse: vitalPulse,
        vital_temperature: vitalTemp,
        vital_spo2: vitalSpo2
    };

    try {
        showToast("Submitting intake & synthesizing AI preliminary note...", "info");
        const res = await fetch(`${API_BASE}/api/intake/submit`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Authorization": `Bearer ${currentToken}`
            },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok && data.success) {
            showToast("Intake recorded successfully! Sent to doctor queue.", "success");

            // Auto-generate AI summary
            const aiRes = await fetch(`${API_BASE}/api/ai/generate-summary`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    patient_id: patId,
                    consultation_id: data.consultation_id,
                    vitals: { bp: vitalBp, pulse: vitalPulse, temp: vitalTemp, spo2: vitalSpo2 }
                })
            });
            const aiData = await aiRes.json();
            const aiElem = document.getElementById("ai-summary-text-display");
            if (aiElem && aiData.ai_summary) {
                aiElem.textContent = aiData.ai_summary;
            }

            setTimeout(() => {
                switchView("doctor");
            }, 800);
        } else {
            showToast(data.detail || "Intake submission failed.", "emergency");
        }
    } catch (e) {
        showToast("Error submitting intake.", "emergency");
    }
}

// =============================================================================
// 7. DOCTOR CLINICAL WORKSPACE & QUEUE
// =============================================================================

async function loadDoctorQueue(docId = null) {
    try {
        let url = `${API_BASE}/api/clinical/doctor/queue`;
        if (docId) url += `?doctor_id=${docId}`;

        const res = await fetch(url);
        const data = await res.json();

        const container = document.getElementById("doctor-patient-queue-list");
        const countDisp = document.getElementById("queue-count-display");
        const headerBadge = document.getElementById("doctor-queue-counter");

        const queue = data.queue || [];
        if (countDisp) countDisp.textContent = `${queue.length} Patient(s) in Queue`;
        if (headerBadge) headerBadge.textContent = queue.length;

        if (container) {
            container.innerHTML = "";
            if (queue.length === 0) {
                container.innerHTML = `
                    <div style="text-align:center; padding:2rem; color:#64748b;">
                        👥 <strong>No active patients in queue.</strong><br>
                        When a patient completes an intake questionnaire, their review card will appear here live.
                    </div>
                `;
                return;
            }

            queue.forEach(item => {
                const card = document.createElement("div");
                card.className = `patient-queue-card ${item.is_urgent ? 'urgent' : ''}`;
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>${item.patient_name} (${item.patient_age} yrs, ${item.patient_gender})</strong>
                        <span class="badge-status-pill ${item.is_urgent ? 'emergency' : 'green'}">
                            ${item.is_urgent ? '⚠️ URGENT' : 'Regular'}
                        </span>
                    </div>
                    <p style="font-size:0.8rem; color:#64748b; margin:0.25rem 0;">Complaint: ${item.chief_complaint} (${item.duration})</p>
                    <button type="button" class="btn-sm-primary" style="margin-top:0.4rem; font-size:0.75rem;" onclick="selectPatientForReview('${item.consultation_id}', '${item.patient_name}', '${item.chief_complaint}')">
                        🩺 Review & Prescribe
                    </button>
                `;
                container.appendChild(card);
            });
        }
    } catch (e) {
        console.warn("Queue load error:", e);
    }
}

function selectPatientForReview(consultId, name, complaint) {
    const patElem = document.getElementById("active-consult-pat-name");
    const compElem = document.getElementById("active-consult-complaint");

    if (patElem) patElem.textContent = name;
    if (compElem) compElem.textContent = complaint;
    showToast(`Active review loaded for ${name}`, "info");
}

function switchRxMode(modeKey) {
    document.querySelectorAll(".rx-mode-panel").forEach(p => p.style.display = "none");
    document.querySelectorAll(".rx-mode-tab").forEach(t => t.classList.remove("active"));

    const target = document.getElementById(`rx-mode-${modeKey}`);
    if (target) target.style.display = "block";

    const tabs = document.querySelectorAll(".rx-mode-tab");
    if (modeKey === "increase" && tabs[0]) tabs[0].classList.add("active");
    if (modeKey === "new_meds" && tabs[1]) tabs[1].classList.add("active");
    if (modeKey === "referral" && tabs[2]) tabs[2].classList.add("active");
}

async function submitIncreaseDoseRx() {
    const med = document.getElementById("rx-dose-med-name").value;
    const times = parseInt(document.getElementById("rx-dose-times").value) || 2;
    const meal = document.getElementById("rx-dose-meal").value;

    const timings = [];
    if (document.getElementById("rx-time-morn").checked) timings.push("morning");
    if (document.getElementById("rx-time-aft").checked) timings.push("afternoon");
    if (document.getElementById("rx-time-night").checked) timings.push("night");

    const payload = {
        patient_id: (currentUser && currentUser.patient_id) ? currentUser.patient_id : "pat_user",
        doctor_id: (currentUser && currentUser.doctor_id) ? currentUser.doctor_id : "doc_user",
        medicine_name: med,
        times_per_day: times,
        timings: timings.length ? timings : ["morning", "night"],
        meal_timing: meal
    };

    try {
        const res = await fetch(`${API_BASE}/api/clinical/prescription/increase-dose`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || "Prescription updated & sent to Pharmacy!", "success");
        }
    } catch (e) {
        showToast("Error updating prescription.", "emergency");
    }
}

async function submitNewMedsRx() {
    const medRows = document.querySelectorAll(".new-med-row");
    const meds = [];
    medRows.forEach(row => {
        const inputs = row.querySelectorAll("input, select");
        if (inputs[0] && inputs[0].value) {
            meds.push({
                name: inputs[0].value,
                dose_per_day: parseInt(inputs[1].value) || 1,
                meal_timing: inputs[2].value,
                timings: ["morning", "night"],
                duration_days: 7
            });
        }
    });

    const payload = {
        patient_id: (currentUser && currentUser.patient_id) ? currentUser.patient_id : "pat_user",
        doctor_id: (currentUser && currentUser.doctor_id) ? currentUser.doctor_id : "doc_user",
        medicines: meds.length ? meds : [{ name: "Paracetamol 650mg", dose_per_day: 2, meal_timing: "after_eating", timings: ["morning", "night"], duration_days: 5 }]
    };

    try {
        const res = await fetch(`${API_BASE}/api/clinical/prescription/new-medicines`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || "New prescription dispatched to Pharmacy!", "success");
        }
    } catch (e) {
        showToast("Error sending medicines.", "emergency");
    }
}

async function dispatchEmergencyReferral() {
    const hosp = document.getElementById("doc-ref-hospital").value;
    const doc = document.getElementById("doc-ref-doctor").value;
    const pin = document.getElementById("doc-generated-pin").textContent;

    const payload = {
        patient_id: (currentUser && currentUser.patient_id) ? currentUser.patient_id : "pat_user",
        referring_doctor_id: (currentUser && currentUser.doctor_id) ? currentUser.doctor_id : "doc_user",
        target_hospital_name: hosp,
        target_doctor_name: doc,
        specialty: "Critical Care & ICU",
        referral_reason: "High Emergency ICU Transfer Authorized",
        is_high_emergency: true,
        confirmation_pin: pin
    };

    try {
        const res = await fetch(`${API_BASE}/api/clinical/referral/consult-doctor`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Emergency ICU Transfer Authorized! PIN: ${pin}`, "emergency");
        }
    } catch (e) {
        showToast("Error dispatching referral.", "emergency");
    }
}

async function schedulePatientDate() {
    const date = document.getElementById("doc-sched-date").value;
    const time = document.getElementById("doc-sched-time").value;

    const payload = {
        patient_id: (currentUser && currentUser.patient_id) ? currentUser.patient_id : "pat_user",
        doctor_id: (currentUser && currentUser.doctor_id) ? currentUser.doctor_id : "doc_user",
        follow_up_date: date,
        follow_up_time: time,
        reason: "Follow-up consultation"
    };

    try {
        const res = await fetch(`${API_BASE}/api/clinical/doctor/schedule-date`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Follow-up scheduled for ${date} at ${time}!`, "success");
        }
    } catch (e) {
        showToast("Error scheduling date.", "emergency");
    }
}

// =============================================================================
// 8. HOSPITAL WARDS, BEDS & DISCHARGE
// =============================================================================

async function loadHospitalBeds() {
    try {
        const res = await fetch(`${API_BASE}/api/clinical/hospital/beds`);
        const data = await res.json();

        const grid = document.getElementById("hospital-beds-matrix-grid");
        const occDisp = document.getElementById("hosp-beds-occ");
        const availDisp = document.getElementById("hosp-beds-avail");

        if (occDisp) occDisp.textContent = data.occupied_beds || 0;
        if (availDisp) availDisp.textContent = data.available_beds || 0;

        if (grid) {
            grid.innerHTML = "";
            (data.beds || []).forEach(b => {
                const card = document.createElement("div");
                card.className = `bed-card ${b.is_occupied ? 'occupied' : 'available'}`;
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>${b.bed_number}</strong>
                        <span class="bed-status-tag ${b.is_occupied ? 'occ' : 'avail'}">
                            ${b.is_occupied ? 'OCCUPIED' : 'AVAILABLE'}
                        </span>
                    </div>
                    <p style="font-size:0.75rem; color:#64748b; margin:0.25rem 0;">${b.ward_name}</p>
                    ${b.is_occupied ? `<p style="font-size:0.78rem; font-weight:700; color:#0f172a;">👤 ${b.patient_name || 'Patient'}</p>` : ''}
                `;
                grid.appendChild(card);
            });
        }
    } catch (e) {}
}

async function allocatePatientWardAction() {
    const patientId = document.getElementById("alloc-patient-id").value;
    const ward = document.getElementById("alloc-ward-select").value;
    const bed = document.getElementById("alloc-bed-num").value;
    const specialist = document.getElementById("alloc-specialist").value;

    try {
        const res = await fetch(`${API_BASE}/api/clinical/hospital/allocate-ward`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ patient_id: patientId, ward_name: ward, bed_number: bed, assigned_doctor_name: specialist })
        });
        const data = await res.json();
        if (data.success) {
            showToast(`Patient allocated to ${ward} (Bed: ${bed})`, "success");
            await loadHospitalBeds();
        }
    } catch (e) {
        showToast("Error allocating bed.", "emergency");
    }
}

async function dischargePatientAction() {
    const bedVal = document.getElementById("discharge-bed-select").value;
    const summary = document.getElementById("discharge-summary-text").value;

    try {
        const res = await fetch(`${API_BASE}/api/clinical/hospital/discharge-patient`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bed_id: bedVal, patient_id: "pat_user", discharge_summary: summary })
        });
        const data = await res.json();
        if (data.success) {
            showToast("Discharge finalized! Bed released.", "success");
            await loadHospitalBeds();
        }
    } catch (e) {
        showToast("Error processing discharge.", "emergency");
    }
}

// =============================================================================
// 9. PHARMACY DASHBOARD & INVENTORY
// =============================================================================

async function loadPharmacyQueueAndInventory() {
    try {
        // Prescriptions Queue
        const rxRes = await fetch(`${API_BASE}/api/clinical/prescriptions`);
        const rxData = await rxRes.json();

        const rxContainer = document.getElementById("pharmacy-rx-queue-container");
        const rxCounter = document.getElementById("pending-rx-count");
        const headerAlert = document.getElementById("pharmacy-alert-counter");

        const pendingList = (rxData.prescriptions || []).filter(r => r.status === "PENDING");
        if (rxCounter) rxCounter.textContent = `${pendingList.length} Pending`;
        if (headerAlert) headerAlert.textContent = pendingList.length;

        if (rxContainer) {
            rxContainer.innerHTML = "";
            if (rxData.prescriptions && rxData.prescriptions.length === 0) {
                rxContainer.innerHTML = `
                    <div style="grid-column:1/-1; text-align:center; padding:2rem; color:#64748b;">
                        💊 <strong>No pending prescriptions at this moment.</strong><br>
                        When doctors submit new medicines or dose adjustments, they will appear here for 1-click dispensing.
                    </div>
                `;
            } else {
                (rxData.prescriptions || []).forEach(r => {
                    const rxCard = document.createElement("div");
                    rxCard.className = "dashboard-card";
                    rxCard.style.padding = "1rem";
                    rxCard.style.border = "1.5px solid #e2e8f0";

                    const medItemsList = (r.medicines || []).map(m => `<li><strong>${m.name}</strong> - ${m.dosage || m.frequency}</li>`).join("");

                    rxCard.innerHTML = `
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <strong>Patient: ${r.patient_name}</strong>
                            <span class="badge-status-pill ${r.status === 'PENDING' ? 'green' : 'green'}">${r.status}</span>
                        </div>
                        <p style="font-size:0.78rem; color:#64748b; margin:0.25rem 0;">Prescribed by: ${r.doctor_name}</p>
                        <ul style="font-size:0.82rem; margin:0.5rem 0 0 1.25rem;">
                            ${medItemsList}
                        </ul>
                        <div style="margin-top:0.75rem;">
                            ${r.status === 'PENDING'
                                ? `<button type="button" class="btn-sm-primary" onclick="dispensePrescriptionAction('${r.id}')">💊 1-Click Dispense</button>`
                                : `<span style="font-size:0.8rem; color:#059669; font-weight:700;">✓ Dispensed</span>`}
                        </div>
                    `;
                    rxContainer.appendChild(rxCard);
                });
            }
        }

        // Inventory
        const invRes = await fetch(`${API_BASE}/api/clinical/pharmacy/inventory`);
        const invData = await invRes.json();

        const tbody = document.getElementById("pharmacy-inventory-tbody");
        const alertBanner = document.getElementById("low-stock-alerts-banner");

        if (alertBanner) {
            alertBanner.innerHTML = (invData.low_stock_alerts || []).map(a => `<div class="low-stock-pill">${a}</div>`).join("");
        }

        if (tbody) {
            tbody.innerHTML = "";
            (invData.inventory || []).forEach(item => {
                const tr = document.createElement("tr");

                let statusBadge = `<span class="badge-stock in-stock">In Stock</span>`;
                if (item.is_finished) statusBadge = `<span class="badge-stock finish">🚨 FINISH</span>`;
                else if (item.is_low_stock) statusBadge = `<span class="badge-stock low">⚠️ LOW</span>`;

                tr.innerHTML = `
                    <td><strong>${item.medicine_name}</strong></td>
                    <td>${item.category}</td>
                    <td><strong>${item.stock_quantity}</strong></td>
                    <td>${item.low_stock_threshold}</td>
                    <td>${statusBadge}</td>
                    <td><button type="button" class="btn-xs-outline" onclick="openRestockModal('${item.id}', '${item.medicine_name}')">+ Restock</button></td>
                `;
                tbody.appendChild(tr);
            });
        }

        // Dispense Logs
        const logsRes = await fetch(`${API_BASE}/api/clinical/pharmacy/dispense-logs`);
        const logsData = await logsRes.json();
        const logsTbody = document.getElementById("dispense-logs-tbody");

        if (logsTbody) {
            logsTbody.innerHTML = "";
            (logsData.logs || []).forEach(log => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><code>${log.id}</code></td>
                    <td><strong>${log.patient_name}</strong></td>
                    <td>${log.doctor_name}</td>
                    <td>${(log.medicines_provided || []).join(", ")}</td>
                    <td>${log.dispensed_at}</td>
                    <td>${log.pharmacist}</td>
                    <td><span class="badge-stock in-stock">${log.status}</span></td>
                `;
                logsTbody.appendChild(tr);
            });
        }
    } catch (e) {}
}

async function dispensePrescriptionAction(rxId) {
    try {
        const res = await fetch(`${API_BASE}/api/clinical/prescriptions/dispense`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prescription_id: rxId })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || "Prescription dispensed!", "success");
            await loadPharmacyQueueAndInventory();
        }
    } catch (e) {
        showToast("Error dispensing prescription.", "emergency");
    }
}

function openRestockModal(itemId, itemName) {
    const modal = document.getElementById("restock-modal");
    const select = document.getElementById("restock-item-select");
    if (!modal) return;

    if (select) {
        select.innerHTML = `
            <option value="${itemId}" selected>${itemName}</option>
        `;
    }

    modal.classList.add("active");
}

function closeRestockModal() {
    const modal = document.getElementById("restock-modal");
    if (modal) modal.classList.remove("active");
}

async function submitRestockAction() {
    const itemId = document.getElementById("restock-item-select").value;
    const qty = parseInt(document.getElementById("restock-qty-input").value) || 50;

    try {
        const res = await fetch(`${API_BASE}/api/clinical/pharmacy/restock`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ inventory_id: itemId, quantity_to_add: qty })
        });
        const data = await res.json();
        if (data.success) {
            showToast("Item restocked successfully!", "success");
            closeRestockModal();
            await loadPharmacyQueueAndInventory();
        }
    } catch (e) {
        showToast("Error restocking item.", "emergency");
    }
}

// =============================================================================
// 10. EMERGENCY ICU TRANSFER SCREEN
// =============================================================================

async function loadIcuTransferScreen() {
    const patId = (currentUser && (currentUser.patient_id || currentUser.id)) ? (currentUser.patient_id || currentUser.id) : "pat_user";
    try {
        const res = await fetch(`${API_BASE}/api/qr/generate/${patId}/TRANSFER_AUTH`);
        const data = await res.json();
        if (data.success && data.qr_image_base64) {
            const img = document.getElementById("icu-transfer-qr-img");
            if (img) img.src = data.qr_image_base64;
        }
    } catch (e) {}
}

async function submitIcuPinVerification() {
    try {
        const res = await fetch(`${API_BASE}/api/qr/verify-transfer-pin`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token_payload: "TRANSFER_AUTH", pin: "584920" })
        });
        const data = await res.json();
        const resBox = document.getElementById("icu-verification-result");
        if (resBox) {
            resBox.style.display = "block";
            resBox.style.background = "#ecfdf5";
            resBox.style.border = "1px solid #a7f3d0";
            resBox.style.color = "#065f46";
            resBox.innerHTML = `<h4>✅ ${data.message}</h4><p>Allocated Ward: ${data.ward_name} (Bed: ${data.allocated_bed})</p>`;
            showToast("ICU Transfer PIN Verified! Bed Allocated.", "success");
        }
    } catch (e) {
        showToast("Error verifying PIN.", "emergency");
    }
}

// =============================================================================
// 11. MODAL & TOAST UTILITIES
// =============================================================================

function expandQrModal(imgSrc, title) {
    const modal = document.getElementById("qr-expand-modal");
    const img = document.getElementById("qr-expanded-img");
    const titleElem = document.getElementById("qr-modal-title");

    if (img) img.src = imgSrc;
    if (titleElem) titleElem.textContent = title;
    if (modal) modal.classList.add("active");
}

function closeQrModal() {
    const modal = document.getElementById("qr-expand-modal");
    if (modal) modal.classList.remove("active");
}

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
