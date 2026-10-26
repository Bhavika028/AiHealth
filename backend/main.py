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
from .routers import auth, intake, ai_summarizer, qr_engine, clinical, realtime, workflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pulsesync.main")

from fastapi.exceptions import RequestValidationError

app = FastAPI(
    title="PulseSync AI API",
    description="AI-Powered Healthcare Workflow, Dynamic Patient Intake, ICU Bed & Pharmacy Dispensing Engine",
    version="2.0.0"
)

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422,content={'detail':[{'loc':list(e['loc']),'msg':e['msg'],'type':e['type']} for e in exc.errors()]})

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=(self)"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

# Register API Routers
from .routers import pin_access
app.include_router(pin_access.router)
from .routers import visit
app.include_router(visit.router)
app.include_router(workflow.router)
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

@app.get("/qr/admission/{patient_id}")
def qr_admission_card(patient_id: str, db: Session = Depends(get_db)):
    return qr_engine.view_admission_public_card(patient_id, db)


# Health & Metrics Endpoint
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "PulseSync AI Healthcare Platform",
        "version": "2.0.0",
        "database": "configured"
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

@app.get('/qr/{kind}/{provider_id}', response_class=__import__('fastapi.responses',fromlist=['HTMLResponse']).HTMLResponse)
def provider_landing(kind:str,provider_id:str,db:Session=Depends(get_db)):
    import html
    from .models import Doctor,Hospital,PharmacyStore
    from fastapi.responses import HTMLResponse
    model={'doctor':Doctor,'hospital':Hospital,'pharmacy':PharmacyStore}.get(kind)
    if not model: return HTMLResponse('Not found',status_code=404)
    row=db.get(model,provider_id)
    if not row: return HTMLResponse('Not found',status_code=404)
    name=getattr(row,'full_name',None) or getattr(row,'name',None) or getattr(row,'store_name',None)
    address=getattr(row,'clinic_address',None) or getattr(row,'address',None) or ''
    return HTMLResponse(f'<!doctype html><meta name="viewport" content="width=device-width"><title>PulseSync provider</title><h1>{html.escape(name)}</h1><p>{html.escape(address)}</p><a href="/">Sign in to request care</a>')
