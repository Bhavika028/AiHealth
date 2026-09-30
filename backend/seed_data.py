"""
PulseSync AI - Database Seeder
Populates initial clinical test data, demo patient profiles, hospital wards, ICU transfer, prescriptions, and pharmacy inventory
"""

from datetime import datetime, date, timedelta
from .database import SessionLocal, init_db
from .models import (
    User, Patient, Clinic, Hospital, Doctor, WardAndBed,
    Consultation, DoctorNote, Prescription, PharmacyStore, Inventory, PatientQRToken
)

def seed_database():
    """Initializes schema. Fake data seeding has been permanently disabled."""
    init_db()
    print("[SEED] Database schema initialized. Fake data seeding is disabled to ensure only real registered users and live data are used.")
    return

    if False:
        # 1. USERS
        patient_user = User(
            id="usr_patient_rahul",
            email="rahul.mishra@example.com",
            name="Rahul Mishra",
            phone="+91-9876543210",
            role="PATIENT",
            language_preference="en"
        )
        doctor_user = User(
            id="usr_doc_amit",
            email="dr.amit.verma@pulsesync.care",
            name="Dr. Amit Verma",
            phone="+91-9811223344",
            role="DOCTOR",
            language_preference="en"
        )
        hosp_admin_user = User(
            id="usr_hosp_admin",
            email="admin@citygeneral.health",
            name="City Hospital Admin",
            phone="+91-11-2894001",
            role="HOSPITAL_ADMIN",
            language_preference="en"
        )
        pharma_user = User(
            id="usr_pharma_apex",
            email="contact@apexmedico.com",
            name="Apex Medico Store",
            phone="+91-9988776655",
            role="PHARMACY",
            language_preference="en"
        )
        db.add_all([patient_user, doctor_user, hosp_admin_user, pharma_user])
        db.commit()

        # 2. CLINIC & HOSPITAL
        clinic = Clinic(
            id="clinic_metro_01",
            name="Metro Wellness & Cardiology Clinic",
            registration_no="MWC-2024-88",
            address="Plot 42, Sector 14, Ring Road",
            city="New Delhi",
            phone="+91-11-26549900",
            email="contact@metrowellness.in",
            qr_clinic_code="QR_CLINIC_METRO_01"
        )
        hospital = Hospital(
            id="hosp_city_general",
            name="City General Hospital",
            registration_no="CGH-DEL-1092",
            address="Main Institutional Area, Outer Ring Road",
            city="New Delhi",
            emergency_phone="+91-11-2894000",
            total_icu_beds=25,
            total_general_beds=150
        )
        db.add_all([clinic, hospital])
        db.commit()

        # 3. DOCTOR
        doctor = Doctor(
            id="doc_amit_verma",
            user_id="usr_doc_amit",
            clinic_id="clinic_metro_01",
            hospital_id="hosp_city_general",
            full_name="Dr. Amit Verma",
            specialization="Interventional Cardiology & Internal Medicine",
            license_no="MCI-49201-DEL",
            available_hours={"mon_sat": "09:00 - 17:00"},
            is_verified=True
        )
        db.add(doctor)
        db.commit()

        # 4. PATIENT PROFILE (Matching UI Mockup)
        patient = Patient(
            id="pat_rahul_mishra",
            user_id="usr_patient_rahul",
            full_name="Rahul Mishra",
            age=34,
            dob=date(1992, 4, 14),
            gender="Male",
            blood_group="O+",
            existing_conditions=["Hypertension", "Borderline Hyperlipidemia"],
            allergies=["Penicillin"],
            current_medications=[{"name": "Amlodipine", "dosage": "5mg", "frequency": "Once daily (Morning)", "since": "2 years"}],
            medical_history=["Hospitalized in 2023 for acute gastroenteritis", "No past surgical history"],
            is_child=False,
            emergency_contact_name="Pooja Mishra (Spouse)",
            emergency_contact_phone="+91-9876543219",
            insurance_provider="Star Health Comprehensive Insurance",
            insurance_policy_no="SH-POL-9830219-X",
            insurance_is_active=True
        )
        db.add(patient)
        db.commit()

        # 5. WARDS & BEDS (ICU Allocation)
        beds = [
            WardAndBed(
                id="bed_cgh_icu_01",
                hospital_id="hosp_city_general",
                ward_name="Cardiac ICU Ward A",
                ward_type="ICU",
                bed_number="ICU-01",
                is_occupied=False
            ),
            WardAndBed(
                id="bed_cgh_icu_02",
                hospital_id="hosp_city_general",
                ward_name="Cardiac ICU Ward A",
                ward_type="ICU",
                bed_number="ICU-02",
                is_occupied=False
            ),
            WardAndBed(
                id="bed_cgh_icu_03",
                hospital_id="hosp_city_general",
                ward_name="Cardiac ICU Ward A",
                ward_type="ICU",
                bed_number="ICU-03",
                is_occupied=True,
                assigned_doctor_id="doc_amit_verma",
                admission_reason="Post-CABG recovery",
                admission_date=datetime.utcnow() - timedelta(days=2),
                estimated_discharge_date=date.today() + timedelta(days=3)
            ),
            WardAndBed(
                id="bed_cgh_icu_04",
                hospital_id="hosp_city_general",
                ward_name="Cardiac ICU Ward A",
                ward_type="ICU",
                bed_number="ICU-04",
                is_occupied=True,
                current_patient_id="pat_rahul_mishra",
                assigned_doctor_id="doc_amit_verma",
                admission_reason="Emergency ICU Transfer: Hypertensive Crisis (BP 210/130 mmHg)",
                admission_date=datetime.utcnow(),
                estimated_discharge_date=date.today() + timedelta(days=2)
            ),
            WardAndBed(
                id="bed_cgh_icu_05",
                hospital_id="hosp_city_general",
                ward_name="Cardiac ICU Ward A",
                ward_type="ICU",
                bed_number="ICU-05",
                is_occupied=False
            ),
            WardAndBed(
                id="bed_cgh_gen_01",
                hospital_id="hosp_city_general",
                ward_name="General Medicine Ward B",
                ward_type="GENERAL",
                bed_number="BED-101",
                is_occupied=False
            )
        ]
        db.add_all(beds)
        db.commit()

        # 6. CONSULTATION (Intake Responses)
        consultation = Consultation(
            id="consult_rahul_2026_001",
            patient_id="pat_rahul_mishra",
            clinic_id="clinic_metro_01",
            doctor_id="doc_amit_verma",
            visit_type="FIRST_VISIT",
            chief_complaint="Blood Pressure",
            symptom_duration_value=4,
            symptom_duration_unit="Hours",
            symptom_severity="Severe",
            is_repeat_visit=False,
            medicine_taken=True,
            medicine_taken_name="Amlodipine 5mg (Taken 2 hours ago with no relief)",
            regular_medications_confirmed=True,
            existing_conditions_confirmed=True,
            allergies_confirmed=True,
            warning_symptoms=["chest_pain", "severe_weakness"],
            patient_notes="Sudden occipital throbbing headache, blurred vision, and chest tightness starting around 9:00 AM.",
            branch_responses={
                "qm1_visit_type": "problem-related visit",
                "qm2_latest_bp": "210/130 mmHg",
                "qm2_latest_glucose": "142 mg/dL",
                "qm3_taking_medication": True,
                "qm4_new_symptoms": "Occipital headache, palpitations, chest constriction, nausea"
            },
            seasonal_context="monsoon",
            status="REFERRED_ICU",
            is_urgent=True,
            urgency_reason="Hypertensive Urgency/Crisis with chest tightness - immediate ICU transfer required"
        )
        db.add(consultation)
        db.commit()

        # 7. DOCTOR NOTE (Matching Frontend UI Flow)
        doctor_note = DoctorNote(
            id="note_rahul_2026_001",
            consultation_id="consult_rahul_2026_001",
            doctor_id="doc_amit_verma",
            patient_id="pat_rahul_mishra",
            vital_bp="210/130 mmHg",
            vital_pulse=108,
            vital_temperature="98.6 F",
            vital_spo2=97,
            vital_glucose="142 mg/dL",
            ai_generated_summary=(
                "PATIENT BIO: 34-year-old male with established history of hypertension. Allergic to Penicillin.\n"
                "CHIEF COMPLAINT: Acute severe elevation of blood pressure (210/130 mmHg) associated with chest discomfort and visual disturbance lasting 4 hours.\n"
                "WARNING FLAGS: Chest tightness and palpitations reported (Urgent Safety Alert Triggered).\n"
                "SEASONAL CONTEXT: Monsoon (elevated humidity/stress risk).\n"
                "RECOMMENDATION: Immediate intravenous antihypertensive titration and continuous invasive hemodynamic monitoring in ICU."
            ),
            ai_risk_flags=["Severe Hypertensive Emergency Risk", "Penicillin Allergy Alert", "Critical Cardiac Referral"],
            clinical_observations="Patient in acute distress, diaphoresis noted. Bilateral chest clear, S1/S2 heard, tachycardic rhythm. Fundoscopic examination reveals arteriolar narrowing. No focal neurological deficits.",
            confirmed_diagnosis="Hypertensive Crisis (BP 210/130 mmHg)",
            treatment_plan=(
                "1. Start IV Labetalol 20mg bolus over 2 mins under continuous ECG/BP monitoring.\n"
                "2. Immediate transfer to Cardiac ICU at City General Hospital.\n"
                "3. Serial cardiac enzymes (Troponin I) and 12-lead ECG.\n"
                "4. Renal function test and serum electrolytes."
            ),
            follow_up_instructions="Strict bed rest in ICU. Immediate transfer under cardiac ambulance supervision.",
            follow_up_date=date.today() + timedelta(days=2),
            is_emergency_transfer=True,
            referral_type="ICU_ADMISSION",
            referral_hospital_id="hosp_city_general",
            referral_doctor_name="Dr. Amit Verma",
            referral_destination_name="CITY GENERAL HOSPITAL",
            referral_reason="ICU Admission",
            transfer_status="In Progress",
            confirmation_pin="584920",
            is_finalized=True
        )
        db.add(doctor_note)
        db.commit()

        # 8. PRESCRIPTION
        prescription = Prescription(
            id="rx_rahul_2026_001",
            consultation_id="consult_rahul_2026_001",
            doctor_note_id="note_rahul_2026_001",
            patient_id="pat_rahul_mishra",
            doctor_id="doc_amit_verma",
            medicines=[
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
            ],
            status="PENDING",
            dispense_alert_sent=True,
            notes="Urgent pharmacy alert triggered for stat Labetalol injection and ICU stabilization stock"
        )
        db.add(prescription)
        db.commit()

        # 9. PHARMACY STORE & INVENTORY
        pharma_store = PharmacyStore(
            id="pharma_apex_01",
            user_id="usr_pharma_apex",
            store_name="Apex Medico & Emergency Pharmacy",
            license_no="DL-PH-2024-9912",
            address="Shop 4, Ground Floor, Hospital Complex, Outer Ring Road",
            phone="+91-11-2894009"
        )
        db.add(pharma_store)
        db.commit()

        inventory_items = [
            Inventory(
                id="inv_med_01",
                pharmacy_id="pharma_apex_01",
                medicine_name="Labetalol Hydrochloride IV 20mg",
                generic_name="Labetalol HCl",
                dosage_form="Injection",
                stock_quantity=35,
                low_stock_threshold=10,
                price=245.00
            ),
            Inventory(
                id="inv_med_02",
                pharmacy_id="pharma_apex_01",
                medicine_name="Amlodipine Besylate 10mg",
                generic_name="Amlodipine",
                dosage_form="Tablet",
                stock_quantity=180,
                low_stock_threshold=25,
                price=45.00
            ),
            Inventory(
                id="inv_med_03",
                pharmacy_id="pharma_apex_01",
                medicine_name="Telmisartan 40mg",
                generic_name="Telmisartan",
                dosage_form="Tablet",
                stock_quantity=120,
                low_stock_threshold=20,
                price=88.00
            ),
            Inventory(
                id="inv_med_04",
                pharmacy_id="pharma_apex_01",
                medicine_name="Paracetamol 650mg",
                generic_name="Paracetamol",
                dosage_form="Tablet",
                stock_quantity=300,
                low_stock_threshold=50,
                price=30.00
            ),
            Inventory(
                id="inv_med_05",
                pharmacy_id="pharma_apex_01",
                medicine_name="Azithromycin 500mg",
                generic_name="Azithromycin",
                dosage_form="Tablet",
                stock_quantity=8,  # Low stock
                low_stock_threshold=15,
                price=115.00
            ),
            Inventory(
                id="inv_med_06",
                pharmacy_id="pharma_apex_01",
                medicine_name="Levocetirizine 5mg",
                generic_name="Levocetirizine",
                dosage_form="Tablet",
                stock_quantity=95,
                low_stock_threshold=20,
                price=55.00
            ),
            Inventory(
                id="inv_med_07",
                pharmacy_id="pharma_apex_01",
                medicine_name="Salbutamol Inhaler 100mcg",
                generic_name="Salbutamol",
                dosage_form="Inhaler",
                stock_quantity=4,  # Low stock
                low_stock_threshold=10,
                price=160.00
            )
        ]
        db.add_all(inventory_items)
        db.commit()

        # 10. QR TOKENS
        qr_tokens = [
            PatientQRToken(
                id="qr_tok_rahul_profile",
                patient_id="pat_rahul_mishra",
                qr_type="PROFILE_INTAKE",
                token_payload="PULSESYNC:PAT:pat_rahul_mishra:TOKEN:eyJhbGciOiJIUzI1NiJ9.eyJpZCI6InBhdF9yYWh1bF9taXNocmEifQ",
                expires_at=datetime.utcnow() + timedelta(days=30),
                is_active=True
            ),
            PatientQRToken(
                id="qr_tok_rahul_insurance",
                patient_id="pat_rahul_mishra",
                qr_type="INSURANCE_CLAIM",
                token_payload="PULSESYNC:INS:pat_rahul_mishra:SH-POL-9830219-X:CLAIM_AUTH",
                expires_at=datetime.utcnow() + timedelta(days=30),
                is_active=True
            ),
            PatientQRToken(
                id="qr_tok_rahul_icu_transfer",
                patient_id="pat_rahul_mishra",
                qr_type="TRANSFER_AUTH",
                token_payload="PULSESYNC:TRANSFER:CGH:ICU:pat_rahul_mishra:PIN:584920",
                expires_at=datetime.utcnow() + timedelta(hours=24),
                is_active=True
            )
        ]
        db.add_all(qr_tokens)
        db.commit()

        print("[SEED] Successfully seeded all 10 clinical data tables!")

    except Exception as e:
        db.rollback()
        print(f"[SEED ERROR] Error seeding database: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
