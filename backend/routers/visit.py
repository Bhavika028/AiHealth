"""Consultation drafts and atomic application through the existing completion route."""
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import update
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Patient, Doctor, Hospital, Clinic, Prescription, DoctorNote, Consultation, PharmacyStore
from ..workflow_models import ConsultationPlan, OutpatientAppointment, Medication, Referral, Diagnosis, Vital, Document, FollowUp, MedicalEvent, Allergy, AccessRequest, AccessGrant, ConsultationAuthorization, AuditLog, Notification
from ..security import current_user, encounter_access, entity, require_role, check_daily_visit_limit
from ..pin_security import verify_pin, check_lock
from .workflow import serial, migrate_patient_records, version, event, notify
router=APIRouter(prefix='/api/workflow',tags=['Consultation decisions'])

class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action:Literal['frequency','replace','add']
    medication_id:Optional[str]=None
    name:str=''
    times_per_day:int=Field(ge=1,strict=True)
    food:Optional[Literal['Before food','After food','Not specified']]=None
    dosage:Optional[str]=None
    duration_days:Optional[int]=Field(default=None,ge=1,le=3650)
    timing:Optional[str]=None
    reason:Optional[str]=None
    quantity:Optional[int]=Field(default=None,ge=1,le=10000,strict=True)
    pharmacy_id:Optional[str]=None

class Destination(BaseModel):
    hospital_id:Optional[str]=None
    name:str=''
    address:str=''
    reason:str=Field(min_length=1)
    specialty:str='Not specified'
    priority:Literal['ROUTINE','URGENT','EMERGENCY']='ROUTINE'
    preferred_at:Optional[datetime]=None
    clinical_summary:str=Field(min_length=1)

class Plan(BaseModel):
    revision:int=0
    observations:str=''
    assessment:str=''
    advice:str=''
    medications:list[Decision]=Field(default_factory=list,max_length=50)
    referrals:list[Destination]=Field(default_factory=list,max_length=20)
    acknowledge_warnings:bool=False


def warnings_and_validate(db,c,plan):
    p=db.get(Patient,c.patient_id); migrate_patient_records(db,p)
    active=db.query(Medication).filter_by(patient_id=p.id,status='ACTIVE').all()
    seen=set(); names={m.name.strip().casefold():m.id for m in active}; warnings=[]
    allergies=list(p.allergies or [])+[a.substance for a in db.query(Allergy).filter_by(patient_id=p.id,status='ACTIVE')]
    for m in plan.medications:
        if m.action!='add':
            old=db.get(Medication,m.medication_id)
            if not old or old.patient_id!=p.id or old.status!='ACTIVE': raise HTTPException(409,'Selected medication is no longer active; reload and review')
            if old.id in seen: raise HTTPException(422,'Only one decision per existing medication')
            seen.add(old.id)
        if m.action!='frequency':
            if not m.name.strip(): raise HTTPException(422,'Medicine name is required')
            key=m.name.strip().casefold()
            if key in names and names[key]!=m.medication_id: warnings.append('Duplicate active medicine: '+m.name)
            names[key]=m.medication_id or 'new'
            if any(str(a).lower() in key or key in str(a).lower() for a in allergies if a): warnings.append('Possible allergy conflict: '+m.name)
            if m.pharmacy_id and not m.quantity: raise HTTPException(422,'A pharmacy dispensing order requires an explicit quantity')
            if m.pharmacy_id and not db.get(PharmacyStore,m.pharmacy_id): raise HTTPException(422,'Unknown pharmacy')
    destinations=set()
    for r in plan.referrals:
        key=(r.hospital_id or r.name.strip().casefold(),r.reason.strip(),r.preferred_at)
        if key in destinations: raise HTTPException(422,'Duplicate referral in this check-up; remove the repeated decision')
        destinations.add(key)
        if r.hospital_id:
            h=db.get(Hospital,r.hospital_id)
            if not h or not h.is_active or not h.user_id: raise HTTPException(422,'Registered hospital account unavailable')
        elif not r.name.strip() or not r.address.strip(): raise HTTPException(422,'External hospital name and address required')
    return warnings

@router.get('/consultations/{cid}/plan')
def get_plan(cid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'DOCTOR');c=encounter_access(db,user,cid,True)
    migrate_patient_records(db,db.get(Patient,c.patient_id));db.commit()
    row=db.get(ConsultationPlan,cid)
    legacy=db.query(DoctorNote).filter_by(consultation_id=cid).first()
    initial={'observations':legacy.clinical_observations or '' if legacy else (c.branch_responses or {}).get('clinical_observations',''),'assessment':legacy.confirmed_diagnosis if legacy else '', 'advice':legacy.treatment_plan or '' if legacy else ''}
    facility=db.get(Clinic,c.clinic_id) if c.clinic_id else db.get(Hospital,c.hospital_id) if c.hospital_id else None
    return {'location':{'label':facility.name if facility else 'No facility location recorded','latitude':facility.latitude if facility else None,'longitude':facility.longitude if facility else None},'patient_name':c.patient.full_name,'patient_id':c.patient_id,'content':row.content if row else initial,'revision':row.revision if row else 0,'finalized':bool(row and row.finalized_at),'medications':[serial(m) for m in db.query(Medication).filter_by(patient_id=c.patient_id,status='ACTIVE')]}

@router.put('/consultations/{cid}/plan')
def save_plan(cid:str,body:Plan,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'DOCTOR');c=encounter_access(db,user,cid,True)
    if c.status in ('COMPLETED','CANCELLED','NO_SHOW'): raise HTTPException(409,'This consultation is closed')
    # Serialize draft writes with completion, including the first draft insertion.
    claimed=db.execute(update(Consultation).where(Consultation.id==cid,Consultation.status.notin_(['COMPLETED','CANCELLED','NO_SHOW'])).values(updated_at=datetime.utcnow())).rowcount
    if not claimed: raise HTTPException(409,'Consultation closed concurrently; reload')
    warnings=warnings_and_validate(db,c,body)
    content=body.model_dump(mode='json',exclude={'revision'})
    for referral in content['referrals']:
        if referral['hospital_id']:
            hospital=db.get(Hospital,referral['hospital_id']);referral.update(name=hospital.name,address=hospital.address or '')
    row=db.get(ConsultationPlan,cid)
    if row:
        changed=db.execute(update(ConsultationPlan).where(ConsultationPlan.consultation_id==cid,ConsultationPlan.revision==body.revision,ConsultationPlan.finalized_at.is_(None)).values(content=content,revision=body.revision+1)).rowcount
        if not changed: raise HTTPException(409,'Draft changed in another window; reopen it')
    else:
        if body.revision: raise HTTPException(409,'Draft revision does not exist')
        db.add(ConsultationPlan(consultation_id=cid,content=content,revision=1))
    from sqlalchemy.exc import IntegrityError
    try: db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Draft changed concurrently; reopen it')
    return {'revision':body.revision+1,'warnings':warnings}


def apply_plan(db,user,c):
    """Caller owns the transaction. No partial medication/referral commits."""
    row=db.query(ConsultationPlan).filter_by(consultation_id=c.id).with_for_update().first()
    if not row or row.finalized_at: return
    plan=Plan(**row.content)
    warnings=warnings_and_validate(db,c,plan)
    if warnings and not plan.acknowledge_warnings: raise HTTPException(409,{'message':'Review warnings in Doctor’s Note and acknowledge before finalizing','warnings':warnings})
    changes=[]
    for m in plan.medications:
        old=db.get(Medication,m.medication_id) if m.action!='add' else None
        before=serial(old) if old else None
        instructions=dict(old.instructions or {}) if old and m.action=='frequency' else {}
        instructions.update(times_per_day=m.times_per_day)
        if m.food is not None: instructions['food']=m.food
        instructions.setdefault('food','Not specified')
        frequency=f'{m.times_per_day} times per day'
        if m.action=='frequency':
            # Version clinical instructions; never rewrite a dispensed prescription.
            old.status='CHANGED';version(db,user,old,before,'Frequency amendment')
            new=Medication(patient_id=c.patient_id,doctor_id=c.doctor_id,consultation_id=c.id,name=old.name,dosage=old.dosage,frequency=frequency,start_date=old.start_date,end_date=old.end_date,duration_days=old.duration_days,instructions=instructions,reason=old.reason,source=old.source,created_by=user.id)
        else:
            if old:
                old.status='DISCONTINUED';version(db,user,old,before,m.reason or 'Medication replacement')
            instructions.update(timing=m.timing,dosage=m.dosage,duration_days=m.duration_days,reason=m.reason)
            new=Medication(patient_id=c.patient_id,doctor_id=c.doctor_id,consultation_id=c.id,name=m.name.strip(),dosage=m.dosage,frequency=frequency,start_date=date.today(),duration_days=m.duration_days,end_date=date.today()+timedelta(days=m.duration_days-1) if m.duration_days else None,instructions=instructions,created_by=user.id)
        meddata=dict(instructions,name=new.name,dosage=new.dosage,frequency=frequency,duration_days=new.duration_days)
        # Instruction amendments do not silently create refill quantities.
        rx=Prescription(patient_id=c.patient_id,doctor_id=c.doctor_id,consultation_id=c.id,medicines=[dict(meddata,**({'quantity':m.quantity} if m.quantity else {}))],pharmacy_id=m.pharmacy_id if m.action!='frequency' else None,status='PENDING' if m.action!='frequency' and m.quantity else 'INSTRUCTIONS_ONLY',notes='Consultation medication decision; no refill for instructions-only amendments')
        db.add(rx);db.flush();new.prescription_id=rx.id;db.add(new);db.flush()
        # Supersede unfilled items for this medication, leaving other items and dispensing history intact.
        if old and old.prescription_id:
            previous=db.get(Prescription,old.prescription_id)
            if previous and previous.status=='PENDING':
                prior=serial(previous)
                previous.medicines=[(dict(x,frequency=frequency,food=instructions['food'],times_per_day=m.times_per_day) if m.action=='frequency' else dict(x,discontinued=True)) if x.get('name','').casefold()==old.name.casefold() else x for x in previous.medicines]
                if all(x.get('discontinued') for x in previous.medicines): previous.status='SUPERSEDED'
                version(db,user,previous,prior,'Superseded medication instructions')
        changes.append({'action':m.action,'previous':before,'revised':serial(new),'reason':m.reason})
        event(db,user,c.patient_id,'PRESCRIPTION','Medication instructions updated',rx.id,c,{'medicines':rx.medicines})
        if m.pharmacy_id: notify(db,c.patient_id,'Medication instructions ready',rx.id,user_id=db.get(PharmacyStore,m.pharmacy_id).user_id)
    for r in plan.referrals:
        if not r.hospital_id: continue # External letter is retained in the finalized plan, without fake booking.
        h=db.get(Hospital,r.hospital_id)
        ref=Referral(patient_id=c.patient_id,consultation_id=c.id,doctor_id=c.doctor_id,source_facility_id=c.hospital_id or c.clinic_id,hospital_id=h.id,specialty=r.specialty,reason=r.reason,clinical_summary=r.clinical_summary,priority=r.priority,status='SENT',created_by=user.id)
        db.add(ref);db.flush()
        ap=OutpatientAppointment(referral_id=ref.id,consultation_id=c.id,patient_id=c.patient_id,hospital_id=h.id,doctor_id=c.doctor_id,preferred_at=r.preferred_at.replace(tzinfo=None) if r.preferred_at else None,status='REQUESTED',created_by=user.id)
        db.add(ap);db.flush()
        event(db,user,c.patient_id,'REFERRAL','Referral to '+h.name,ref.id,c,{'reason':r.reason})
        notify(db,c.patient_id,'Appointment requested / Pending hospital confirmation: '+h.name,ap.id)
        notify(db,c.patient_id,'Incoming outpatient appointment request',ap.id,user_id=h.user_id)
    n=db.query(DoctorNote).filter_by(consultation_id=c.id).first()
    if not n:
        n=DoctorNote(consultation_id=c.id,doctor_id=c.doctor_id,patient_id=c.patient_id,confirmed_diagnosis=plan.assessment or 'No additional assessment recorded');db.add(n)
    if plan.assessment: n.confirmed_diagnosis=plan.assessment
    n.clinical_observations=plan.observations;n.treatment_plan=plan.advice;n.is_finalized=True
    db.flush()
    snapshot=[serial(m) for m in db.query(Medication).filter_by(patient_id=c.patient_id,status='ACTIVE')]
    row.content=dict(row.content,changes=changes,warnings=warnings,active_medications=snapshot);row.finalized_at=datetime.utcnow()
    notify(db,c.patient_id,'Complete check-up record available',c.id)

@router.get('/outpatient-appointments')
def appointments(db:Session=Depends(get_db),user=Depends(current_user)):
    q=db.query(OutpatientAppointment)
    if user.role=='PATIENT':q=q.filter_by(patient_id=entity(db,user,Patient).id)
    elif user.role=='DOCTOR':q=q.filter_by(doctor_id=entity(db,user,Doctor).id)
    elif user.role=='HOSPITAL_ADMIN':q=q.filter_by(hospital_id=entity(db,user,Hospital).id)
    else:raise HTTPException(403,'Clinical role required')
    return [dict(serial(a),hospital_name=db.get(Hospital,a.hospital_id).name,patient_name=db.get(Patient,a.patient_id).full_name) for a in q]

class AppointmentResponse(BaseModel):
    status:Literal['CONFIRMED','RESCHEDULED','DECLINED']
    scheduled_at:Optional[datetime]=None
    reason:str=Field(min_length=1)
    revision:int

@router.patch('/outpatient-appointments/{aid}')
def respond(aid:str,body:AppointmentResponse,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'HOSPITAL_ADMIN');a=db.query(OutpatientAppointment).filter_by(id=aid).with_for_update().first()
    if not a:raise HTTPException(404,'Appointment not found')
    if a.hospital_id!=entity(db,user,Hospital).id:raise HTTPException(403,'Appointment belongs to another hospital')
    # revision is the response-event count; conditional update prevents repeated notifications.
    rev=db.query(MedicalEvent).filter_by(resource_id=a.id,kind='APPOINTMENT_RESPONSE').count()
    if body.revision!=rev:raise HTTPException(409,'Appointment changed; reload')
    if body.status!='DECLINED' and not body.scheduled_at:raise HTTPException(422,'Confirmed or rescheduled time required')
    if a.status==body.status and a.scheduled_at==(body.scheduled_at.replace(tzinfo=None) if body.scheduled_at else None) and a.response==body.reason:return serial(a)
    a.status=body.status;a.scheduled_at=body.scheduled_at.replace(tzinfo=None) if body.scheduled_at else None;a.response=body.reason
    ref=db.get(Referral,a.referral_id);ref.status='DECLINED' if a.status=='DECLINED' else 'ACCEPTED'
    event(db,user,a.patient_id,'APPOINTMENT_RESPONSE','Appointment '+a.status.lower(),a.id,db.get(Consultation,a.consultation_id),{'reason':body.reason},dedupe='appointment:'+a.id+':'+str(rev+1))
    notify(db,a.patient_id,'Hospital appointment '+a.status.lower()+': '+body.reason,a.id)
    notify(db,a.patient_id,'Hospital appointment '+a.status.lower()+': '+body.reason,a.id,user_id=db.get(Doctor,a.doctor_id).user_id)
    from sqlalchemy.exc import IntegrityError
    try: db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Appointment changed concurrently; reload')
    return serial(a)

@router.get('/consultations/{cid}/complete-record')
def complete_record(cid:str,db:Session=Depends(get_db),user=Depends(current_user)):
    c=encounter_access(db,user,cid)
    if c.status!='COMPLETED':raise HTTPException(403,'Only finalized records are available')
    plan=db.get(ConsultationPlan,cid);doc=db.get(Doctor,c.doctor_id) if c.doctor_id else None
    facility=db.get(Hospital,c.hospital_id) if c.hospital_id else db.get(Clinic,c.clinic_id) if c.clinic_id else None
    notes=db.query(DoctorNote).filter_by(consultation_id=cid,is_finalized=True).all()
    aps=db.query(OutpatientAppointment).filter_by(consultation_id=cid).all()
    return {'visit':{'id':c.id,'date':c.created_at.isoformat(),'patient':c.patient.full_name,'doctor':doc.full_name if doc else None,'facility':facility.name if facility else None,'complaint':c.chief_complaint,'symptoms':c.patient_notes,'duration':str(c.symptom_duration_value or '')+' '+str(c.symptom_duration_unit or ''),'severity':c.symptom_severity,'warning_symptoms':c.warning_symptoms or [],'intake':{__import__('re').sub(r'^q[a-z]*[0-9]+_', '',k).replace('_',' ').capitalize():v for k,v in (c.branch_responses or {}).items() if isinstance(v,(str,int,float,bool)) and v!='' and k!='clinical_observations'},'observations':(c.branch_responses or {}).get('clinical_observations')},
      'note':plan.content if plan and plan.finalized_at else {},'legacy_notes':[{'assessment':n.confirmed_diagnosis,'observations':n.clinical_observations,'advice':n.treatment_plan,'follow_up':n.follow_up_instructions,'vitals':{key:getattr(n,key) for key in ('vital_bp','vital_pulse','vital_temperature','vital_spo2','vital_glucose') if getattr(n,key) is not None}} for n in notes],
      'diagnoses':[serial(x) for x in db.query(Diagnosis).filter_by(consultation_id=cid)],'vitals':[serial(x) for x in db.query(Vital).filter_by(consultation_id=cid)],'prescriptions':[serial(x) for x in db.query(Prescription).filter_by(consultation_id=cid)],
      'referrals':[dict(serial(x),hospital_name=db.get(Hospital,x.hospital_id).name) for x in db.query(Referral).filter_by(consultation_id=cid)],
      'appointments':[dict(serial(x),revision=db.query(MedicalEvent).filter_by(resource_id=x.id,kind='APPOINTMENT_RESPONSE').count(),hospital_name=db.get(Hospital,x.hospital_id).name) for x in aps],
      'documents':[serial(x) for x in db.query(Document).filter_by(consultation_id=cid)],'follow_up':[serial(x) for x in db.query(FollowUp).filter_by(consultation_id=cid)]}


@router.get('/external-referrals')
def external_referrals(db:Session=Depends(get_db),user=Depends(current_user)):
    q=db.query(Consultation).filter_by(status='COMPLETED')
    if user.role=='PATIENT': q=q.filter_by(patient_id=entity(db,user,Patient).id)
    elif user.role=='DOCTOR': q=q.filter_by(doctor_id=entity(db,user,Doctor).id)
    else: raise HTTPException(403,'Patient or referring doctor required')
    result=[]
    for c in q:
        plan=db.get(ConsultationPlan,c.id)
        if plan and plan.finalized_at:
            for index,r in enumerate(plan.content.get('referrals',[])):
                if not r.get('hospital_id'):result.append(dict(r,consultation_id=c.id,index=index,patient_name=c.patient.full_name))
    return result

class PatientScanDoctorConsultation(BaseModel):
    doctor_id: str
    pin: str
    chief_complaint: str
    severity: Optional[str] = "Moderate"
    patient_notes: Optional[str] = ""

@router.post('/consultations/patient-scan-doctor')
def patient_scan_doctor(body: PatientScanDoctorConsultation, db: Session = Depends(get_db), user = Depends(current_user)):
    require_role(user, 'PATIENT')
    patient = entity(db, user, Patient)
    check_lock(db, user)
    verify_pin(db, user, body.pin)

    doctor = db.get(Doctor, body.doctor_id)
    if not doctor or not doctor.user_id:
        raise HTTPException(404, 'Doctor not found')

    check_daily_visit_limit(db, patient.id, is_urgent=(body.severity == 'Severe'))

    import secrets, hashlib
    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=60)

    r = AccessRequest(
        patient_id=patient.id,
        provider_user_id=doctor.user_id,
        scope='CLINICAL',
        expires_at=expires_at,
        status='APPROVED'
    )
    db.add(r)
    db.flush()

    token_hash = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    g = AccessGrant(
        patient_id=patient.id,
        user_id=doctor.user_id,
        scope='CLINICAL',
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(g)
    db.flush()
    r.grant_id = g.id

    c = Consultation(
        patient_id=patient.id,
        doctor_id=doctor.id,
        clinic_id=doctor.clinic_id,
        hospital_id=doctor.hospital_id,
        created_by=user.id,
        chief_complaint=body.chief_complaint.strip() or 'General Consultation',
        symptom_severity=body.severity or 'Moderate',
        patient_notes=body.patient_notes or '',
        status='WAITING'
    )
    db.add(c)
    db.flush()

    db.add(ConsultationAuthorization(
        consultation_id=c.id,
        request_id=r.id,
        patient_id=patient.id,
        provider_user_id=doctor.user_id
    ))

    db.add(AuditLog(user_id=user.id, patient_id=patient.id, action='PATIENT_AUTHORIZED_CONSULTATION_PIN', resource=c.id))
    db.add(Notification(user_id=doctor.user_id, patient_id=patient.id, message=f'Patient {patient.full_name} scanned your QR, verified PIN, and started consultation: {c.chief_complaint}', resource_id=c.id))
    db.commit()

    return {
        'success': True,
        'consultation_id': c.id,
        'doctor_name': doctor.full_name,
        'status': c.status,
        'message': f'Consultation authorized with PIN and started with Dr. {doctor.full_name}.'
    }

