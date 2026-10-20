"""Real database journey and cross-account access regression checks (isolated SQLite)."""
import os, tempfile, uuid
os.environ['DATABASE_URL']='sqlite:///'+tempfile.mktemp(suffix='.db')
os.environ['ENABLE_EXTERNAL_MAPS']='false'
os.environ['UPLOAD_DIR']=tempfile.mkdtemp(prefix='healthflow-test-documents-')
os.environ['JWT_SECRET']='test-only-key-'+uuid.uuid4().hex
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal,init_db
from backend.models import Hospital,Patient,Consultation,WardAndBed
from backend.workflow_models import MedicalEvent,Medication


def test_full_journey():
    with TestClient(app) as client:
        def call(path,actor=None,method='GET',body=None,expected=200):
            headers={'Authorization':'Bearer '+actor['access_token']} if actor else {}
            res=client.request(method,'/api/'+path,headers=headers,json=body)
            assert res.status_code==expected,(path,res.status_code,res.text)
            return res.json()
        def register(role,name,**fields):
            return call('auth/register',method='POST',body={'role':role,'name':name,'email':name+'@test.invalid','pin':'012345','confirm_pin':'012345','password':'correct-horse-12','phone':'9999999999',**fields})
        p=register('PATIENT','PatientA',age=20,gender='Male',allergies=['Penicillin'])
        p2=register('PATIENT','PatientB',age=30,gender='Female')
        d=register('DOCTOR','DoctorA',specialization='General Medicine',clinic_name='ClinicA')
        d2=register('DOCTOR','DoctorB',specialization='Cardiology')
        h=register('HOSPITAL_ADMIN','HospitalA',hospital_name='Care A',latitude=19.076,longitude=72.8777,address='Road A',city='Mumbai',total_icu_beds=1,total_general_beds=1)
        h2=register('HOSPITAL_ADMIN','HospitalB',hospital_name='Care B',latitude=19.08,longitude=72.88,total_icu_beds=1,total_general_beds=0)
        h3=register('HOSPITAL_ADMIN','HospitalNoCoordinates',hospital_name='Address only',address='Local Road',total_icu_beds=0,total_general_beds=0)
        ph=register('PHARMACY','PharmacyA',store_name='Store A',latitude=19.076,longitude=72.8777)
        ph2=register('PHARMACY','PharmacyB',store_name='Store B')
        pid=p['user']['patient_id'];did=d['user']['doctor_id'];hid=h['user']['hospital_id'];phid=ph['user']['pharmacy_id']
        assert h2['user']['hospital_id']!=hid
        assert call('auth/me',h)['user']['hospital_id']==hid
        facilities=call('clinical/facilities/nearby?lat=19.076&lng=72.8777',p)['facilities']
        assert any(x['id']==hid and x['distance_km']==0 for x in facilities)
        assert any(x['name']=='Address only' and x['distance_km'] is None for x in facilities)
        assert not call('workflow/beds',h3)
        call('workflow/history/'+pid,p2,expected=403)
        call('workflow/history/'+pid,d2,expected=403)
        call('workflow/history/'+pid,ph,expected=403)
        call('auth/me?user_id='+p['user']['id'],expected=401)
        call('workflow/history/'+pid,expected=401)
        call('clinical/pharmacy/inventory',p,expected=403)
        call('auth/register',method='POST',body={'role':'ADMIN','name':'BadRole','email':'bad@test.invalid','pin':'012345','confirm_pin':'012345','password':'abcd'},expected=400)
        # Full adaptive intake drives the doctor's existing queue.
        intake=call('intake/submit',p,'POST',{'patient_id':pid,'doctor_id':did,'q1_chief_complaint':'Fever','q2_duration_value':2,'q10_additional_notes':'Fever and fatigue','branch_responses':{'temperature':'38'}})
        cid=intake['consultation_id']
        queue=call('clinical/doctor/queue',d)['queue'];assert queue[0]['id']==cid
        call('intake/submit',p2,'POST',{'patient_id':pid,'doctor_id':did,'q1_chief_complaint':'Fever','q2_duration_value':1},403)
        call('workflow/consultations/'+cid,d,'PATCH',{'status':'IN_PROGRESS','reason':'Patient seen'},403)
        call('workflow/access/'+pid,p,'POST',{'scope':'CLINICAL','provider_user_id':d['user']['id'],'pin':'012345'})
        call('workflow/consultations/'+cid,d,'PATCH',{'status':'IN_PROGRESS','reason':'Patient seen'})
        vital=call('workflow/consultations/'+cid+'/vitals',d,'POST',{'name':'BP','value':'120/80','unit':'mmHg'})
        dx=call('workflow/consultations/'+cid+'/diagnoses',d,'POST',{'name':'Viral fever','status':'PROVISIONAL'})
        assert not any(x['kind'] in ('VITAL','DIAGNOSIS') for x in call('workflow/history/'+pid,p)['events'])
        draft=call('ai/generate-summary',d,'POST',{'consultation_id':cid})
        assert '210/130' not in draft['structured_note_markdown']
        call('workflow/consultations/'+cid,d2,'PATCH',{'status':'COMPLETED','reason':'wrong doctor'},403)
        call('workflow/consultations/'+cid,d,'PATCH',{'status':'COMPLETED','observations':'Rest, hydration; reviewed','reason':'Consultation completed'})
        # Prescription assignment, warning acknowledgement, and inventory deduction.
        call('workflow/consultations/'+cid+'/prescriptions',d,'POST',{'medicines':[{'name':'Penicillin','dosage':'500 mg','frequency':'Daily'}]},409)
        rx=call('workflow/consultations/'+cid+'/prescriptions',d,'POST',{'pharmacy_id':phid,'medicines':[{'name':'Paracetamol','dosage':'500 mg','frequency':'As directed','duration_days':3,'quantity':6}]})
        med=call('workflow/medications/'+pid,p)[0];assert med['status']=='ACTIVE'
        assert call('workflow/prescriptions',ph2)==[]
        call('workflow/prescriptions/'+rx['id']+'/dispense',ph2,'POST',expected=403)
        call('workflow/prescriptions/'+rx['id']+'/dispense',ph,'POST',expected=409)
        inv=call('workflow/inventory',ph,'POST',{'medicine_name':'Paracetamol','dosage_form':'Tablet','stock_quantity':20})
        call('clinical/pharmacy/restock',ph2,'POST',{'inventory_id':inv['id'],'quantity_to_add':2},404)
        call('workflow/prescriptions/'+rx['id']+'/dispense',ph,'POST')
        call('workflow/prescriptions/'+rx['id']+'/dispense',ph,'POST',expected=409)
        assert call('clinical/pharmacy/inventory',ph)['inventory'][0]['stock_quantity']==14
        assert call('workflow/medications/'+pid,p)[0]['status']=='ACTIVE'
        r=call('workflow/referrals',d,'POST',{'consultation_id':cid,'hospital_id':hid,'specialty':'General medicine','reason':'Persistent symptoms','clinical_summary':'Assessment requested','priority':'ROUTINE'})
        assert len(call('workflow/referrals',h))==1
        assert call('workflow/referrals',h2)==[]
        call('workflow/referrals/'+r['id'],h2,'PATCH',{'status':'RECEIVED','reason':'Wrong facility'},403)
        for status in ['RECEIVED','ACCEPTED','PATIENT_ARRIVED']:
            call('workflow/referrals/'+r['id'],h,'PATCH',{'status':status,'reason':'Workflow acknowledged'})
        token=call('workflow/hospital/invite',h,'POST')['invitation']
        call('workflow/doctor/affiliation',d2,'POST',{'invitation':token})
        c2=call('workflow/consultations',h,'POST',{'patient_id':pid,'doctor_id':d2['user']['doctor_id'],'chief_complaint':'Specialist review','referral_id':r['id']})
        call('workflow/access/'+pid,p,'POST',{'scope':'CLINICAL','provider_user_id':d2['user']['id'],'pin':'012345'})
        call('workflow/consultations/'+c2['id'],d2,'PATCH',{'status':'IN_PROGRESS','reason':'Review started'})
        call('workflow/consultations/'+c2['id']+'/diagnoses',d2,'POST',{'name':'Viral illness','status':'CONFIRMED'})
        call('workflow/consultations/'+c2['id'],d2,'PATCH',{'status':'COMPLETED','reason':'Specialist completed','observations':'Clinical improvement'})
        beds=call('workflow/beds',h);b=beds[0]
        call('workflow/admissions',h2,'POST',{'patient_id':pid,'bed_id':b['id'],'reason':'Wrong hospital'},403)
        a=call('workflow/admissions',h,'POST',{'patient_id':pid,'bed_id':b['id'],'reason':'Observation','consultation_id':c2['id'],'referral_id':r['id'],'doctor_id':d2['user']['doctor_id']})
        call('workflow/admissions',h,'POST',{'patient_id':pid,'bed_id':b['id'],'reason':'Duplicate'},409)
        call('workflow/admissions/'+a['id']+'/discharge',h,'POST',{'summary':'Improved; return if worsening'})
        assert call('workflow/beds',h)[0]['state']=='CLEANING'
        call('workflow/beds/'+b['id'],h,'PATCH',{'status':'AVAILABLE','reason':'Cleaning complete'})
        call('workflow/referrals/'+r['id'],h,'PATCH',{'status':'COMPLETED','reason':'Care completed','outcome_summary':'Improved; review in 7 days'})
        assert call('workflow/referrals',d)[0]['outcome_summary']
        f=call('workflow/follow-ups',d,'POST',{'consultation_id':cid,'after_days':7,'reason':'Review recovery'})
        assert call('workflow/follow-ups',p)[0]['id']==f['id']
        c3=call('workflow/consultations',p,'POST',{'doctor_id':did,'chief_complaint':'Recovery review','follow_up_id':f['id']})
        assert c3['previous_consultation_id']==cid
        # Profile provenance, corrections, documents, summary and audit.
        call('workflow/profile',p,'PATCH',{'emergency_contact_name':'Family','emergency_contact_phone':'999999','confirm_current':True})
        allergy=call('workflow/allergies',p,'POST',{'patient_id':pid,'substance':'Peanut','reaction':'Anaphylaxis reported','severity':'SEVERE'})
        call('workflow/records/diagnosis/'+dx['id'],d,'PATCH',{'status':'RESOLVED','reason':'Recovered'})
        assert call('workflow/versions/'+pid,p)
        upload=client.post('/api/workflow/documents',headers={'Authorization':'Bearer '+p['access_token']},data={'patient_id':pid,'title':'Previous record','category':'HISTORICAL'},files={'file':('record.txt',b'Historical visit record','text/plain')})
        assert upload.status_code==200,upload.text
        didoc=upload.json()['id']
        assert client.get('/api/workflow/document/'+didoc+'/download',headers={'Authorization':'Bearer '+p2['access_token']}).status_code==403
        assert client.get('/api/workflow/document/'+didoc+'/download',headers={'Authorization':'Bearer '+p['access_token']}).content==b'Historical visit record'
        history=call('workflow/history/'+pid,p)['events']
        kinds={x['kind'] for x in history}
        assert {'CONSULTATION','VITAL','DIAGNOSIS','PRESCRIPTION','DISPENSING','REFERRAL','SPECIALIST_CONSULTATION','ADMISSION','DISCHARGE','FOLLOW_UP_SCHEDULED','DOCUMENT','CORRECTION'}<=kinds
        s=call('workflow/summary/'+pid,p,'POST');assert s['method']=='RECORD_DIGEST';assert s['source_refs'];assert s['content']['hospitalizations']
        ns=call('workflow/notifications',p);assert len(ns)>=8
        call('workflow/notifications/'+ns[0]['id'],p,'PATCH')
        assert call('workflow/audit/'+pid,p)
        assert client.get('/qr/patient/'+pid).status_code==403
        g=call('workflow/access/'+pid,p,'POST',{'scope':'EMERGENCY','minutes':1})
        emergency=call('workflow/emergency/'+g['token']);assert emergency['name']=='PatientA';assert 'medical_history' not in emergency;assert emergency['severe_allergies']
        call('workflow/access/'+g['grant']['id'],p,'DELETE')
        call('workflow/emergency/'+g['token'],expected=403)
        cg=call('workflow/access/'+pid,p,'POST',{'pin':'012345','scope':'PRESCRIPTION','provider_user_id':ph2['user']['id'],'minutes':1})
        call('workflow/access/redeem',ph2,'POST',{'token':cg['token']})
        call('workflow/history/'+pid,ph2,expected=403)
        call('workflow/access/redeem',ph,'POST',{'token':cg['token']},403)
        call('auth/logout',p,'POST');call('auth/me',p,expected=401)
        p=call('auth/login',method='POST',body={'email':'PatientA@test.invalid','pin':'012345','confirm_pin':'012345','password':'correct-horse-12'})
        assert len(call('workflow/history/'+pid,p)['events'])>=len(history)
        print('PASS: full patient→doctor→pharmacy→hospital→discharge→follow-up journey; ownership, privacy, persistence, and graceful AI fallback')

def test_expiry_ai_failure_and_concurrent_bed_allocation(monkeypatch):
    import hashlib
    from datetime import datetime,timedelta,date
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from backend.workflow_models import AccessGrant
    from sqlalchemy import select
    with TestClient(app) as client:
        def register(role,**extra):
            name=uuid.uuid4().hex
            r=client.post('/api/auth/register',json={'role':role,'name':name,'email':name+'@test.invalid','pin':'012345','confirm_pin':'012345','password':'safe-test-password','age':20,'gender':'Male',**extra})
            assert r.status_code==200,r.text
            return r.json()
        def headers(actor):return {'Authorization':'Bearer '+actor['access_token']}
        p=register('PATIENT');pid=p['user']['patient_id']
        d=register('DOCTOR');h=register('HOSPITAL_ADMIN',total_icu_beds=1,total_general_beds=0)
        c=client.post('/api/workflow/consultations',headers=headers(p),json={'doctor_id':d['user']['doctor_id'],'chief_complaint':'Checkup'}).json()
        assert client.patch('/api/workflow/consultations/'+c['id'],headers=headers(d),json={'status':'IN_PROGRESS','reason':'Review'}).status_code==403
        approval=client.post('/api/workflow/access/'+pid,headers=headers(p),json={'scope':'CLINICAL','provider_user_id':d['user']['id'],'pin':'012345'})
        assert approval.status_code==200,approval.text
        for status in ('IN_PROGRESS','COMPLETED'):
            assert client.patch('/api/workflow/consultations/'+c['id'],headers=headers(d),json={'status':status,'reason':'Review'}).status_code==200
        rx=client.post('/api/workflow/consultations/'+c['id']+'/prescriptions',headers=headers(d),json={'medicines':[{'name':'Historical course','dosage':'Recorded dose','frequency':'Recorded schedule','duration_days':1,'start_date':str(date.today()-timedelta(days=4))}]})
        assert rx.status_code==200
        meds=client.get('/api/workflow/medications/'+pid,headers=headers(p)).json();assert meds[0]['status']=='COMPLETED'
        count1=len(client.get('/api/workflow/notifications',headers=headers(p)).json())
        client.get('/api/workflow/medications/'+pid,headers=headers(p))
        count2=len(client.get('/api/workflow/notifications',headers=headers(p)).json());assert count1==count2
        # Expired emergency bearer cannot read even the limited profile.
        g=client.post('/api/workflow/access/'+pid,headers=headers(p),json={'scope':'EMERGENCY','minutes':1}).json()
        with SessionLocal() as db:
            db.get(AccessGrant,g['grant']['id']).expires_at=datetime.utcnow()-timedelta(seconds=1);db.commit()
        assert client.get('/api/workflow/emergency/'+g['token']).status_code==403
        monkeypatch.setenv('AI_BASE_URL','https://configured.example/v1');monkeypatch.setenv('AI_API_KEY','test-only');monkeypatch.setenv('AI_MODEL','test-model')
        import httpx
        async def fail(*args,**kwargs):raise httpx.ConnectError('optional service offline')
        monkeypatch.setattr(httpx.AsyncClient,'post',fail)
        summary=client.post('/api/workflow/summary/'+pid,headers=headers(p));assert summary.status_code==200
        assert summary.json()['method']=='RECORD_DIGEST';assert 'unavailable' in summary.json()['notice']
        assert client.get('/api/workflow/history/'+pid,headers=headers(p)).status_code==200
        # Two patients and requests compete for the same bed.
        p2=register('PATIENT')
        for pat in (p,p2):
            r=client.post('/api/workflow/access/'+pat['user']['patient_id'],headers=headers(pat),json={'pin':'012345','scope':'CLINICAL','provider_user_id':h['user']['id'],'minutes':10})
            assert r.status_code==200
        bed=client.get('/api/workflow/beds',headers=headers(h)).json()[0]
        barrier=Barrier(2)
        def allocate(pat):
            barrier.wait()
            return client.post('/api/workflow/admissions',headers=headers(h),json={'patient_id':pat['user']['patient_id'],'bed_id':bed['id'],'reason':'Observation'}).status_code
        with ThreadPoolExecutor(2) as pool:out=list(pool.map(allocate,[p,p2]))
        assert sorted(out)==[200,409],out
