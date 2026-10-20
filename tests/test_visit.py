"""Transactional visit decisions through authenticated HTTP and an isolated database."""
import os,tempfile,uuid
os.environ['DATABASE_URL']='sqlite:///'+tempfile.mktemp(suffix='.db')
os.environ['JWT_SECRET']='visit-test-'+uuid.uuid4().hex
os.environ['ENABLE_EXTERNAL_MAPS']='false'
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import Prescription,Consultation
from backend.workflow_models import Medication,ConsultationPlan,OutpatientAppointment,Notification,RecordVersion
from unittest.mock import patch

def test_decisions_and_atomic_finalization():
 with TestClient(app) as client:
  def call(path,a=None,method='GET',body=None,status=200):
   r=client.request(method,'/api/'+path,headers={'Authorization':'Bearer '+a['access_token']} if a else {},json=body)
   assert r.status_code==status,(path,r.status_code,r.text)
   return r.json()
  def reg(role,name,**kw):return call('auth/register',method='POST',body=dict(role=role,name=name,email=uuid.uuid4().hex+'@visit.invalid',password='test-password',pin='123456',confirm_pin='123456',**kw))
  p=reg('PATIENT','Visit Patient',current_medications=[{'name':'Medicine A','dosage':'5 mg / 1 tablet','frequency':'1 time per day','times_per_day':1,'food':'After food','disease':'Blood pressure','additional_instructions':'Keep the original instructions'},{'name':'Medicine B','frequency':'Daily','food':'Before food'}],allergies=['Penicillin'])
  p2=reg('PATIENT','Other Patient');d=reg('DOCTOR','Visit Doctor',clinic_name='Visit Clinic');d2=reg('DOCTOR','Other Doctor');h=reg('HOSPITAL_ADMIN','Hospital',hospital_name='Registered Care',address='Road',total_icu_beds=0,total_general_beds=0);h2=reg('HOSPITAL_ADMIN','Other Hospital');ph=reg('PHARMACY','Pharmacy',store_name='Store')
  pid=p['user']['patient_id'];hid=h['user']['hospital_id']
  cid=call('workflow/consultations',p,'POST',{'doctor_id':d['user']['doctor_id'],'chief_complaint':'Review medication'})['id']
  call('workflow/consultations/'+cid,d,'PATCH',{'status':'IN_PROGRESS','reason':'Seen'},403)
  call('workflow/access/'+pid,p,'POST',{'scope':'CLINICAL','provider_user_id':d['user']['id'],'pin':'123456'})
  call('workflow/consultations/'+cid,d,'PATCH',{'status':'IN_PROGRESS','reason':'Seen'})
  root='workflow/consultations/'+cid
  call(root+'/plan',p,status=403);call(root+'/plan',d2,status=403);call(root+'/complete-record',p,status=403)
  data=call(root+'/plan',d);meds=data['medications'];a=next(m for m in meds if m['name']=='Medicine A');b=next(m for m in meds if m['name']=='Medicine B')
  assert a['instructions']['food']=='After food' and a['source']=='PATIENT_REPORTED'
  assert a['instructions']['additional_instructions']=='Keep the original instructions'
  assert call('workflow/prescriptions',p)==[]
  assert len(call('workflow/medications/'+pid,p))==2
  # Existing completed dispensing record must remain byte-for-byte unchanged.
  with SessionLocal() as db:
   rx=Prescription(patient_id=pid,doctor_id=d['user']['doctor_id'],consultation_id=cid,pharmacy_id=ph['user']['pharmacy_id'],status='DISPENSED',medicines=[{'name':'Medicine A','dosage':'5 mg','frequency':'Daily','quantity':30}]);db.add(rx);db.flush();rid=rx.id;db.get(Medication,a['id']).prescription_id=rid;db.commit()
  body={'revision':0,'observations':'Reviewed during consultation','assessment':'Stable','medications':[{'action':'frequency','medication_id':a['id'],'times_per_day':2},{'action':'replace','medication_id':b['id'],'name':'Medicine C','times_per_day':3,'food':'Before food','dosage':'10 mg','reason':'Changed regimen'},{'action':'add','name':'Medicine D','times_per_day':1,'food':'After food','quantity':7,'pharmacy_id':ph['user']['pharmacy_id']}],'referrals':[{'hospital_id':hid,'reason':'Specialist review','clinical_summary':'Reviewed by doctor','preferred_at':'2026-11-01T10:00:00Z'},{'name':'External Hospital','address':'Other Road','reason':'Second opinion','clinical_summary':'Reviewed external summary'}]}
  for value in [0,-1,1.5,'2']:
   invalid={**body,'medications':[dict(body['medications'][0],times_per_day=value)]};call(root+'/plan',d,'PUT',invalid,422)
  call(root+'/plan',d,'PUT',body);call(root+'/plan',d,'PUT',body,409)
  assert call(root+'/plan',d)['content']['observations']=='Reviewed during consultation'
  assert len([m for m in call('workflow/medications/'+pid,p) if m['status']=='ACTIVE'])==2
  assert call('workflow/outpatient-appointments',h)==[]
  # Inject a database failure after medication mutation: entire completion must roll back.
  import backend.routers.visit as visit
  original=visit.notify
  def fail(*args,**kwargs):raise RuntimeError('injected persistence failure')
  with patch.object(visit,'notify',fail):
   try:call(root,d,'PATCH',{'status':'COMPLETED','reason':'Finalized'})
   except RuntimeError:pass
   else:raise AssertionError('Expected injected failure')
  with SessionLocal() as db:
   assert db.get(Consultation,cid).status=='IN_PROGRESS'
   assert db.get(Medication,a['id']).status=='ACTIVE' and db.get(Medication,b['id']).status=='ACTIVE'
   assert db.query(OutpatientAppointment).count()==0
   assert db.get(ConsultationPlan,cid).finalized_at is None
  call(root,d,'PATCH',{'status':'COMPLETED','reason':'Reviewed and finalized'})
  with SessionLocal() as db:
   rx=db.get(Prescription,rid);assert rx.status=='DISPENSED' and rx.medicines==[{'name':'Medicine A','dosage':'5 mg','frequency':'Daily','quantity':30}]
   active=db.query(Medication).filter_by(patient_id=pid,status='ACTIVE').all();newa=next(x for x in active if x.name=='Medicine A');assert newa.dosage==a['dosage'] and newa.instructions['food']=='After food' and newa.instructions['disease']=='Blood pressure' and newa.instructions['additional_instructions']=='Keep the original instructions'
   assert db.get(Prescription,newa.prescription_id).status=='INSTRUCTIONS_ONLY'
   counts=(db.query(Prescription).count(),db.query(Notification).count(),db.query(OutpatientAppointment).count())
  call(root,d,'PATCH',{'status':'COMPLETED','reason':'Retry'})
  with SessionLocal() as db:assert counts==(db.query(Prescription).count(),db.query(Notification).count(),db.query(OutpatientAppointment).count())
  record=call(root+'/complete-record',p);assert len(record['note']['changes'])==3 and len(record['appointments'])==1
  call(root+'/complete-record',p2,status=403);call(root+'/complete-record',d2,status=403)
  ap=call('workflow/outpatient-appointments',h)[0];assert ap['status']=='REQUESTED'
  response={'status':'CONFIRMED','reason':'Time confirmed','scheduled_at':'2026-11-01T10:30:00Z','revision':0}
  call('workflow/outpatient-appointments/'+ap['id'],h2,'PATCH',response,403)
  call('workflow/outpatient-appointments/'+ap['id'],h,'PATCH',dict(response,scheduled_at=None),422)
  call('workflow/outpatient-appointments/'+ap['id'],h,'PATCH',response)
  call('workflow/outpatient-appointments/'+ap['id'],h,'PATCH',response,409)
  assert call(root+'/complete-record',p)['appointments'][0]['status']=='CONFIRMED'
  for status,revision in [('RESCHEDULED',1),('DECLINED',2)]:
   call('workflow/outpatient-appointments/'+ap['id'],h,'PATCH',dict(response,status=status,revision=revision,reason=status))
  assert call(root+'/complete-record',p)['appointments'][0]['status']=='DECLINED'
  rx=next(x for x in call('workflow/prescriptions',ph) if x['status']=='PENDING');assert rx['medicines'][0]['food']=='After food'
  call('workflow/prescriptions/'+rx['id']+'/dispense',ph,'POST',status=409)
  call('workflow/inventory',ph,'POST',{'medicine_name':'Medicine D','dosage_form':'Tablet','stock_quantity':10})
  call('workflow/prescriptions/'+rx['id']+'/dispense',ph,'POST')
  assert call('clinical/pharmacy/inventory',ph)['inventory'][0]['stock_quantity']==3
  # Warnings must block finalization, retaining the original active medicine.
  cid2=call('workflow/consultations',p,'POST',{'doctor_id':d['user']['doctor_id'],'chief_complaint':'Allergy safeguard'})['id'];root2='workflow/consultations/'+cid2
  call(root2,d,'PATCH',{'status':'IN_PROGRESS','reason':'Seen'})
  warning={'revision':0,'medications':[{'action':'add','name':'Penicillin','times_per_day':1}]}
  assert call(root2+'/plan',d,'PUT',warning)['warnings']
  call(root2,d,'PATCH',{'status':'COMPLETED','reason':'Review'},409)
  with SessionLocal() as db:assert db.get(Consultation,cid2).status=='IN_PROGRESS'
  warning.update(revision=1,acknowledge_warnings=True);call(root2+'/plan',d,'PUT',warning)
  call(root2,d,'PATCH',{'status':'COMPLETED','reason':'Warnings reviewed'})
