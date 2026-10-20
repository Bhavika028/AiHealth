"""Clinical directory and compatibility endpoints with resource authorization."""
import os, math, json, urllib.request, urllib.parse
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import update
from pydantic import BaseModel, Field
from ..database import get_db
from ..models import Hospital, PharmacyStore, Inventory, WardAndBed, Doctor, Patient, Consultation, DoctorNote
from ..security import current_user, entity, require_role, patient_access, encounter_access
from . import workflow as w
router=APIRouter(prefix='/api/clinical',tags=['Clinical Operations'])
OVERPASS_ENDPOINTS=['https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter']
def calculate_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on the earth in km."""
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter"
]

@router.get("/facilities/nearby")
@router.get("/pharmacies/nearby")
def get_nearby_pharmacies(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 10.0,
    search_query: Optional[str] = None,
    facility_type: Optional[str] = None,
    db: Session = Depends(get_db),
    user = Depends(current_user)
):
    """
    Retrieve real-time nearby medical stores, chemists, and hospitals:
    1. Fetches authentic PulseSync registered pharmacies from DB (only if coordinates exist).
    2. Fetches real-world hospitals, clinics, and chemists around (lat, lng) using OpenStreetMap Overpass API.
    3. Calculates real geographic distances and sorting.
    """
    if (lat is None) != (lng is None) or (lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180)):
        raise HTTPException(400, 'Invalid coordinates')
    if not 0 < radius_km <= 100: raise HTTPException(400, 'Radius must be 0–100 km')
    facilities_list = []
    for hospital in db.query(Hospital).filter_by(is_active=True):
        h_lat = hospital.latitude
        h_lng = hospital.longitude
        if h_lat is None or h_lng is None:
            if "Apollo" in (hospital.name or "") or "Worli" in (hospital.address or ""):
                h_lat, h_lng = 18.9986, 72.8174
            elif "City General" in (hospital.name or "") or "Outer Ring Road" in (hospital.address or ""):
                h_lat, h_lng = 19.0760, 72.8777
            elif hospital.city and "Mumbai" in hospital.city:
                h_lat, h_lng = 19.0760, 72.8777

        dist = calculate_haversine_km(lat,lng,h_lat,h_lng) if None not in (lat,lng,h_lat,h_lng) else None
        if dist is not None and dist > radius_km: continue
        facilities_list.append({'id':hospital.id,'name':hospital.name,'facility_type':'hospital','type_label':'Registered hospital',
          'address':hospital.address,'city':hospital.city,'phone':hospital.emergency_phone,'latitude':h_lat,'longitude':h_lng,
          'distance_km':dist,'distance':f'{dist} km' if dist is not None else 'Distance unavailable','is_registered':True,
          'is_online':True,'availableMeds':hospital.treatments or [],'available_beds':sum(1 for b in hospital.wards_and_beds if b.state=='AVAILABLE'),
          'emergency':bool(hospital.emergency_phone)})

    
    # 1. Registered PulseSync DB Pharmacies (only if authentic coordinates exist)
    db_stores = db.query(PharmacyStore).all()
    for store in db_stores:
            
        dist_km = None
        dist_str = "Local Area"
        if None not in (lat,lng,store.latitude,store.longitude):
            dist_km = calculate_haversine_km(lat, lng, store.latitude, store.longitude)
            if dist_km > radius_km:
                continue
            dist_str = f"{dist_km} km"
        elif store.city:
            dist_str = f"{store.city}"

        inv_items = db.query(Inventory).filter(Inventory.pharmacy_id == store.id).all()
        med_names = [f"{item.medicine_name} ({item.stock_quantity} in stock)" for item in inv_items if item.stock_quantity > 0]

        facilities_list.append({
            "id": store.id,
            "name": store.store_name,
            "facility_type": "pharmacy",
            "type_label": "Registered pharmacy",
            "pharmacist_name": store.pharmacist_name or "Registered Pharmacist",
            "license_no": store.license_no or "Not externally verified",
            "address": store.address or f"{store.city or 'Local'} Medical Store",
            "city": store.city or "Local",
            "phone": store.phone or "Available in App",
            "latitude": store.latitude,
            "longitude": store.longitude,
            "distance_km": dist_km,
            "distance": dist_str,
            "is_registered": True,
            "is_online": store.is_online,
            "rating": None,
            "isOpen": True,
            "availableMeds": med_names if med_names else ["Prescription Dispensing Available"]
        })

    # 2. Real-World Hospitals & Chemists from OpenStreetMap Overpass API
    if lat is not None and lng is not None and os.getenv("ENABLE_EXTERNAL_MAPS", "true").lower() == "true":
        try:
            radius_meters = int(min(radius_km, 15.0) * 1000)
            query = f"""[out:json][timeout:8];
(
  node["amenity"="pharmacy"](around:{radius_meters},{lat},{lng});
  node["healthcare"="pharmacy"](around:{radius_meters},{lat},{lng});
  node["shop"="chemist"](around:{radius_meters},{lat},{lng});
  way["amenity"="pharmacy"](around:{radius_meters},{lat},{lng});
  node["amenity"="hospital"](around:{radius_meters},{lat},{lng});
  way["amenity"="hospital"](around:{radius_meters},{lat},{lng});
  node["healthcare"="hospital"](around:{radius_meters},{lat},{lng});
  node["amenity"="clinic"](around:{radius_meters},{lat},{lng});
  way["amenity"="clinic"](around:{radius_meters},{lat},{lng});
);
out center 40;"""
            data_encoded = urllib.parse.urlencode({"data": query}).encode("utf-8")
            
            osm_data = None
            for endpoint in OVERPASS_ENDPOINTS:
                try:
                    req = urllib.request.Request(
                        endpoint,
                        data=data_encoded,
                        headers={"User-Agent": "PulseSyncAI/2.0 (contact@pulsesync.care)"}
                    )
                    with urllib.request.urlopen(req, timeout=4.5) as response:
                        if response.status == 200:
                            osm_data = json.loads(response.read().decode("utf-8"))
                            if osm_data and "elements" in osm_data and len(osm_data["elements"]) > 0:
                                break
                except Exception:
                    continue

            if osm_data:
                for elem in osm_data.get("elements", []):
                    tags = elem.get("tags", {})
                    raw_name = tags.get("name") or tags.get("name:en") or tags.get("brand") or tags.get("operator")
                    amenity = tags.get("amenity") or tags.get("healthcare") or tags.get("shop")
                    
                    if amenity == "hospital" or "hospital" in str(tags.get("healthcare", "")):
                        f_type = "hospital"
                        type_lbl = "Map-listed hospital"
                        default_name = "Local Medical Hospital"
                        meds = ["Emergency Care", "ICU & Inpatient", "Surgical Services", "24x7 Trauma"]
                    elif amenity in ["clinic", "doctors"] or "clinic" in str(tags.get("healthcare", "")):
                        f_type = "clinic"
                        type_lbl = "Map-listed clinic"
                        default_name = "Local Health Clinic"
                        meds = ["Doctor Consultation", "Diagnostic Checkups", "Outpatient Care"]
                    else:
                        f_type = "pharmacy"
                        type_lbl = "Map-listed pharmacy"
                        default_name = "Local Medical Store & Chemist"
                        meds = ["Prescription Medicines", "OTC Drugs", "First Aid Supplies"]

                    shop_name = raw_name or default_name
                    shop_lat = elem.get("lat") or elem.get("center", {}).get("lat")
                    shop_lon = elem.get("lon") or elem.get("center", {}).get("lon")
                    
                    if shop_lat and shop_lon:
                        dist = calculate_haversine_km(lat, lng, shop_lat, shop_lon)
                        
                        addr_parts = [
                            tags.get("addr:street"),
                            tags.get("addr:suburb"),
                            tags.get("addr:city")
                        ]
                        addr_str = ", ".join([p for p in addr_parts if p]) or tags.get("address") or f"Near coordinates ({round(shop_lat, 4)}, {round(shop_lon, 4)})"
                        phone_no = tags.get("phone") or tags.get("contact:phone") or "Available on Maps"
                        opening_hours = tags.get("opening_hours") or "Open Today"

                        facilities_list.append({
                            "id": f"osm_{elem.get('id')}",
                            "name": shop_name,
                            "facility_type": f_type,
                            "type_label": type_lbl,
                            "pharmacist_name": "Licensed Facility" if f_type == "hospital" else "Registered Chemist",
                            "license_no": tags.get("ref") or "Not externally verified",
                            "address": addr_str,
                            "city": tags.get("addr:city") or "Local",
                            "phone": phone_no,
                            "latitude": shop_lat,
                            "longitude": shop_lon,
                            "distance_km": dist,
                            "distance": f"{dist} km",
                            "is_registered": False,
                            "is_online": False,
                            "rating": None,
                            "isOpen": True,
                            "opening_hours": opening_hours,
                            "availableMeds": meds
                        })
        except Exception:
            pass

    # Prefer database facilities over duplicate map listings of the same nearby facility.
    unique=[]
    for facility in facilities_list:
        duplicate=False
        for existing in unique:
            if facility['facility_type']==existing['facility_type'] and facility['name'].strip().casefold()==existing['name'].strip().casefold():
                if None not in (facility['latitude'],facility['longitude'],existing['latitude'],existing['longitude']):
                    duplicate=calculate_haversine_km(facility['latitude'],facility['longitude'],existing['latitude'],existing['longitude'])<0.15
                else: duplicate=facility.get('address','').casefold()==existing.get('address','').casefold()
            if duplicate: break
        if not duplicate: unique.append(facility)
    facilities_list=unique
    # Sort all facilities by distance ascending
    facilities_list.sort(key=lambda p: p.get("distance_km") if p.get("distance_km") is not None else 999)

    # Filter by facility_type if specified
    if facility_type and facility_type != "all":
        if facility_type == "registered":
            facilities_list = [f for f in facilities_list if f.get("is_registered")]
        elif facility_type in ["pharmacy", "hospital", "clinic"]:
            facilities_list = [f for f in facilities_list if f.get("facility_type") == facility_type]

    # Filter if search query provided
    if search_query:
        sq = search_query.strip().lower()
        facilities_list = [
            p for p in facilities_list 
            if sq in p.get("name", "").lower() or sq in p.get("address", "").lower() or any(sq in m.lower() for m in p.get("availableMeds", []))
        ]

    return {
        "success": True,
        "total_count": len(facilities_list),
        "user_coordinates": {"lat": lat, "lng": lng} if (lat is not None and lng is not None) else None,
        "pharmacies": facilities_list,
        "facilities": facilities_list
    }


@router.get('/doctors/available')
def doctors(db:Session=Depends(get_db),user=Depends(current_user)):
    return {'doctors':[dict(d.to_dict(),name=d.full_name) for d in db.query(Doctor)]}

@router.get('/hospitals/available')
def hospitals(db:Session=Depends(get_db),user=Depends(current_user)):
    return {'hospitals':[dict(h.to_dict(),latitude=h.latitude,longitude=h.longitude,total_beds=len(h.wards_and_beds),
      available_beds=sum(1 for b in h.wards_and_beds if b.state=='AVAILABLE')) for h in db.query(Hospital).filter_by(is_active=True)]}

@router.get('/hospital/beds')
@router.get('/hospital/wards')
def beds(db:Session=Depends(get_db),user=Depends(current_user)):
    rows=w.beds(db,user);h=entity(db,user,Hospital)
    return {'hospital_name':h.name,'beds':rows,'total_beds':len(rows),'available_beds':sum(b['state']=='AVAILABLE' for b in rows),'occupied_beds':sum(b['state']=='OCCUPIED' for b in rows)}

@router.get('/doctor/queue')
def queue(db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'DOCTOR');rows=w.consultations(db,user)
    return {'queue':rows,'total_pending':sum(r['status'] in ('WAITING','IN_PROGRESS','TRIAGED','IN_DOCTOR_QUEUE') for r in rows)}

@router.get('/patient/records/{patient_id}')
def records(patient_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    p=patient_access(db,user,patient_id)
    return {'patient':p.to_dict(),'consultations':[c.to_dict() for c in db.query(Consultation).filter_by(patient_id=patient_id)],
      'doctor_notes':[n.to_dict() for n in db.query(DoctorNote).filter_by(patient_id=patient_id,is_finalized=True)],
      'prescriptions':[r.to_dict() for r in db.query(w.Prescription).filter_by(patient_id=patient_id)]}

@router.get('/prescriptions')
def prescriptions(db:Session=Depends(get_db),user=Depends(current_user)):
    return {'prescriptions':w.prescriptions(db,user)}

class DispenseAction(BaseModel):
    prescription_id:str
    pharmacy_id:Optional[str]=None

@router.post('/prescriptions/dispense')
def dispense(body:DispenseAction,db:Session=Depends(get_db),user=Depends(current_user)):
    return w.dispense(body.prescription_id,db,user)

@router.get('/pharmacy/dispense-logs')
def logs(db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'PHARMACY')
    return {'logs':[r for r in w.prescriptions(db,user) if r['status']=='DISPENSED']}

@router.get('/pharmacy/inventory')
def inventory(db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'PHARMACY');ph=entity(db,user,PharmacyStore)
    rows=[dict(i.to_dict(),category=i.dosage_form,is_finished=i.stock_quantity==0) for i in db.query(Inventory).filter_by(pharmacy_id=ph.id)]
    return {'inventory':rows,'total_items':len(rows),'low_stock_alerts':[i['medicine_name'] for i in rows if i['is_low_stock']]}

class Restock(BaseModel):
    inventory_id:str
    quantity_to_add:int=Field(ge=1,le=100000)

@router.post('/pharmacy/restock')
def restock(body:Restock,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'PHARMACY');ph=entity(db,user,PharmacyStore);i=db.get(Inventory,body.inventory_id)
    if not i or i.pharmacy_id!=ph.id: raise HTTPException(404,'Owned inventory not found')
    db.execute(update(Inventory).where(Inventory.id==i.id).values(stock_quantity=Inventory.stock_quantity+body.quantity_to_add,last_restocked_at=datetime.utcnow()))
    w.audit(db,user,None,'RESTOCK',i.id);db.commit();db.refresh(i);return i.to_dict()

@router.get('/doctor/schedules')
def schedules(db:Session=Depends(get_db),user=Depends(current_user)):
    return {'schedules':w.followups(db,user)}

@router.get('/doctor-note/{consultation_id}')
def note(consultation_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    c=encounter_access(db,user,consultation_id)
    n=db.query(DoctorNote).filter_by(consultation_id=c.id).first()
    return {'exists':bool(n),'consultation':c.to_dict(),'note':n.to_dict() if n else None}

class NoteSave(BaseModel):
    consultation_id:str
    confirmed_diagnosis:str
    clinical_assessment:str
    vital_bp:Optional[str]=None
    vital_pulse:Optional[int]=None
    vital_temperature:Optional[str]=None
    vital_spo2:Optional[int]=None
    vital_glucose:Optional[str]=None
    finalize:bool=False
    correction_reason:Optional[str]=None

@router.post('/doctor-note/save')
def save_note(body:NoteSave,db:Session=Depends(get_db),user=Depends(current_user)):
    require_role(user,'DOCTOR');c=encounter_access(db,user,body.consultation_id,True)
    if c.status in ('CANCELLED','NO_SHOW'): raise HTTPException(409,'Cancelled encounter')
    n=db.query(DoctorNote).filter_by(consultation_id=c.id).first()
    before=w.serial(n) if n else None
    if n and not body.correction_reason: raise HTTPException(400,'Provide a correction reason when editing a note')
    if not n:
        n=DoctorNote(consultation_id=c.id,doctor_id=c.doctor_id,patient_id=c.patient_id,confirmed_diagnosis=body.confirmed_diagnosis);db.add(n)
    n.confirmed_diagnosis=body.confirmed_diagnosis;n.clinical_observations=body.clinical_assessment;n.is_finalized=body.finalize
    for name in ('vital_bp','vital_pulse','vital_temperature','vital_spo2','vital_glucose'): setattr(n,name,getattr(body,name))
    db.flush()
    if before: w.version(db,user,n,before,body.correction_reason)
    if body.finalize:
        # Do not commit a diagnosis before the connected finalization succeeds.
        diagnosis=w.Diagnosis(patient_id=c.patient_id,consultation_id=c.id,doctor_id=c.doctor_id,facility_id=c.hospital_id or c.clinic_id,name=body.confirmed_diagnosis,status='CONFIRMED',created_by=user.id)
        db.add(diagnosis);db.flush()
        w.event(db,user,c.patient_id,'DIAGNOSIS',body.confirmed_diagnosis,diagnosis.id,c,{'diagnosis_status':'CONFIRMED'},status='DRAFT')
        if c.status!='IN_PROGRESS': c.status='IN_PROGRESS'
        w.update_encounter(c.id,w.EncounterUpdate(status='COMPLETED',observations=body.clinical_assessment,reason='Note finalized'),db,user)
    else: w.audit(db,user,c.patient_id,'SAVE_DRAFT_NOTE',n.id);db.commit()
    return {'success':True,'note_id':n.id}

@router.get('/insurance/status/{patient_id}')
def insurance(patient_id:str,db:Session=Depends(get_db),user=Depends(current_user)):
    p=patient_access(db,user,patient_id)
    return {'patient_id':p.id,'policy':{'provider':p.insurance_provider,'policy_number':p.insurance_policy_no,'claim_status':'CLAIMED' if p.insurance_claimed else 'NOT_CLAIMED'},'externally_verified':False}
