"""
PulseSync AI - End-to-End API Verification Suite
Tests Multi-Role Registration (Patient, Doctor, Hospital, Pharmacy), Dual QR Generation,
Dynamic Adaptive Questionnaire Engine, AI Summary Synthesis, and Hospital/Pharmacy workflows.
"""

import sys
import os
import uuid
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.main import app

client = TestClient(app)

def run_api_tests():
    print("=" * 80)
    print(" PULSESYNC AI - COMPREHENSIVE MULTI-ROLE & QR TEST SUITE")
    print("=" * 80)

    # 1. Health Check
    print("\n[TEST 1] Testing Health Endpoint & DB Connectivity...")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    data = res.json()
    print(f" [PASS] API Status: {data['status'].upper()} | Dialect: {data['database']['dialect']}")
    print(f"        Active URL: {data['database']['active_url']}")
    print(f"        Tables Count: {data['database']['tables_count']}")

    # 2. Dynamic Registration of All 4 Roles
    unique_suffix = uuid.uuid4().hex[:6]
    
    # 2A. Register Dynamic Patient
    print("\n[TEST 2A] Registering Dynamic Patient with Dual QR & Insurance details...")
    pat_payload = {
        "role": "PATIENT",
        "name": f"Pooja Sharma {unique_suffix}",
        "email": f"pooja_{unique_suffix}@example.com",
        "phone": "+91-9876501234",
        "age": 29,
        "gender": "Female",
        "blood_group": "B+",
        "city": "Mumbai",
        "address": "402 Sea View Apartments, Bandra West, Mumbai",
        "aadhaar_card_no": "9812-4412-8819",
        "pan_card_no": "PQRS1234T",
        "has_insurance": True,
        "insurance_provider": "HDFC ERGO Health Optima",
        "insurance_policy_no": f"HDFC-MED-{unique_suffix}",
        "insurance_claimed": False,
        "allergies": ["Sulfa Drugs"],
        "existing_conditions": ["Mild Asthma"]
    }
    reg_pat_res = client.post("/api/auth/register", json=pat_payload)
    assert reg_pat_res.status_code == 200, f"Patient register failed: {reg_pat_res.text}"
    pat_data = reg_pat_res.json()
    new_pat_id = pat_data["user"]["patient_id"]
    print(f" [PASS] Registered Patient ID: {new_pat_id} ({pat_data['user']['name']})")
    print(f"        Aadhaar: {pat_data['user']['aadhaar_card_no']} | Insurance: {pat_data['user']['insurance_provider']}")

    # 2B. Register Dynamic Doctor
    print("\n[TEST 2B] Registering Dynamic Doctor with Clinic & Certificate...")
    doc_payload = {
        "role": "DOCTOR",
        "name": f"Dr. Vikram Malhotra {unique_suffix}",
        "email": f"dr.vikram_{unique_suffix}@pulsesync.care",
        "phone": "+91-9811223399",
        "specialization": "Interventional Cardiology & Critical Care",
        "education": "MBBS, MD (Medicine), DM (Cardiology), FACC",
        "license_no": f"MCI-MUM-{unique_suffix}",
        "clinic_name": "Malhotra Heart & Wellness Clinic",
        "clinic_address": "Bandra Medical Enclave, Mumbai",
        "patients_checked_count": 35
    }
    reg_doc_res = client.post("/api/auth/register", json=doc_payload)
    assert reg_doc_res.status_code == 200, f"Doctor register failed: {reg_doc_res.text}"
    doc_data = reg_doc_res.json()
    new_doc_id = doc_data["user"]["doctor_id"]
    print(f" [PASS] Registered Doctor ID: {new_doc_id} ({doc_data['user']['name']})")
    print(f"        Specialization: {doc_data['user']['specialization']} | Clinic: {doc_data['user']['clinic_name']}")

    # 2C. Register Dynamic Hospital
    print("\n[TEST 2C] Registering Multiservice Hospital with Treatments & Wards...")
    hosp_payload = {
        "role": "HOSPITAL_ADMIN",
        "name": f"Apollo Multispecialty Hospital {unique_suffix}",
        "email": f"admin_apollo_{unique_suffix}@apollo.health",
        "phone": "+91-22-26994000",
        "hospital_name": f"Apollo Multispecialty Hospital {unique_suffix}",
        "registration_no": f"APOLLO-REG-{unique_suffix}",
        "emergency_phone": "+91-22-26994108",
        "city": "Mumbai",
        "address": "Opp. Coastal Road, Worli, Mumbai",
        "total_doctors": 28,
        "total_wards": 6,
        "total_icu_beds": 30,
        "total_general_beds": 180,
        "treatments": ["Cardiology", "Organ Transplant", "Emergency Trauma & ICU", "Neurosurgery"]
    }
    reg_hosp_res = client.post("/api/auth/register", json=hosp_payload)
    assert reg_hosp_res.status_code == 200, f"Hospital register failed: {reg_hosp_res.text}"
    hosp_data = reg_hosp_res.json()
    new_hosp_id = hosp_data["user"]["hospital_id"]
    print(f" [PASS] Registered Hospital ID: {new_hosp_id} ({hosp_data['user']['hospital_name']})")
    print(f"        ICU Beds: {hosp_data['user']['total_icu_beds']} | Treatments: {hosp_data['user']['treatments']}")

    # 2D. Register Dynamic Pharmacy
    print("\n[TEST 2D] Registering Medical Store (Pharmacy) with Drug License...")
    pharma_payload = {
        "role": "PHARMACY",
        "name": "Karan Sharma (R.Ph.)",
        "email": f"karan_pharma_{unique_suffix}@medstore.in",
        "phone": "+91-9988771122",
        "store_name": f"Sanjeevani 24x7 Chemist {unique_suffix}",
        "pharmacist_name": "Karan Sharma (R.Ph.)",
        "drug_license_no": f"MH-20B-MUM-{unique_suffix}",
        "address": "Shop 12, Ground Floor, Apollo Hospital Complex, Worli, Mumbai"
    }
    reg_pharm_res = client.post("/api/auth/register", json=pharma_payload)
    assert reg_pharm_res.status_code == 200, f"Pharmacy register failed: {reg_pharm_res.text}"
    pharm_data = reg_pharm_res.json()
    new_pharm_id = pharm_data["user"]["pharmacy_id"]
    print(f" [PASS] Registered Pharmacy ID: {new_pharm_id} ({pharm_data['user']['store_name']})")
    print(f"        License: {pharm_data['user']['license_no']} | Pharmacist: {pharm_data['user']['pharmacist_name']}")

    # 3. Test Dynamic QR Code Generation for All Entities
    print("\n[TEST 3] Testing Dynamic QR Code Generation for All 4 Roles...")
    
    # 3A. Patient QR 1: Medical Profile QR
    qr_p1_res = client.get(f"/api/qr/generate/{new_pat_id}/PROFILE_INTAKE")
    assert qr_p1_res.status_code == 200
    assert qr_p1_res.json()["qr_image_base64"].startswith("data:image/png;base64,")
    print(f" [PASS] Patient Medical Profile QR Generated: {qr_p1_res.json()['token_payload']}")

    # 3B. Patient QR 2: Insurance Claim QR
    qr_p2_res = client.get(f"/api/qr/generate/{new_pat_id}/INSURANCE_CLAIM")
    assert qr_p2_res.status_code == 200
    assert qr_p2_res.json()["qr_image_base64"].startswith("data:image/png;base64,")
    print(f" [PASS] Patient Insurance Claim QR Generated: {qr_p2_res.json()['token_payload']}")

    # 3C. Doctor Clinic QR
    qr_doc_res = client.get(f"/api/qr/doctor/{new_doc_id}")
    assert qr_doc_res.status_code == 200
    print(f" [PASS] Doctor Clinic QR Generated: {qr_doc_res.json()['token_payload']}")

    # 3D. Hospital QR
    qr_hosp_res = client.get(f"/api/qr/hospital/{new_hosp_id}")
    assert qr_hosp_res.status_code == 200
    print(f" [PASS] Hospital QR Generated: {qr_hosp_res.json()['token_payload']}")

    # 3E. Pharmacy QR
    qr_pharm_res = client.get(f"/api/qr/pharmacy/{new_pharm_id}")
    assert qr_pharm_res.status_code == 200
    print(f" [PASS] Pharmacy Store QR Generated: {qr_pharm_res.json()['token_payload']}")

    # 4. Multi-Role Authentication (Login) Verification
    print("\n[TEST 4] Testing Login for Registered Accounts...")
    login_res = client.post("/api/auth/login", json={"email": pat_payload["email"]})
    assert login_res.status_code == 200
    assert login_res.json()["user"]["role"] == "PATIENT"
    print(f" [PASS] Patient Login Successful: {login_res.json()['user']['name']}")

    login_doc = client.post("/api/auth/login", json={"email": doc_payload["email"]})
    assert login_doc.status_code == 200
    assert login_doc.json()["user"]["role"] == "DOCTOR"
    print(f" [PASS] Doctor Login Successful: {login_doc.json()['user']['name']}")

    # 5. Dynamic Intake Submission & Emergency Triage
    print("\n[TEST 5] Submitting Dynamic Patient Intake for Newly Registered Patient...")
    intake_payload = {
        "patient_id": new_pat_id,
        "doctor_id": new_doc_id,
        "q1_chief_complaint": "Blood Pressure",
        "q2_duration_value": 3,
        "q2_duration_unit": "Hours",
        "q3_severity": "Severe",
        "q4_is_first_visit": True,
        "q5_taken_any_medication": False,
        "q9_warning_symptoms": ["chest_pain", "severe_weakness"],
        "vital_bp": "215/135 mmHg",
        "vital_pulse": 110,
        "vital_temperature": "98.6 °F",
        "vital_spo2": 96
    }
    submit_res = client.post("/api/intake/submit", json=intake_payload)
    assert submit_res.status_code == 200
    s_data = submit_res.json()
    assert s_data["is_urgent"] == True
    print(f" [PASS] Intake Recorded: ID {s_data['consultation_id']} (Urgent Triage: {s_data['triage_status']})")

    # 6. Doctor Consultation & The 3 Prescription Outputs
    print("\n[TEST 6] Testing Doctor Prescription Outputs for New Patient...")
    
    # Output 1: Increase Dose
    inc_res = client.post("/api/clinical/prescription/increase-dose", json={
        "patient_id": new_pat_id,
        "doctor_id": new_doc_id,
        "medicine_name": "Telmisartan 40mg",
        "times_per_day": 2,
        "timings": ["morning", "night"],
        "meal_timing": "after_eating",
        "doctor_notes": "Escalated dose due to acute elevation"
    })
    assert inc_res.status_code == 200
    print(f" [PASS] Output 1 (Increase Dose): {inc_res.json()['summary']}")

    # Output 2: New Medicines Multiple
    new_meds_res = client.post("/api/clinical/prescription/new-medicines", json={
        "patient_id": new_pat_id,
        "doctor_id": new_doc_id,
        "is_multiple": True,
        "medicines": [
            {"name": "Amlodipine Besylate 10mg", "dose_per_day": 2, "meal_timing": "after_eating", "timings": ["morning", "night"], "duration_days": 14},
            {"name": "Hydrochlorothiazide 12.5mg", "dose_per_day": 1, "meal_timing": "before_eating", "timings": ["morning"], "duration_days": 14}
        ]
    })
    assert new_meds_res.status_code == 200
    new_rx_id = new_meds_res.json()["prescription_id"]
    print(f" [PASS] Output 2 (New Meds Multiple): {new_meds_res.json()['message']}")

    # Output 3: Consult Another Doctor & Emergency Transfer
    ref_res = client.post("/api/clinical/referral/consult-doctor", json={
        "patient_id": new_pat_id,
        "referring_doctor_id": new_doc_id,
        "target_hospital_name": hosp_payload["name"],
        "target_doctor_name": "Dr. Rajesh Gupta",
        "specialty": "Cardiology & ICU",
        "referral_reason": "Hypertensive Urgency with chest symptoms",
        "is_high_emergency": True,
        "confirmation_pin": "584920"
    })
    assert ref_res.status_code == 200
    print(f" [PASS] Output 3 (Specialist Referral): {ref_res.json()['message']}")

    # 7. Follow-Up Date Scheduler ("Give a Date to Patients")
    print("\n[TEST 7] Testing Follow-Up Date Scheduler...")
    sched_res = client.post("/api/clinical/doctor/schedule-date", json={
        "patient_id": new_pat_id,
        "doctor_id": new_doc_id,
        "follow_up_date": "2026-08-30",
        "follow_up_time": "11:00 AM",
        "reason": "Blood Pressure & Treatment Titration Review"
    })
    assert sched_res.status_code == 200
    print(f" [PASS] Date Scheduled: {sched_res.json()['message']}")

    # 8. Hospital Bed Allocation & Discharge
    print("\n[TEST 8] Testing Hospital Ward Bed Allocation & Discharge...")
    alloc_res = client.post("/api/clinical/hospital/allocate-ward", json={
        "patient_id": new_pat_id,
        "ward_name": "Cardiac ICU Ward A",
        "bed_number": "ICU-02",
        "assigned_doctor_name": doc_payload["name"]
    })
    assert alloc_res.status_code == 200
    print(f" [PASS] Ward Allocated: {alloc_res.json()['message']}")

    disch_res = client.post("/api/clinical/hospital/discharge-patient", json={
        "bed_id": "ICU-02",
        "patient_id": new_pat_id,
        "discharge_summary": "Patient stabilized. Discharged with home medication plan."
    })
    assert disch_res.status_code == 200
    print(f" [PASS] Discharge Handled: {disch_res.json()['message']}")

    # 9. Pharmacy Dispensing & Stock Audit
    print("\n[TEST 9] Testing Pharmacy Prescription Dispense & Audit Trail...")
    disp_res = client.post("/api/clinical/prescriptions/dispense", json={
        "prescription_id": new_rx_id,
        "pharmacy_id": new_pharm_id
    })
    assert disp_res.status_code == 200
    print(f" [PASS] Dispensed Prescription: {disp_res.json()['message']}")

    # 10. QR Confirmation PIN Verification
    print("\n[TEST 10] Testing Emergency Transfer PIN Verification...")
    pin_res = client.post("/api/qr/verify-transfer-pin", json={
        "token_payload": "TRANSFER_AUTH_TOKEN",
        "pin": "584920"
    })
    assert pin_res.status_code == 200
    assert pin_res.json()["verified"] == True
    print(f" [PASS] PIN 584920 Verified: {pin_res.json()['message']}")

    print("\n" + "=" * 80)
    print(" [SUCCESS] ALL MULTI-ROLE & DYNAMIC QR API MODULES PASSED WITH 100% SUCCESS!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_api_tests()
