"""Backend resource authorization. Identity never grants clinical consent by itself."""
import hashlib
import os
from datetime import datetime
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Patient, Doctor, Hospital, PharmacyStore, Consultation, FamilyMember
from .workflow_models import AccessGrant, AccessRequest, ConsultationAuthorization, Referral, Admission, RevokedToken
from .routers.auth import decode_access_token

DAILY_VISIT_LIMIT = int(os.getenv("MAX_VISITS_PER_DAY", "2"))

def get_patient_daily_visit_count(db: Session, patient_id: str) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.query(Consultation).filter(
        Consultation.patient_id == patient_id,
        Consultation.created_at >= today_start,
        Consultation.status.notin_(['CANCELLED', 'NO_SHOW'])
    ).count()

def check_daily_visit_limit(db: Session, patient_id: str, is_urgent: bool = False) -> int:
    """Enforce daily visit limit per patient (configurable, default 2). Urgent/emergency bypasses standard limit."""
    count = get_patient_daily_visit_count(db, patient_id)
    if count >= DAILY_VISIT_LIMIT and not is_urgent:
        raise HTTPException(
            status_code=429,
            detail=f"Daily visit limit reached. You have already booked {count} of {DAILY_VISIT_LIMIT} allowed visits today. For urgent medical emergencies, please proceed to an emergency care facility or choose emergency triage."
        )
    return count

def current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Sign in required')
    token = authorization[7:]
    data = decode_access_token(token)
    if db.get(RevokedToken, data.get('jti', hashlib.sha256(token.encode()).hexdigest())):
        raise HTTPException(401, 'Session signed out')
    user = db.get(User, data.get('sub'))
    if not user or not user.is_active:
        raise HTTPException(401, 'Inactive or missing account')
    return user

def entity(db, user, model):
    row = db.query(model).filter(model.user_id == user.id).first()
    if not row:
        raise HTTPException(403, 'No provider profile linked to this account. Use local ownership recovery for legacy accounts.')
    return row

def require_role(user, *roles):
    if user.role not in roles:
        raise HTTPException(403, 'This action is not permitted for your role')

def grant_exists(db, user, patient_id, scopes):
    return db.query(AccessGrant).filter(AccessGrant.patient_id == patient_id,
        AccessGrant.user_id == user.id, AccessGrant.scope.in_(scopes),
        AccessGrant.revoked_at.is_(None), AccessGrant.expires_at > datetime.utcnow()).first() is not None

def patient_access(db, user, patient_id, scope='CLINICAL'):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(404, 'Patient not found')
    if user.role == 'PATIENT':
        if patient.user_id == user.id:
            return patient
        fam = db.query(FamilyMember).filter(FamilyMember.primary_user_id == user.id, FamilyMember.patient_id == patient.id).first()
        if fam:
            return patient
    if scope == 'PRESCRIPTION' and user.role == 'PHARMACY':
        if grant_exists(db, user, patient_id, ['PRESCRIPTION']):
            return patient
    if user.role == 'DOCTOR':
        doc = entity(db, user, Doctor)
        if grant_exists(db, user, patient_id, ['CLINICAL']):
            return patient
        # Doctors who completed a consultation with this patient retain read access to patient clinical record
        if db.query(Consultation).filter(Consultation.patient_id == patient_id, Consultation.doctor_id == doc.id, Consultation.status == 'COMPLETED').first():
            return patient
    if user.role == 'HOSPITAL_ADMIN':
        hosp = entity(db, user, Hospital)
        authorized = db.query(Referral).filter(Referral.patient_id == patient_id,
            Referral.hospital_id == hosp.id, Referral.status.in_(['SENT','RECEIVED','ACCEPTED','PATIENT_ARRIVED','SPECIALIST_CONSULTATION','COMPLETED'])).first()
        if authorized or grant_exists(db, user, patient_id, ['CLINICAL']) or db.query(Admission).filter(
            Admission.patient_id == patient_id, Admission.hospital_id == hosp.id).first():
            return patient
    raise HTTPException(403, 'No authorized care relationship or current patient consent')

def approved_request(db, user, patient_id, request_id=None):
    q = db.query(AccessRequest).join(AccessGrant, AccessRequest.grant_id == AccessGrant.id).filter(
        AccessRequest.patient_id == patient_id, AccessRequest.provider_user_id == user.id,
        AccessRequest.scope == 'CLINICAL', AccessRequest.status == 'APPROVED',
        AccessRequest.expires_at > datetime.utcnow(), AccessGrant.patient_id == patient_id,
        AccessGrant.user_id == user.id, AccessGrant.scope == 'CLINICAL',
        AccessGrant.revoked_at.is_(None), AccessGrant.expires_at > datetime.utcnow())
    if request_id: q=q.filter(AccessRequest.id == request_id)
    r=q.first()
    if not r: raise HTTPException(403,'Patient PIN approval is required for this doctor and consultation')
    return r

def encounter_access(db, user, consult_id, write=False):
    c = db.get(Consultation, consult_id)
    if not c:
        raise HTTPException(404, 'Consultation not found')
    
    # Completed consultations can always be viewed (read-only) by the assigned clinician, patient, or hospital
    if c.status == 'COMPLETED' and not write:
        if user.role == 'PATIENT':
            patient = db.get(Patient, c.patient_id)
            if patient:
                if patient.user_id == user.id:
                    return c
                fam = db.query(FamilyMember).filter(FamilyMember.primary_user_id == user.id, FamilyMember.patient_id == patient.id).first()
                if fam:
                    return c

        elif user.role == 'DOCTOR':
            doc = entity(db, user, Doctor)
            if c.doctor_id == doc.id:
                return c
        elif user.role == 'HOSPITAL_ADMIN':
            hosp = entity(db, user, Hospital)
            if c.hospital_id == hosp.id:
                return c

    patient_access(db, user, c.patient_id)
    if user.role == 'DOCTOR':
        link=db.get(ConsultationAuthorization, c.id)
        if link:
            if link.patient_id != c.patient_id or link.provider_user_id != user.id:
                raise HTTPException(403,'Consultation authorization mismatch')
            if c.status != 'COMPLETED':
                approved_request(db,user,c.patient_id,link.request_id)
        else:
            pass
    if write:
        require_role(user, 'DOCTOR', 'HOSPITAL_ADMIN')
        if user.role == 'DOCTOR' and c.doctor_id != entity(db, user, Doctor).id:
            raise HTTPException(403, 'Only the assigned clinician can edit this consultation')
        if user.role == 'HOSPITAL_ADMIN' and c.hospital_id != entity(db, user, Hospital).id:
            raise HTTPException(403, 'Consultation belongs to another facility')
    return c
