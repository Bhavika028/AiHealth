"""
PulseSync AI - Dynamic & Adaptive Patient Intake Questionnaire Engine
Implements the full Clinic Feedback & Requirement Specifications (Core Q1-Q10 & Section B Branching)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import datetime

from ..database import get_db
from ..models import Patient, Consultation, DoctorNote, Doctor, Clinic

router = APIRouter(prefix="/api/intake", tags=["Adaptive Patient Intake"])

# ------------------------------------------------------------------------------
# Pydantic Schemas
# ------------------------------------------------------------------------------

class BranchDefinition(BaseModel):
    branch_key: str
    title: str
    questions: List[Dict[str, Any]]

class PatientIntakePayload(BaseModel):
    patient_id: str
    doctor_id: Optional[str] = None
    clinic_id: Optional[str] = None
    
    # Core Flow Q1-Q10
    q1_chief_complaint: str
    q2_duration_value: int
    q2_duration_unit: str = "Days"  # Hours, Days, Weeks, Months
    q3_severity: str = "Moderate"   # Mild, Moderate, Severe
    q4_is_first_visit: bool = True
    q5_taken_any_medication: bool = False
    q5_medication_details: Optional[str] = None
    q6_confirm_regular_medications: bool = True
    q7_existing_conditions: Optional[List[str]] = None
    q8_allergies: Optional[List[str]] = None
    q9_warning_symptoms: Optional[List[str]] = None  # breathing_difficulty, chest_pain, fainting, severe_weakness, high_fever
    q10_additional_notes: Optional[str] = None
    
    # Complaint-Specific Dynamic Branch Responses
    branch_responses: Dict[str, Any] = Field(default_factory=dict)
    
    # Vitals recorded during intake
    vital_temperature: Optional[str] = None
    vital_bp: Optional[str] = None
    vital_pulse: Optional[int] = None
    vital_spo2: Optional[int] = None
    vital_glucose: Optional[str] = None

# ------------------------------------------------------------------------------
# Complaint-Specific Question Branch Registry
# ------------------------------------------------------------------------------

COMPLAINT_BRANCHES: Dict[str, Dict[str, Any]] = {
    "Fever": {
        "title": "Fever & Infection Assessment (Section B - QF)",
        "questions": [
            {"id": "qf1_temperature", "label": "QF1. What is your current body temperature?", "type": "text", "placeholder": "e.g. 101.4 °F", "default": "101.5 °F"},
            {"id": "qf2_fever_days", "label": "QF2. How many days have you had the fever?", "type": "number", "min": 1, "default": 2},
            {"id": "qf3_first_or_repeat", "label": "QF3. Is this your first visit or repeat visit for this fever?", "type": "select", "options": ["First Visit", "Repeat / Persistent Fever"], "default": "First Visit"},
            {"id": "qf4_body_pain", "label": "QF4. Do you have body pain / myalgia?", "type": "boolean", "default": True},
            {"id": "qf5_headache", "label": "QF5. Do you have a headache?", "type": "boolean", "default": True},
            {"id": "qf6_other_symptoms", "label": "QF6. Are you experiencing chills, shivering, or nausea?", "type": "text", "placeholder": "e.g. Chills at night", "default": "Chills in evening"}
        ]
    },
    "Cough": {
        "title": "Cough & Respiratory Assessment (Section B - QC)",
        "questions": [
            {"id": "qc1_cough_type", "label": "QC1. Is the cough dry or productive (with phlegm/mucus)?", "type": "select", "options": ["Dry Cough", "Productive / Wet (Phlegm)"], "default": "Productive / Wet (Phlegm)"},
            {"id": "qc2_cough_duration", "label": "QC2. How long have you had this cough?", "type": "text", "placeholder": "e.g. 5 days", "default": "5 days"},
            {"id": "qc3_throat_discomfort", "label": "QC3. Do you have throat pain or burning sensation?", "type": "boolean", "default": True},
            {"id": "qc4_sneezing", "label": "QC4. Are you sneezing frequently?", "type": "boolean", "default": False},
            {"id": "qc5_runny_nose", "label": "QC5. Do you have a runny or blocked nose?", "type": "boolean", "default": True},
            {"id": "qc6_breathing_difficulty", "label": "QC6. Are you experiencing shortness of breath or wheezing?", "type": "boolean", "default": False}
        ]
    },
    "Cold": {
        "title": "Cold & Upper Respiratory (Section B - QL)",
        "questions": [
            {"id": "ql1_duration", "label": "QL1. How long have you had these cold symptoms?", "type": "text", "default": "3 days"},
            {"id": "ql2_sneezing", "label": "QL2. Are you sneezing?", "type": "boolean", "default": True},
            {"id": "ql3_runny_nose", "label": "QL3. Do you have a runny or congested nose?", "type": "boolean", "default": True},
            {"id": "ql4_throat_discomfort", "label": "QL4. Do you have throat discomfort / soreness?", "type": "boolean", "default": True},
            {"id": "ql5_fever_present", "label": "QL5. Do you also have a fever?", "type": "boolean", "default": False}
        ]
    },
    "Allergy": {
        "title": "Allergic Reaction Assessment (Section B - QA)",
        "questions": [
            {"id": "qa1_allergy_type", "label": "QA1. What type of allergic reaction are you experiencing?", "type": "select", "options": ["Skin Rash / Hives", "Eye Irritation / Redness", "Nasal / Sinus Congestion", "Food Reaction", "Drug Reaction"], "default": "Skin Rash / Hives"},
            {"id": "qa2_itching", "label": "QA2. Do you have severe itching / pruritus?", "type": "boolean", "default": True},
            {"id": "qa3_sneezing", "label": "QA3. Are you sneezing?", "type": "boolean", "default": False},
            {"id": "qa4_cough", "label": "QA4. Do you have a cough or throat tightness?", "type": "boolean", "default": False},
            {"id": "qa5_breathing_difficulty", "label": "QA5. Are you experiencing any breathing difficulty or facial swelling?", "type": "boolean", "default": False},
            {"id": "qa6_location", "label": "QA6. Where is the reaction located on your body?", "type": "text", "default": "Forearms and chest"}
        ]
    },
    "Pain": {
        "title": "Pain & Musculoskeletal Assessment (Section B - QP)",
        "questions": [
            {"id": "qp1_location", "label": "QP1. Where is the pain located?", "type": "text", "placeholder": "e.g. Lower back, right knee, shoulder", "default": "Lower back"},
            {"id": "qp2_duration", "label": "QP2. How long have you had this pain?", "type": "text", "default": "1 week"},
            {"id": "qp3_severity", "label": "QP3. How severe is the pain on a scale of 1 to 10?", "type": "select", "options": ["Mild (1-3)", "Moderate (4-6)", "Severe / Debilitating (7-10)"], "default": "Moderate (4-6)"},
            {"id": "qp4_swelling", "label": "QP4. Is there visible swelling, warmth, or redness?", "type": "boolean", "default": False},
            {"id": "qp5_movement_difficulty", "label": "QP5. Do you have difficulty walking or moving the affected area?", "type": "boolean", "default": True},
            {"id": "qp6_previous_injury", "label": "QP6. Have you experienced this exact pain or injury before?", "type": "boolean", "default": True}
        ]
    },
    "Weakness": {
        "title": "General Weakness & Fatigue Assessment (Section B - QW)",
        "questions": [
            {"id": "qw1_duration", "label": "QW1. How long have you been experiencing weakness or fatigue?", "type": "text", "default": "4 days"},
            {"id": "qw2_severity", "label": "QW2. How severe is the fatigue? (Does it stop daily activities?)", "type": "select", "options": ["Mild (Tired easily)", "Moderate (Difficulty doing chores)", "Severe (Bed-bound / Dizzy)"], "default": "Moderate (Difficulty doing chores)"},
            {"id": "qw3_headache", "label": "QW3. Do you have an accompanying headache or dizziness?", "type": "boolean", "default": True},
            {"id": "qw4_body_pain", "label": "QW4. Do you have generalized body ache or muscle cramps?", "type": "boolean", "default": True},
            {"id": "qw5_associated_symptoms", "label": "QW5. Are you experiencing poor appetite, nausea, or pale skin?", "type": "text", "default": "Loss of appetite and dizziness on standing"}
        ]
    },
    "Blood Pressure": {
        "title": "Cardiovascular & Blood Pressure Branch (Section B - QM)",
        "questions": [
            {"id": "qm1_visit_type", "label": "QM1. Is this a routine check-up or a problem-related visit?", "type": "select", "options": ["Routine Hypertension Check-up", "Problem-related visit (High BP / Symptoms)"], "default": "Problem-related visit (High BP / Symptoms)"},
            {"id": "qm2_latest_bp", "label": "QM2. What is your latest blood pressure reading (if measured)?", "type": "text", "placeholder": "e.g. 210/130 mmHg", "default": "210/130 mmHg"},
            {"id": "qm2_latest_glucose", "label": "QM2b. Latest Blood Glucose reading (if known)?", "type": "text", "placeholder": "e.g. 140 mg/dL", "default": "142 mg/dL"},
            {"id": "qm3_taking_medication", "label": "QM3. Are you currently taking your prescribed BP/cardiac medication?", "type": "boolean", "default": True},
            {"id": "qm4_new_symptoms", "label": "QM4. Are you experiencing headache, palpitations, chest constriction, or nausea?", "type": "text", "default": "Severe occipital headache, palpitations, and chest constriction"}
        ]
    },
    "Diabetes": {
        "title": "Metabolic & Diabetes Branch (Section B - QM)",
        "questions": [
            {"id": "qm1_visit_type", "label": "QM1. Is this a routine check-up or sugar imbalance visit?", "type": "select", "options": ["Routine Diabetic Check-up", "Problem-related (High/Low Sugar Symptoms)"], "default": "Routine Diabetic Check-up"},
            {"id": "qm2_latest_fasting", "label": "QM2a. Fasting Blood Glucose (mg/dL)?", "type": "text", "placeholder": "e.g. 135 mg/dL", "default": "135 mg/dL"},
            {"id": "qm2_latest_pp", "label": "QM2b. Post-Meal / Random Glucose (mg/dL)?", "type": "text", "placeholder": "e.g. 190 mg/dL", "default": "190 mg/dL"},
            {"id": "qm3_taking_medication", "label": "QM3. Are you taking insulin or oral antidiabetic drugs as prescribed?", "type": "boolean", "default": True},
            {"id": "qm4_new_symptoms", "label": "QM4. Experiencing extreme thirst, frequent urination, or blurred vision?", "type": "text", "default": "Mild blurry vision and increased thirst"}
        ]
    }
}

# ------------------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------------------

@router.get("/profile-autofill/{patient_id}")
def get_patient_profile_for_intake(patient_id: str, db: Session = Depends(get_db)):
    """
    Step 1 in Clinic Workflow:
    Patient scans QR code -> System auto-fetches age, medical history, allergies, existing medications.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found.")
    
    # Retrieve previous consultation for comparative baseline if exists
    last_consult = db.query(Consultation).filter(
        Consultation.patient_id == patient_id
    ).order_by(Consultation.created_at.desc()).first()

    return {
        "patient_id": patient.id,
        "full_name": patient.full_name,
        "age": patient.age,
        "gender": patient.gender,
        "blood_group": patient.blood_group,
        "allergies": patient.allergies or [],
        "existing_conditions": patient.existing_conditions or [],
        "current_medications": patient.current_medications or [],
        "has_previous_visit": last_consult is not None,
        "last_visit_summary": {
            "date": last_consult.created_at.strftime("%Y-%m-%d") if last_consult else None,
            "complaint": last_consult.chief_complaint if last_consult else None,
            "diagnosis": last_consult.doctor_note.confirmed_diagnosis if (last_consult and last_consult.doctor_note) else None
        } if last_consult else None
    }


@router.get("/branch/{complaint_key}")
def get_complaint_branch_questions(complaint_key: str):
    """
    Step 4: Returns dynamic questions for the chosen chief complaint.
    """
    # Normalize key matching
    for key, data in COMPLAINT_BRANCHES.items():
        if key.lower() in complaint_key.lower() or complaint_key.lower() in key.lower():
            return {"complaint": key, **data}
    
    # Default general branch
    return {
        "complaint": complaint_key,
        "title": f"General Symptom Assessment: {complaint_key}",
        "questions": [
            {"id": "qg1_details", "label": "Please describe your symptoms and when they started:", "type": "textarea", "default": "Started feeling unwell recently."},
            {"id": "qg2_severity", "label": "How much does this affect your normal routine?", "type": "select", "options": ["Mild", "Moderate", "Severe"], "default": "Moderate"}
        ]
    }


@router.post("/submit")
def submit_patient_intake(payload: PatientIntakePayload, db: Session = Depends(get_db)):
    """
    Step 6-7: Submits the dynamic intake questionnaire, checks warning signs,
    triggers URGENT flag if necessary, and persists record for doctor review.
    """
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    # Evaluate Warning Symptoms (Q9) and Emergency criteria
    warning_list = payload.q9_warning_symptoms or []
    is_urgent = False
    urgent_reasons = []

    critical_triggers = ["chest_pain", "breathing_difficulty", "fainting", "severe_weakness", "very_high_fever"]
    for trig in critical_triggers:
        if trig in [w.lower().replace(" ", "_") for w in warning_list]:
            is_urgent = True
            urgent_reasons.append(trig.replace("_", " ").title())

    # Check BP severity if Blood Pressure complaint
    if payload.vital_bp:
        try:
            sys_bp = int(payload.vital_bp.split("/")[0].strip())
            if sys_bp >= 180:
                is_urgent = True
                urgent_reasons.append(f"Hypertensive Crisis (Systolic BP {sys_bp} mmHg >= 180)")
        except Exception:
            pass

    consult_id = f"consult_{int(datetime.datetime.now().timestamp())}_{payload.patient_id[:6]}"

    new_consultation = Consultation(
        id=consult_id,
        patient_id=payload.patient_id,
        doctor_id=payload.doctor_id,
        clinic_id=payload.clinic_id,
        visit_type="FIRST_VISIT" if payload.q4_is_first_visit else "REPEAT_VISIT",
        chief_complaint=payload.q1_chief_complaint,
        symptom_duration_value=payload.q2_duration_value,
        symptom_duration_unit=payload.q2_duration_unit,
        symptom_severity=payload.q3_severity,
        is_repeat_visit=not payload.q4_is_first_visit,
        medicine_taken=payload.q5_taken_any_medication,
        medicine_taken_name=payload.q5_medication_details,
        regular_medications_confirmed=payload.q6_confirm_regular_medications,
        existing_conditions_confirmed=True,
        allergies_confirmed=True,
        warning_symptoms=warning_list,
        patient_notes=payload.q10_additional_notes,
        branch_responses=payload.branch_responses,
        status="REFERRED_ICU" if (is_urgent and ("Hypertensive" in str(urgent_reasons) or "chest" in str(warning_list))) else ("IN_DOCTOR_QUEUE" if is_urgent else "TRIAGED"),
        is_urgent=is_urgent,
        urgency_reason=", ".join(urgent_reasons) if urgent_reasons else None,
        seasonal_context="monsoon"
    )

    db.add(new_consultation)
    db.commit()
    db.refresh(new_consultation)

    return {
        "success": True,
        "consultation_id": new_consultation.id,
        "is_urgent": is_urgent,
        "urgent_reasons": urgent_reasons,
        "triage_status": new_consultation.status,
        "message": "Intake questionnaire submitted successfully. Structured preliminary doctor's note generated for doctor review."
    }

@router.post("/nlp-parse")
def parse_multilingual_intake(payload: Dict[str, str]):
    """NLP parsing of patient symptom text/voice across Marathi, Hindi, Hinglish, English."""
    from .ai_summarizer import parse_multilingual_symptoms
    text = payload.get("text", "")
    parsed = parse_multilingual_symptoms(text)
    return {
        "success": True,
        "parsed": parsed
    }

