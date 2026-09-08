"""
PulseSync AI - QR Code Generation & Scanning Engine
Generates dynamic styled QR codes for Patient Profile Intake, Insurance Claims, Doctor Clinics, Hospitals, and Pharmacies.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import io
import base64
import qrcode
from datetime import datetime, timedelta

from ..database import get_db
from ..models import PatientQRToken, Patient, Doctor, Hospital, PharmacyStore, DoctorNote

router = APIRouter(prefix="/api/qr", tags=["QR Code Engine"])

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
        version=1,
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


@router.get("/generate/{patient_id}/{qr_type}")
def get_patient_qr(patient_id: str, qr_type: str, db: Session = Depends(get_db)):
    """
    Generate and return dynamic Base64 QR code image and payload for Patient.
    Supports PROFILE_INTAKE (Medical Bio) and INSURANCE_CLAIM (Insurance verification).
    """
    norm_type = qr_type.upper()
    token = db.query(PatientQRToken).filter(
        PatientQRToken.patient_id == patient_id,
        PatientQRToken.qr_type == norm_type,
        PatientQRToken.is_active == True
    ).first()

    pat = db.query(Patient).filter(Patient.id == patient_id).first()

    if not token:
        # Generate dynamic payload from patient record
        if pat:
            if norm_type == "INSURANCE_CLAIM":
                payload_text = f"PULSESYNC:INS:{pat.id}:POLICY:{pat.insurance_policy_no or 'SH-MED-9912'}:PROVIDER:{pat.insurance_provider or 'Star Health'}:CLAIMED:{pat.insurance_claimed}"
            elif norm_type == "TRANSFER_AUTH":
                payload_text = f"PULSESYNC:TRANSFER:CGH:ICU:{pat.id}:PIN:584920"
            else:
                allergies_str = ",".join(pat.allergies) if pat.allergies else "None"
                payload_text = f"PULSESYNC:PAT:{pat.id}:NAME:{pat.full_name}:BLOOD:{pat.blood_group}:ALLERGIES:{allergies_str}"
        else:
            payload_text = f"PULSESYNC:{norm_type}:{patient_id}:PIN:584920"

        # Save to DB
        token = PatientQRToken(
            patient_id=patient_id,
            qr_type=norm_type,
            token_payload=payload_text,
            expires_at=datetime.utcnow() + timedelta(days=90),
            is_active=True
        )
        db.add(token)
        db.commit()
    else:
        payload_text = token.token_payload

    # Color code according to design specifications
    if norm_type == "TRANSFER_AUTH":
        fill_color = (225, 29, 72) # Rose / Emergency Red
    elif norm_type == "INSURANCE_CLAIM":
        fill_color = (13, 148, 136) # Teal / Insurance Green
    else:
        fill_color = (79, 70, 229) # Indigo / Health Purple

    qr_img = generate_qr_base64_image(payload_text, fill_color=fill_color)

    return {
        "success": True,
        "patient_id": patient_id,
        "patient_name": pat.full_name if pat else "Patient",
        "qr_type": norm_type,
        "token_payload": payload_text,
        "qr_image_base64": qr_img
    }


@router.get("/doctor/{doctor_id}")
def get_doctor_qr(doctor_id: str, db: Session = Depends(get_db)):
    """Generate dynamic QR Code for Doctor's Clinic & Appointments."""
    doc = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    doc_name = doc.full_name if doc else "Doctor"
    spec = doc.specialization if doc else "Cardiologist"
    clinic = doc.clinic_name if doc and doc.clinic_name else "PulseSync Clinic"
    
    payload_text = f"PULSESYNC:DOC:{doctor_id}:NAME:{doc_name}:SPEC:{spec}:CLINIC:{clinic}"
    qr_img = generate_qr_base64_image(payload_text, fill_color=(2, 132, 199)) # Sky Blue

    return {
        "success": True,
        "doctor_id": doctor_id,
        "doctor_name": doc_name,
        "token_payload": payload_text,
        "qr_image_base64": qr_img
    }


@router.get("/hospital/{hospital_id}")
def get_hospital_qr(hospital_id: str, db: Session = Depends(get_db)):
    """Generate dynamic QR Code for Multiservice Hospital Admissions."""
    hosp = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    hosp_name = hosp.name if hosp else "Multi-Specialty Hospital"
    city = hosp.city if hosp else "New Delhi"
    
    payload_text = f"PULSESYNC:HOSP:{hospital_id}:NAME:{hosp_name}:CITY:{city}:EMERGENCY_ICU"
    qr_img = generate_qr_base64_image(payload_text, fill_color=(124, 58, 237)) # Purple

    return {
        "success": True,
        "hospital_id": hospital_id,
        "hospital_name": hosp_name,
        "token_payload": payload_text,
        "qr_image_base64": qr_img
    }


@router.get("/pharmacy/{pharmacy_id}")
def get_pharmacy_qr(pharmacy_id: str, db: Session = Depends(get_db)):
    """Generate dynamic QR Code for Medical Store / Pharmacy."""
    pharm = db.query(PharmacyStore).filter(PharmacyStore.id == pharmacy_id).first()
    store_name = pharm.store_name if pharm else "Medical Store"
    
    payload_text = f"PULSESYNC:PHARM:{pharmacy_id}:NAME:{store_name}:DISPENSE_COUNTER"
    qr_img = generate_qr_base64_image(payload_text, fill_color=(217, 119, 6)) # Amber

    return {
        "success": True,
        "pharmacy_id": pharmacy_id,
        "store_name": store_name,
        "token_payload": payload_text,
        "qr_image_base64": qr_img
    }


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
