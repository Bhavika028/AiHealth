import os
import uuid
import json
import base64
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

try:
    import jwt
    HAS_PYJWT = True
except ImportError:
    HAS_PYJWT = False

from ..database import get_db
from ..models import (
    User, Patient, Doctor, Clinic, Hospital, WardAndBed, 
    PharmacyStore, Inventory, PatientQRToken
)

router = APIRouter(prefix="/api/auth", tags=["Authentication & Registration"])

from pathlib import Path
import secrets
_secret_file = Path(__file__).resolve().parents[2] / ".jwt-secret"
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    try:
        fd = os.open(str(_secret_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    JWT_SECRET = _secret_file.read_text().strip()
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 72

# ==============================================================================
# Security & Hashing Helpers
# ==============================================================================

def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def _b64_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += '=' * padding
    return base64.urlsafe_b64decode(data.encode('utf-8'))

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"pbkdf2${salt}${digest}"

def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith("sha256$"):
        expected = "sha256$" + hashlib.sha256(f"pulsesync_secure_salt_v2{plain_password}".encode()).hexdigest()
        return hmac.compare_digest(expected, hashed_password)
    try:
        _, salt, digest = hashed_password.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt.encode(), 260000).hex()
        return hmac.compare_digest(actual, digest)
    except ValueError:
        return False

def create_access_token(user_id: str, email: str, role: str) -> str:
    """Generate signed HS256 JWT Token with expiration."""
    exp_ts = int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp())
    iat_ts = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": user_id,
        "jti": uuid.uuid4().hex,
        "email": email,
        "role": role,
        "exp": exp_ts,
        "iat": iat_ts
    }
    if HAS_PYJWT:
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    # Pure Python zero-dependency HS256 JWT implementation
    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = _b64_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    p_b64 = _b64_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
    signing_input = f"{h_b64}.{p_b64}".encode('utf-8')
    sig = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64_encode(sig)
    return f"{h_b64}.{p_b64}.{sig_b64}"

def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    if HAS_PYJWT:
        try:
            return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please log in again.")
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization token.")
    
    # Pure Python JWT decode & verify
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        h_b64, p_b64, sig_b64 = parts
        signing_input = f"{h_b64}.{p_b64}".encode('utf-8')
        expected_sig = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
        actual_sig = _b64_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature.")
        payload = json.loads(_b64_decode(p_b64).decode('utf-8'))
        exp = payload.get("exp")
        if exp and int(datetime.now(timezone.utc).timestamp()) > exp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please log in again.")
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization token.")

# ==============================================================================
# Pydantic Request & Response Schemas
# ==============================================================================

class LoginRequest(BaseModel):
    email: str
    password: str
    role: Optional[str] = None


class UnifiedRegisterRequest(BaseModel):
    pin: str
    confirm_pin: str
    role: str  # PATIENT, DOCTOR, HOSPITAL_ADMIN, PHARMACY
    email: str
    password: str
    name: str
    phone: Optional[str] = ""
    preferred_language: Optional[str] = "en"
    
    # Geolocation Coordinates
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # --- PATIENT SPECIFIC FIELDS ---
    age: Optional[int] = 30
    gender: Optional[str] = "Male"
    blood_group: Optional[str] = None
    address: Optional[str] = ""
    city: Optional[str] = ""
    aadhaar_card_no: Optional[str] = ""
    pan_card_no: Optional[str] = ""
    has_insurance: Optional[bool] = False
    insurance_provider: Optional[str] = ""
    insurance_policy_no: Optional[str] = ""
    insurance_claimed: Optional[bool] = False
    existing_conditions: Optional[List[str]] = []
    allergies: Optional[List[str]] = []
    current_medications: Optional[List[Dict[str, Any]]] = []
    
    @field_validator('current_medications')
    @classmethod
    def validate_reported_medications(cls,items):
        for m in items or []:
            if not str(m.get('name','')).strip(): raise ValueError('Current medication requires a name')
            times=m.get('times_per_day')
            if times is not None and (type(times) is not int or not 1<=times<=24): raise ValueError('Medication times per day must be a whole number from 1 to 24')
            if m.get('food') not in (None,'Before food','After food','Not specified'): raise ValueError('Invalid medication food instruction')
        return items

    # --- DOCTOR SPECIFIC FIELDS ---
    specialization: Optional[str] = ""
    education: Optional[str] = ""
    license_no: Optional[str] = ""
    clinic_name: Optional[str] = ""
    clinic_address: Optional[str] = ""
    patients_checked_count: Optional[int] = 0
    
    # --- HOSPITAL SPECIFIC FIELDS ---
    hospital_name: Optional[str] = ""
    registration_no: Optional[str] = ""
    emergency_phone: Optional[str] = ""
    treatments: Optional[List[str]] = []
    total_doctors: Optional[int] = 0
    total_wards: Optional[int] = 0
    total_icu_beds: Optional[int] = 0
    total_general_beds: Optional[int] = 0
    
    # --- PHARMACY SPECIFIC FIELDS ---
    store_name: Optional[str] = ""
    pharmacist_name: Optional[str] = ""
    drug_license_no: Optional[str] = ""


class AuthResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]
    message: Optional[str] = "Authentication successful"


def hydrate_user_payload(user: User, db: Session) -> Dict[str, Any]:
    """Helper to load all related role-specific database fields for an active user."""
    entity_data: Dict[str, Any] = {}
    
    if user.role == "PATIENT":
        pat = db.query(Patient).filter(Patient.user_id == user.id).first()
        if pat:
            qr_tokens = db.query(PatientQRToken).filter(PatientQRToken.patient_id == pat.id).all()
            entity_data = {
                "patient_id": pat.id,
                "full_name": pat.full_name,
                "age": pat.age,
                "gender": pat.gender,
                "blood_group": pat.blood_group,
                "address": pat.address or "",
                "city": pat.city or "",
                "latitude": pat.latitude,
                "longitude": pat.longitude,
                "aadhaar_card_no": pat.aadhaar_card_no or "",
                "pan_card_no": pat.pan_card_no or "",
                "has_insurance": pat.has_insurance,
                "insurance_provider": pat.insurance_provider or "",
                "insurance_policy_no": pat.insurance_policy_no or "",
                "insurance_claimed": pat.insurance_claimed,
                "allergies": pat.allergies or [],
                "existing_conditions": pat.existing_conditions or [],
                "current_medications": pat.current_medications or [],
                "qr_tokens_count": len(qr_tokens)
            }
    elif user.role == "DOCTOR":
        doc = db.query(Doctor).filter(Doctor.user_id == user.id).first()
        if doc:
            entity_data = {
                "doctor_id": doc.id,
                "full_name": doc.full_name,
                "specialization": doc.specialization,
                "education": doc.education or "",
                "license_no": doc.license_no or "",
                "clinic_name": doc.clinic_name or (doc.clinic.name if doc.clinic else ""),
                "clinic_address": doc.clinic_address or (doc.clinic.address if doc.clinic else ""),
                "patients_checked_count": doc.patients_checked_count or 0,
                "latitude": doc.clinic.latitude if doc.clinic else None,
                "longitude": doc.clinic.longitude if doc.clinic else None,
                "clinic_id": doc.clinic_id,
                "hospital_id": doc.hospital_id
            }
    elif user.role in ["HOSPITAL_ADMIN", "HOSPITAL"]:
        hosp = db.query(Hospital).filter(Hospital.user_id == user.id).first()
        if hosp:
            entity_data = {
                "hospital_id": hosp.id,
                "hospital_name": hosp.name,
                "registration_no": hosp.registration_no or "",
                "address": hosp.address,
                "city": hosp.city,
                "latitude": hosp.latitude,
                "longitude": hosp.longitude,
                "emergency_phone": hosp.emergency_phone or "",
                "treatments": hosp.treatments or [],
                "total_doctors": hosp.total_doctors or 0,
                "total_wards": hosp.total_wards or 0,
                "total_icu_beds": hosp.total_icu_beds or 0,
                "total_general_beds": hosp.total_general_beds or 0
            }
    elif user.role == "PHARMACY":
        pharm = db.query(PharmacyStore).filter(PharmacyStore.user_id == user.id).first()
        if pharm:
            entity_data = {
                "pharmacy_id": pharm.id,
                "store_name": pharm.store_name,
                "pharmacist_name": pharm.pharmacist_name or "",
                "license_no": pharm.license_no or "",
                "address": pharm.address,
                "city": pharm.city or "",
                "latitude": pharm.latitude,
                "longitude": pharm.longitude,
                "is_online": pharm.is_online,
                "phone": pharm.phone or ""
            }

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone or "",
        "role": user.role,
        "preferred_language": user.language_preference or "en",
        **entity_data
    }


# ==============================================================================
# Auth Endpoints
# ==============================================================================

@router.post("/register", response_model=AuthResponse)
def register(payload: UnifiedRegisterRequest, db: Session = Depends(get_db)):
    """
    Strict Dynamic Multi-Role Registration with Real JWT Authentication:
    Registers a new User, validates password, and generates genuine QR pass.
    """
    clean_email = payload.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address."
        )

    raw_password = payload.password or ""
    if len(raw_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 4 characters long."
        )

    if not payload.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide your full name."
        )

    normalized_role = payload.role.strip().upper()
    if normalized_role == "HOSPITAL":
        normalized_role = "HOSPITAL_ADMIN"

    if normalized_role not in {"PATIENT", "DOCTOR", "HOSPITAL_ADMIN", "PHARMACY"}:
        raise HTTPException(400, "Unsupported role")
    if (payload.latitude is None) != (payload.longitude is None):
        raise HTTPException(400, "Enter both latitude and longitude")
    if payload.latitude is not None and not (-90 <= payload.latitude <= 90 and -180 <= payload.longitude <= 180):
        raise HTTPException(400, "Coordinates out of range")
    # STRICT CHECK: Reject if user already registered
    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An account with email '{clean_email}' already exists. Please sign in instead."
        )

    from ..pin_security import validate_new_pin, hash_pin
    validate_new_pin(payload.pin, payload.confirm_pin)

    # 1. Create Base User with Password Hash
    user_id = f"usr_{uuid.uuid4().hex[:8]}"
    pwd_hash = hash_password(raw_password)

    new_user = User(
        id=user_id,
        email=clean_email,
        password_hash=pwd_hash,
        pin_hash=hash_pin(payload.pin),
        name=payload.name.strip(),
        phone=payload.phone.strip() if payload.phone else "",
        role=normalized_role,
        language_preference=payload.preferred_language or "en",
        is_active=True
    )
    db.add(new_user)
    db.flush()

    # 2. Create Entity according to Role
    if normalized_role == "PATIENT":
        pat_id = f"pat_{uuid.uuid4().hex[:8]}"
        new_patient = Patient(
            id=pat_id,
            user_id=user_id,
            full_name=payload.name.strip(),
            age=payload.age or 30,
            gender=payload.gender or "Male",
            blood_group=payload.blood_group or None,
            address=payload.address or "",
            city=payload.city or "",
            latitude=payload.latitude,
            longitude=payload.longitude,
            aadhaar_card_no=payload.aadhaar_card_no or "",
            pan_card_no=payload.pan_card_no or "",
            has_insurance=payload.has_insurance if payload.has_insurance is not None else False,
            insurance_provider=payload.insurance_provider or "",
            insurance_policy_no=payload.insurance_policy_no or "",
            insurance_claimed=payload.insurance_claimed if payload.insurance_claimed is not None else False,
            existing_conditions=payload.existing_conditions or [],
            allergies=payload.allergies or [],
            current_medications=payload.current_medications or []
        )
        db.add(new_patient)
        db.flush()

        # Generate the Dynamic Patient QR Tokens
        qr_profile = PatientQRToken(
            id=f"qr_prof_{uuid.uuid4().hex[:6]}",
            patient_id=pat_id,
            qr_type="PROFILE_INTAKE",
            token_payload=f"PULSESYNC:IDENTITY:{pat_id}",
            expires_at=datetime.now(timezone.utc) + timedelta(days=90),
            is_active=True
        )
        qr_insurance = PatientQRToken(
            id=f"qr_ins_{uuid.uuid4().hex[:6]}",
            patient_id=pat_id,
            qr_type="INSURANCE_CLAIM",
            token_payload=f"PULSESYNC:INSURANCE:IDENTITY:{pat_id}",
            expires_at=datetime.now(timezone.utc) + timedelta(days=90),
            is_active=True
        )
        db.add_all([qr_profile, qr_insurance])

    elif normalized_role == "DOCTOR":
        clinic_id = f"clinic_{uuid.uuid4().hex[:6]}"
        clinic = Clinic(
            id=clinic_id,
            name=payload.clinic_name or f"{payload.name.strip()}'s Clinic",
            address=payload.clinic_address or payload.address or "Clinic Address",
            city=payload.city or "City",
            latitude=payload.latitude,
            longitude=payload.longitude,
            phone=payload.phone or "",
            email=clean_email
        )
        db.add(clinic)
        db.flush()

        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        new_doc = Doctor(
            id=doc_id,
            user_id=user_id,
            clinic_id=clinic_id,
            full_name=payload.name.strip(),
            specialization=payload.specialization or "General Physician",
            education=payload.education or "MBBS",
            license_no=payload.license_no or None,
            clinic_name=payload.clinic_name or clinic.name,
            clinic_address=payload.clinic_address or clinic.address,
            patients_checked_count=payload.patients_checked_count or 0,
            is_verified=True
        )
        db.add(new_doc)

    elif normalized_role == "HOSPITAL_ADMIN":
        hosp_id = f"hosp_{uuid.uuid4().hex[:6]}"
        hospital = Hospital(
            id=hosp_id,
            user_id=user_id,
            is_active=True,
            name=payload.hospital_name or payload.name.strip(),
            registration_no=payload.registration_no or None,
            address=payload.address or "Hospital Address",
            city=payload.city or "City",
            latitude=payload.latitude,
            longitude=payload.longitude,
            emergency_phone=payload.emergency_phone or payload.phone or "",
            treatments=payload.treatments or [],
            total_doctors=payload.total_doctors if payload.total_doctors is not None else 0,
            total_wards=payload.total_wards if payload.total_wards is not None else 0,
            total_icu_beds=payload.total_icu_beds if payload.total_icu_beds is not None else 0,
            total_general_beds=payload.total_general_beds if payload.total_general_beds is not None else 0
        )
        db.add(hospital)
        db.flush()

        for kind, count in [("ICU", hospital.total_icu_beds), ("GENERAL", hospital.total_general_beds)]:
            if count < 0 or count > 500:
                raise HTTPException(400, "Bed count must be between 0 and 500")
            for number in range(1, count + 1):
                db.add(WardAndBed(hospital_id=hosp_id, ward_name=f"{kind} Ward", ward_type=kind,
                                  bed_number=f"{kind}-{number:03}", is_occupied=False, state="AVAILABLE"))

    elif normalized_role == "PHARMACY":
        pharma_id = f"pharma_{uuid.uuid4().hex[:6]}"
        pharma = PharmacyStore(
            id=pharma_id,
            user_id=user_id,
            store_name=payload.store_name or payload.name.strip(),
            pharmacist_name=payload.pharmacist_name or payload.name.strip(),
            license_no=payload.drug_license_no or payload.license_no or None,
            address=payload.address or "Medical Complex",
            city=payload.city or "",
            latitude=payload.latitude,
            longitude=payload.longitude,
            is_online=True,
            last_active_at=datetime.utcnow(),
            phone=payload.phone or ""
        )
        db.add(pharma)
        db.flush()


    db.commit()
    db.refresh(new_user)

    token = create_access_token(new_user.id, new_user.email, new_user.role)
    user_data = hydrate_user_payload(new_user, db)

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": user_data,
        "message": f"Successfully registered {new_user.name} ({new_user.role})! JWT issued."
    }


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Strict Authentication by Email and Password with JWT issuance.
    Rejects unregistered users with a 404 error.
    """
    clean_email = payload.email.strip().lower()
    if not clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is required."
        )

    user = db.query(User).filter(User.email == clean_email).first()

    # STRICT CHECK: User must be registered earlier
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No registered account found with email '{clean_email}'. Please register first."
        )

    # STRICT PASSWORD VALIDATION
    raw_login_pwd = payload.password or ""
    if user.password_hash:
        if not verify_password(raw_login_pwd, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password. Please try again."
            )
    else:
        raise HTTPException(401, "Legacy account has no password. Set it using the local recovery command.")
    if not user.is_active:
        raise HTTPException(401, "Account disabled")

    # Verify role if provided
    if payload.role:
        role_search = payload.role.strip().upper()
        if role_search == "HOSPITAL":
            role_search = "HOSPITAL_ADMIN"
        if user.role != role_search:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account '{clean_email}' is registered as {user.role}, not {role_search}."
            )

    # If Pharmacy user, mark online
    if user.role == "PHARMACY":
        pharm = db.query(PharmacyStore).filter(PharmacyStore.user_id == user.id).first()
        if pharm:
            pharm.is_online = True
            pharm.last_active_at = datetime.utcnow()
            db.commit()

    token = create_access_token(user.id, user.email, user.role)
    user_data = hydrate_user_payload(user, db)

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user": user_data,
        "message": f"Welcome back, {user.name}!"
    }


@router.post("/logout")
def logout(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """Mark pharmacy / user offline on logout."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = decode_access_token(token)
            from ..workflow_models import RevokedToken
            db.add(RevokedToken(id=payload.get("jti", hashlib.sha256(token.encode()).hexdigest())))
            db.commit()
            user_id = payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user and user.role == "PHARMACY":
                    pharm = db.query(PharmacyStore).filter(PharmacyStore.user_id == user.id).first()
                    if pharm:
                        pharm.is_online = False
                        db.commit()
        except Exception:
            pass

    return {"success": True, "message": "Logged out successfully."}


@router.get("/me")
def get_current_user_profile(
    authorization: Optional[str] = Header(None), 
    user_id: Optional[str] = None, 
    db: Session = Depends(get_db)
):
    """Retrieve full dynamic profile from verified JWT token."""
    from ..security import current_user
    user = current_user(authorization, db)

    return {
        "success": True,
        "user": hydrate_user_payload(user, db)
    }
