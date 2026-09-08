-- ==============================================================================
-- PulseSync AI - PostgreSQL Database Schema (Phase 1)
-- AI-Powered Healthcare Workflow & Patient Medical Record System
-- ==============================================================================

-- Enable UUID extension if available
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 1. USERS & ROLES
-- ==============================================================================
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(32),
    role VARCHAR(32) NOT NULL DEFAULT 'PATIENT', -- 'PATIENT', 'DOCTOR', 'HOSPITAL_ADMIN', 'PHARMACY'
    language_preference VARCHAR(16) DEFAULT 'en', -- 'en', 'hi', etc.
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 2. PATIENT PROFILES (Longitudinal Medical History)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS patients (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    age INTEGER NOT NULL,
    dob DATE,
    gender VARCHAR(32) NOT NULL, -- 'Male', 'Female', 'Other'
    blood_group VARCHAR(8),
    existing_conditions JSONB DEFAULT '[]'::jsonb, -- e.g. ["Diabetes", "Hypertension", "Asthma"]
    allergies JSONB DEFAULT '[]'::jsonb, -- e.g. ["Penicillin", "Sulfa Drugs", "Peanuts"]
    current_medications JSONB DEFAULT '[]'::jsonb, -- e.g. [{"name": "Amlodipine 5mg", "frequency": "Daily"}]
    medical_history JSONB DEFAULT '[]'::jsonb, -- past surgeries, chronic issues
    is_child BOOLEAN DEFAULT FALSE,
    parent_guardian_name VARCHAR(255),
    parent_guardian_phone VARCHAR(32),
    emergency_contact_name VARCHAR(255),
    emergency_contact_phone VARCHAR(32),
    insurance_provider VARCHAR(255),
    insurance_policy_no VARCHAR(128),
    insurance_is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 3. CLINICS & HOSPITALS
-- ==============================================================================
CREATE TABLE IF NOT EXISTS clinics (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    registration_no VARCHAR(128) UNIQUE,
    address TEXT NOT NULL,
    city VARCHAR(128) NOT NULL,
    phone VARCHAR(32),
    email VARCHAR(255),
    qr_clinic_code VARCHAR(255) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hospitals (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    registration_no VARCHAR(128) UNIQUE,
    address TEXT NOT NULL,
    city VARCHAR(128) NOT NULL,
    emergency_phone VARCHAR(32),
    total_icu_beds INTEGER DEFAULT 0,
    total_general_beds INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 4. DOCTORS
-- ==============================================================================
CREATE TABLE IF NOT EXISTS doctors (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    clinic_id VARCHAR(64) REFERENCES clinics(id) ON DELETE SET NULL,
    hospital_id VARCHAR(64) REFERENCES hospitals(id) ON DELETE SET NULL,
    full_name VARCHAR(255) NOT NULL,
    specialization VARCHAR(128) NOT NULL,
    license_no VARCHAR(128) UNIQUE,
    degree_proof_url TEXT,
    available_hours JSONB DEFAULT '{"mon_fri": "09:00 - 18:00"}'::jsonb,
    is_verified BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 5. WARDS & BEDS (Hospital Management & ICU Tracking)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS wards_and_beds (
    id VARCHAR(64) PRIMARY KEY,
    hospital_id VARCHAR(64) NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    ward_name VARCHAR(128) NOT NULL, -- e.g. "Cardiac ICU", "General Ward A"
    ward_type VARCHAR(64) NOT NULL, -- "ICU", "GENERAL", "EMERGENCY", "PEDIATRIC"
    bed_number VARCHAR(32) NOT NULL, -- e.g. "ICU-04", "BED-12"
    is_occupied BOOLEAN DEFAULT FALSE,
    current_patient_id VARCHAR(64) REFERENCES patients(id) ON DELETE SET NULL,
    assigned_doctor_id VARCHAR(64) REFERENCES doctors(id) ON DELETE SET NULL,
    admission_reason TEXT,
    admission_date TIMESTAMP WITH TIME ZONE,
    estimated_discharge_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(hospital_id, ward_name, bed_number)
);

-- ==============================================================================
-- 6. CONSULTATIONS & ADAPTIVE INTAKE QUESTIONNAIRE
-- ==============================================================================
CREATE TABLE IF NOT EXISTS consultations (
    id VARCHAR(64) PRIMARY KEY,
    patient_id VARCHAR(64) NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    clinic_id VARCHAR(64) REFERENCES clinics(id) ON DELETE SET NULL,
    doctor_id VARCHAR(64) REFERENCES doctors(id) ON DELETE SET NULL,
    visit_type VARCHAR(32) DEFAULT 'FIRST_VISIT', -- 'FIRST_VISIT', 'REPEAT_VISIT'
    
    -- Core Intake Questions (Q1 - Q10)
    chief_complaint VARCHAR(128) NOT NULL, -- Q1: Fever, Cough, Cold, Pain, Weakness, Allergy, Blood Pressure, Diabetes, Other
    symptom_duration_value INTEGER, -- Q2: duration value
    symptom_duration_unit VARCHAR(32), -- Q2: Hours, Days, Weeks, Months
    symptom_severity VARCHAR(32) NOT NULL, -- Q3: Mild, Moderate, Severe
    is_repeat_visit BOOLEAN DEFAULT FALSE, -- Q4: First visit vs repeat visit
    previous_consultation_id VARCHAR(64) REFERENCES consultations(id) ON DELETE SET NULL, -- Q4 linked history
    medicine_taken BOOLEAN DEFAULT FALSE, -- Q5
    medicine_taken_name VARCHAR(255), -- Q5 details
    regular_medications_confirmed BOOLEAN DEFAULT TRUE, -- Q6
    existing_conditions_confirmed BOOLEAN DEFAULT TRUE, -- Q7
    allergies_confirmed BOOLEAN DEFAULT TRUE, -- Q8
    warning_symptoms JSONB DEFAULT '[]'::jsonb, -- Q9: ["breathing_difficulty", "chest_pain", "fainting", "severe_weakness", "very_high_fever"]
    patient_notes TEXT, -- Q10: Optional free text response
    
    -- Complaint-Specific Branch Responses (Section B)
    branch_responses JSONB DEFAULT '{}'::jsonb, 
    -- Examples:
    -- Fever: {"current_temp": "103 F", "days_of_fever": 4, "has_body_pain": true, "has_headache": true}
    -- Cough: {"is_productive": true, "throat_pain": true, "sneezing": false, "runny_nose": false, "breathing_difficulty": true}
    -- Pain: {"location": "Lower back", "severity": "Severe", "swelling_discoloration": false, "difficulty_moving": true}
    -- BP/Diabetes: {"latest_bp": "210/130", "latest_glucose": "240", "taking_meds": true, "new_symptoms": "Dizziness & chest tightness"}
    
    seasonal_context VARCHAR(64), -- 'monsoon', 'winter', 'summer'
    status VARCHAR(64) DEFAULT 'TRIAGED', -- 'TRIAGED', 'IN_DOCTOR_QUEUE', 'UNDER_REVIEW', 'COMPLETED', 'REFERRED_ICU'
    is_urgent BOOLEAN DEFAULT FALSE, -- Auto-flagged if warning symptoms selected
    urgency_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 7. DOCTOR NOTES & CLINICAL ASSESSMENTS
-- ==============================================================================
CREATE TABLE IF NOT EXISTS doctor_notes (
    id VARCHAR(64) PRIMARY KEY,
    consultation_id VARCHAR(64) UNIQUE NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    doctor_id VARCHAR(64) NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    patient_id VARCHAR(64) NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    
    -- Vitals Captured During Consultation
    vital_bp VARCHAR(32), -- e.g. "210/130 mmHg"
    vital_pulse INTEGER, -- e.g. 104 bpm
    vital_temperature VARCHAR(32), -- e.g. "103.2 F"
    vital_spo2 INTEGER, -- e.g. 96 %
    vital_glucose VARCHAR(32), -- e.g. "240 mg/dL"
    
    -- AI-Assisted Preliminary Note
    ai_generated_summary TEXT, -- Automated synthesis of intake responses, baseline bio, and recurring history
    ai_risk_flags JSONB DEFAULT '[]'::jsonb, -- e.g. ["Severe Hypertensive Crisis Risk", "Monsoon Viral Spike"]
    
    -- Doctor's Final Assessment & Treatment
    clinical_observations TEXT,
    confirmed_diagnosis VARCHAR(255) NOT NULL, -- e.g. "Hypertensive Crisis"
    treatment_plan TEXT,
    follow_up_instructions TEXT,
    follow_up_date DATE,
    
    -- Referral & Emergency Transfer (Matching Frontend UI Flow)
    is_emergency_transfer BOOLEAN DEFAULT FALSE,
    referral_type VARCHAR(64) DEFAULT 'NONE', -- 'NONE', 'ICU_ADMISSION', 'SPECIALIST_REFERRAL'
    referral_hospital_id VARCHAR(64) REFERENCES hospitals(id) ON DELETE SET NULL,
    referral_doctor_name VARCHAR(255),
    referral_destination_name VARCHAR(255), -- e.g. "CITY GENERAL HOSPITAL"
    referral_reason TEXT, -- e.g. "ICU Admission"
    transfer_status VARCHAR(64) DEFAULT 'NONE', -- 'NONE', 'In Progress', 'Hospital Notified', 'Admitted'
    confirmation_pin VARCHAR(16), -- 6-digit confirmation PIN (e.g. "584920")
    
    is_finalized BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 8. PRESCRIPTIONS & PHARMACY DISPENSING
-- ==============================================================================
CREATE TABLE IF NOT EXISTS prescriptions (
    id VARCHAR(64) PRIMARY KEY,
    consultation_id VARCHAR(64) REFERENCES consultations(id) ON DELETE SET NULL,
    doctor_note_id VARCHAR(64) REFERENCES doctor_notes(id) ON DELETE SET NULL,
    patient_id VARCHAR(64) NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id VARCHAR(64) NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    pharmacy_id VARCHAR(64),
    
    -- List of medicines prescribed
    medicines JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- Structure: [
    --   {"name": "Amlodipine", "dosage": "10mg", "frequency": "1-0-1", "duration": "10 days", "timing": "After food", "instructions": "Take with water"},
    --   {"name": "Labetalol IV", "dosage": "20mg", "frequency": "Stat", "duration": "Single Dose", "timing": "Immediate", "instructions": "Administer under observation"}
    -- ]
    
    status VARCHAR(32) DEFAULT 'PENDING', -- 'PENDING', 'DISPENSED', 'OUT_OF_STOCK'
    dispense_alert_sent BOOLEAN DEFAULT FALSE,
    dispensed_at TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 9. PHARMACY STORES & INVENTORY
-- ==============================================================================
CREATE TABLE IF NOT EXISTS pharmacy_stores (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    store_name VARCHAR(255) NOT NULL,
    license_no VARCHAR(128) UNIQUE,
    address TEXT NOT NULL,
    phone VARCHAR(32),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory (
    id VARCHAR(64) PRIMARY KEY,
    pharmacy_id VARCHAR(64) NOT NULL REFERENCES pharmacy_stores(id) ON DELETE CASCADE,
    medicine_name VARCHAR(255) NOT NULL,
    generic_name VARCHAR(255),
    dosage_form VARCHAR(64) NOT NULL, -- "Tablet", "Syrup", "Injection", "Capsule"
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    low_stock_threshold INTEGER NOT NULL DEFAULT 10,
    price NUMERIC(10, 2) DEFAULT 0.00,
    is_low_stock BOOLEAN GENERATED ALWAYS AS (stock_quantity <= low_stock_threshold) STORED,
    last_restocked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pharmacy_id, medicine_name)
);

-- ==============================================================================
-- 10. PATIENT QR TOKENS & IDENTIFICATION
-- ==============================================================================
CREATE TABLE IF NOT EXISTS patient_qr_tokens (
    id VARCHAR(64) PRIMARY KEY,
    patient_id VARCHAR(64) NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    qr_type VARCHAR(64) NOT NULL, -- 'PROFILE_INTAKE' (QR 1), 'INSURANCE_CLAIM' (QR 2), 'TRANSFER_AUTH'
    token_payload TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- INDEXES FOR PERFORMANCE
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_patients_user_id ON patients(user_id);
CREATE INDEX IF NOT EXISTS idx_consultations_patient_id ON consultations(patient_id);
CREATE INDEX IF NOT EXISTS idx_consultations_doctor_id ON consultations(doctor_id);
CREATE INDEX IF NOT EXISTS idx_consultations_status ON consultations(status);
CREATE INDEX IF NOT EXISTS idx_consultations_is_urgent ON consultations(is_urgent);
CREATE INDEX IF NOT EXISTS idx_doctor_notes_consultation_id ON doctor_notes(consultation_id);
CREATE INDEX IF NOT EXISTS idx_wards_hospital_occupied ON wards_and_beds(hospital_id, is_occupied);
CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions(patient_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_status ON prescriptions(status);
CREATE INDEX IF NOT EXISTS idx_inventory_pharmacy ON inventory(pharmacy_id);
