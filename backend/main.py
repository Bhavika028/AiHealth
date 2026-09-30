"""
PulseSync AI - Core FastAPI Application Server
Integrates Dynamic Adaptive Intake Engine, AI Clinical Note Generator, QR Services, Clinical Dashboards, and Real-Time WebSocket Engine.
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import logging

from .database import init_db, get_db_info
from .routers import auth, intake, ai_summarizer, qr_engine, clinical, realtime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pulsesync.main")

app = FastAPI(
    title="PulseSync AI API",
    description="AI-Powered Healthcare Workflow, Dynamic Patient Intake, ICU Bed & Pharmacy Dispensing Engine",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth.router)
app.include_router(intake.router)
app.include_router(ai_summarizer.router)
app.include_router(qr_engine.router)
app.include_router(clinical.router)
app.include_router(realtime.router)

# Direct Public QR Verification Routes (Easily scannable by mobile phones)
from .database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends

@app.get("/qr/patient/{patient_id}")
def qr_patient_card(patient_id: str, db: Session = Depends(get_db)):
    return qr_engine.view_patient_public_card(patient_id, db)

@app.get("/qr/insurance/{patient_id}")
def qr_insurance_card(patient_id: str, db: Session = Depends(get_db)):
    return qr_engine.view_insurance_public_card(patient_id, db)

# Health & Metrics Endpoint
@app.get("/api/health")
def health_check():
    db_info = get_db_info()
    return {
        "status": "healthy",
        "service": "PulseSync AI Healthcare Platform",
        "version": "2.0.0",
        "database": db_info
    }

# Mount Frontend Static Assets
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
def serve_frontend_root():
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(
            index_file,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {
        "message": "PulseSync AI API is active. Visit /docs for Swagger UI documentation.",
        "api_docs": "/docs"
    }

@app.on_event("startup")
def on_startup():
    logger.info("[STARTUP] Initializing PulseSync AI tables and verifying database connectivity...")
    init_db()
    info = get_db_info()
    logger.info(f"[STARTUP] Database connected: {info['dialect'].upper()} ({info['tables_count']} tables present).")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
