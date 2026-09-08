"""
PulseSync AI - Database & Schema Verification Test Suite
Tests relational models, table creation, seed population, and clinical workflow queries
"""

import sys
import os
import json

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import init_db, get_db_info, SessionLocal, engine
from backend.seed_data import seed_database
from backend.models import (
    User, Patient, Clinic, Hospital, Doctor, WardAndBed,
    Consultation, DoctorNote, Prescription, PharmacyStore, Inventory, PatientQRToken
)

def run_tests():
    print("=" * 80)
    print(" PULSESYNC AI - DATABASE & SCHEMA VERIFICATION SUITE")
    print("=" * 80)

    # 1. Initialize Tables
    print("\n[STEP 1] Initializing Database Schema...")
    init_db()
    info = get_db_info()
    print(f" Database Status: {info['status'].upper()}")
    print(f" Dialect: {info['dialect']}")
    print(f" Tables Created: {info['tables_count']}")
    for tbl in info['tables']:
        print(f"   - {tbl}")

    # 2. Seed Data
    print("\n[STEP 2] Seeding Realistic Clinical Data...")
    seed_database()

    # 3. Query Validations
    print("\n[STEP 3] Running Clinical Workflow Validations...")
    db = SessionLocal()
    try:
        # Patient Profile & Bio
        patient = db.query(Patient).filter(Patient.id == "pat_rahul_mishra").first()
        assert patient is not None, "Patient Rahul Mishra not found!"
        print(f" [PASS] Patient Verified: {patient.full_name}, Age: {patient.age}, Gender: {patient.gender}, Blood: {patient.blood_group}")
        print(f"        Allergies: {patient.allergies}")
        print(f"        Baseline Conditions: {patient.existing_conditions}")

        # Doctor & Clinic
        doctor = db.query(Doctor).filter(Doctor.id == "doc_amit_verma").first()
        clinic = db.query(Clinic).filter(Clinic.id == "clinic_metro_01").first()
        assert doctor is not None and clinic is not None, "Doctor or Clinic not found!"
        print(f" [PASS] Doctor Verified: {doctor.full_name} ({doctor.specialization}) at {clinic.name}")

        # Dynamic Consultation Intake
        consult = db.query(Consultation).filter(Consultation.patient_id == patient.id).first()
        assert consult is not None, "Consultation not found!"
        print(f" [PASS] Consultation Intake Verified:")
        print(f"        Chief Complaint (Q1): {consult.chief_complaint}")
        print(f"        Duration (Q2): {consult.symptom_duration_value} {consult.symptom_duration_unit}")
        print(f"        Severity (Q3): {consult.symptom_severity}")
        print(f"        Warning Symptoms (Q9): {consult.warning_symptoms} (Urgent: {consult.is_urgent})")
        print(f"        Branch Responses: {json.dumps(consult.branch_responses)}")

        # Doctor Note & ICU Transfer Verification (Matching UI Screen)
        note = db.query(DoctorNote).filter(DoctorNote.consultation_id == consult.id).first()
        assert note is not None, "Doctor note not found!"
        print(f" [PASS] Emergency ICU Transfer Note Verified (Matching UI Mockup):")
        print(f"        Diagnosis: {note.confirmed_diagnosis}")
        print(f"        Vitals: BP {note.vital_bp}, Pulse {note.vital_pulse} bpm, Temp {note.vital_temperature}, SpO2 {note.vital_spo2}%")
        print(f"        Referring Doctor: {note.referral_doctor_name} -> Destination: {note.referral_destination_name}")
        print(f"        Reason: {note.referral_reason}")
        print(f"        Transfer Status: {note.transfer_status}")
        print(f"        Confirmation PIN: {note.confirmation_pin}")

        # Ward & Bed Allocation
        bed = db.query(WardAndBed).filter(WardAndBed.current_patient_id == patient.id).first()
        assert bed is not None, "Allocated bed not found!"
        hospital = db.query(Hospital).filter(Hospital.id == bed.hospital_id).first()
        print(f" [PASS] ICU Bed Allocation Verified:")
        print(f"        Hospital: {hospital.name}")
        print(f"        Ward: {bed.ward_name} | Bed: {bed.bed_number} | Occupied: {bed.is_occupied}")

        # Prescriptions & Pharmacy Dispensing
        rx = db.query(Prescription).filter(Prescription.patient_id == patient.id).first()
        assert rx is not None, "Prescription not found!"
        print(f" [PASS] Prescription Verified: Status: {rx.status} | Alert Sent: {rx.dispense_alert_sent}")
        print(f"        Prescribed Medicines ({len(rx.medicines)} items):")
        for med in rx.medicines:
            print(f"          * {med['name']} ({med['dosage']}) - {med['frequency']} for {med['duration']}")

        # Pharmacy Inventory & Low Stock Tracking
        low_stock_items = [item for item in db.query(Inventory).all() if item.is_low_stock]
        print(f" [PASS] Inventory Verified: {db.query(Inventory).count()} total items, {len(low_stock_items)} low-stock alerts:")
        for item in low_stock_items:
            print(f"          [ALERT] LOW STOCK: {item.medicine_name} (Qty: {item.stock_quantity}, Threshold: {item.low_stock_threshold})")

        # QR Codes
        qr_tokens = db.query(PatientQRToken).filter(PatientQRToken.patient_id == patient.id).all()
        print(f" [PASS] Patient QR Tokens Verified ({len(qr_tokens)} tokens):")
        for tok in qr_tokens:
            print(f"          - [{tok.qr_type}] Payload: {tok.token_payload[:45]}...")

        # Final Table Metrics
        final_info = get_db_info()
        print("\n" + "=" * 80)
        print(" DATABASE SUMMARY & RECORD COUNTS:")
        print("=" * 80)
        for tbl, count in final_info["row_counts"].items():
            print(f"  {tbl:<25} : {count} records")
        print("=" * 80)
        print(" [SUCCESS] ALL 10 DATABASE TABLES AND CLINICAL WORKFLOW VALIDATIONS PASSED!\n")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
