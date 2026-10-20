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



from pydantic import BaseModel
from ..pin_security import verify_pin, check_lock
from ..workflow_models import Medication, Vital, Diagnosis, Allergy

class PinUnlockRequest(BaseModel):
    pin: str

@router.get('/generate/{patient_id}/{qr_type}')
def get_patient_qr(patient_id:str,qr_type:str,request:Request,db:Session=Depends(get_db),user=Depends(current_user)):
    if qr_type not in ('identity','patient','PROFILE_INTAKE'):
        raise HTTPException(400,'Only patient identification QR is supported here')
    p=patient_access(db,user,patient_id)
    if user.role != 'PATIENT' or p.user_id != user.id:
        raise HTTPException(403,'Only the patient can issue their identification QR')
    url = str(request.base_url).rstrip('/') + f'/qr/patient/{p.id}'
    payload = url
    return {'success':True,'patient_id':p.id,'patient_name':p.full_name,'qr_type':qr_type,'token_payload':payload,
      'web_url':url,'qr_image_base64':generate_qr_base64_image(payload),'notice':'Identification only. Patient consent or assigned care relationship is required for clinical access.'}

def view_patient_public_card(patient_id:str,db:Session):
    p = db.get(Patient, patient_id)
    if not p:
        return HTMLResponse('<!doctype html><title>Patient Not Found</title><h1>Patient Not Found</h1>', status_code=404)
    allergies = ", ".join(p.allergies or []) or "None reported"
    conditions = ", ".join(p.existing_conditions or []) or "None reported"
    emergency_contact = f"{p.emergency_contact_name or 'Not specified'} ({p.emergency_contact_phone or 'No phone'})"
    
    html_content = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PulseSync Digital Health ID - {html.escape(p.full_name)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  body {{ background: #f1f5f9; padding: 20px; color: #1e293b; line-height: 1.5; }}
  .card {{ max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1); overflow: hidden; }}
  .header {{ background: linear-gradient(135deg, #0284c7, #0f172a); color: #fff; padding: 24px; text-align: center; }}
  .header h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; letter-spacing: 0.5px; }}
  .header p {{ font-size: 13px; opacity: 0.85; }}
  .body {{ padding: 20px; }}
  .badge {{ display: inline-block; background: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 9999px; font-size: 13px; font-weight: 600; }}
  .blood-badge {{ background: #fee2e2; color: #b91c1c; font-weight: 700; font-size: 15px; padding: 4px 12px; }}
  .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 16px 0; }}
  .info-item {{ background: #f8fafc; padding: 10px 12px; border-radius: 8px; border: 1px solid #e2e8f0; }}
  .info-item small {{ display: block; font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; margin-bottom: 2px; }}
  .info-item strong {{ font-size: 14px; color: #0f172a; word-break: break-word; }}
  .section {{ margin-top: 16px; border-top: 1px solid #e2e8f0; padding-top: 14px; }}
  .section h2 {{ font-size: 14px; color: #334155; margin-bottom: 8px; font-weight: 700; }}
  .pin-box {{ background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 16px; margin-top: 18px; }}
  .pin-input {{ width: 140px; text-align: center; font-size: 18px; letter-spacing: 5px; padding: 8px; border: 1px solid #94a3b8; border-radius: 8px; }}
  .btn {{ background: #0284c7; color: white; border: none; padding: 10px 16px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; }}
  .btn:hover {{ background: #0369a1; }}
  .actions {{ margin-top: 20px; text-align: center; }}
  .actions a {{ color: #0284c7; text-decoration: none; font-size: 14px; font-weight: 600; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>PulseSync HealthFlow</h1>
    <p>Official Patient Identification Card</p>
  </div>
  <div class="body">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px;">
      <div>
        <h2 style="font-size: 20px; color:#0f172a;">{html.escape(p.full_name)}</h2>
        <span class="badge">Patient ID: {html.escape(p.id)}</span>
      </div>
      <span class="badge blood-badge">{html.escape(p.blood_group or 'Unknown')}</span>
    </div>

    <div class="info-grid">
      <div class="info-item"><small>Age / Gender</small><strong>{p.age or 'N/A'} yrs · {html.escape(p.gender or 'N/A')}</strong></div>
      <div class="info-item"><small>City</small><strong>{html.escape(p.city or 'Not recorded')}</strong></div>
      <div class="info-item" style="grid-column: span 2;"><small>Emergency Contact</small><strong>{html.escape(emergency_contact)}</strong></div>
      <div class="info-item" style="grid-column: span 2;"><small>Insurance</small><strong>{html.escape(p.insurance_provider or 'No insurance recorded')} ({html.escape(p.insurance_policy_no or 'N/A')})</strong></div>
    </div>

    <div class="section">
      <h2>Allergies & Medical Alerts</h2>
      <p style="font-size: 14px; color: #475569;">{html.escape(allergies)}</p>
    </div>

    <div class="section">
      <h2>Reported Chronic Conditions</h2>
      <p style="font-size: 14px; color: #475569;">{html.escape(conditions)}</p>
    </div>

    <div class="pin-box">
      <h2 style="color:#1e40af; font-size: 14px; margin-bottom: 6px;">Unlock Complete Medical Records</h2>
      <p style="font-size: 12px; color: #475569; margin-bottom: 10px;">Enter patient 6-digit registration PIN to view active prescriptions, vitals, and recent consultations.</p>
      <div style="display:flex; gap: 8px; align-items:center;">
        <input type="password" id="patient-pin" maxlength="6" pattern="\\d{6}" placeholder="••••••" class="pin-input">
        <button type="button" class="btn" onclick="unlockProfile()">Unlock</button>
      </div>
      <div id="unlock-result" style="margin-top: 12px;"></div>
    </div>

    <div class="actions">
      <a href="/">Open PulseSync Portal & Sign In</a>
    </div>
  </div>
</div>

<script>
async function unlockProfile() {{
  const pin = document.getElementById('patient-pin').value;
  const resBox = document.getElementById('unlock-result');
  if(!/^\\d{{6}}$/.test(pin)) {{
    resBox.innerHTML = '<p style="color:#dc2626;font-size:13px;">Please enter valid 6-digit PIN.</p>';
    return;
  }}
  resBox.innerHTML = '<p style="color:#0284c7;font-size:13px;">Verifying PIN…</p>';
  try {{
    const res = await fetch('/api/qr/patient/{p.id}/unlock', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{pin: pin}})
    }});
    const data = await res.json();
    if(!res.ok) throw new Error(data.detail || 'PIN verification failed');
    
    let html = '<div style="margin-top:10px;padding:12px;background:#fff;border-radius:8px;border:1px solid #cbd5e1;">';
    html += '<h3 style="font-size:14px;color:#0f172a;margin-bottom:6px;">Active Medications (' + data.medications.length + ')</h3>';
    if(data.medications.length) {{
      html += '<ul style="font-size:13px;padding-left:18px;margin-bottom:10px;">' + data.medications.map(m => '<li><strong>' + m.name + '</strong> · ' + (m.frequency || '') + ' · ' + (m.dosage || '') + '</li>').join('') + '</ul>';
    }} else {{
      html += '<p style="font-size:12px;color:#64748b;">No active medicines.</p>';
    }}
    html += '<h3 style="font-size:14px;color:#0f172a;margin-bottom:6px;">Recorded Diagnoses</h3>';
    if(data.diagnoses.length) {{
      html += '<ul style="font-size:13px;padding-left:18px;margin-bottom:10px;">' + data.diagnoses.map(d => '<li>' + d.name + ' (' + d.status + ')</li>').join('') + '</ul>';
    }} else {{
      html += '<p style="font-size:12px;color:#64748b;">None recorded.</p>';
    }}
    html += '</div>';
    resBox.innerHTML = html;
  }} catch(err) {{
    resBox.innerHTML = '<p style="color:#dc2626;font-size:13px;">' + err.message + '</p>';
  }}
}}
</script>
</body>
</html>'''
    return HTMLResponse(html_content, status_code=403)

@router.get('/patient/{patient_id}')
def protected_patient_card(patient_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    return patient_access(db,user,patient_id).to_dict()

@router.post('/patient/{patient_id}/unlock')
def unlock_patient_card(patient_id:str, body:PinUnlockRequest, db:Session=Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or not p.user_id:
        raise HTTPException(404, 'Patient not found')
    user = db.get(User, p.user_id)
    if not user:
        raise HTTPException(404, 'Patient account not found')
    check_lock(db, user)
    verify_pin(db, user, body.pin)
    meds = db.query(Medication).filter_by(patient_id=p.id, status='ACTIVE').all()
    vitals = db.query(Vital).filter_by(patient_id=p.id).order_by(Vital.measured_at.desc()).limit(10).all()
    diagnoses = db.query(Diagnosis).filter_by(patient_id=p.id).all()
    from .workflow import serial
    return {
        'success': True,
        'patient_name': p.full_name,
        'patient_id': p.id,
        'blood_group': p.blood_group,
        'medications': [serial(m) for m in meds],
        'vitals': [serial(v) for v in vitals],
        'diagnoses': [serial(d) for d in diagnoses]
    }

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
