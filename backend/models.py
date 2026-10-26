"""
PulseSync AI - SQLAlchemy 2.0 Models & Pydantic Schemas
Relational Models for Healthcare Workflow, Intake Questionnaire, and ICU Management
"""

import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, Date, 
    ForeignKey, UniqueConstraint, JSON
)
from sqlalchemy.orm import declarative_base, relationship
from pydantic import BaseModel, Field

Base = declarative_base()

def generate_uuid() -> str:
    return str(uuid.uuid4())

# ==============================================================================
# 1. USER MODEL
# ==============================================================================
class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(32), nullable=True)
    password_hash = Column(String(255), nullable=True)
    pin_hash = Column(String(255), nullable=True)
    pin_failures = Column(Integer, default=0)
    pin_locked_until = Column(DateTime, nullable=True)
    role = Column(String(32), nullable=False, default="PATIENT")  # PATIENT, DOCTOR, HOSPITAL_ADMIN, PHARMACY
    language_preference = Column(String(16), default="en")  # en, hi
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient_profile = relationship("Patient", back_populates="user", uselist=False, cascade="all, delete-orphan")
    doctor_profile = relationship("Doctor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    pharmacy_store = relationship("PharmacyStore", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "phone": self.phone,
            "role": self.role,
            "language_preference": self.language_preference,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# ==============================================================================
# 2. PATIENT PROFILE MODEL
# ==============================================================================
class Patient(Base):
    __tablename__ = "patients"

    last_verified_at = Column(DateTime, nullable=True)

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    age = Column(Integer, nullable=False)
    dob = Column(Date, nullable=True)
    gender = Column(String(32), nullable=False)
    blood_group = Column(String(8), nullable=True)
    existing_conditions = Column(JSON, default=list)  # ["Diabetes", "Hypertension"]
    allergies = Column(JSON, default=list)  # ["Penicillin"]
    current_medications = Column(JSON, default=list)  # [{"name": "Amlodipine 5mg", "frequency": "Daily"}]
    medical_history = Column(JSON, default=list)
    is_child = Column(Boolean, default=False)
    parent_guardian_name = Column(String(255), nullable=True)
    parent_guardian_phone = Column(String(32), nullable=True)
    emergency_contact_name = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(32), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(128), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    aadhaar_card_no = Column(String(32), nullable=True)
    pan_card_no = Column(String(32), nullable=True)
    has_insurance = Column(Boolean, default=True)
    insurance_claimed = Column(Boolean, default=False)
    insurance_provider = Column(String(255), nullable=True)
    insurance_policy_no = Column(String(128), nullable=True)
    insurance_is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="patient_profile")
    consultations = relationship("Consultation", back_populates="patient", cascade="all, delete-orphan")
    doctor_notes = relationship("DoctorNote", back_populates="patient", cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="patient", cascade="all, delete-orphan")
    qr_tokens = relationship("PatientQRToken", back_populates="patient", cascade="all, delete-orphan")
    occupied_bed = relationship("WardAndBed", back_populates="current_patient", uselist=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "full_name": self.full_name,
            "age": self.age,
            "dob": self.dob.isoformat() if self.dob else None,
            "gender": self.gender,
            "blood_group": self.blood_group,
            "existing_conditions": self.existing_conditions or [],
            "allergies": self.allergies or [],
            "current_medications": self.current_medications or [],
            "medical_history": self.medical_history or [],
            "is_child": self.is_child,
            "parent_guardian_name": self.parent_guardian_name,
            "parent_guardian_phone": self.parent_guardian_phone,
            "emergency_contact_name": self.emergency_contact_name,
            "emergency_contact_phone": self.emergency_contact_phone,
            "address": self.address,
            "city": self.city,
            "aadhaar_card_no": self.aadhaar_card_no,
            "pan_card_no": self.pan_card_no,
            "has_insurance": self.has_insurance,
            "insurance_claimed": self.insurance_claimed,
            "insurance_provider": self.insurance_provider,
            "insurance_policy_no": self.insurance_policy_no,
            "insurance_is_active": self.insurance_is_active
        }


# ==============================================================================
# 3. CLINIC & HOSPITAL MODELS
# ==============================================================================
class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    registration_no = Column(String(128), unique=True, nullable=True)
    address = Column(Text, nullable=False)
    city = Column(String(128), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    phone = Column(String(32), nullable=True)
    email = Column(String(255), nullable=True)
    qr_clinic_code = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    doctors = relationship("Doctor", back_populates="clinic")
    consultations = relationship("Consultation", back_populates="clinic")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "registration_no": self.registration_no,
            "address": self.address,
            "city": self.city,
            "phone": self.phone,
            "email": self.email,
            "qr_clinic_code": self.qr_clinic_code
        }


class Hospital(Base):
    __tablename__ = "hospitals"

    user_id = Column(String(64), ForeignKey("users.id"), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)

    id = Column(String(64), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    registration_no = Column(String(128), unique=True, nullable=True)
    address = Column(Text, nullable=False)
    city = Column(String(128), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    emergency_phone = Column(String(32), nullable=True)
    treatments = Column(JSON, default=list)  # e.g. ["Cardiology", "Neurology", "Emergency & Trauma", "Pediatrics"]
    total_doctors = Column(Integer, default=12)
    total_wards = Column(Integer, default=4)
    total_icu_beds = Column(Integer, default=0)
    total_general_beds = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    doctors = relationship("Doctor", back_populates="hospital")
    wards_and_beds = relationship("WardAndBed", back_populates="hospital", cascade="all, delete-orphan")
    referrals_received = relationship("DoctorNote", back_populates="referral_hospital")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "registration_no": self.registration_no,
            "address": self.address,
            "city": self.city,
            "emergency_phone": self.emergency_phone,
            "treatments": self.treatments or [],
            "total_doctors": self.total_doctors,
            "total_wards": self.total_wards,
            "total_icu_beds": self.total_icu_beds,
            "total_general_beds": self.total_general_beds
        }


# ==============================================================================
# 4. DOCTOR MODEL
# ==============================================================================
class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    clinic_id = Column(String(64), ForeignKey("clinics.id", ondelete="SET NULL"), nullable=True)
    hospital_id = Column(String(64), ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True)
    full_name = Column(String(255), nullable=False)
    specialization = Column(String(128), nullable=False)
    education = Column(String(255), nullable=True)  # e.g. "MBBS, MD (Medicine), DM (Cardiology)"
    license_no = Column(String(128), unique=True, nullable=True)
    clinic_name = Column(String(255), nullable=True)
    clinic_address = Column(Text, nullable=True)
    patients_checked_count = Column(Integer, default=0)
    degree_proof_url = Column(Text, nullable=True)
    available_hours = Column(JSON, default=dict)
    is_verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="doctor_profile")
    clinic = relationship("Clinic", back_populates="doctors")
    hospital = relationship("Hospital", back_populates="doctors")
    consultations = relationship("Consultation", back_populates="doctor")
    doctor_notes = relationship("DoctorNote", back_populates="doctor")
    prescriptions = relationship("Prescription", back_populates="doctor")
    assigned_beds = relationship("WardAndBed", back_populates="assigned_doctor")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "clinic_id": self.clinic_id,
            "hospital_id": self.hospital_id,
            "full_name": self.full_name,
            "specialization": self.specialization,
            "education": self.education or "Not recorded",
            "license_no": self.license_no,
            "clinic_name": self.clinic_name or (self.clinic.name if self.clinic else "Not recorded"),
            "clinic_address": self.clinic_address or (self.clinic.address if self.clinic else "Not recorded"),
            "patients_checked_count": self.patients_checked_count,
            "available_hours": self.available_hours or {},
            "is_verified": self.is_verified
        }


# ==============================================================================
# 5. WARDS & BEDS MODEL (ICU Tracker)
# ==============================================================================
class WardAndBed(Base):
    __tablename__ = "wards_and_beds"

    state = Column(String(32), default="AVAILABLE")

    id = Column(String(64), primary_key=True, default=generate_uuid)
    hospital_id = Column(String(64), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False)
    ward_name = Column(String(128), nullable=False)  # e.g. "Cardiac ICU", "General Ward A"
    ward_type = Column(String(64), nullable=False)  # "ICU", "GENERAL", "EMERGENCY", "PEDIATRIC"
    bed_number = Column(String(32), nullable=False)  # e.g. "ICU-04", "BED-12"
    is_occupied = Column(Boolean, default=False)
    current_patient_id = Column(String(64), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True)
    assigned_doctor_id = Column(String(64), ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True)
    admission_reason = Column(Text, nullable=True)
    admission_date = Column(DateTime, nullable=True)
    estimated_discharge_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("hospital_id", "ward_name", "bed_number", name="uq_hospital_ward_bed"),
    )

    # Relationships
    hospital = relationship("Hospital", back_populates="wards_and_beds")
    current_patient = relationship("Patient", back_populates="occupied_bed")
    assigned_doctor = relationship("Doctor", back_populates="assigned_beds")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "hospital_id": self.hospital_id,
            "ward_name": self.ward_name,
            "ward_type": self.ward_type,
            "bed_number": self.bed_number,
            "is_occupied": self.is_occupied,
            "current_patient_id": self.current_patient_id,
            "assigned_doctor_id": self.assigned_doctor_id,
            "admission_reason": self.admission_reason,
            "admission_date": self.admission_date.isoformat() if self.admission_date else None,
            "estimated_discharge_date": self.estimated_discharge_date.isoformat() if self.estimated_discharge_date else None
        }


# ==============================================================================
# 6. CONSULTATIONS (Intake Questionnaire Flow)
# ==============================================================================
class Consultation(Base):
    __tablename__ = "consultations"

    hospital_id = Column(String(64), ForeignKey("hospitals.id"), nullable=True)
    referral_id = Column(String(64), ForeignKey("referrals.id", use_alter=True, name="fk_consultation_referral"), nullable=True)
    created_by = Column(String(64), ForeignKey("users.id"), nullable=True)

    id = Column(String(64), primary_key=True, default=generate_uuid)
    patient_id = Column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    clinic_id = Column(String(64), ForeignKey("clinics.id", ondelete="SET NULL"), nullable=True)
    doctor_id = Column(String(64), ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True, index=True)
    visit_type = Column(String(32), default="FIRST_VISIT")  # FIRST_VISIT, REPEAT_VISIT
    
    # Core Questions Q1-Q10
    chief_complaint = Column(String(128), nullable=False)  # Q1
    symptom_duration_value = Column(Integer, nullable=True)  # Q2
    symptom_duration_unit = Column(String(32), nullable=True)  # Q2 (Hours, Days, Weeks, Months)
    symptom_severity = Column(String(32), nullable=False)  # Q3 (Mild, Moderate, Severe)
    is_repeat_visit = Column(Boolean, default=False)  # Q4
    previous_consultation_id = Column(String(64), ForeignKey("consultations.id", ondelete="SET NULL"), nullable=True)
    medicine_taken = Column(Boolean, default=False)  # Q5
    medicine_taken_name = Column(String(255), nullable=True)
    regular_medications_confirmed = Column(Boolean, default=True)  # Q6
    existing_conditions_confirmed = Column(Boolean, default=True)  # Q7
    allergies_confirmed = Column(Boolean, default=True)  # Q8
    warning_symptoms = Column(JSON, default=list)  # Q9 (e.g. ["chest_pain", "severe_weakness"])
    patient_notes = Column(Text, nullable=True)  # Q10

    # Branch Specific Responses (Section B)
    branch_responses = Column(JSON, default=dict)
    seasonal_context = Column(String(64), nullable=True)  # monsoon, winter, summer
    status = Column(String(64), default="TRIAGED", index=True)  # TRIAGED, IN_DOCTOR_QUEUE, UNDER_REVIEW, COMPLETED, REFERRED_ICU
    is_urgent = Column(Boolean, default=False, index=True)
    urgency_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="consultations")
    clinic = relationship("Clinic", back_populates="consultations")
    doctor = relationship("Doctor", back_populates="consultations")
    doctor_note = relationship("DoctorNote", back_populates="consultation", uselist=False, cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="consultation")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "clinic_id": self.clinic_id,
            "doctor_id": self.doctor_id,
            "visit_type": self.visit_type,
            "chief_complaint": self.chief_complaint,
            "symptom_duration_value": self.symptom_duration_value,
            "symptom_duration_unit": self.symptom_duration_unit,
            "symptom_severity": self.symptom_severity,
            "is_repeat_visit": self.is_repeat_visit,
            "previous_consultation_id": self.previous_consultation_id,
            "medicine_taken": self.medicine_taken,
            "medicine_taken_name": self.medicine_taken_name,
            "regular_medications_confirmed": self.regular_medications_confirmed,
            "existing_conditions_confirmed": self.existing_conditions_confirmed,
            "allergies_confirmed": self.allergies_confirmed,
            "warning_symptoms": self.warning_symptoms or [],
            "patient_notes": self.patient_notes,
            "branch_responses": self.branch_responses or {},
            "seasonal_context": self.seasonal_context,
            "status": self.status,
            "is_urgent": self.is_urgent,
            "urgency_reason": self.urgency_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# ==============================================================================
# 7. DOCTOR NOTES & CLINICAL ASSESSMENTS
# ==============================================================================
class DoctorNote(Base):
    __tablename__ = "doctor_notes"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    consultation_id = Column(String(64), ForeignKey("consultations.id", ondelete="CASCADE"), unique=True, nullable=False)
    doctor_id = Column(String(64), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)

    # Vitals
    vital_bp = Column(String(32), nullable=True)  # e.g. "210/130 mmHg"
    vital_pulse = Column(Integer, nullable=True)  # e.g. 108
    vital_temperature = Column(String(32), nullable=True)  # e.g. "98.6 F"
    vital_spo2 = Column(Integer, nullable=True)  # e.g. 97
    vital_glucose = Column(String(32), nullable=True)  # e.g. "142 mg/dL"

    # AI Preliminary Draft
    ai_generated_summary = Column(Text, nullable=True)
    ai_risk_flags = Column(JSON, default=list)

    # Doctor Assessment
    clinical_observations = Column(Text, nullable=True)
    confirmed_diagnosis = Column(String(255), nullable=False)
    treatment_plan = Column(Text, nullable=True)
    follow_up_instructions = Column(Text, nullable=True)
    follow_up_date = Column(Date, nullable=True)

    # Referral & Emergency ICU Transfer (Matching Frontend Mockup)
    is_emergency_transfer = Column(Boolean, default=False)
    referral_type = Column(String(64), default="NONE")  # NONE, ICU_ADMISSION, SPECIALIST_REFERRAL
    referral_hospital_id = Column(String(64), ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True)
    referral_doctor_name = Column(String(255), nullable=True)
    referral_destination_name = Column(String(255), nullable=True)  # e.g. "CITY GENERAL HOSPITAL"
    referral_reason = Column(Text, nullable=True)  # e.g. "ICU Admission"
    transfer_status = Column(String(64), default="NONE")  # NONE, In Progress, Hospital Notified, Admitted
    confirmation_pin = Column(String(16), nullable=True)  # e.g. "584920"

    is_finalized = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    consultation = relationship("Consultation", back_populates="doctor_note")
    doctor = relationship("Doctor", back_populates="doctor_notes")
    patient = relationship("Patient", back_populates="doctor_notes")
    referral_hospital = relationship("Hospital", back_populates="referrals_received")
    prescriptions = relationship("Prescription", back_populates="doctor_note")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "consultation_id": self.consultation_id,
            "doctor_id": self.doctor_id,
            "patient_id": self.patient_id,
            "vital_bp": self.vital_bp,
            "vital_pulse": self.vital_pulse,
            "vital_temperature": self.vital_temperature,
            "vital_spo2": self.vital_spo2,
            "vital_glucose": self.vital_glucose,
            "ai_generated_summary": self.ai_generated_summary,
            "ai_risk_flags": self.ai_risk_flags or [],
            "clinical_observations": self.clinical_observations,
            "confirmed_diagnosis": self.confirmed_diagnosis,
            "treatment_plan": self.treatment_plan,
            "follow_up_instructions": self.follow_up_instructions,
            "follow_up_date": self.follow_up_date.isoformat() if self.follow_up_date else None,
            "is_emergency_transfer": self.is_emergency_transfer,
            "referral_type": self.referral_type,
            "referral_hospital_id": self.referral_hospital_id,
            "referral_doctor_name": self.referral_doctor_name,
            "referral_destination_name": self.referral_destination_name,
            "referral_reason": self.referral_reason,
            "transfer_status": self.transfer_status,
            "confirmation_pin": self.confirmation_pin,
            "is_finalized": self.is_finalized
        }


# ==============================================================================
# 8. PRESCRIPTIONS & PHARMACY DISPENSING
# ==============================================================================
class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    consultation_id = Column(String(64), ForeignKey("consultations.id", ondelete="SET NULL"), nullable=True)
    doctor_note_id = Column(String(64), ForeignKey("doctor_notes.id", ondelete="SET NULL"), nullable=True)
    patient_id = Column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(String(64), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)
    pharmacy_id = Column(String(64), ForeignKey("pharmacy_stores.id", ondelete="SET NULL"), nullable=True)
    medicines = Column(JSON, default=list)
    status = Column(String(32), default="PENDING", index=True)  # PENDING, DISPENSED, OUT_OF_STOCK
    dispense_alert_sent = Column(Boolean, default=False)
    dispensed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    consultation = relationship("Consultation", back_populates="prescriptions")
    doctor_note = relationship("DoctorNote", back_populates="prescriptions")
    patient = relationship("Patient", back_populates="prescriptions")
    doctor = relationship("Doctor", back_populates="prescriptions")
    pharmacy = relationship("PharmacyStore", back_populates="prescriptions")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "consultation_id": self.consultation_id,
            "doctor_note_id": self.doctor_note_id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "pharmacy_id": self.pharmacy_id,
            "medicines": self.medicines or [],
            "status": self.status,
            "dispense_alert_sent": self.dispense_alert_sent,
            "dispensed_at": self.dispensed_at.isoformat() if self.dispensed_at else None,
            "notes": self.notes
        }


# ==============================================================================
# 9. PHARMACY STORES & INVENTORY
# ==============================================================================
class PharmacyStore(Base):
    __tablename__ = "pharmacy_stores"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    store_name = Column(String(255), nullable=False)
    pharmacist_name = Column(String(255), nullable=True)
    license_no = Column(String(128), unique=True, nullable=True)
    address = Column(Text, nullable=False)
    city = Column(String(128), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_online = Column(Boolean, default=False)
    last_active_at = Column(DateTime, nullable=True)
    phone = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="pharmacy_store")
    inventory = relationship("Inventory", back_populates="pharmacy", cascade="all, delete-orphan")
    prescriptions = relationship("Prescription", back_populates="pharmacy")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "store_name": self.store_name,
            "pharmacist_name": self.pharmacist_name or "Registered Pharmacist",
            "license_no": self.license_no,
            "address": self.address,
            "city": self.city or "New Delhi",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "is_online": self.is_online,
            "phone": self.phone
        }


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    pharmacy_id = Column(String(64), ForeignKey("pharmacy_stores.id", ondelete="CASCADE"), nullable=False, index=True)
    medicine_name = Column(String(255), nullable=False)
    generic_name = Column(String(255), nullable=True)
    dosage_form = Column(String(64), nullable=False)  # Tablet, Syrup, Injection, Capsule, Inhaler
    stock_quantity = Column(Integer, default=0)
    low_stock_threshold = Column(Integer, default=10)
    price = Column(Float, default=0.0)
    last_restocked_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("pharmacy_id", "medicine_name", name="uq_pharmacy_medicine"),
    )

    # Relationships
    pharmacy = relationship("PharmacyStore", back_populates="inventory")

    @property
    def is_low_stock(self) -> bool:
        return self.stock_quantity <= self.low_stock_threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "pharmacy_id": self.pharmacy_id,
            "medicine_name": self.medicine_name,
            "generic_name": self.generic_name,
            "dosage_form": self.dosage_form,
            "stock_quantity": self.stock_quantity,
            "low_stock_threshold": self.low_stock_threshold,
            "price": self.price,
            "is_low_stock": self.is_low_stock,
            "last_restocked_at": self.last_restocked_at.isoformat() if self.last_restocked_at else None
        }


# ==============================================================================
# 10. PATIENT QR TOKENS
# ==============================================================================
class PatientQRToken(Base):
    __tablename__ = "patient_qr_tokens"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    patient_id = Column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    qr_type = Column(String(64), nullable=False)  # PROFILE_INTAKE, INSURANCE_CLAIM, TRANSFER_AUTH
    token_payload = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    patient = relationship("Patient", back_populates="qr_tokens")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "qr_type": self.qr_type,
            "token_payload": self.token_payload,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active
        }


# ==============================================================================
# 11. FAMILY MEMBERS & DEPENDENTS (Children, Elderly Parents)
# ==============================================================================
class FamilyMember(Base):
    __tablename__ = "family_members"

    id = Column(String(64), primary_key=True, default=generate_uuid)
    primary_user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(String(64), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(32), nullable=False)  # "CHILD", "ELDERLY_PARENT", "SPOUSE", "OTHER"
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    primary_user = relationship("User", foreign_keys=[primary_user_id])
    patient = relationship("Patient", foreign_keys=[patient_id])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "primary_user_id": self.primary_user_id,
            "patient_id": self.patient_id,
            "relationship_type": self.relationship_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "patient": self.patient.to_dict() if self.patient else None
        }

