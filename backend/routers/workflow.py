"""Connected clinical workflows and patient portal endpoints."""
import os, json, secrets, hashlib
from pathlib import Path
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy import or_, update, inspect
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, Literal
from ..database import get_db
from ..models import Patient, Doctor, Hospital, PharmacyStore, Consultation, Prescription, DoctorNote, WardAndBed, Inventory, User
from ..workflow_models import *
from ..security import approved_request, current_user, patient_access, encounter_access, entity, require_role

router = APIRouter(prefix='/api/workflow', tags=['Longitudinal workflow'])
UPLOAD_ROOT = Path(os.getenv('UPLOAD_DIR', str(Path(__file__).resolve().parents[2] / 'uploads'))).resolve()

def serial(row):
    result = {}
    for c in inspect(row).mapper.column_attrs:
        value = getattr(row, c.key)
        result[c.key] = value.isoformat() if isinstance(value, (datetime, date)) else value
    return result

def audit(db, user, patient_id, action, resource):
    db.add(AuditLog(user_id=user.id if user else None, patient_id=patient_id, action=action, resource=resource))

def event(db, user, patient_id, kind, title, resource_id=None, consult=None, details=None, status='ACTIVE', source=None, dedupe=None):
    row = MedicalEvent(patient_id=patient_id, kind=kind, title=title, resource_id=resource_id,
        consultation_id=consult.id if consult else None, doctor_id=consult.doctor_id if consult else None,
        facility_id=(consult.hospital_id or consult.clinic_id) if consult else None,
        created_by=user.id if user else None, source=source or ('PATIENT_REPORTED' if user and user.role == 'PATIENT' else 'CLINICIAN'),
        status=status, details=details or {}, dedupe_key=dedupe)
    db.add(row)
    audit(db, user, patient_id, kind, resource_id)
    return row

def notify(db, patient_id, message, resource=None, user_id=None, dedupe=None):
    if not user_id:
        p = db.get(Patient, patient_id)
        user_id = p.user_id if p else None
    if user_id:
        if dedupe and db.query(Notification).filter_by(dedupe_key=dedupe).first():
            return
        db.add(Notification(user_id=user_id, patient_id=patient_id, message=message, resource_id=resource, dedupe_key=dedupe))

def version(db, user, row, before, reason):
    db.flush()
    db.add(RecordVersion(patient_id=getattr(row,"patient_id",row.id), resource=row.__tablename__, resource_id=row.id,
        editor_id=user.id, before=before, after=serial(row), reason=reason))
    audit(db, user, getattr(row,"patient_id",row.id), 'CORRECTION', row.id)

def expire_courses(db, patient_id):
    for m in db.query(Medication).filter(Medication.patient_id == patient_id, Medication.status == 'ACTIVE', Medication.end_date < date.today()).all():
        m.status = 'COMPLETED'
        event(db, None, patient_id, 'MEDICATION_COMPLETED', f'Course completed: {m.name}', m.id, source='SYSTEM')
        notify(db, patient_id, f'Medication course completed: {m.name}', m.id, dedupe='course:'+m.id)
    for f in db.query(FollowUp).filter(FollowUp.patient_id == patient_id, FollowUp.status == 'SCHEDULED', FollowUp.due_at <= datetime.utcnow()+timedelta(days=2)).all():
        notify(db, patient_id, f'Follow-up due {f.due_at.strftime("%d %b %H:%M")}: {f.reason}', f.id, dedupe='follow:'+f.id)

def migrate_patient_records(db, p):
    """Idempotent projection of existing records; only finalized notes become diagnoses."""
    if p.current_medications and not db.query(MedicalEvent).filter_by(dedupe_key='baseline-meds:'+p.id).first():
        for raw in p.current_medications:
            med=raw if isinstance(raw,dict) else {'name':str(raw)}
            db.add(Medication(patient_id=p.id,name=med.get('name','Unspecified'),dosage=med.get('dosage'),frequency=med.get('frequency') or (str(med['times_per_day'])+' times per day' if med.get('times_per_day') else None),instructions=med,
                status='ACTIVE',source='PATIENT_REPORTED',created_by=p.user_id,start_date=None))
        event(db,None,p.id,'BASELINE_MEDICATIONS','Patient-reported medication list',p.id,details={'medications':p.current_medications,'start_dates':'Not recorded'},source='PATIENT_REPORTED',dedupe='baseline-meds:'+p.id)
    if p.medical_history and not db.query(MedicalEvent).filter_by(dedupe_key='baseline-history:'+p.id).first():
        event(db,None,p.id,'HISTORICAL_INFORMATION','Previously reported history',p.id,details={'reported_history':p.medical_history,'care_dates':'See original reported information; event timestamp is import time'},source='PATIENT_REPORTED',dedupe='baseline-history:'+p.id)
    for rx in db.query(Prescription).filter_by(patient_id=p.id).all():
        key = 'legacy-rx:'+rx.id
        if not db.query(MedicalEvent).filter_by(resource_id=rx.id,kind='PRESCRIPTION').first():
            c = db.get(Consultation, rx.consultation_id) if rx.consultation_id else None
            event(db, None, p.id, 'PRESCRIPTION', 'Prescription', rx.id, c, {'medicines':rx.medicines}, source='LEGACY_RECORD', dedupe=key)
            if not db.query(Medication).filter_by(prescription_id=rx.id).first():
                for m in rx.medicines or []:
                    start = rx.created_at.date()
                    duration = m.get('duration_days')
                    end = start + timedelta(days=int(duration)-1) if duration else None
                    db.add(Medication(patient_id=p.id, prescription_id=rx.id, consultation_id=rx.consultation_id,
                        doctor_id=rx.doctor_id, name=m.get('name','Unspecified'), dosage=m.get('dosage'), frequency=m.get('frequency'),instructions=m,
                        start_date=start, duration_days=duration, end_date=end, status='COMPLETED' if end and end < date.today() else 'ACTIVE', source='LEGACY_RECORD'))
    for n in db.query(DoctorNote).filter_by(patient_id=p.id, is_finalized=True).all():
        key = 'legacy-note:'+n.id
        if not db.query(MedicalEvent).filter_by(dedupe_key=key).first():
            c = db.get(Consultation, n.consultation_id)
            event(db, None, p.id, 'CONSULTATION', n.confirmed_diagnosis, n.id, c, {'observations':n.clinical_observations}, source='LEGACY_RECORD', dedupe=key)
    # Backfill instructions for rows projected by earlier releases without rewriting history.
    for existing in db.query(Medication).filter_by(patient_id=p.id).all():
        if existing.instructions: continue
        if existing.prescription_id:
            original=db.get(Prescription,existing.prescription_id)
            match=next((x for x in (original.medicines if original else []) if x.get('name')==existing.name),None)
        elif existing.source=='PATIENT_REPORTED':
            match=next((x for x in (p.current_medications or []) if isinstance(x,dict) and x.get('name')==existing.name),None)
        else: match=None
        if match: existing.instructions=dict(match)
    db.flush()

@router.get('/patients')
def patients(db: Session=Depends(get_db), user=Depends(current_user)):
    require_role(user, 'DOCTOR', 'HOSPITAL_ADMIN')
    if user.role == 'DOCTOR':
        doc = entity(db, user, Doctor)
        ids = [c.patient_id for c in db.query(Consultation).filter_by(doctor_id=doc.id)]
    else:
        h = entity(db, user, Hospital)
        ids = [r.patient_id for r in db.query(Referral).filter_by(hospital_id=h.id)] + [c.patient_id for c in db.query(Consultation).filter_by(hospital_id=h.id)]
    ids += [g.patient_id for g in db.query(AccessGrant).filter(AccessGrant.user_id==user.id, AccessGrant.scope=='CLINICAL', AccessGrant.revoked_at.is_(None), AccessGrant.expires_at>datetime.utcnow())]
    return [dict(id=p.id, full_name=p.full_name, age=p.age, blood_group=p.blood_group) for p in db.query(Patient).filter(Patient.id.in_(ids)).all()]

@router.get('/history/{patient_id}')
def history(patient_id: str, db: Session=Depends(get_db), user=Depends(current_user)):
    p = patient_access(db, user, patient_id)
    migrate_patient_records(db,p)
    expire_courses(db,patient_id)
    rows = db.query(MedicalEvent).filter(MedicalEvent.patient_id==patient_id, MedicalEvent.status!='DRAFT').order_by(MedicalEvent.created_at.desc()).all()
    result=[]
    for row in rows:
        x=serial(row)
        actor=db.get(User,row.created_by) if row.created_by else None
        doc=db.get(Doctor,row.doctor_id) if row.doctor_id else None
        h=db.get(Hospital,row.facility_id) if row.facility_id else None
        from ..models import Clinic
        clinic=db.get(Clinic,row.facility_id) if row.facility_id and not h else None
        x.update(provider=actor.name if actor else row.source,doctor=doc.full_name if doc else None,facility=h.name if h else clinic.name if clinic else None)
        result.append(x)
    audit(db,user,patient_id,'VIEW_HISTORY',patient_id); db.commit()
    return {'patient':p.to_dict(), 'events':result, 'last_verified_at':p.last_verified_at.isoformat() if p.last_verified_at else None}

class EncounterCreate(BaseModel):
    doctor_id: Optional[str]=None
    patient_id: Optional[str]=None
    chief_complaint: str=Field(min_length=1,max_length=128)
    severity: str='Moderate'
    patient_notes: Optional[str]=None
    previous_consultation_id: Optional[str]=None
    referral_id: Optional[str]=None
    follow_up_id: Optional[str]=None
    access_request_id: Optional[str]=None

@router.post('/consultations')
def create_encounter(body: EncounterCreate,db: Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'PATIENT','DOCTOR','HOSPITAL_ADMIN')
    pid=entity(db,user,Patient).id if user.role=='PATIENT' else body.patient_id
    p=patient_access(db,user,pid)
    authorization=approved_request(db,user,pid,body.access_request_id) if user.role=='DOCTOR' else None
    if user.role=='DOCTOR' and not body.access_request_id:
        raise HTTPException(403,'Select an approved consultation access request')
    if authorization:
        from ..workflow_models import ConsultationAuthorization
        if db.query(ConsultationAuthorization).filter_by(request_id=authorization.id).first():
            raise HTTPException(409,'Consent request is already bound to a consultation; request fresh approval')
    doc=entity(db,user,Doctor) if user.role=='DOCTOR' else db.get(Doctor,body.doctor_id) if body.doctor_id else None
    hid=entity(db,user,Hospital).id if user.role=='HOSPITAL_ADMIN' else None
    if not doc and not hid: raise HTTPException(400,'Select a registered doctor')
    if user.role=='HOSPITAL_ADMIN' and doc and doc.hospital_id != hid: raise HTTPException(403,'Select a doctor assigned to your hospital')
    if body.previous_consultation_id:
        previous=encounter_access(db,user,body.previous_consultation_id)
        if previous.patient_id!=pid: raise HTTPException(400,'Follow-up patient mismatch')
    ref=None
    if body.referral_id:
        ref=db.get(Referral,body.referral_id)
        if not ref or ref.patient_id!=pid or ref.hospital_id!=hid or ref.status not in ('PATIENT_ARRIVED','SPECIALIST_CONSULTATION'):
            raise HTTPException(400,'Referral must be arrived at your hospital')
        if ref.outcome_consultation_id: raise HTTPException(409,'Referral already has an encounter')
    follow=None
    if body.follow_up_id:
        follow=db.get(FollowUp,body.follow_up_id)
        if not follow or follow.patient_id!=pid or follow.status!='SCHEDULED': raise HTTPException(400,'Invalid scheduled follow-up')
        if body.doctor_id != follow.doctor_id and user.role=='PATIENT': raise HTTPException(400,'Follow-up must use its scheduled clinician')
        body.previous_consultation_id=follow.consultation_id
    c=Consultation(patient_id=pid,doctor_id=doc.id if doc else None,clinic_id=doc.clinic_id if doc else None,
        hospital_id=hid,referral_id=body.referral_id,created_by=user.id,chief_complaint=body.chief_complaint,
        symptom_severity=body.severity,patient_notes=body.patient_notes,status='WAITING',
        previous_consultation_id=body.previous_consultation_id,is_repeat_visit=bool(body.previous_consultation_id))
    db.add(c);db.flush()
    if authorization:
        from ..workflow_models import ConsultationAuthorization
        db.add(ConsultationAuthorization(consultation_id=c.id,request_id=authorization.id,patient_id=pid,provider_user_id=user.id))
    if ref:
        before=serial(ref)
        ref.outcome_consultation_id=c.id;ref.status='SPECIALIST_CONSULTATION';ref.receiving_doctor_id=doc.id if doc else None
        version(db,user,ref,before,'Specialist encounter opened')
        event(db,user,pid,'REFERRAL_STATUS','Specialist consultation started',ref.id,c,{'source_consultation_id':ref.consultation_id})
    if follow: follow.outcome_consultation_id=c.id;follow.status='COMPLETED'
    audit(db,user,pid,'CREATE_CONSULTATION',c.id);db.commit()
    return serial(c)

@router.get('/consultations')
def consultations(db: Session=Depends(get_db),user=Depends(current_user)):
    q=db.query(Consultation)
    if user.role=='PATIENT': q=q.filter_by(patient_id=entity(db,user,Patient).id)
    elif user.role=='DOCTOR': q=q.filter_by(doctor_id=entity(db,user,Doctor).id)
    elif user.role=='HOSPITAL_ADMIN': q=q.filter_by(hospital_id=entity(db,user,Hospital).id)
    else: raise HTTPException(403,'Clinical role required')
    rows=[]
    for c in q.order_by(Consultation.created_at.desc()).all():
        data=dict(serial(c),patient_name=c.patient.full_name,doctor_name=c.doctor.full_name if c.doctor else None)
        if user.role=='DOCTOR':
            try: encounter_access(db,user,c.id)
            except HTTPException:
                # Queue visibility is not permission to read symptoms, notes or history.
                data={k:data.get(k) for k in ('id','patient_id','doctor_id','patient_name','doctor_name','status','created_at')}
                data['authorization_required']=True
        rows.append(data)
    return rows

class EncounterUpdate(BaseModel):
    status: Literal['WAITING','IN_PROGRESS','COMPLETED','CANCELLED','NO_SHOW']
    observations: Optional[str]=None
    reason: str=Field(min_length=1)

@router.patch('/consultations/{cid}')
def update_encounter(cid:str,body:EncounterUpdate,db:Session=Depends(get_db),user=Depends(current_user)):
    c=encounter_access(db,user,cid,True)
    if body.status=='COMPLETED' and c.doctor_id: require_role(user,'DOCTOR')
    before=serial(c)
    valid={'WAITING':{'IN_PROGRESS','CANCELLED','NO_SHOW'},'TRIAGED':{'IN_PROGRESS','CANCELLED','NO_SHOW'},'IN_DOCTOR_QUEUE':{'IN_PROGRESS','CANCELLED','NO_SHOW'},'REFERRED_ICU':{'IN_PROGRESS','CANCELLED'},'UNDER_REVIEW':{'IN_PROGRESS','COMPLETED','CANCELLED'},'IN_PROGRESS':{'COMPLETED','CANCELLED'}}
    if body.status=='COMPLETED' and db.get(ConsultationPlan,c.id) and c.status not in ('CANCELLED','NO_SHOW','COMPLETED'):
        valid.setdefault(c.status,set()).add('COMPLETED')
    if body.status!=c.status and body.status not in valid.get(c.status,set()): raise HTTPException(409,'Invalid consultation transition')
    if body.status=='COMPLETED':
        if c.status=='COMPLETED': return serial(c)
        from .visit import apply_plan
        claimed=db.execute(update(Consultation).where(Consultation.id==cid,Consultation.status==c.status).values(status='COMPLETED')).rowcount
        if not claimed: raise HTTPException(409,'Consultation changed; reload before retrying')
        apply_plan(db,user,c)
    c.status=body.status
    if body.observations is not None:
        c.branch_responses=dict(c.branch_responses or {},clinical_observations=body.observations)
    if c.status=='COMPLETED':
        for e in db.query(MedicalEvent).filter_by(consultation_id=c.id,status='DRAFT'): e.status='ACTIVE'
        for diagnosis in db.query(Diagnosis).filter_by(consultation_id=c.id,status='DRAFT'): diagnosis.status='PROVISIONAL'
        for n in db.query(DoctorNote).filter_by(consultation_id=c.id): n.is_finalized=True
        if not db.query(MedicalEvent).filter_by(dedupe_key='consult:'+c.id).first():
            event(db,user,c.patient_id,'FOLLOW_UP' if c.previous_consultation_id else 'SPECIALIST_CONSULTATION' if c.referral_id else 'CONSULTATION',c.chief_complaint,c.id,c,{'symptoms':c.patient_notes,'observations':body.observations,'previous_consultation_id':c.previous_consultation_id},dedupe='consult:'+c.id)
    elif c.status in ('CANCELLED','NO_SHOW'):
        for e in db.query(MedicalEvent).filter_by(consultation_id=c.id,status='DRAFT'): e.status='CANCELLED'
        event(db,user,c.patient_id,'CONSULTATION_STATUS',c.status.replace('_',' ').title(),c.id,c)
    version(db,user,c,before,body.reason);db.commit();return serial(c)

class DiagnosisCreate(BaseModel):
    name:str=Field(min_length=1,max_length=255)
    status:Literal['SUSPECTED','PROVISIONAL','CONFIRMED','RULED_OUT','RESOLVED']='PROVISIONAL'

@router.post('/consultations/{cid}/diagnoses')
def diagnose(cid:str,body:DiagnosisCreate,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'DOCTOR')
    c=encounter_access(db,user,cid,True)
    if c.status in ('CANCELLED','NO_SHOW'): raise HTTPException(409,'Encounter cancelled')
    d=Diagnosis(patient_id=c.patient_id,consultation_id=cid,doctor_id=c.doctor_id,facility_id=c.hospital_id or c.clinic_id,
        name=body.name,status=body.status,created_by=user.id)
    db.add(d);db.flush()
    event(db,user,c.patient_id,'DIAGNOSIS',body.name,d.id,c,{'diagnosis_status':body.status},status='ACTIVE' if c.status=='COMPLETED' else 'DRAFT')
    db.commit();return serial(d)

class VitalCreate(BaseModel):
    name:Literal['BP','temperature','pulse','SpO2','weight','glucose']
    value:str=Field(min_length=1,max_length=64)
    unit:str=Field(min_length=1,max_length=32)
    measured_at:Optional[datetime]=None

@router.post('/consultations/{cid}/vitals')
def record_vital(cid:str,body:VitalCreate,db:Session=Depends(get_db),user=Depends(current_user)):
    c=encounter_access(db,user,cid,True)
    if c.status in ('CANCELLED','NO_SHOW'): raise HTTPException(409,'Encounter cancelled')
    v=Vital(patient_id=c.patient_id,consultation_id=cid,name=body.name,value=body.value,unit=body.unit,
        measured_at=body.measured_at or datetime.utcnow(),created_by=user.id,source="HOSPITAL_STAFF" if user.role=="HOSPITAL_ADMIN" else "CLINICIAN")
    db.add(v);db.flush();event(db,user,c.patient_id,'VITAL',f'{v.name}: {v.value} {v.unit}',v.id,c,{'measured_at':v.measured_at.isoformat()},status='ACTIVE' if c.status=='COMPLETED' else 'DRAFT');db.commit();return serial(v)

class MedItem(BaseModel):
    name:str=Field(min_length=1,max_length=255)
    dosage:str=Field(min_length=1)
    frequency:str=Field(min_length=1)
    duration_days:Optional[int]=Field(default=None,ge=1,le=3650)
    start_date:Optional[date]=None
    quantity:int=Field(default=1,ge=1,le=10000)

class RxCreate(BaseModel):
    medicines:list[MedItem]=Field(min_length=1)
    pharmacy_id:Optional[str]=None
    notes:Optional[str]=None
    acknowledge_warnings:bool=False
    replaces_medication_id:Optional[str]=None
    change_reason:Optional[str]=None

@router.post('/consultations/{cid}/prescriptions')
def prescribe(cid:str,body:RxCreate,db:Session=Depends(get_db),user=Depends(current_user)):
    c=encounter_access(db,user,cid,True)
    if c.status!='COMPLETED': raise HTTPException(409,'Complete the consultation before issuing a prescription')
    # Hospital administrators can record an encounter but cannot independently prescribe.
    require_role(user,'DOCTOR')
    p=patient_access(db,user,c.patient_id)
    if body.pharmacy_id and not db.get(PharmacyStore,body.pharmacy_id): raise HTTPException(404,'Pharmacy not found')
    active=db.query(Medication).filter_by(patient_id=p.id,status='ACTIVE').all()
    allergies=list(p.allergies or [])+[a.substance for a in db.query(Allergy).filter_by(patient_id=p.id,status='ACTIVE')]
    warnings=[]
    for med in body.medicines:
        if any(a.lower() in med.name.lower() or med.name.lower() in a.lower() for a in allergies if a): warnings.append(f'Possible recorded allergy conflict: {med.name}; clinician review required')
        if any(m.name.lower()==med.name.lower() and m.id!=body.replaces_medication_id for m in active): warnings.append(f'Duplicate active medicine: {med.name}')
    if warnings and not body.acknowledge_warnings: raise HTTPException(409,{'message':'Review warnings and explicitly acknowledge to proceed','warnings':warnings})
    if body.replaces_medication_id:
        old=db.get(Medication,body.replaces_medication_id)
        if not old or old.patient_id!=p.id or old.status!='ACTIVE' or not body.change_reason: raise HTTPException(400,'Select active medicine and provide change reason')
        before=serial(old);old.status='CHANGED';old.reason=body.change_reason
        version(db,user,old,before,body.change_reason);event(db,user,p.id,'MEDICATION_CHANGED',old.name,old.id,c,{'reason':body.change_reason})
    rx=Prescription(patient_id=p.id,doctor_id=c.doctor_id,consultation_id=c.id,pharmacy_id=body.pharmacy_id,
        medicines=[m.model_dump(mode='json') for m in body.medicines],notes=body.notes,status='PENDING')
    db.add(rx);db.flush()
    for m in body.medicines:
        start=m.start_date or date.today()
        db.add(Medication(patient_id=p.id,prescription_id=rx.id,consultation_id=c.id,doctor_id=c.doctor_id,name=m.name,
            dosage=m.dosage,frequency=m.frequency,start_date=start,duration_days=m.duration_days,
            end_date=start+timedelta(days=m.duration_days-1) if m.duration_days else None,created_by=user.id,status='ACTIVE'))
    event(db,user,p.id,'PRESCRIPTION','Prescription issued',rx.id,c,{'medicines':rx.medicines,'warnings_acknowledged':warnings})
    notify(db,p.id,'New prescription issued',rx.id)
    if body.pharmacy_id:
        notify(db,p.id,'Prescription ready for dispensing',rx.id,user_id=db.get(PharmacyStore,body.pharmacy_id).user_id)
    db.commit();return dict(serial(rx),warnings=warnings)

@router.get('/medications/{pid}')
def medications(pid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    p=patient_access(db,user,pid);migrate_patient_records(db,p);expire_courses(db,pid);db.commit()
    return [serial(m) for m in db.query(Medication).filter_by(patient_id=pid).order_by(Medication.created_at.desc())]

class StatusChange(BaseModel):
    status:str
    reason:str=Field(min_length=1)

@router.patch('/medications/{mid}')
def med_status(mid:str,body:StatusChange,db:Session=Depends(get_db),user=Depends(current_user)):
    m=db.get(Medication,mid)
    if not m: raise HTTPException(404,'Medication not found')
    patient_access(db,user,m.patient_id)
    require_role(user,'DOCTOR')
    if body.status not in ('COMPLETED','DISCONTINUED','CHANGED'): raise HTTPException(400,'Invalid medication status')
    if m.status!='ACTIVE': raise HTTPException(409,'Medication is already historical')
    before=serial(m);m.status=body.status;m.reason=body.reason;version(db,user,m,before,body.reason)
    event(db,user,m.patient_id,'MEDICATION_STATUS',f'{m.name}: {m.status}',m.id,details={'reason':body.reason});db.commit();return serial(m)

@router.get('/prescriptions')
def prescriptions(db:Session=Depends(get_db),user=Depends(current_user)):
    q=db.query(Prescription)
    if user.role=='PATIENT': q=q.filter_by(patient_id=entity(db,user,Patient).id)
    elif user.role=='DOCTOR': q=q.filter_by(doctor_id=entity(db,user,Doctor).id)
    elif user.role=='PHARMACY':
        pharm=entity(db,user,PharmacyStore)
        ids=[g.patient_id for g in db.query(AccessGrant).filter(AccessGrant.user_id==user.id,AccessGrant.scope=='PRESCRIPTION',AccessGrant.expires_at>datetime.utcnow(),AccessGrant.revoked_at.is_(None))]
        q=q.filter(or_(Prescription.pharmacy_id==pharm.id,Prescription.patient_id.in_(ids)))
    else: raise HTTPException(403,'Prescription role required')
    results=[]
    for rx in q.order_by(Prescription.created_at.desc()):
        audit(db,user,rx.patient_id,'VIEW_PRESCRIPTION',rx.id)
        x=serial(rx);x.update(patient_name=rx.patient.full_name,doctor_name=rx.doctor.full_name if rx.doctor else None)
        if user.role=='PHARMACY':
            # Expose only dispensing fields and allergies, never consultation notes/history.
            x={k:x[k] for k in ('id','patient_name','doctor_name','medicines','status','created_at','dispensed_at','pharmacy_id')}
            x['allergies']=rx.patient.allergies or []
        results.append(x)
    db.commit();return results

@router.post('/prescriptions/{rid}/dispense')
def dispense(rid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'PHARMACY');pharm=entity(db,user,PharmacyStore)
    rx=db.query(Prescription).filter_by(id=rid).with_for_update().first()
    if not rx: raise HTTPException(404,'Prescription not found')
    if rx.pharmacy_id!=pharm.id: patient_access(db,user,rx.patient_id,'PRESCRIPTION')
    if rx.pharmacy_id and rx.pharmacy_id!=pharm.id: raise HTTPException(403,'Prescription assigned to another pharmacy')
    if rx.status!='PENDING': raise HTTPException(409,'Prescription already processed')
    for med in rx.medicines or []:
        if med.get('discontinued'): continue
        item=db.query(Inventory).filter_by(pharmacy_id=pharm.id,medicine_name=med.get('name')).first()
        qty=int(med.get('quantity',1))
        if not item: raise HTTPException(409,f'Add inventory for {med.get("name")} before dispensing')
        changed=db.execute(update(Inventory).where(Inventory.id==item.id,Inventory.stock_quantity>=qty).values(stock_quantity=Inventory.stock_quantity-qty)).rowcount
        if not changed: raise HTTPException(409,f'Insufficient stock: {med.get("name")}')
    changed=db.execute(update(Prescription).where(Prescription.id==rid,Prescription.status=='PENDING').values(status='DISPENSED',pharmacy_id=pharm.id,dispensed_at=datetime.utcnow())).rowcount
    if not changed: raise HTTPException(409,'Prescription was processed concurrently')
    event(db,user,rx.patient_id,'DISPENSING','Prescription dispensed',rid,details={'pharmacy':pharm.store_name})
    notify(db,rx.patient_id,'Prescription dispensed',rid);db.commit();return {'status':'DISPENSED'}

class ReferralCreate(BaseModel):
    consultation_id:str
    hospital_id:str
    specialty:str=Field(min_length=1)
    reason:str=Field(min_length=1)
    clinical_summary:Optional[str]=None
    priority:Literal['ROUTINE','URGENT','EMERGENCY']='ROUTINE'

@router.post('/referrals')
def create_referral(body:ReferralCreate,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'DOCTOR');c=encounter_access(db,user,body.consultation_id,True)
    if c.status!='COMPLETED': raise HTTPException(409,'Complete source consultation first')
    h=db.get(Hospital,body.hospital_id)
    if not h or not h.is_active: raise HTTPException(404,'Active hospital not found')
    r=Referral(patient_id=c.patient_id,consultation_id=c.id,doctor_id=c.doctor_id,source_facility_id=c.hospital_id or c.clinic_id,
        hospital_id=h.id,specialty=body.specialty,reason=body.reason,clinical_summary=body.clinical_summary,priority=body.priority,status='CREATED',created_by=user.id)
    db.add(r);db.flush();event(db,user,c.patient_id,'REFERRAL','Referral created',r.id,c,{'hospital':h.name,'reason':r.reason,'priority':r.priority})
    r.status='SENT';event(db,user,c.patient_id,'REFERRAL_STATUS','Referral sent',r.id,c)
    notify(db,c.patient_id,f'Referral sent to {h.name}',r.id);notify(db,c.patient_id,'Incoming referral',r.id,user_id=h.user_id)
    db.commit();return serial(r)

@router.get('/referrals')
def referrals(db:Session=Depends(get_db),user=Depends(current_user)):
    q=db.query(Referral)
    if user.role=='PATIENT': q=q.filter_by(patient_id=entity(db,user,Patient).id)
    elif user.role=='DOCTOR':
        d=entity(db,user,Doctor);q=q.filter(or_(Referral.doctor_id==d.id,Referral.receiving_doctor_id==d.id))
    elif user.role=='HOSPITAL_ADMIN': q=q.filter_by(hospital_id=entity(db,user,Hospital).id)
    else: raise HTTPException(403,'Clinical role required')
    result=[]
    for r in q.order_by(Referral.created_at.desc()):
        audit(db,user,r.patient_id,'VIEW_REFERRAL',r.id)
        result.append(dict(serial(r),patient_name=db.get(Patient,r.patient_id).full_name,hospital_name=db.get(Hospital,r.hospital_id).name))
    db.commit();return result

class ReferralChange(BaseModel):
    status:Literal['RECEIVED','ACCEPTED','PATIENT_ARRIVED','COMPLETED','DECLINED','CANCELLED']
    reason:str=Field(min_length=1)
    receiving_doctor_id:Optional[str]=None
    outcome_summary:Optional[str]=None

@router.patch('/referrals/{rid}')
def referral_status(rid:str,body:ReferralChange,db:Session=Depends(get_db),user=Depends(current_user)):
    r=db.get(Referral,rid)
    if not r: raise HTTPException(404,'Referral not found')
    patient_access(db,user,r.patient_id)
    if body.status=='CANCELLED':
        if user.role=='PATIENT':
            if entity(db,user,Patient).id!=r.patient_id: raise HTTPException(403,'Not your referral')
        elif user.role=='DOCTOR':
            if entity(db,user,Doctor).id!=r.doctor_id: raise HTTPException(403,'Not your referral')
        else: raise HTTPException(403,'Cancellation is for patient or referring clinician')
    else:
        require_role(user,'HOSPITAL_ADMIN')
        if entity(db,user,Hospital).id!=r.hospital_id: raise HTTPException(403,'Not your incoming referral')
    valid={'SENT':{'RECEIVED','CANCELLED'},'RECEIVED':{'ACCEPTED','DECLINED','CANCELLED'},'ACCEPTED':{'PATIENT_ARRIVED','CANCELLED'},'PATIENT_ARRIVED':{'CANCELLED'},'SPECIALIST_CONSULTATION':{'COMPLETED'}}
    if body.status not in valid.get(r.status,set()): raise HTTPException(409,'Invalid referral transition')
    if body.receiving_doctor_id:
        d=db.get(Doctor,body.receiving_doctor_id)
        if not d or d.hospital_id!=r.hospital_id: raise HTTPException(400,'Clinician must be assigned to destination hospital')
    if body.status=='COMPLETED':
        c=db.get(Consultation,r.outcome_consultation_id) if r.outcome_consultation_id else None
        if not c or c.status!='COMPLETED' or not body.outcome_summary: raise HTTPException(409,'Complete the specialist encounter and record an outcome first')
    before=serial(r);r.status=body.status;r.receiving_doctor_id=body.receiving_doctor_id or r.receiving_doctor_id;r.outcome_summary=body.outcome_summary or r.outcome_summary
    version(db,user,r,before,body.reason);event(db,user,r.patient_id,'REFERRAL_STATUS',f'Referral {r.status.replace("_"," ").lower()}',r.id,db.get(Consultation,r.consultation_id),{'reason':body.reason,'outcome':r.outcome_summary})
    notify(db,r.patient_id,f'Referral {r.status.replace("_"," ").lower()}',r.id)
    doc=db.get(Doctor,r.doctor_id)
    if doc: notify(db,r.patient_id,f'Referral {r.status}: {r.outcome_summary or body.reason}',r.id,user_id=doc.user_id)
    db.commit();return serial(r)

class BedCreate(BaseModel):
    ward_name:str=Field(min_length=1)
    ward_type:Literal['ICU','GENERAL','EMERGENCY','PEDIATRIC']
    bed_number:str=Field(min_length=1)

@router.post('/beds')
def add_bed(body:BedCreate,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'HOSPITAL_ADMIN');h=entity(db,user,Hospital)
    if db.query(WardAndBed).filter_by(hospital_id=h.id,ward_name=body.ward_name,bed_number=body.bed_number).first(): raise HTTPException(409,'Bed already exists')
    b=WardAndBed(hospital_id=h.id,**body.model_dump(),state='AVAILABLE',is_occupied=False)
    db.add(b);db.commit();return serial(b)

@router.get('/beds')
def beds(db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'HOSPITAL_ADMIN');h=entity(db,user,Hospital)
    return [serial(b) for b in db.query(WardAndBed).filter_by(hospital_id=h.id).order_by(WardAndBed.ward_name,WardAndBed.bed_number)]

@router.patch('/beds/{bid}')
def bed_status(bid:str,body:StatusChange,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'HOSPITAL_ADMIN');h=entity(db,user,Hospital)
    b=db.get(WardAndBed,bid)
    if not b or b.hospital_id!=h.id: raise HTTPException(404,'Owned bed not found')
    valid={'AVAILABLE':{'RESERVED','CLEANING'},'RESERVED':{'AVAILABLE','CLEANING'},'CLEANING':{'AVAILABLE'}}
    if body.status not in valid.get(b.state,set()): raise HTTPException(409,'Use discharge to release an occupied bed')
    changed=db.execute(update(WardAndBed).where(WardAndBed.id==bid,WardAndBed.state==b.state).values(state=body.status)).rowcount
    if not changed: raise HTTPException(409,'Bed changed concurrently')
    audit(db,user,None,'BED_STATUS',bid);db.commit();return serial(b)

class AdmissionCreate(BaseModel):
    patient_id:str
    bed_id:str
    reason:str=Field(min_length=1)
    consultation_id:Optional[str]=None
    referral_id:Optional[str]=None
    doctor_id:Optional[str]=None

@router.post('/admissions')
def admit(body:AdmissionCreate,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'HOSPITAL_ADMIN');h=entity(db,user,Hospital);patient_access(db,user,body.patient_id)
    if db.query(Admission).filter_by(patient_id=body.patient_id,status='ADMITTED').first(): raise HTTPException(409,'Patient already admitted')
    b=db.get(WardAndBed,body.bed_id)
    if not b or b.hospital_id!=h.id: raise HTTPException(404,'Owned bed not found')
    if body.doctor_id:
        d=db.get(Doctor,body.doctor_id)
        if not d or d.hospital_id!=h.id: raise HTTPException(400,'Responsible doctor must belong to your hospital')
    c=encounter_access(db,user,body.consultation_id,True) if body.consultation_id else None
    if c and c.patient_id!=body.patient_id: raise HTTPException(400,'Patient/encounter mismatch')
    if body.referral_id:
        r=db.get(Referral,body.referral_id)
        if not r or r.patient_id!=body.patient_id or r.hospital_id!=h.id: raise HTTPException(400,'Referral mismatch')
    changed=db.execute(update(WardAndBed).where(WardAndBed.id==b.id,WardAndBed.state=='AVAILABLE',WardAndBed.is_occupied==False).values(
        state='OCCUPIED',is_occupied=True,current_patient_id=body.patient_id,assigned_doctor_id=body.doctor_id,admission_reason=body.reason,admission_date=datetime.utcnow())).rowcount
    if not changed: raise HTTPException(409,'Bed is no longer available')
    # CAS on patient row serializes concurrent admission attempts across different beds.
    patient=db.query(Patient).filter_by(id=body.patient_id).with_for_update().first()
    db.execute(update(Patient).where(Patient.id==patient.id).values(updated_at=datetime.utcnow()))
    if db.query(Admission).filter_by(patient_id=body.patient_id,status='ADMITTED').first(): raise HTTPException(409,'Patient already admitted concurrently')
    a=Admission(hospital_id=h.id,created_by=user.id,status='ADMITTED',**body.model_dump())
    db.add(a);db.flush();event(db,user,a.patient_id,'ADMISSION',f'Admitted to {h.name}',a.id,c,{'ward':b.ward_name,'bed':b.bed_number,'reason':a.reason});notify(db,a.patient_id,f'Admitted to {h.name}',a.id)
    from sqlalchemy.exc import IntegrityError
    try: db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Concurrent admission conflict; refresh beds and admissions')
    return serial(a)

@router.get('/admissions')
def admissions(db:Session=Depends(get_db),user=Depends(current_user)):
    if user.role=='HOSPITAL_ADMIN': q=db.query(Admission).filter_by(hospital_id=entity(db,user,Hospital).id)
    elif user.role=='PATIENT': q=db.query(Admission).filter_by(patient_id=entity(db,user,Patient).id)
    else: raise HTTPException(403,'Admission role required')
    return [dict(serial(a),patient_name=db.get(Patient,a.patient_id).full_name) for a in q.order_by(Admission.created_at.desc())]

class Discharge(BaseModel):
    summary:str=Field(min_length=1)

@router.post('/admissions/{aid}/discharge')
def discharge(aid:str,body:Discharge,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'HOSPITAL_ADMIN');h=entity(db,user,Hospital)
    a=db.query(Admission).filter_by(id=aid).with_for_update().first()
    if not a or a.hospital_id!=h.id: raise HTTPException(404,'Owned admission not found')
    before=serial(a)
    changed=db.execute(update(Admission).where(Admission.id==aid,Admission.status=='ADMITTED').values(status='DISCHARGED',discharged_at=datetime.utcnow(),discharge_summary=body.summary)).rowcount
    if not changed: raise HTTPException(409,'Admission already discharged')
    db.execute(update(WardAndBed).where(WardAndBed.id==a.bed_id,WardAndBed.current_patient_id==a.patient_id).values(state='CLEANING',is_occupied=False,current_patient_id=None,assigned_doctor_id=None,admission_reason=None,admission_date=None))
    db.refresh(a);version(db,user,a,before,'Discharge')
    c=db.get(Consultation,a.consultation_id) if a.consultation_id else None
    event(db,user,a.patient_id,'DISCHARGE','Discharge summary',a.id,c,{'summary':body.summary});notify(db,a.patient_id,'Hospital discharge recorded',a.id);db.commit();return serial(a)

class FollowCreate(BaseModel):
    consultation_id:str
    due_at:Optional[datetime]=None
    after_days:Optional[int]=Field(default=None,ge=1,le=3650)
    reason:str=Field(min_length=1)

@router.post('/follow-ups')
def schedule(body:FollowCreate,db:Session=Depends(get_db),user=Depends(current_user)):
    c=encounter_access(db,user,body.consultation_id,True)
    due=body.due_at or (datetime.utcnow()+timedelta(days=body.after_days) if body.after_days else None)
    if not due or due.replace(tzinfo=None)<datetime.utcnow(): raise HTTPException(400,'Specify a future follow-up date or positive day interval')
    f=FollowUp(patient_id=c.patient_id,consultation_id=c.id,doctor_id=c.doctor_id,hospital_id=c.hospital_id,due_at=due.replace(tzinfo=None),reason=body.reason,status='SCHEDULED',created_by=user.id)
    db.add(f);db.flush();event(db,user,c.patient_id,'FOLLOW_UP_SCHEDULED','Follow-up scheduled',f.id,c,{'due_at':due.isoformat(),'reason':body.reason});notify(db,c.patient_id,f'Follow-up scheduled: {due.strftime("%d %b %H:%M")}',f.id);db.commit();return serial(f)

@router.get('/follow-ups')
def followups(db:Session=Depends(get_db),user=Depends(current_user)):
    if user.role=='PATIENT':
        pid=entity(db,user,Patient).id;expire_courses(db,pid);db.commit();q=db.query(FollowUp).filter_by(patient_id=pid)
    elif user.role=='DOCTOR': q=db.query(FollowUp).filter_by(doctor_id=entity(db,user,Doctor).id)
    elif user.role=='HOSPITAL_ADMIN': q=db.query(FollowUp).filter_by(hospital_id=entity(db,user,Hospital).id)
    else: raise HTTPException(403,'Clinical role required')
    return [serial(f) for f in q.order_by(FollowUp.due_at)]

class AllergyCreate(BaseModel):
    patient_id:str
    substance:str=Field(min_length=1)
    reaction:Optional[str]=None
    severity:Literal['UNKNOWN','MILD','MODERATE','SEVERE']='UNKNOWN'

@router.post('/allergies')
def add_allergy(body:AllergyCreate,db:Session=Depends(get_db),user=Depends(current_user)):
    patient_access(db,user,body.patient_id)
    require_role(user,'PATIENT','DOCTOR','HOSPITAL_ADMIN')
    a=Allergy(**body.model_dump(),created_by=user.id,source='PATIENT_REPORTED' if user.role=='PATIENT' else 'CLINICIAN',last_verified_at=datetime.utcnow() if user.role=='DOCTOR' else None)
    db.add(a);db.flush();event(db,user,a.patient_id,'ALLERGY',f'Allergy: {a.substance}',a.id,details={'reaction':a.reaction,'severity':a.severity});db.commit();return serial(a)

@router.get('/allergies/{pid}')
def allergies(pid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    p=patient_access(db,user,pid)
    return {'reported':p.allergies or [],'records':[serial(a) for a in db.query(Allergy).filter_by(patient_id=pid)]}

@router.get('/vitals/{pid}')
def vitals(pid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    patient_access(db,user,pid)
    return [serial(v) for v in db.query(Vital).join(Consultation,Vital.consultation_id==Consultation.id).filter(Vital.patient_id==pid,Consultation.status=='COMPLETED').order_by(Vital.measured_at.desc())]

@router.post('/documents')
async def upload(patient_id:str=Form(...),title:str=Form(...),category:str=Form('HISTORICAL'),file:UploadFile=File(...),db:Session=Depends(get_db),user=Depends(current_user)):
    patient_access(db,user,patient_id);require_role(user,'PATIENT','DOCTOR','HOSPITAL_ADMIN')
    allowed={'application/pdf':'.pdf','image/png':'.png','image/jpeg':'.jpg','text/plain':'.txt'}
    if file.content_type not in allowed: raise HTTPException(400,'Upload PDF, PNG, JPEG, or plain text')
    data=await file.read(10*1024*1024+1)
    if len(data)>10*1024*1024: raise HTTPException(413,'Maximum size is 10 MB')
    if not data: raise HTTPException(400,'Empty document')
    mime=file.content_type
    if (mime=='application/pdf' and not data.startswith(b'%PDF-')) or (mime=='image/png' and not data.startswith(b'\x89PNG\r\n\x1a\n')) or (mime=='image/jpeg' and not data.startswith(b'\xff\xd8')): raise HTTPException(400,'File content does not match its type')
    if mime=='text/plain':
        try: data.decode('utf-8')
        except UnicodeDecodeError: raise HTTPException(400,'Text documents must be UTF-8')
    UPLOAD_ROOT.mkdir(exist_ok=True,parents=True);stored=secrets.token_hex(20)+allowed[mime]
    path=UPLOAD_ROOT/stored;path.write_bytes(data)
    try:
        d=Document(patient_id=patient_id,title=title[:255],category=category[:64],filename=Path(file.filename or 'record').name,stored_name=stored,content_type=mime,created_by=user.id,source='PATIENT_UPLOAD' if user.role=='PATIENT' else 'CLINICIAN_UPLOAD')
        db.add(d);db.flush();event(db,user,patient_id,'DOCUMENT',d.title,d.id,details={'category':d.category,'filename':d.filename});db.commit()
    except Exception:
        path.unlink(missing_ok=True);raise
    return serial(d)

@router.get('/documents/{pid}')
def documents(pid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    patient_access(db,user,pid)
    return [serial(d) for d in db.query(Document).filter(Document.patient_id==pid,Document.status=='ACTIVE').order_by(Document.created_at.desc())]

@router.get('/document/{did}/download')
def download(did:str,db:Session=Depends(get_db),user=Depends(current_user)):
    d=db.get(Document,did)
    if not d or d.status!='ACTIVE': raise HTTPException(404,'Document not found')
    patient_access(db,user,d.patient_id);audit(db,user,d.patient_id,'VIEW_DOCUMENT',did);db.commit()
    path=(UPLOAD_ROOT/d.stored_name).resolve()
    if path.parent!=UPLOAD_ROOT or not path.exists(): raise HTTPException(404,'Document bytes unavailable')
    return FileResponse(path,media_type=d.content_type,filename=d.filename)

@router.get('/notifications')
def notifications(db:Session=Depends(get_db),user=Depends(current_user)):
    if user.role=='PATIENT': expire_courses(db,entity(db,user,Patient).id);db.commit()
    return [serial(n) for n in db.query(Notification).filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(100)]

@router.patch('/notifications/{nid}')
def read_notification(nid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    n=db.get(Notification,nid)
    if not n or n.user_id!=user.id: raise HTTPException(404,'Notification not found')
    n.status='READ';db.commit();return serial(n)

@router.get('/audit/{pid}')
def audit_view(pid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    patient_access(db,user,pid)
    require_role(user,'PATIENT')
    return [dict(serial(a),user_name=db.get(User,a.user_id).name if a.user_id and db.get(User,a.user_id) else 'Emergency token / System') for a in db.query(AuditLog).filter_by(patient_id=pid).order_by(AuditLog.created_at.desc()).limit(200)]

class Redeem(BaseModel):
    token:str

@router.post('/access/redeem')
def redeem(body:Redeem,db:Session=Depends(get_db),user=Depends(current_user)):
    raw=body.token.removeprefix('PULSESYNC:CONSENT:')
    g=db.query(AccessGrant).filter_by(token_hash=hashlib.sha256(raw.encode()).hexdigest()).first()
    if not g or g.revoked_at or g.expires_at<=datetime.utcnow() or g.user_id!=user.id: raise HTTPException(403,'Consent expired, revoked, or intended for another provider')
    audit(db,user,g.patient_id,'REDEEM_ACCESS',g.id);db.commit();return {'patient_id':g.patient_id,'scope':g.scope,'expires_at':g.expires_at.isoformat()}

class GrantCreate(BaseModel):
    pin:str=""
    scope:Literal['CLINICAL','PRESCRIPTION','EMERGENCY']
    provider_user_id:Optional[str]=None
    minutes:int=Field(default=30,ge=1,le=1440)

@router.post('/access/{pid}')
def create_access(pid:str,body:GrantCreate,request:Request,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'PATIENT');patient_access(db,user,pid)
    target=db.get(User,body.provider_user_id) if body.provider_user_id else None
    if body.scope!='EMERGENCY' and (not target or target.role not in ({'DOCTOR','HOSPITAL_ADMIN'} if body.scope=='CLINICAL' else {'PHARMACY'})): raise HTTPException(400,'Select a provider appropriate to this access scope')
    if body.scope!='EMERGENCY':
        from ..pin_security import verify_pin
        verify_pin(db,user,body.pin)
    raw=secrets.token_urlsafe(32)
    grant=AccessGrant(patient_id=pid,user_id=target.id if target else None,scope=body.scope,token_hash=hashlib.sha256(raw.encode()).hexdigest(),expires_at=datetime.utcnow()+timedelta(minutes=body.minutes))
    db.add(grant);db.flush();audit(db,user,pid,'GRANT_ACCESS',grant.id);db.commit()
    from .qr_engine import generate_qr_base64_image
    url=str(request.base_url).rstrip('/')+f'/api/workflow/emergency/{raw}' if body.scope=='EMERGENCY' else f'PULSESYNC:CONSENT:{raw}'
    return {'grant':serial(grant),'token':raw,'qr_image_base64':generate_qr_base64_image(url),'payload':url}

@router.get('/access/{pid}')
def grants(pid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'PATIENT');patient_access(db,user,pid)
    return [{k:v for k,v in serial(g).items() if k!='token_hash'} for g in db.query(AccessGrant).filter_by(patient_id=pid).order_by(AccessGrant.created_at.desc())]

@router.delete('/access/{gid}')
def revoke(gid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    g=db.get(AccessGrant,gid)
    if not g: raise HTTPException(404,'Grant not found')
    require_role(user,'PATIENT');patient_access(db,user,g.patient_id);g.revoked_at=datetime.utcnow();audit(db,user,g.patient_id,'REVOKE_ACCESS',gid);db.commit();return {'revoked':True}

@router.get('/emergency/{token}')
def emergency(token:str,db:Session=Depends(get_db)):
    g=db.query(AccessGrant).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest(),scope='EMERGENCY').first()
    if not g or g.revoked_at or g.expires_at<=datetime.utcnow(): raise HTTPException(403,'Emergency access expired or revoked')
    p=db.get(Patient,g.patient_id)
    severe=[serial(a) for a in db.query(Allergy).filter_by(patient_id=p.id,severity='SEVERE',status='ACTIVE')]
    meds=[{'name':m.name,'dosage':m.dosage} for m in db.query(Medication).filter(Medication.patient_id==p.id,Medication.status=='ACTIVE',or_(Medication.end_date.is_(None),Medication.end_date>=date.today()))]
    audit(db,None,p.id,'EMERGENCY_ACCESS',g.id);db.commit()
    return {'name':p.full_name,'age':p.age,'blood_group':p.blood_group,'severe_allergies':[{'substance':a['substance'],'reaction':a['reaction']} for a in severe],
        'reported_allergies_unverified':p.allergies or [],'reported_chronic_conditions':p.existing_conditions or [],'active_medications':meds,
        'emergency_contact':{'name':p.emergency_contact_name,'phone':p.emergency_contact_phone}}

@router.get('/providers')
def providers(db:Session=Depends(get_db),user=Depends(current_user)):
    result=[]
    for model,label,field in [(Doctor,'DOCTOR','full_name'),(Hospital,'HOSPITAL_ADMIN','name'),(PharmacyStore,'PHARMACY','store_name')]:
        for row in db.query(model):
            if row.user_id: result.append({'id':row.id,'user_id':row.user_id,'name':getattr(row,field),'role':label,'hospital_id':row.hospital_id if isinstance(row,Doctor) else None})
    return result

class Affiliation(BaseModel):
    invitation:str

@router.post('/hospital/invite')
def invite(db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'HOSPITAL_ADMIN');h=entity(db,user,Hospital)
    from .auth import JWT_SECRET
    import jwt
    token=jwt.encode({'purpose':'hospital_affiliation','hospital_id':h.id,'exp':datetime.utcnow()+timedelta(hours=1)},JWT_SECRET,algorithm='HS256')
    return {'invitation':token,'expires_in_minutes':60}

@router.post('/doctor/affiliation')
def affiliate(body:Affiliation,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'DOCTOR')
    from .auth import JWT_SECRET
    import jwt
    try:
        payload=jwt.decode(body.invitation,JWT_SECRET,algorithms=['HS256'])
        if payload.get('purpose')!='hospital_affiliation': raise ValueError()
        h=db.get(Hospital,payload['hospital_id'])
        if not h: raise ValueError()
    except Exception: raise HTTPException(400,'Invalid or expired hospital invitation')
    doc=entity(db,user,Doctor);doc.hospital_id=h.id;db.commit();return {'hospital_id':h.id,'hospital_name':h.name}

class ProfileUpdate(BaseModel):
    emergency_contact_name:Optional[str]=None
    emergency_contact_phone:Optional[str]=None
    existing_conditions:Optional[list[str]]=None
    blood_group:Optional[str]=None
    address:Optional[str]=None
    city:Optional[str]=None
    confirm_current:bool=False

@router.patch('/profile')
def profile(body:ProfileUpdate,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'PATIENT');p=entity(db,user,Patient);before=serial(p)
    for k,v in body.model_dump(exclude_unset=True).items():
        if k!='confirm_current': setattr(p,k,v)
    if body.confirm_current: p.last_verified_at=datetime.utcnow()
    version(db,user,p,before,'Patient updated or confirmed profile');event(db,user,p.id,'PROFILE','Patient profile updated',p.id,details={'last_verified_at':p.last_verified_at.isoformat() if p.last_verified_at else None});db.commit();return p.to_dict()

class Correction(BaseModel):
    status:Optional[str]=None
    name:Optional[str]=None
    value:Optional[str]=None
    reason:str=Field(min_length=1)

@router.patch('/records/{kind}/{rid}')
def correct(kind:str,rid:str,body:Correction,db:Session=Depends(get_db),user=Depends(current_user)):
    models={'diagnosis':Diagnosis,'vital':Vital,'document':Document,'allergy':Allergy}
    model=models.get(kind)
    if not model: raise HTTPException(400,'Unsupported correction type')
    row=db.get(model,rid)
    if not row: raise HTTPException(404,'Record not found')
    patient_access(db,user,row.patient_id)
    if kind=='diagnosis': require_role(user,'DOCTOR')
    if kind in ('diagnosis','vital'):
        encounter_access(db,user,row.consultation_id,True)
    elif row.created_by!=user.id and user.role!='DOCTOR': raise HTTPException(403,'Only author or clinician can correct this record')
    valid={'diagnosis':{'SUSPECTED','PROVISIONAL','CONFIRMED','RULED_OUT','RESOLVED','ENTERED_IN_ERROR','SUPERSEDED'},'vital':{'ACTIVE','ENTERED_IN_ERROR','SUPERSEDED'},'document':{'ACTIVE','CANCELLED','ENTERED_IN_ERROR','SUPERSEDED'},'allergy':{'ACTIVE','RESOLVED','ENTERED_IN_ERROR','SUPERSEDED'}}
    if body.status and body.status not in valid[kind]: raise HTTPException(400,'Invalid record status')
    before=serial(row)
    if body.status: row.status=body.status
    if body.name is not None:
        if kind=='diagnosis': row.name=body.name
        elif kind=='document': row.title=body.name
        elif kind=='allergy': row.substance=body.name
        else: raise HTTPException(400,'Vital name cannot be changed; correct its value')
    if body.value is not None:
        if kind!='vital': raise HTTPException(400,'Value correction is for vitals')
        row.value=body.value
    version(db,user,row,before,body.reason)
    for e in db.query(MedicalEvent).filter_by(resource_id=rid): e.status='SUPERSEDED'
    c=db.get(Consultation,row.consultation_id) if hasattr(row,'consultation_id') and row.consultation_id else None
    event(db,user,row.patient_id,'CORRECTION',f'{kind.title()} corrected',row.id,c,{'reason':body.reason,'updated_record':serial(row)})
    db.commit();return serial(row)

@router.get('/versions/{pid}')
def versions(pid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    patient_access(db,user,pid)
    return [serial(v) for v in db.query(RecordVersion).filter_by(patient_id=pid).order_by(RecordVersion.created_at.desc())]

class SummaryReview(BaseModel):
    status:Literal['CLINICIAN_APPROVED','CLINICIAN_EDITED']
    review_note:str=Field(min_length=1)
    content:Optional[dict]=None

@router.patch('/summaries/{sid}')
def review_summary(sid:str,body:SummaryReview,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'DOCTOR');s=db.get(HistorySummary,sid)
    if not s: raise HTTPException(404,'Summary not found')
    patient_access(db,user,s.patient_id);before=serial(s)
    s.status=body.status;s.review_note=body.review_note
    if body.content is not None: s.content=body.content
    version(db,user,s,before,body.review_note);db.commit();return serial(s)

@router.post('/summary/{pid}')
async def summary(pid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    p=patient_access(db,user,pid);migrate_patient_records(db,p);expire_courses(db,pid)
    ds=db.query(Diagnosis).join(Consultation,Diagnosis.consultation_id==Consultation.id).filter(Diagnosis.patient_id==pid,Consultation.status=='COMPLETED').all()
    meds=db.query(Medication).filter_by(patient_id=pid).all()
    encounters=db.query(Consultation).filter_by(patient_id=pid,status='COMPLETED').order_by(Consultation.created_at.desc()).all()
    admissions=db.query(Admission).filter_by(patient_id=pid).all()
    allergies=db.query(Allergy).filter_by(patient_id=pid).all()
    vs=db.query(Vital).join(Consultation,Vital.consultation_id==Consultation.id).filter(Vital.patient_id==pid,Consultation.status=='COMPLETED',Vital.status=='ACTIVE').all()
    # This fallback is explicitly a factual record digest, never mislabeled as model output.
    content={'reported_chronic_conditions':p.existing_conditions or [],'reported_allergies':p.allergies or [],
        'allergy_records':[serial(a) for a in allergies], 'active_medications':[serial(m) for m in meds if m.status=='ACTIVE'],
        'previous_diagnoses':[{'name':d.name,'status':d.status,'source':d.source,'date':d.created_at.isoformat()} for d in ds],
        'recent_consultations':[{'id':c.id,'complaint':c.chief_complaint,'date':c.created_at.isoformat()} for c in encounters[:10]],
        'hospitalizations':[serial(a) for a in admissions],
        'vital_measurements':[{'name':v.name,'value':v.value,'unit':v.unit,'date':v.measured_at.isoformat()} for v in vs],
        'uncertainty':['Patient-reported conditions and allergies are not clinician confirmation.','Missing records are unknown; no diagnosis or trend is inferred.','Uploaded document contents are not extracted.']}
    refs=[{'table':x.__tablename__,'id':x.id} for x in ds+meds+encounters+admissions+allergies+vs]
    events=db.query(MedicalEvent).filter(MedicalEvent.patient_id==pid,MedicalEvent.status=='ACTIVE').order_by(MedicalEvent.created_at.desc()).limit(100).all()
    content['major_medical_events']=[{'kind':ev.kind,'title':ev.title,'date':ev.created_at.isoformat(),'source':ev.source,'details':ev.details} for ev in events]
    refs.extend({'table':'medical_events','id':ev.id} for ev in events)
    refs.append({'table':'patients','id':pid})
    method='RECORD_DIGEST';failure=None
    url=os.getenv('AI_BASE_URL');key=os.getenv('AI_API_KEY');model=os.getenv('AI_MODEL')
    if url and key and model:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=20) as client:
                response=await client.post(url.rstrip('/')+'/chat/completions',headers={'Authorization':'Bearer '+key},json={
                    'model':model,'temperature':0,'messages':[{'role':'system','content':'Summarize only these stored medical facts. Preserve suspected/provisional/ruled-out statuses and patient-reported provenance. State uncertainty. Do not diagnose, recommend medication, or invent missing values. Return a JSON object with chronic_conditions, allergies, active_medications, previous_diagnoses, recent_consultations, hospitalizations, trends, major_events, uncertainty.'},{'role':'user','content':json.dumps(content)}], 'response_format':{'type':'json_object'}})
                response.raise_for_status();generated=json.loads(response.json()['choices'][0]['message']['content'])
                if not isinstance(generated,dict): raise ValueError('Expected object')
                content={'generated_summary':generated,'stored_facts':content,'review_required':True};method='AI_MODEL'
        except Exception:
            failure='AI unavailable. Showing factual stored-record digest.'
    else: failure='AI is not configured. Showing factual stored-record digest.'
    s=HistorySummary(patient_id=pid,content=content,source_refs=refs,method=method,status='UNREVIEWED',created_by=user.id,source='AI' if method=='AI_MODEL' else 'SYSTEM')
    db.add(s);db.flush();audit(db,user,pid,'GENERATE_SUMMARY',s.id);db.commit();return dict(serial(s),notice=failure)

@router.get('/summaries/{pid}')
def summaries(pid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    patient_access(db,user,pid)
    return [serial(s) for s in db.query(HistorySummary).filter_by(patient_id=pid).order_by(HistorySummary.created_at.desc())]

class InventoryCreate(BaseModel):
    medicine_name:str=Field(min_length=1)
    dosage_form:str=Field(min_length=1)
    stock_quantity:int=Field(default=0,ge=0)
    low_stock_threshold:int=Field(default=10,ge=0)
    price:float=Field(default=0,ge=0)

@router.post('/inventory')
def inventory_create(body:InventoryCreate,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'PHARMACY');ph=entity(db,user,PharmacyStore)
    if db.query(Inventory).filter_by(pharmacy_id=ph.id,medicine_name=body.medicine_name).first(): raise HTTPException(409,'Medicine already exists; restock instead')
    i=Inventory(pharmacy_id=ph.id,**body.model_dump());db.add(i);db.commit();return serial(i)

@router.get('/consultations/{cid}/clinical-records')
def clinical_records(cid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    c=encounter_access(db,user,cid)
    plan=db.get(ConsultationPlan,cid)
    note=db.query(DoctorNote).filter_by(consultation_id=cid).first()
    rx_list=db.query(Prescription).filter_by(consultation_id=cid).all()
    ref_list=db.query(Referral).filter_by(consultation_id=cid).all()
    med_list=db.query(Medication).filter_by(consultation_id=cid).all()
    return {
        'diagnoses':[serial(d) for d in db.query(Diagnosis).filter_by(consultation_id=cid)],
        'vitals':[serial(v) for v in db.query(Vital).filter_by(consultation_id=cid)],
        'plan': plan.content if plan else None,
        'finalized_at': plan.finalized_at.isoformat() if (plan and plan.finalized_at) else None,
        'doctor_note': {
            'confirmed_diagnosis': note.confirmed_diagnosis,
            'clinical_observations': note.clinical_observations,
            'treatment_plan': note.treatment_plan
        } if note else None,
        'prescriptions': [serial(p) for p in rx_list],
        'medications': [serial(m) for m in med_list],
        'referrals': [dict(serial(r), hospital_name=db.get(Hospital, r.hospital_id).name if r.hospital_id and db.get(Hospital, r.hospital_id) else r.name) for r in ref_list]
    }

class ProviderUpdate(BaseModel):
    address:str
    city:Optional[str]=None
    latitude:Optional[float]=None
    longitude:Optional[float]=None

@router.patch('/provider-profile')
def provider_update(body:ProviderUpdate,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'DOCTOR','HOSPITAL_ADMIN','PHARMACY')
    if (body.latitude is None)!=(body.longitude is None): raise HTTPException(400,'Enter both coordinates')
    if body.latitude is not None and not (-90<=body.latitude<=90 and -180<=body.longitude<=180): raise HTTPException(400,'Coordinates out of range')
    if user.role=='DOCTOR':
        d=entity(db,user,Doctor)
        row=d.clinic
        if not row: raise HTTPException(409,'Clinic association missing')
        d.clinic_address=body.address
    else: row=entity(db,user,Hospital if user.role=='HOSPITAL_ADMIN' else PharmacyStore)
    row.address=body.address
    if body.city is not None: row.city=body.city
    row.latitude=body.latitude;row.longitude=body.longitude
    audit(db,user,None,'UPDATE_PROVIDER',row.id);db.commit();return {'saved':True}

@router.get('/record-documents/{pid}')
def generated_documents(pid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    patient_access(db,user,pid)
    result=[]
    for model,category in [(Prescription,'PRESCRIPTION'),(Referral,'REFERRAL'),(Admission,'DISCHARGE')]:
        q=db.query(model).filter_by(patient_id=pid)
        if category=='DISCHARGE': q=q.filter_by(status='DISCHARGED')
        for record in q:
            result.append({'id':record.id,'category':category,'title':category.replace('_',' ').title()+' · '+record.id[:8],
                'created_at':record.created_at.isoformat(),'content':serial(record)})
    audit(db,user,pid,'VIEW_RECORD_DOCUMENTS',pid);db.commit();return result
