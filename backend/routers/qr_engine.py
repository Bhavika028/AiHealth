"""Identification QR codes contain no medical history. Consent is a separate workflow."""
import io, base64, qrcode, html
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Patient, Doctor, Hospital, PharmacyStore
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
    valid_types = ('identity','patient','PROFILE_INTAKE','admission','insurance')
    if qr_type not in valid_types:
        raise HTTPException(400, f'Only {valid_types} QR types are supported here')
    p=patient_access(db,user,patient_id)
    if user.role != 'PATIENT':
        raise HTTPException(403,'Only the patient or registered family guardian can issue their patient QR')

    if qr_type == 'admission':
        url = str(request.base_url).rstrip('/') + f'/qr/admission/{p.id}'
        payload = f'PULSESYNC:ADMISSION:{p.id}'
        notice = 'Official Hospital Admission Form & Fast-Track Triage Pass. Present at hospital reception or admitting counter.'
    elif qr_type == 'insurance':
        url = str(request.base_url).rstrip('/') + f'/qr/insurance/{p.id}'
        payload = f'PULSESYNC:INSURANCE:{p.id}'
        notice = 'Digital Health Insurance Verification & Pre-Authorization Pass.'
    else:
        url = str(request.base_url).rstrip('/') + f'/qr/patient/{p.id}'
        payload = f'PULSESYNC:IDENTITY:{p.id}'
        notice = 'Identification only. Patient consent or assigned care relationship is required for clinical access.'

    return {
        'success': True,
        'patient_id': p.id,
        'patient_name': p.full_name,
        'qr_type': qr_type,
        'token_payload': payload,
        'web_url': url,
        'qr_image_base64': generate_qr_base64_image(payload),
        'notice': notice
    }

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


class InsuranceClaimRequest(BaseModel):
    pin: str
    hospital_name: str = "City General Multiservice Hospital"
    treatment_reason: str = "Medical Treatment"
    estimated_amount: float = 0.0

@router.post('/insurance/{patient_id}/claim')
def submit_insurance_claim(patient_id: str, body: InsuranceClaimRequest, db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or not p.user_id:
        raise HTTPException(404, 'Patient not found')
    user = db.get(User, p.user_id)
    if not user:
        raise HTTPException(404, 'Patient user account not found')
    check_lock(db, user)
    verify_pin(db, user, body.pin)
    p.insurance_claimed = True
    db.commit()
    return {
        'success': True,
        'message': f'Pre-authorization request filed with {p.insurance_provider or "Insurance Provider"} (Policy: {p.insurance_policy_no or "Registered"}). Status: Claim in progress.',
        'provider': p.insurance_provider,
        'policy_number': p.insurance_policy_no,
        'claimed': True
    }

@router.get('/admission/{patient_id}')
def get_admission_prefill(patient_id: str, db: Session = Depends(get_db), user = Depends(current_user)):
    p = patient_access(db, user, patient_id)
    from ..models import Consultation
    consult = db.query(Consultation).filter(Consultation.patient_id == patient_id).order_by(Consultation.created_at.desc()).first()
    return {
        'patient_id': p.id,
        'patient_name': p.full_name,
        'age': p.age,
        'gender': p.gender,
        'blood_group': p.blood_group,
        'emergency_contact': f"{p.emergency_contact_name or 'N/A'} ({p.emergency_contact_phone or 'N/A'})",
        'guardian': f"{p.parent_guardian_name or 'N/A'} ({p.parent_guardian_phone or 'N/A'})",
        'chief_complaint': consult.chief_complaint if consult else 'Acute Medical Admission',
        'severity': consult.symptom_severity if consult else 'Moderate',
        'is_urgent': consult.is_urgent if consult else False,
        'allergies': p.allergies or [],
        'existing_conditions': p.existing_conditions or [],
        'has_insurance': p.has_insurance,
        'insurance_provider': p.insurance_provider,
        'insurance_policy_no': p.insurance_policy_no
    }


def view_insurance_public_card(patient_id: str, db: Session):
    p = db.get(Patient, patient_id)
    if not p:
        return HTMLResponse('<!doctype html><title>Patient Not Found</title><h1>Patient Not Found</h1>', status_code=404)
    provider = p.insurance_provider or "Self-Pay / Not Registered"
    policy_no = p.insurance_policy_no or "None"
    claimed = "Claim Filed / Under Review" if p.insurance_claimed else "Active / No Claim Pending"
    status_color = "#d97706" if p.insurance_claimed else "#059669"
    badge_bg = "#fef3c7" if p.insurance_claimed else "#d1fae5"
    has_ins = p.has_insurance and bool(p.insurance_provider)

    html_content = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PulseSync Digital Health Insurance Card - {html.escape(p.full_name)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  body {{ background: #f0fdf4; padding: 20px; color: #1e293b; line-height: 1.5; }}
  .card {{ max-width: 500px; margin: 0 auto; background: #ffffff; border-radius: 20px; box-shadow: 0 12px 30px -5px rgba(5,150,105,0.15); overflow: hidden; border: 1px solid #bbf7d0; }}
  .header {{ background: linear-gradient(135deg, #059669, #065f46); color: #fff; padding: 24px; text-align: center; position: relative; }}
  .header h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
  .header p {{ font-size: 13px; opacity: 0.9; }}
  .body {{ padding: 22px; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
  .policy-chip {{ background: #ecfdf5; border: 1.5px solid #a7f3d0; border-radius: 12px; padding: 14px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }}
  .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 16px 0; }}
  .info-item {{ background: #f8fafc; padding: 10px 12px; border-radius: 10px; border: 1px solid #e2e8f0; }}
  .info-item small {{ display: block; font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; margin-bottom: 2px; }}
  .info-item strong {{ font-size: 14px; color: #0f172a; word-break: break-word; }}
  .section {{ margin-top: 18px; border-top: 1px solid #e2e8f0; padding-top: 16px; }}
  .section h2 {{ font-size: 14px; color: #1e293b; margin-bottom: 8px; font-weight: 700; }}
  .claim-box {{ background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 14px; padding: 16px; margin-top: 16px; }}
  .form-group {{ margin-bottom: 10px; }}
  .form-group label {{ display: block; font-size: 12px; font-weight: 600; color: #334155; margin-bottom: 4px; }}
  .form-control {{ width: 100%; padding: 8px 10px; font-size: 13px; border: 1px solid #cbd5e1; border-radius: 8px; }}
  .btn {{ background: #059669; color: white; border: none; padding: 10px 16px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; width: 100%; }}
  .btn:hover {{ background: #047857; }}
  .btn-print {{ background: #0284c7; margin-top: 8px; }}
  .actions {{ margin-top: 20px; text-align: center; display: flex; flex-direction: column; gap: 8px; }}
  .actions a {{ color: #059669; text-decoration: none; font-size: 14px; font-weight: 600; }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .claim-box, .actions {{ display: none; }}
    .card {{ box-shadow: none; border: 1px solid #ccc; }}
  }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div style="display:inline-block; background:rgba(255,255,255,0.2); padding:4px 10px; border-radius:9999px; font-size:11px; font-weight:700; margin-bottom:6px; letter-spacing:0.5px;">HEALTH INSURANCE PASS</div>
    <h1>{html.escape(p.full_name)}</h1>
    <p>PulseSync Verified Policy Pass · ID: {html.escape(p.id)}</p>
  </div>
  <div class="body">
    <div class="policy-chip">
      <div>
        <small style="color:#065f46; font-size:11px; text-transform:uppercase; font-weight:700;">Provider & Plan</small>
        <h3 style="color:#064e3b; font-size:16px; font-weight:800;">{html.escape(provider)}</h3>
        <p style="color:#047857; font-size:13px; font-weight:600; margin-top:2px;">Policy No: {html.escape(policy_no)}</p>
      </div>
      <span class="badge" style="background:{badge_bg}; color:{status_color};">{claimed}</span>
    </div>

    <div class="info-grid">
      <div class="info-item"><small>Policyholder</small><strong>{html.escape(p.full_name)}</strong></div>
      <div class="info-item"><small>Age / Gender</small><strong>{p.age} yrs · {html.escape(p.gender or 'N/A')}</strong></div>
      <div class="info-item"><small>Blood Group</small><strong style="color:#b91c1c;">{html.escape(p.blood_group or 'Unknown')}</strong></div>
      <div class="info-item"><small>Emergency Phone</small><strong>{html.escape(p.emergency_contact_phone or 'Not recorded')}</strong></div>
    </div>

    <div class="section">
      <h2>Cashless Hospitalization & TPA Verification</h2>
      <p style="font-size: 13px; color: #475569; margin-bottom: 8px;">
        {'✅ Active Policy: Present this pass at hospital admission or TPA desk for instant verification and pre-authorization processing.' if has_ins else '⚠️ No insurance policy registered on profile. Contact hospital billing for cash or government scheme assistance.'}
      </p>
      <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:10px; font-size:12px; color:#64748b;">
        <strong>24x7 TPA Pre-Authorization Support:</strong> 1800-200-HEALTH<br>
        <strong>Network Hospital Desk:</strong> Show QR to Desk Coordinator
      </div>
    </div>

    <div class="claim-box">
      <h2 style="color:#065f46; font-size:14px; margin-bottom:6px;">Submit Pre-Authorization / Claim Request</h2>
      <p style="font-size: 12px; color: #475569; margin-bottom: 12px;">Fast-track hospital pre-authorization by entering your 6-digit registration PIN.</p>
      <div class="form-group">
        <label>Hospital Name</label>
        <input type="text" id="claim-hospital" class="form-control" placeholder="e.g. City General Hospital" value="City General Multiservice Hospital">
      </div>
      <div class="form-group">
        <label>Reason for Claim / Treatment</label>
        <input type="text" id="claim-reason" class="form-control" placeholder="e.g. Inpatient Admission / Cardiology Care" value="Hospital Treatment">
      </div>
      <div class="form-group">
        <label>Estimated Amount (INR)</label>
        <input type="number" id="claim-amount" class="form-control" placeholder="e.g. 50000" value="25000">
      </div>
      <div class="form-group">
        <label>6-Digit Registration PIN</label>
        <input type="password" id="claim-pin" maxlength="6" pattern="\\d{6}" placeholder="••••••" class="form-control" style="text-align:center; font-size:16px; letter-spacing:4px;">
      </div>
      <button type="button" class="btn" onclick="submitClaim()">Submit Pre-Authorization</button>
      <div id="claim-result" style="margin-top:10px;"></div>
    </div>

    <div class="actions">
      <button type="button" class="btn btn-print" onclick="window.print()">🖨️ Print Digital Insurance Card</button>
      <a href="/">← Return to PulseSync Portal</a>
    </div>
  </div>
</div>

<script>
async function submitClaim() {{
  const pin = document.getElementById('claim-pin').value;
  const hospital = document.getElementById('claim-hospital').value;
  const reason = document.getElementById('claim-reason').value;
  const amount = document.getElementById('claim-amount').value;
  const resBox = document.getElementById('claim-result');
  if(!/^\\d{{6}}$/.test(pin)) {{
    resBox.innerHTML = '<p style="color:#dc2626;font-size:13px;">Please enter valid 6-digit registration PIN.</p>';
    return;
  }}
  resBox.innerHTML = '<p style="color:#059669;font-size:13px;">Submitting pre-authorization...</p>';
  try {{
    const res = await fetch('/api/qr/insurance/{p.id}/claim', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{pin, hospital_name: hospital, treatment_reason: reason, estimated_amount: Number(amount)}})
    }});
    const data = await res.json();
    if(!res.ok) throw new Error(data.detail || 'Claim submission failed');
    resBox.innerHTML = '<div style="padding:10px;background:#d1fae5;color:#065f46;border-radius:8px;font-size:13px;font-weight:600;">✅ ' + data.message + '</div>';
  }} catch(err) {{
    resBox.innerHTML = '<p style="color:#dc2626;font-size:13px;">' + err.message + '</p>';
  }}
}}
</script>
</body>
</html>'''
    return HTMLResponse(html_content)


def view_admission_public_card(patient_id: str, db: Session):
    p = db.get(Patient, patient_id)
    if not p:
        return HTMLResponse('<!doctype html><title>Patient Not Found</title><h1>Patient Not Found</h1>', status_code=404)
    
    from ..models import Consultation
    consult = db.query(Consultation).filter(
        Consultation.patient_id == patient_id
    ).order_by(Consultation.created_at.desc()).first()

    allergies = ", ".join(p.allergies or []) or "None reported"
    conditions = ", ".join(p.existing_conditions or []) or "None reported"
    emergency_contact = f"{p.emergency_contact_name or 'Not specified'} ({p.emergency_contact_phone or 'No phone'})"
    guardian = f"{p.parent_guardian_name or 'N/A'} ({p.parent_guardian_phone or 'No phone'})" if (p.is_child or (p.age and p.age >= 60)) else "Self"
    
    chief_complaint = consult.chief_complaint if consult else "Acute Inpatient Admission / Medical Evaluation"
    severity = consult.symptom_severity if consult else "Moderate"
    status_label = "URGENT ADMISSION" if (consult and consult.is_urgent) else "STANDARD ADMISSION PASS"
    status_color = "#dc2626" if (consult and consult.is_urgent) else "#2563eb"
    badge_bg = "#fee2e2" if (consult and consult.is_urgent) else "#dbeafe"

    html_content = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PulseSync Hospital Admission Form - {html.escape(p.full_name)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  body {{ background: #eff6ff; padding: 20px; color: #1e293b; line-height: 1.5; }}
  .card {{ max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 20px; box-shadow: 0 12px 30px -5px rgba(37,99,235,0.15); overflow: hidden; border: 1px solid #bfdbfe; }}
  .header {{ background: linear-gradient(135deg, #1d4ed8, #0f172a); color: #fff; padding: 24px; text-align: center; }}
  .header h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
  .header p {{ font-size: 13px; opacity: 0.9; }}
  .body {{ padding: 22px; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
  .chip {{ background: #f8fafc; border: 1.5px solid #cbd5e1; border-radius: 12px; padding: 14px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }}
  .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 16px 0; }}
  .info-item {{ background: #f8fafc; padding: 10px 12px; border-radius: 10px; border: 1px solid #e2e8f0; }}
  .info-item small {{ display: block; font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; margin-bottom: 2px; }}
  .info-item strong {{ font-size: 14px; color: #0f172a; word-break: break-word; }}
  .section {{ margin-top: 18px; border-top: 1px solid #e2e8f0; padding-top: 14px; }}
  .section h2 {{ font-size: 14px; color: #1e293b; margin-bottom: 8px; font-weight: 700; }}
  .pin-box {{ background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 12px; padding: 16px; margin-top: 18px; }}
  .pin-input {{ width: 140px; text-align: center; font-size: 18px; letter-spacing: 5px; padding: 8px; border: 1px solid #94a3b8; border-radius: 8px; }}
  .btn {{ background: #2563eb; color: white; border: none; padding: 10px 16px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; width: 100%; }}
  .btn:hover {{ background: #1d4ed8; }}
  .btn-print {{ background: #059669; margin-top: 8px; }}
  .actions {{ margin-top: 20px; text-align: center; display: flex; flex-direction: column; gap: 8px; }}
  .actions a {{ color: #2563eb; text-decoration: none; font-size: 14px; font-weight: 600; }}
  @media print {{
    body {{ background: #fff; padding: 0; }}
    .pin-box, .actions {{ display: none; }}
    .card {{ box-shadow: none; border: 1px solid #ccc; }}
  }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <div style="display:inline-block; background:rgba(255,255,255,0.2); padding:4px 10px; border-radius:9999px; font-size:11px; font-weight:700; margin-bottom:6px; letter-spacing:0.5px;">FAST-TRACK ADMISSION PASS</div>
    <h1>{html.escape(p.full_name)}</h1>
    <p>Hospital Inpatient Intake & Triage Record · Patient ID: {html.escape(p.id)}</p>
  </div>
  <div class="body">
    <div class="chip">
      <div>
        <small style="color:#64748b; font-size:11px; text-transform:uppercase; font-weight:700;">Admission Reason / Complaint</small>
        <h3 style="color:#0f172a; font-size:16px; font-weight:700;">{html.escape(chief_complaint)}</h3>
        <p style="color:#2563eb; font-size:13px; font-weight:600; margin-top:2px;">Triage Severity: {html.escape(severity)}</p>
      </div>
      <span class="badge" style="background:{badge_bg}; color:{status_color};">{status_label}</span>
    </div>

    <div class="info-grid">
      <div class="info-item"><small>Age / Gender</small><strong>{p.age} yrs · {html.escape(p.gender or 'N/A')}</strong></div>
      <div class="info-item"><small>Blood Group</small><strong style="color:#b91c1c;">{html.escape(p.blood_group or 'Unknown')}</strong></div>
      <div class="info-item"><small>City / Address</small><strong>{html.escape(p.city or 'Not recorded')}</strong></div>
      <div class="info-item"><small>Emergency Contact</small><strong>{html.escape(emergency_contact)}</strong></div>
      <div class="info-item" style="grid-column: span 2;"><small>Guardian / Caregiver</small><strong>{html.escape(guardian)}</strong></div>
      <div class="info-item" style="grid-column: span 2;"><small>Insurance Coverage</small><strong>{html.escape(p.insurance_provider or 'No insurance recorded')} ({html.escape(p.insurance_policy_no or 'N/A')})</strong></div>
    </div>

    <div class="section">
      <h2>Medical Alerts & Chronic History</h2>
      <p style="font-size: 13px; color: #475569; margin-bottom: 4px;"><strong>Allergies:</strong> {html.escape(allergies)}</p>
      <p style="font-size: 13px; color: #475569;"><strong>Chronic Conditions:</strong> {html.escape(conditions)}</p>
    </div>

    <div class="pin-box">
      <h2 style="color:#1e40af; font-size:14px; margin-bottom: 6px;">Hospital Staff / Bed Assignment Access</h2>
      <p style="font-size: 12px; color: #475569; margin-bottom: 10px;">Enter patient PIN to inspect complete clinical chart, active prescriptions, and recent vitals for ward admission.</p>
      <div style="display:flex; gap: 8px; align-items:center;">
        <input type="password" id="patient-pin" maxlength="6" pattern="\\d{6}" placeholder="••••••" class="pin-input">
        <button type="button" class="btn" style="width:auto;" onclick="unlockProfile()">Verify PIN</button>
      </div>
      <div id="unlock-result" style="margin-top: 12px;"></div>
    </div>

    <div class="actions">
      <button type="button" class="btn btn-print" onclick="window.print()">🖨️ Print Hospital Admission Form</button>
      <a href="/">← Return to PulseSync Portal</a>
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
  resBox.innerHTML = '<p style="color:#2563eb;font-size:13px;">Verifying PIN…</p>';
  try {{
    const res = await fetch('/api/qr/patient/{p.id}/unlock', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{pin: pin}})
    }});
    const data = await res.json();
    if(!res.ok) throw new Error(data.detail || 'PIN verification failed');
    
    let html = '<div style="margin-top:10px;padding:12px;background:#fff;border-radius:8px;border:1px solid #cbd5e1;">';
    html += '<h3 style="font-size:14px;color:#0f172a;margin-bottom:6px;">Current Medications (' + data.medications.length + ')</h3>';
    if(data.medications.length) {{
      html += '<ul style="font-size:13px;padding-left:18px;margin-bottom:10px;">' + data.medications.map(m => '<li><strong>' + m.name + '</strong> · ' + (m.frequency || '') + '</li>').join('') + '</ul>';
    }} else {{
      html += '<p style="font-size:12px;color:#64748b;">No active medicines.</p>';
    }}
    html += '<h3 style="font-size:14px;color:#0f172a;margin-bottom:6px;">Diagnoses & Alerts</h3>';
    if(data.diagnoses.length) {{
      html += '<ul style="font-size:13px;padding-left:18px;">' + data.diagnoses.map(d => '<li>' + d.name + '</li>').join('') + '</ul>';
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
    return HTMLResponse(html_content)

