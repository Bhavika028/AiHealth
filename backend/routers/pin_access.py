"""Authenticated PIN management and provider-specific patient approval."""
from datetime import datetime,timedelta
import secrets,hashlib
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy.orm import Session
from sqlalchemy import update
from ..database import get_db
from ..models import User,Patient,Doctor,Hospital,PharmacyStore
from ..workflow_models import AccessRequest,AccessGrant,Notification,AuditLog
from ..security import current_user,require_role,entity
from ..pin_security import validate_new_pin,hash_pin,verify_pin,check_lock,failed
from .auth import verify_password
router=APIRouter(prefix='/api/security',tags=['PIN and consent requests'])

class PinBody(BaseModel):
    pin:str
    confirm_pin:str
    password:str=''
    current_pin:str=''
    action:Literal['setup','change','reset']='setup'

@router.get('/pin')
def pin_status(db:Session=Depends(get_db),user=Depends(current_user)):
    return {'has_pin':bool(user.pin_hash),'locked_until':user.pin_locked_until}

@router.post('/pin')
def manage_pin(body:PinBody,db:Session=Depends(get_db),user=Depends(current_user)):
    check_lock(db,user);validate_new_pin(body.pin,body.confirm_pin)
    if body.action=='setup' and user.pin_hash: raise HTTPException(409,'PIN already exists; choose change or reset')
    if body.action=='change': verify_pin(db,user,body.current_pin)
    # Setup/reset require fresh password proof in addition to authenticated session.
    if not verify_password(body.password,user.password_hash): failed(db,user)
    # Resetting a patient PIN invalidates existing access grants and pending requests.
    if body.action == 'reset' and user.role == 'PATIENT':
        patient = entity(db, user, Patient)
        now = datetime.utcnow()
        db.execute(update(AccessGrant).where(AccessGrant.patient_id == patient.id,
                    AccessGrant.revoked_at.is_(None)).values(revoked_at=now))
        db.execute(update(AccessRequest).where(AccessRequest.patient_id == patient.id,
                    AccessRequest.status.in_(['PENDING', 'APPROVED'])).values(status='REVOKED'))
        db.add(AuditLog(user_id=user.id, patient_id=patient.id,
                        action='CONSENT_REVOKED_AFTER_PIN_RESET'))
    user.pin_hash=hash_pin(body.pin);user.pin_failures=0;user.pin_locked_until=None
    db.add(AuditLog(user_id=user.id,action='PIN_'+body.action.upper()))
    db.add(Notification(user_id=user.id,message='Your account PIN was '+body.action+' successfully.'))
    db.commit();return {'success':True}

class RequestBody(BaseModel):
    patient_id:str
    minutes:int=Field(default=30,ge=1,le=1440)

class Decision(BaseModel):
    action:Literal['approve','deny','revoke']
    pin:str=''

def state(db,r):
    g=db.get(AccessGrant,r.grant_id) if r.grant_id else None
    if g and g.revoked_at:return 'REVOKED'
    if r.status in ('PENDING','APPROVED') and r.expires_at<=datetime.utcnow():return 'EXPIRED'
    return r.status

def view(db,r):
    provider=db.get(User,r.provider_user_id);patient=db.get(Patient,r.patient_id)
    return {'id':r.id,'patient_id':r.patient_id,'patient_name':patient.full_name,'provider_user_id':provider.id,'provider_name':provider.name,'provider_role':provider.role,'scope':r.scope,'expires_at':r.expires_at,'status':state(db,r),'grant_id':r.grant_id}

@router.post('/requests')
def request_access(body:RequestBody,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'DOCTOR','HOSPITAL_ADMIN','PHARMACY')
    entity(db,user,{'DOCTOR':Doctor,'HOSPITAL_ADMIN':Hospital,'PHARMACY':PharmacyStore}[user.role])
    patient=db.get(Patient,body.patient_id)
    if not patient or not patient.user_id:raise HTTPException(404,'Patient identity unavailable')
    r=db.query(AccessRequest).filter(AccessRequest.patient_id==patient.id,AccessRequest.provider_user_id==user.id,AccessRequest.status=='PENDING',AccessRequest.expires_at>datetime.utcnow()).first()
    if not r:
        r=AccessRequest(patient_id=patient.id,provider_user_id=user.id,scope='PRESCRIPTION' if user.role=='PHARMACY' else 'CLINICAL',expires_at=datetime.utcnow()+timedelta(minutes=body.minutes))
        db.add(r);db.flush()
        db.add(Notification(user_id=patient.user_id,patient_id=patient.id,message=user.name+' requested '+r.scope+' access. Review in QR access requests.',resource_id=r.id))
        db.add(AuditLog(user_id=user.id,patient_id=patient.id,action='REQUEST_ACCESS',resource=r.id));db.commit()
    return view(db,r)

@router.get('/requests')
def requests(db:Session=Depends(get_db),user=Depends(current_user)):
    q=db.query(AccessRequest)
    q=q.filter(AccessRequest.patient_id==entity(db,user,Patient).id) if user.role=='PATIENT' else q.filter(AccessRequest.provider_user_id==user.id)
    return [view(db,r) for r in q.order_by(AccessRequest.created_at.desc()).limit(100)]

@router.post('/requests/{rid}')
def decide(rid:str,body:Decision,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'PATIENT');patient=entity(db,user,Patient)
    r=db.query(AccessRequest).filter_by(id=rid,patient_id=patient.id).with_for_update().first()
    if not r:raise HTTPException(404,'Access request not found')
    if body.action=='revoke':
        if state(db,r)!='APPROVED':raise HTTPException(409,'Only approved access can be revoked')
        db.get(AccessGrant,r.grant_id).revoked_at=datetime.utcnow();r.status='REVOKED'
    else:
        if state(db,r)!='PENDING':raise HTTPException(409,'Request is no longer pending')
        if body.action=='approve':
            verify_pin(db,user,body.pin)
            changed=db.execute(update(AccessRequest).where(AccessRequest.id==r.id,AccessRequest.status=='PENDING').values(status='APPROVED'),execution_options={'synchronize_session':False})
            if changed.rowcount!=1:
                db.rollback();raise HTTPException(409,'Request already decided')
            g=AccessGrant(patient_id=patient.id,user_id=r.provider_user_id,scope=r.scope,token_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),expires_at=r.expires_at)
            db.add(g);db.flush();r.grant_id=g.id;r.status='APPROVED'
        else:
            changed=db.execute(update(AccessRequest).where(AccessRequest.id==r.id,AccessRequest.status=='PENDING').values(status='DENIED'),execution_options={'synchronize_session':False})
            if changed.rowcount!=1:
                db.rollback();raise HTTPException(409,'Request already decided')
            r.status='DENIED'
    db.add(AuditLog(user_id=user.id,patient_id=patient.id,action='REQUEST_'+r.status,resource=r.id))
    db.add(Notification(user_id=r.provider_user_id,patient_id=patient.id,message='Patient access request: '+r.status,resource_id=r.id))
    db.commit();return view(db,r)
