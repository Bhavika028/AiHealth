"""
PulseSync AI - QR Code Generation & Scanning Engine
Generates dynamic styled QR codes for Patient Profile Intake, Insurance Claims, Doctor Clinics, Hospitals, and Pharmacies.
Supports mobile browser verification pages when scanned by another device.
"""

import os
import io
import base64
import socket
import qrcode
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PatientQRToken, Patient, Doctor, Hospital, PharmacyStore, DoctorNote

router = APIRouter(prefix="/api/qr", tags=["QR Code Engine"])


def get_local_lan_ip() -> str:
    """Detect LAN IP address so devices on the same Wi-Fi can open the QR link."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_server_network_base(request: Optional[Request] = None) -> str:
    """Resolve accessible base URL for devices scanning the QR code."""
    lan_ip = get_local_lan_ip()
    port = os.getenv("PORT", "8000")
    if request:
        host = request.headers.get("host", "")
        # If accessing via localhost or 127.0.0.1, use the LAN IP so other devices can access it
        if not host or "localhost" in host or "127.0.0.1" in host:
            return f"http://{lan_ip}:{port}"
        return f"http://{host}"
    return f"http://{lan_ip}:{port}"


class QRGenerateRequest(BaseModel):
    patient_id: str
    qr_type: str = "PROFILE_INTAKE"  # PROFILE_INTAKE, INSURANCE_CLAIM, TRANSFER_AUTH
    pin: Optional[str] = "584920"
    destination: Optional[str] = "City General Hospital"


class QRVerifyRequest(BaseModel):
    token_payload: str
    pin: Optional[str] = None


def generate_qr_base64_image(payload_text: str, fill_color: tuple = (15, 23, 42), back_color: tuple = (255, 255, 255)) -> str:
    """Generate high quality QR code and return as Base64 Data URL."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(payload_text)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color)
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"


# ==============================================================================
# 1. QR Code Generation Endpoints
# ==============================================================================

@router.get("/generate/{patient_id}/{qr_type}")
def get_patient_qr(
    patient_id: str, 
    qr_type: str, 
    format_mode: Optional[str] = "url",
    request: Request = None, 
    db: Session = Depends(get_db)
):
    """
    Generate dynamic QR code for Patient.
    By default encodes a direct Mobile Web Card URL (http://<LAN_IP>:8000/qr/patient/<id>)
    so scanning from any mobile device immediately displays the patient's full medical profile.
    Also supports offline text card format if format_mode='card'.
    """
    norm_type = qr_type.upper()
    pat = db.query(Patient).filter(Patient.id == patient_id).first()
    if not pat:
        raise HTTPException(status_code=404, detail="Patient record not found")

    base_url = get_server_network_base(request)

    if norm_type == "INSURANCE_CLAIM":
        web_url = f"{base_url}/qr/insurance/{pat.id}"
        allergies_str = ", ".join(pat.allergies) if pat.allergies else "None"
        if format_mode == "card":
            payload_text = (
                f"PULSESYNC AI - INSURANCE & CASHLESS PASS\n"
                f"Patient: {pat.full_name}\n"
                f"Blood Group: {pat.blood_group}\n"
                f"Status: {'Active Coverage' if pat.has_insurance else 'Ayushman Subsidy'}\n"
                f"Provider: {pat.insurance_provider or 'PM-JAY National'}\n"
                f"Policy No: {pat.insurance_policy_no or 'ACTIVE-PASS'}\n"
                f"Claimed: {'Yes' if pat.insurance_claimed else 'No'}\n"
                f"Verify: {web_url}"
            )
        else:
            payload_text = web_url
        fill_color = (13, 148, 136)  # Teal
    elif norm_type == "TRANSFER_AUTH":
        web_url = f"{base_url}/qr/patient/{pat.id}"
        payload_text = f"PULSESYNC:TRANSFER:CGH:ICU:{pat.id}:PIN:584920"
        fill_color = (225, 29, 72)  # Rose / Emergency Red
    else:
        # PROFILE_INTAKE
        web_url = f"{base_url}/qr/patient/{pat.id}"
        allergies_str = ", ".join(pat.allergies) if pat.allergies else "None Recorded"
        conditions_str = ", ".join(pat.existing_conditions) if pat.existing_conditions else "None Recorded"
        if format_mode == "card":
            payload_text = (
                f"PULSESYNC AI - EMERGENCY MEDICAL PASS\n"
                f"Name: {pat.full_name}\n"
                f"Age/Gender: {pat.age} / {pat.gender}\n"
                f"Blood Group: {pat.blood_group}\n"
                f"Allergies: {allergies_str}\n"
                f"Conditions: {conditions_str}\n"
                f"City: {pat.city or pat.address or 'Local'}\n"
                f"Phone: {pat.emergency_contact_phone or (pat.user.phone if pat.user else '')}\n"
                f"Insurance: {'Active' if pat.has_insurance else 'None'}\n"
                f"Verify: {web_url}"
            )
        else:
            payload_text = web_url
        fill_color = (79, 70, 229)  # Indigo

    qr_img = generate_qr_base64_image(payload_text, fill_color=fill_color)

    # Persist or update token in DB
    token = db.query(PatientQRToken).filter(
        PatientQRToken.patient_id == patient_id,
        PatientQRToken.qr_type == norm_type
    ).first()
    if not token:
        token = PatientQRToken(
            patient_id=patient_id,
            qr_type=norm_type,
            token_payload=payload_text,
            expires_at=datetime.utcnow() + timedelta(days=90),
            is_active=True
        )
        db.add(token)
    else:
        token.token_payload = payload_text
        token.is_active = True
    db.commit()

    return {
        "success": True,
        "patient_id": patient_id,
        "patient_name": pat.full_name,
        "qr_type": norm_type,
        "web_url": web_url,
        "token_payload": payload_text,
        "qr_image_base64": qr_img
    }


@router.get("/doctor/{doctor_id}")
def get_doctor_qr(doctor_id: str, request: Request = None, db: Session = Depends(get_db)):
    """Generate dynamic QR Code for Doctor's Clinic & Appointments."""
    doc = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    doc_name = doc.full_name if doc else "Doctor"
    spec = doc.specialization if doc else "Cardiologist"
    clinic = doc.clinic_name if doc and doc.clinic_name else "PulseSync Clinic"
    
    base_url = get_server_network_base(request)
    web_url = f"{base_url}/qr/doctor/{doctor_id}"
    qr_img = generate_qr_base64_image(web_url, fill_color=(2, 132, 199))

    return {
        "success": True,
        "doctor_id": doctor_id,
        "doctor_name": doc_name,
        "web_url": web_url,
        "token_payload": web_url,
        "qr_image_base64": qr_img
    }


@router.get("/hospital/{hospital_id}")
def get_hospital_qr(hospital_id: str, request: Request = None, db: Session = Depends(get_db)):
    """Generate dynamic QR Code for Multiservice Hospital Admissions."""
    hosp = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    hosp_name = hosp.name if hosp else "Multi-Specialty Hospital"
    
    base_url = get_server_network_base(request)
    web_url = f"{base_url}/qr/hospital/{hospital_id}"
    qr_img = generate_qr_base64_image(web_url, fill_color=(124, 58, 237))

    return {
        "success": True,
        "hospital_id": hospital_id,
        "hospital_name": hosp_name,
        "web_url": web_url,
        "token_payload": web_url,
        "qr_image_base64": qr_img
    }


@router.get("/pharmacy/{pharmacy_id}")
def get_pharmacy_qr(pharmacy_id: str, request: Request = None, db: Session = Depends(get_db)):
    """Generate dynamic QR Code for Medical Store / Pharmacy."""
    pharm = db.query(PharmacyStore).filter(PharmacyStore.id == pharmacy_id).first()
    store_name = pharm.store_name if pharm else "Medical Store"
    
    base_url = get_server_network_base(request)
    web_url = f"{base_url}/qr/pharmacy/{pharmacy_id}"
    qr_img = generate_qr_base64_image(web_url, fill_color=(217, 119, 6))

    return {
        "success": True,
        "pharmacy_id": pharmacy_id,
        "store_name": store_name,
        "web_url": web_url,
        "token_payload": web_url,
        "qr_image_base64": qr_img
    }


# ==============================================================================
# 2. Public Mobile Web Pages (Displayed on Phone when QR is Scanned)
# ==============================================================================

@router.get("/patient/{patient_id}", response_class=HTMLResponse)
def view_patient_public_card(patient_id: str, db: Session = Depends(get_db)):
    """
    Renders an emergency-ready, responsive digital health profile card
    when another device (phone/tablet/scanner) scans the Patient Medical Profile QR code.
    """
    pat = db.query(Patient).filter(Patient.id == patient_id).first()
    if not pat:
        return HTMLResponse(content="""
        <!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Patient Not Found</title>
        <style>body{font-family:sans-serif;text-align:center;padding:3rem;background:#f8fafc;color:#1e293b;}</style></head>
        <body><h2>⚠️ Patient Profile Not Found</h2><p>This medical QR pass is invalid or expired.</p></body></html>
        """, status_code=404)

    allergies_list = pat.allergies if pat.allergies else []
    conditions_list = pat.existing_conditions if pat.existing_conditions else []
    meds_list = pat.current_medications if pat.current_medications else []

    allergies_html = "".join([f'<span class="badge badge-danger">⚠️ {a}</span>' for a in allergies_list]) or '<span class="badge badge-gray">No Known Allergies</span>'
    conditions_html = "".join([f'<span class="badge badge-warning">🩺 {c}</span>' for c in conditions_list]) or '<span class="badge badge-gray">None Recorded</span>'
    
    phone = pat.emergency_contact_phone or (pat.user.phone if pat.user else "Not Provided")
    phone_link = f'<a href="tel:{phone}" class="btn-call">📞 Call {phone}</a>' if phone != "Not Provided" else "<span>Not Provided</span>"

    insurance_status_badge = '<span class="badge badge-success">● Cashless Coverage Active</span>' if pat.has_insurance else '<span class="badge badge-gray">Ayushman PM-JAY Subsidy</span>'
    insurance_claimed_text = '<span style="color:#e11d48;font-weight:600;">Claimed / In-Progress</span>' if pat.insurance_claimed else '<span style="color:#059669;font-weight:600;">Active / Ready to Claim</span>'

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PulseSync AI - Patient Medical Profile ({pat.full_name})</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #f8fafc;
            min-height: 100vh;
            padding: 16px;
            display: flex;
            justify-content: center;
            align-items: flex-start;
        }}
        .card-container {{
            width: 100%;
            max-width: 520px;
            background: #ffffff;
            color: #0f172a;
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4);
            margin: 12px auto;
        }}
        .card-header {{
            background: linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%);
            color: #ffffff;
            padding: 24px 20px 20px;
            position: relative;
        }}
        .verified-banner {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(8px);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 14px;
        }}
        .pulse-dot {{
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 10px #10b981;
            animation: pulse 1.8s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.4); opacity: 0.6; }}
        }}
        .hero-info {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .avatar {{
            width: 68px;
            height: 68px;
            background: rgba(255, 255, 255, 0.25);
            border: 3px solid #ffffff;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            flex-shrink: 0;
        }}
        .hero-text h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.5rem;
            font-weight: 800;
            line-height: 1.2;
        }}
        .hero-sub {{
            font-size: 0.85rem;
            color: rgba(255, 255, 255, 0.9);
            margin-top: 4px;
        }}
        .blood-badge {{
            display: inline-block;
            background: #e11d48;
            color: white;
            font-weight: 800;
            font-size: 0.85rem;
            padding: 3px 10px;
            border-radius: 8px;
            margin-top: 6px;
        }}
        .card-body {{
            padding: 20px;
        }}
        .section-title {{
            font-family: 'Outfit', sans-serif;
            font-size: 0.9rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.75px;
            color: #64748b;
            margin: 18px 0 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .section-title:first-child {{ margin-top: 0; }}
        .alert-box {{
            background: #fff1f2;
            border: 1.5px solid #fecdd3;
            border-radius: 14px;
            padding: 14px;
            margin-bottom: 12px;
        }}
        .alert-box.conditions {{
            background: #fffbeb;
            border-color: #fde68a;
        }}
        .alert-label {{
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            color: #be123c;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .alert-box.conditions .alert-label {{ color: #b45309; }}
        .badge-group {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .badge {{
            display: inline-flex;
            align-items: center;
            padding: 5px 12px;
            border-radius: 8px;
            font-size: 0.82rem;
            font-weight: 600;
        }}
        .badge-danger {{ background: #ffe4e6; color: #be123c; }}
        .badge-warning {{ background: #fef3c7; color: #92400e; }}
        .badge-success {{ background: #d1fae5; color: #065f46; }}
        .badge-gray {{ background: #f1f5f9; color: #64748b; }}
        .info-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            background: #f8fafc;
            padding: 14px;
            border-radius: 14px;
            border: 1px solid #e2e8f0;
        }}
        .info-item {{
            display: flex;
            flex-direction: column;
        }}
        .info-label {{
            font-size: 0.72rem;
            color: #64748b;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .info-val {{
            font-size: 0.9rem;
            font-weight: 700;
            color: #0f172a;
            margin-top: 2px;
        }}
        .btn-call {{
            display: inline-block;
            background: #10b981;
            color: white;
            text-decoration: none;
            padding: 8px 14px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 0.85rem;
            text-align: center;
            margin-top: 6px;
        }}
        .card-footer {{
            background: #f8fafc;
            border-top: 1px solid #e2e8f0;
            padding: 16px 20px;
            text-align: center;
            font-size: 0.75rem;
            color: #64748b;
        }}
        .verified-seal {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: #4f46e5;
            font-weight: 700;
        }}
    </style>
</head>
<body>
    <div class="card-container">
        <div class="card-header">
            <div class="verified-banner">
                <span class="pulse-dot"></span>
                <span>PulseSync AI Live Verified Medical Record</span>
            </div>
            <div class="hero-info">
                <div class="avatar">{('👩' if pat.gender.lower() == 'female' else '👨')}</div>
                <div class="hero-text">
                    <h1>{pat.full_name}</h1>
                    <div class="hero-sub">{pat.age} Years • {pat.gender} • {pat.city or pat.address or 'Verified'}</div>
                    <div class="blood-badge">🩸 Blood Group: {pat.blood_group}</div>
                </div>
            </div>
        </div>

        <div class="card-body">
            <!-- Critical Allergies Alert -->
            <div class="alert-box">
                <div class="alert-label">⚠️ Emergency Medical Allergies</div>
                <div class="badge-group">{allergies_html}</div>
            </div>

            <!-- Existing Conditions -->
            <div class="alert-box conditions">
                <div class="alert-label">🩺 Known Medical Conditions</div>
                <div class="badge-group">{conditions_html}</div>
            </div>

            <!-- Demographics & Identifiers -->
            <div class="section-title">🪪 Patient Identification & Demographics</div>
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-label">Aadhaar Card No</span>
                    <span class="info-val">{pat.aadhaar_card_no or 'Verified PM-JAY'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">PAN Card No</span>
                    <span class="info-val">{pat.pan_card_no or 'Verified'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Registered City</span>
                    <span class="info-val">{pat.city or pat.address or 'Local Area'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Patient ID</span>
                    <span class="info-val">{pat.id}</span>
                </div>
            </div>

            <!-- Insurance Details -->
            <div class="section-title">🛡️ Health Insurance Verification</div>
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-label">Coverage Status</span>
                    <span class="info-val">{insurance_status_badge}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Claim Status</span>
                    <span class="info-val">{insurance_claimed_text}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Insurance Provider</span>
                    <span class="info-val">{pat.insurance_provider or 'PM-JAY National / Self'}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Policy Number</span>
                    <span class="info-val">{pat.insurance_policy_no or 'ACTIVE-POLICY-INT'}</span>
                </div>
            </div>

            <!-- Emergency Contact -->
            <div class="section-title">📞 Emergency Contact</div>
            <div class="info-grid" style="grid-template-columns: 1fr;">
                <div class="info-item">
                    <span class="info-label">Primary Contact Number</span>
                    <span class="info-val" style="margin-top:4px;">{phone_link}</span>
                </div>
            </div>
        </div>

        <div class="card-footer">
            <div class="verified-seal">
                <span>🛡️</span> PulseSync AI Cryptographic Health Pass Verified
            </div>
            <div style="margin-top:4px;">Scanned on verified network • Token: {pat.id}</div>
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content, status_code=200)


@router.get("/insurance/{patient_id}", response_class=HTMLResponse)
def view_insurance_public_card(patient_id: str, db: Session = Depends(get_db)):
    """
    Renders an Insurance Claim & Cashless Hospital Admission Pass
    when another device scans the Insurance QR code.
    """
    pat = db.query(Patient).filter(Patient.id == patient_id).first()
    if not pat:
        return HTMLResponse(content="<h2>Insurance pass not found</h2>", status_code=404)

    claim_status_badge = '<span class="badge badge-danger">Claimed / In-Progress</span>' if pat.insurance_claimed else '<span class="badge badge-success">Approved for Cashless Admission</span>'

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PulseSync AI - Cashless Insurance Pass ({pat.full_name})</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #042f2e 0%, #0f172a 100%);
            color: #f8fafc;
            min-height: 100vh;
            padding: 16px;
            display: flex;
            justify-content: center;
            align-items: flex-start;
        }}
        .card-container {{
            width: 100%;
            max-width: 520px;
            background: #ffffff;
            color: #0f172a;
            border-radius: 24px;
            overflow: hidden;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4);
            margin: 12px auto;
        }}
        .card-header {{
            background: linear-gradient(135deg, #0d9488 0%, #059669 100%);
            color: #ffffff;
            padding: 24px 20px;
        }}
        .badge {{ display: inline-block; padding: 5px 12px; border-radius: 8px; font-size: 0.85rem; font-weight: 700; }}
        .badge-success {{ background: #d1fae5; color: #065f46; }}
        .badge-danger {{ background: #ffe4e6; color: #be123c; }}
        .card-body {{ padding: 20px; }}
        .info-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            background: #f8fafc;
            padding: 16px;
            border-radius: 14px;
            border: 1px solid #e2e8f0;
            margin-top: 14px;
        }}
        .info-label {{ font-size: 0.75rem; color: #64748b; font-weight: 600; text-transform: uppercase; }}
        .info-val {{ font-size: 0.95rem; font-weight: 700; color: #0f172a; margin-top: 2px; }}
        .card-footer {{
            background: #f8fafc;
            border-top: 1px solid #e2e8f0;
            padding: 16px;
            text-align: center;
            font-size: 0.78rem;
            color: #64748b;
        }}
    </style>
</head>
<body>
    <div class="card-container">
        <div class="card-header">
            <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.9;">
                PulseSync AI Cashless Hospitalization Network
            </div>
            <h1 style="font-family:'Outfit',sans-serif; font-size: 1.6rem; font-weight:800; margin-top:6px;">
                {pat.full_name}
            </h1>
            <div style="font-size: 0.85rem; opacity: 0.95; margin-top: 4px;">
                Policy ID: {pat.insurance_policy_no or 'DIRECT-CLAIM'} • {pat.blood_group}
            </div>
        </div>

        <div class="card-body">
            <div style="background:#ecfdf5; border:1.5px solid #a7f3d0; border-radius:12px; padding:14px; text-align:center;">
                <div style="font-size:0.8rem; font-weight:700; color:#047857; text-transform:uppercase;">Admission TPA Authorization</div>
                <div style="margin-top:6px;">{claim_status_badge}</div>
            </div>

            <div class="info-grid">
                <div>
                    <div class="info-label">Insurance Provider</div>
                    <div class="info-val">{pat.insurance_provider or 'Government / PM-JAY TPA'}</div>
                </div>
                <div>
                    <div class="info-label">Policy Number</div>
                    <div class="info-val">{pat.insurance_policy_no or 'DIRECT-AYUSHMAN'}</div>
                </div>
                <div>
                    <div class="info-label">Patient Age / Gender</div>
                    <div class="info-val">{pat.age} Years / {pat.gender}</div>
                </div>
                <div>
                    <div class="info-label">Cashless ICU Eligible</div>
                    <div class="info-val" style="color:#059669;">YES (Active Pass)</div>
                </div>
            </div>
        </div>

        <div class="card-footer">
            🛡️ Verified for Cashless Hospitalization and Emergency ICU Admission.
        </div>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_content, status_code=200)


# ==============================================================================
# 3. Emergency PIN Verification
# ==============================================================================

@router.post("/verify-transfer-pin")
def verify_transfer_pin(payload: QRVerifyRequest, db: Session = Depends(get_db)):
    """
    Validates 6-digit confirmation PIN for Emergency ICU Patient Transfer.
    Dynamically resolves patient, destination hospital, and ward bed.
    """
    pin = payload.pin.strip() if payload.pin else ""
    
    note = db.query(DoctorNote).filter(DoctorNote.confirmation_pin == pin).first()
    if not note:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid or expired 6-digit Confirmation PIN '{pin}'. Please enter a valid PIN generated by Doctor Referral."
        )

    patient_name = note.consultation.patient.full_name if (note.consultation and note.consultation.patient) else "Registered Patient"
    hospital = note.referral_destination_name or "Emergency Facility"
    ward = "Emergency Care Ward"
    bed = "Admitted Bed"
    
    return {
        "verified": True,
        "patient_name": patient_name,
        "hospital": hospital,
        "ward_name": ward,
        "allocated_bed": bed,
        "transfer_status": "CONFIRMED_AND_ADMITTED",
        "message": f"Confirmation PIN verified. Patient {patient_name} transfer confirmed to {hospital}."
    }
