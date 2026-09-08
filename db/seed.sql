-- ==============================================================================
-- PulseSync AI - PostgreSQL Database Seed Data
-- ==============================================================================

-- 1. USERS
INSERT INTO users (id, email, name, phone, role, language_preference)
VALUES 
('usr_patient_rahul', 'rahul.mishra@example.com', 'Rahul Mishra', '+91-9876543210', 'PATIENT', 'en'),
('usr_doc_amit', 'dr.amit.verma@pulsesync.care', 'Dr. Amit Verma', '+91-9811223344', 'DOCTOR', 'en'),
('usr_hosp_admin', 'admin@citygeneral.health', 'City Hospital Admin', '+91-11-2894001', 'HOSPITAL_ADMIN', 'en'),
('usr_pharma_apex', 'contact@apexmedico.com', 'Apex Medico Store', '+91-9988776655', 'PHARMACY', 'en')
ON CONFLICT (id) DO NOTHING;

-- 2. CLINICS & HOSPITALS
INSERT INTO clinics (id, name, registration_no, address, city, phone, email, qr_clinic_code)
VALUES 
('clinic_metro_01', 'Metro Wellness & Cardiology Clinic', 'MWC-2024-88', 'Plot 42, Sector 14, Ring Road', 'New Delhi', '+91-11-26549900', 'contact@metrowellness.in', 'QR_CLINIC_METRO_01')
ON CONFLICT (id) DO NOTHING;

INSERT INTO hospitals (id, name, registration_no, address, city, emergency_phone, total_icu_beds, total_general_beds)
VALUES 
('hosp_city_general', 'City General Hospital', 'CGH-DEL-1092', 'Main Institutional Area, Outer Ring Road', 'New Delhi', '+91-11-2894000', 25, 150)
ON CONFLICT (id) DO NOTHING;

-- 3. DOCTORS
INSERT INTO doctors (id, user_id, clinic_id, hospital_id, full_name, specialization, license_no, available_hours, is_verified)
VALUES 
('doc_amit_verma', 'usr_doc_amit', 'clinic_metro_01', 'hosp_city_general', 'Dr. Amit Verma', 'Interventional Cardiology & Internal Medicine', 'MCI-49201-DEL', '{"mon_sat": "09:00 - 17:00"}'::jsonb, TRUE)
ON CONFLICT (id) DO NOTHING;

-- 4. PATIENT PROFILES
INSERT INTO patients (
    id, user_id, full_name, age, dob, gender, blood_group, 
    existing_conditions, allergies, current_medications, medical_history, 
    is_child, emergency_contact_name, emergency_contact_phone, 
    insurance_provider, insurance_policy_no, insurance_is_active
)
VALUES (
    'pat_rahul_mishra', 'usr_patient_rahul', 'Rahul Mishra', 34, '1992-04-14', 'Male', 'O+',
    '["Hypertension", "Borderline Hyperlipidemia"]'::jsonb,
    '["Penicillin"]'::jsonb,
    '[{"name": "Amlodipine", "dosage": "5mg", "frequency": "Once daily (Morning)", "since": "2 years"}]'::jsonb,
    '["Hospitalized in 2023 for acute gastroenteritis", "No past surgical history"]'::jsonb,
    FALSE, 'Pooja Mishra (Spouse)', '+91-9876543219',
    'Star Health Comprehensive Insurance', 'SH-POL-9830219-X', TRUE
)
ON CONFLICT (id) DO NOTHING;

-- 5. WARDS & BEDS
INSERT INTO wards_and_beds (id, hospital_id, ward_name, ward_type, bed_number, is_occupied, current_patient_id, assigned_doctor_id, admission_reason, admission_date, estimated_discharge_date)
VALUES 
('bed_cgh_icu_01', 'hosp_city_general', 'Cardiac ICU Ward A', 'ICU', 'ICU-01', FALSE, NULL, NULL, NULL, NULL, NULL),
('bed_cgh_icu_02', 'hosp_city_general', 'Cardiac ICU Ward A', 'ICU', 'ICU-02', FALSE, NULL, NULL, NULL, NULL, NULL),
('bed_cgh_icu_03', 'hosp_city_general', 'Cardiac ICU Ward A', 'ICU', 'ICU-03', TRUE, NULL, 'doc_amit_verma', 'Post-CABG recovery', CURRENT_TIMESTAMP - INTERVAL '2 days', CURRENT_DATE + INTERVAL '3 days'),
('bed_cgh_icu_04', 'hosp_city_general', 'Cardiac ICU Ward A', 'ICU', 'ICU-04', TRUE, 'pat_rahul_mishra', 'doc_amit_verma', 'Emergency ICU Transfer: Hypertensive Crisis (BP 210/130 mmHg)', CURRENT_TIMESTAMP, CURRENT_DATE + INTERVAL '2 days'),
('bed_cgh_icu_05', 'hosp_city_general', 'Cardiac ICU Ward A', 'ICU', 'ICU-05', FALSE, NULL, NULL, NULL, NULL, NULL),
('bed_cgh_gen_01', 'hosp_city_general', 'General Medicine Ward B', 'GENERAL', 'BED-101', FALSE, NULL, NULL, NULL, NULL, NULL),
('bed_cgh_gen_02', 'hosp_city_general', 'General Medicine Ward B', 'GENERAL', 'BED-102', TRUE, NULL, NULL, 'Dengue recovery', CURRENT_TIMESTAMP - INTERVAL '3 days', CURRENT_DATE + INTERVAL '1 day')
ON CONFLICT (id) DO NOTHING;

-- 6. CONSULTATIONS (Intake Questionnaire Flow)
INSERT INTO consultations (
    id, patient_id, clinic_id, doctor_id, visit_type, 
    chief_complaint, symptom_duration_value, symptom_duration_unit, symptom_severity, 
    is_repeat_visit, medicine_taken, medicine_taken_name, 
    regular_medications_confirmed, existing_conditions_confirmed, allergies_confirmed, 
    warning_symptoms, patient_notes, branch_responses, seasonal_context, status, is_urgent, urgency_reason
)
VALUES (
    'consult_rahul_2026_001', 'pat_rahul_mishra', 'clinic_metro_01', 'doc_amit_verma', 'FIRST_VISIT',
    'Blood Pressure', 4, 'Hours', 'Severe',
    FALSE, TRUE, 'Amlodipine 5mg (Taken 2 hours ago with no relief)',
    TRUE, TRUE, TRUE,
    '["chest_pain", "severe_weakness"]'::jsonb,
    'Sudden occipital throbbing headache, blurred vision, and chest tightness starting around 9:00 AM.',
    '{
        "qm1_visit_type": "problem-related visit",
        "qm2_latest_bp": "210/130 mmHg",
        "qm2_latest_glucose": "142 mg/dL",
        "qm3_taking_medication": true,
        "qm4_new_symptoms": "Occipital headache, palpitations, chest constriction, nausea"
    }'::jsonb,
    'monsoon', 'REFERRED_ICU', TRUE, 'Hypertensive Urgency/Crisis with chest tightness - immediate ICU transfer required'
)
ON CONFLICT (id) DO NOTHING;

-- 7. DOCTOR NOTES & CLINICAL ASSESSMENT
INSERT INTO doctor_notes (
    id, consultation_id, doctor_id, patient_id, 
    vital_bp, vital_pulse, vital_temperature, vital_spo2, vital_glucose, 
    ai_generated_summary, ai_risk_flags, 
    clinical_observations, confirmed_diagnosis, treatment_plan, 
    follow_up_instructions, follow_up_date, 
    is_emergency_transfer, referral_type, referral_hospital_id, referral_doctor_name, 
    referral_destination_name, referral_reason, transfer_status, confirmation_pin, is_finalized
)
VALUES (
    'note_rahul_2026_001', 'consult_rahul_2026_001', 'doc_amit_verma', 'pat_rahul_mishra',
    '210/130 mmHg', 108, '98.6 F', 97, '142 mg/dL',
    'PATIENT BIO: 34-year-old male with established history of hypertension. Allergic to Penicillin.
CHIEF COMPLAINT: Acute severe elevation of blood pressure (210/130 mmHg) associated with chest discomfort and visual disturbance lasting 4 hours.
WARNING FLAGS: Chest tightness and palpitations reported (Urgent Safety Alert Triggered).
SEASONAL CONTEXT: Monsoon (elevated stress/humidity risk).
RECOMMENDATION: Immediate intravenous antihypertensive titration and continuous invasive hemodynamic monitoring in ICU.',
    '["Severe Hypertensive Emergency Risk", "Penicillin Allergy Alert", "Critical Cardiac Referral"]'::jsonb,
    'Patient in acute distress, diaphoresis noted. Bilateral chest clear, S1/S2 heard, tachycardic rhythm. Fundoscopic examination reveals arteriolar narrowing. No focal neurological deficits.',
    'Hypertensive Crisis (BP 210/130 mmHg)',
    '1. Start IV Labetalol 20mg bolus over 2 mins under continuous ECG/BP monitoring.
2. Immediate transfer to Cardiac ICU at City General Hospital.
3. Serial cardiac enzymes (Troponin I) and 12-lead ECG.
4. Renal function test and serum electrolytes.',
    'Strict bed rest in ICU. Immediate transfer under cardiac ambulance supervision.',
    CURRENT_DATE + INTERVAL '2 days',
    TRUE, 'ICU_ADMISSION', 'hosp_city_general', 'Dr. Amit Verma',
    'CITY GENERAL HOSPITAL', 'ICU Admission', 'In Progress', '584920', TRUE
)
ON CONFLICT (id) DO NOTHING;

-- 8. PRESCRIPTIONS
INSERT INTO prescriptions (
    id, consultation_id, doctor_note_id, patient_id, doctor_id, 
    medicines, status, dispense_alert_sent, notes
)
VALUES (
    'rx_rahul_2026_001', 'consult_rahul_2026_001', 'note_rahul_2026_001', 'pat_rahul_mishra', 'doc_amit_verma',
    '[
        {
            "name": "Labetalol Hydrochloride IV",
            "dosage": "20mg / 4ml",
            "frequency": "Stat / Immediate",
            "duration": "Single Dose",
            "timing": "Slow IV bolus over 2 minutes",
            "instructions": "Administer with continuous BP monitoring"
        },
        {
            "name": "Amlodipine Besylate",
            "dosage": "10mg",
            "frequency": "1-0-1 (Twice Daily)",
            "duration": "14 Days",
            "timing": "After meals",
            "instructions": "Take consistently at 9 AM and 9 PM"
        },
        {
            "name": "Telmisartan",
            "dosage": "40mg",
            "frequency": "0-0-1 (Night)",
            "duration": "14 Days",
            "timing": "At bedtime",
            "instructions": "Monitor for dizziness when standing"
        }
    ]'::jsonb,
    'PENDING', TRUE, 'Urgent pharmacy alert triggered for stat Labetalol injection and ICU stabilization stock'
)
ON CONFLICT (id) DO NOTHING;

-- 9. PHARMACY STORES & INVENTORY
INSERT INTO pharmacy_stores (id, user_id, store_name, license_no, address, phone)
VALUES 
('pharma_apex_01', 'usr_pharma_apex', 'Apex Medico & Emergency Pharmacy', 'DL-PH-2024-9912', 'Shop 4, Ground Floor, Hospital Complex, Outer Ring Road', '+91-11-2894009')
ON CONFLICT (id) DO NOTHING;

INSERT INTO inventory (id, pharmacy_id, medicine_name, generic_name, dosage_form, stock_quantity, low_stock_threshold, price)
VALUES 
('inv_med_01', 'pharma_apex_01', 'Labetalol Hydrochloride IV 20mg', 'Labetalol HCl', 'Injection', 35, 10, 245.00),
('inv_med_02', 'pharma_apex_01', 'Amlodipine Besylate 10mg', 'Amlodipine', 'Tablet', 180, 25, 45.00),
('inv_med_03', 'pharma_apex_01', 'Telmisartan 40mg', 'Telmisartan', 'Tablet', 120, 20, 88.00),
('inv_med_04', 'pharma_apex_01', 'Paracetamol 650mg', 'Paracetamol', 'Tablet', 300, 50, 30.00),
('inv_med_05', 'pharma_apex_01', 'Azithromycin 500mg', 'Azithromycin', 'Tablet', 8, 15, 115.00), -- Low stock flag
('inv_med_06', 'pharma_apex_01', 'Levocetirizine 5mg', 'Levocetirizine', 'Tablet', 95, 20, 55.00),
('inv_med_07', 'pharma_apex_01', 'Salbutamol Inhaler 100mcg', 'Salbutamol', 'Inhaler', 4, 10, 160.00) -- Low stock flag
ON CONFLICT (id) DO NOTHING;

-- 10. PATIENT QR TOKENS
INSERT INTO patient_qr_tokens (id, patient_id, qr_type, token_payload, expires_at, is_active)
VALUES 
('qr_tok_rahul_profile', 'pat_rahul_mishra', 'PROFILE_INTAKE', 'PULSESYNC:PAT:pat_rahul_mishra:TOKEN:eyJhbGciOiJIUzI1NiJ9.eyJpZCI6InBhdF9yYWh1bF9taXNocmEifQ', CURRENT_TIMESTAMP + INTERVAL '30 days', TRUE),
('qr_tok_rahul_insurance', 'pat_rahul_mishra', 'INSURANCE_CLAIM', 'PULSESYNC:INS:pat_rahul_mishra:SH-POL-9830219-X:CLAIM_AUTH', CURRENT_TIMESTAMP + INTERVAL '30 days', TRUE),
('qr_tok_rahul_icu_transfer', 'pat_rahul_mishra', 'TRANSFER_AUTH', 'PULSESYNC:TRANSFER:CGH:ICU:pat_rahul_mishra:PIN:584920', CURRENT_TIMESTAMP + INTERVAL '24 hours', TRUE)
ON CONFLICT (id) DO NOTHING;
