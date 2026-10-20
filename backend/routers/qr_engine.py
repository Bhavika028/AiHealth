"""Identification QR codes contain no medical history. Consent is a separate workflow."""
import io, base64, qrcode, html
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Patient, Doctor, Hospital, PharmacyStore
from ..security import current_user, patient_access
router=APIRouter(prefix='/api/qr',tags=['QR identification'])
def generate_qr_base64_image(payload_text: str, fill_color: tuple = (15, 23, 42), back_color: tuple = (255, 255, 255)) -> str:
    """Generate high quality QR code and return as Base64 Data URL."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload_text)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color)
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"



@router.get('/generate/{patient_id}/{qr_type}')
def get_patient_qr(patient_id:str,qr_type:str,request:Request,db:Session=Depends(get_db),user=Depends(current_user)):
    if qr_type not in ('identity','patient'):
        raise HTTPException(400,'Only patient identification QR is supported here')
    p=patient_access(db,user,patient_id)
    if user.role != 'PATIENT' or p.user_id != user.id:
        raise HTTPException(403,'Only the patient can issue their identification QR')
    payload=f'PULSESYNC:IDENTITY:{p.id}'
    return {'success':True,'patient_id':p.id,'patient_name':p.full_name,'qr_type':qr_type,'token_payload':payload,
      'web_url':None,'qr_image_base64':generate_qr_base64_image(payload),'notice':'Identification only. Patient consent or assigned care relationship is required for clinical access.'}

def view_patient_public_card(patient_id:str,db:Session):
    return HTMLResponse('<!doctype html><title>PulseSync identification</title><h1>Patient identification</h1><p>Sign in to PulseSync and obtain patient consent to access records.</p><a href="/">Open portal</a>',status_code=403)

def view_insurance_public_card(patient_id:str,db:Session):
    return HTMLResponse('<!doctype html><title>PulseSync insurance</title><p>Insurance records require authorized sign-in.</p><a href="/">Open portal</a>',status_code=403)

@router.get('/patient/{patient_id}')
def protected_patient_card(patient_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    return patient_access(db,user,patient_id).to_dict()

@router.get('/insurance/{patient_id}')
def protected_insurance_card(patient_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    p=patient_access(db,user,patient_id)
    return {'provider':p.insurance_provider,'policy_number':p.insurance_policy_no,'claimed':p.insurance_claimed}

@router.get('/doctor/{doctor_id}')
def doctor_qr(doctor_id:str,request:Request,db:Session=Depends(get_db),user=Depends(current_user)):
    return provider_qr(db,Doctor,doctor_id,request,'doctor',user)

@router.get('/hospital/{hospital_id}')
def hospital_qr(hospital_id:str,request:Request,db:Session=Depends(get_db),user=Depends(current_user)):
    return provider_qr(db,Hospital,hospital_id,request,'hospital',user)

@router.get('/pharmacy/{pharmacy_id}')
def pharmacy_qr(pharmacy_id:str,request:Request,db:Session=Depends(get_db),user=Depends(current_user)):
    return provider_qr(db,PharmacyStore,pharmacy_id,request,'pharmacy',user)

def provider_qr(db,model,identifier,request,kind,user):
    row=db.get(model,identifier)
    if not row: raise HTTPException(404,'Provider not found')
    if row.user_id != user.id: raise HTTPException(403,'Cannot generate QR for another provider')
    url=str(request.base_url).rstrip('/')+f'/qr/{kind}/{identifier}'
    return {'success':True,'token_payload':url,'web_url':url,'qr_image_base64':generate_qr_base64_image(url)}

@router.get('/identify/{patient_id}')
def identify(patient_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    if user.role not in ('DOCTOR','HOSPITAL_ADMIN','PHARMACY'):
        raise HTTPException(403,'Provider sign-in required')
    p=db.get(Patient,patient_id)
    if not p or not p.user_id: raise HTTPException(404,'Patient identification unavailable')
    return {'patient_id':p.id,'patient_name':p.full_name,'authorization':'REQUIRED'}
