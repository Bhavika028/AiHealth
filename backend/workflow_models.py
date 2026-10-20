"""Additive longitudinal clinical schema; no existing clinical table is replaced."""
from sqlalchemy import Column, String, Text, DateTime, Date, Integer, ForeignKey, JSON, UniqueConstraint, Index, text
from .models import Base, generate_uuid
from datetime import datetime

class RecordMixin:
    id = Column(String(64), primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(64), ForeignKey('users.id'), nullable=True)
    source = Column(String(64), default='CLINICIAN')
    status = Column(String(64), default='ACTIVE')

class MedicalEvent(RecordMixin, Base):
    __tablename__ = 'medical_events'
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False, index=True)
    consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=True)
    doctor_id = Column(String(64), ForeignKey('doctors.id'), nullable=True)
    facility_id = Column(String(64), nullable=True)
    kind = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    details = Column(JSON, default=dict)
    resource_id = Column(String(64), nullable=True)
    dedupe_key = Column(String(255), unique=True, nullable=True)

class Diagnosis(RecordMixin, Base):
    __tablename__ = 'diagnoses'
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=False)
    doctor_id = Column(String(64), ForeignKey('doctors.id'), nullable=True)
    facility_id = Column(String(64), nullable=True)
    name = Column(String(255), nullable=False)

class Vital(RecordMixin, Base):
    __tablename__ = 'vitals'
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=False)
    name = Column(String(64), nullable=False)
    value = Column(String(64), nullable=False)
    unit = Column(String(32), nullable=False)
    measured_at = Column(DateTime, default=datetime.utcnow)

class Medication(RecordMixin, Base):
    __tablename__ = 'medications'
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    prescription_id = Column(String(64), ForeignKey('prescriptions.id'), nullable=True)
    consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=True)
    doctor_id = Column(String(64), ForeignKey('doctors.id'), nullable=True)
    name = Column(String(255), nullable=False)
    dosage = Column(String(128), nullable=True)
    frequency = Column(String(255), nullable=True)
    start_date = Column(Date, nullable=True)
    duration_days = Column(Integer, nullable=True)
    end_date = Column(Date, nullable=True)
    reason = Column(Text, nullable=True)
    instructions = Column(JSON, default=dict)

class Referral(RecordMixin, Base):
    __tablename__ = 'referrals'
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=False)
    doctor_id = Column(String(64), ForeignKey('doctors.id'), nullable=True)
    source_facility_id = Column(String(64), nullable=True)
    hospital_id = Column(String(64), ForeignKey('hospitals.id'), nullable=False)
    specialty = Column(String(128), nullable=False)
    reason = Column(Text, nullable=False)
    clinical_summary = Column(Text, nullable=True)
    priority = Column(String(32), default='ROUTINE')
    receiving_doctor_id = Column(String(64), ForeignKey('doctors.id'), nullable=True)
    outcome_consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=True)
    outcome_summary = Column(Text, nullable=True)

class Admission(RecordMixin, Base):
    __tablename__ = 'admissions'
    __table_args__ = (Index('uq_active_admission_patient','patient_id',unique=True,sqlite_where=text("status = 'ADMITTED'"),postgresql_where=text("status = 'ADMITTED'")),)
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    hospital_id = Column(String(64), ForeignKey('hospitals.id'), nullable=False)
    bed_id = Column(String(64), ForeignKey('wards_and_beds.id'), nullable=False)
    consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=True)
    referral_id = Column(String(64), ForeignKey('referrals.id'), nullable=True)
    doctor_id = Column(String(64), ForeignKey('doctors.id'), nullable=True)
    reason = Column(Text, nullable=False)
    discharged_at = Column(DateTime, nullable=True)
    discharge_summary = Column(Text, nullable=True)

class Allergy(RecordMixin, Base):
    __tablename__ = 'allergy_records'
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    substance = Column(String(255), nullable=False)
    reaction = Column(Text, nullable=True)
    severity = Column(String(32), nullable=True)
    last_verified_at = Column(DateTime, nullable=True)

class Document(RecordMixin, Base):
    __tablename__ = 'medical_documents'
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    title = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False)
    filename = Column(String(255), nullable=False)
    stored_name = Column(String(128), nullable=False)
    content_type = Column(String(128), nullable=False)
    consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=True)

class FollowUp(RecordMixin, Base):
    __tablename__ = 'follow_ups'
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=False)
    doctor_id = Column(String(64), ForeignKey('doctors.id'), nullable=True)
    hospital_id = Column(String(64), ForeignKey('hospitals.id'), nullable=True)
    due_at = Column(DateTime, nullable=False)
    reason = Column(Text, nullable=False)
    outcome_consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=True)

class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey('users.id'), nullable=False, index=True)
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=True)
    message = Column(Text, nullable=False)
    resource_id = Column(String(64), nullable=True)
    status = Column(String(32), default='UNREAD')
    created_at = Column(DateTime, default=datetime.utcnow)
    dedupe_key = Column(String(255), unique=True, nullable=True)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(String(64), primary_key=True, default=generate_uuid)
    user_id = Column(String(64), ForeignKey('users.id'), nullable=True)
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=True, index=True)
    action = Column(String(128), nullable=False)
    resource = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class RecordVersion(Base):
    __tablename__ = 'record_versions'
    id = Column(String(64), primary_key=True, default=generate_uuid)
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    resource = Column(String(64), nullable=False)
    resource_id = Column(String(64), nullable=False)
    editor_id = Column(String(64), ForeignKey('users.id'), nullable=False)
    before = Column(JSON, nullable=False)
    after = Column(JSON, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class AccessGrant(Base):
    __tablename__ = 'access_grants'
    id = Column(String(64), primary_key=True, default=generate_uuid)
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    user_id = Column(String(64), ForeignKey('users.id'), nullable=True)
    scope = Column(String(32), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class HistorySummary(RecordMixin, Base):
    __tablename__ = 'history_summaries'
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    content = Column(JSON, nullable=False)
    source_refs = Column(JSON, default=list)
    method = Column(String(64), nullable=False)
    review_note = Column(Text, nullable=True)

class RevokedToken(Base):
    __tablename__ = 'revoked_tokens'
    id = Column(String(128), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AccessRequest(Base):
    __tablename__ = 'access_requests'
    id = Column(String(64), primary_key=True, default=generate_uuid)
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False, index=True)
    provider_user_id = Column(String(64), ForeignKey('users.id'), nullable=False, index=True)
    scope = Column(String(32), nullable=False)
    status = Column(String(32), default='PENDING', nullable=False)
    expires_at = Column(DateTime, nullable=False)
    grant_id = Column(String(64), ForeignKey('access_grants.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConsultationPlan(Base):
    __tablename__ = 'consultation_plans'
    consultation_id = Column(String(64), ForeignKey('consultations.id'), primary_key=True)
    content = Column(JSON, default=dict, nullable=False)
    revision = Column(Integer, default=0, nullable=False)
    finalized_at = Column(DateTime, nullable=True)

class OutpatientAppointment(RecordMixin, Base):
    __tablename__ = 'outpatient_appointments'
    referral_id = Column(String(64), ForeignKey('referrals.id'), unique=True, nullable=False)
    consultation_id = Column(String(64), ForeignKey('consultations.id'), nullable=False)
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    hospital_id = Column(String(64), ForeignKey('hospitals.id'), nullable=False)
    doctor_id = Column(String(64), ForeignKey('doctors.id'), nullable=False)
    preferred_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    response = Column(Text, nullable=True)

class ConsultationAuthorization(Base):
    __tablename__ = 'consultation_authorizations'
    consultation_id = Column(String(64), ForeignKey('consultations.id'), primary_key=True)
    request_id = Column(String(64), ForeignKey('access_requests.id'), nullable=False, unique=True)
    patient_id = Column(String(64), ForeignKey('patients.id'), nullable=False)
    provider_user_id = Column(String(64), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
