"""Two-account workflow with QR identity, PIN challenge and server-side enforcement."""
import uuid
from datetime import datetime,timedelta
from fastapi.testclient import TestClient
from test_journey import app,SessionLocal
from backend.models import Consultation
from backend.workflow_models import AccessRequest,AccessGrant

def test_qr_pin_consultation_authorization():
 with TestClient(app) as c:
  def req(method,path,actor=None,data=None,code=200):
   r=c.request(method,'/api/'+path,headers={'Authorization':'Bearer '+actor['access_token']} if actor else {},json=data)
   assert r.status_code==code,(path,r.status_code,r.text)
   return r.json()
  def reg(role):
   return req('POST','auth/register',data={'role':role,'name':'QR '+role,'email':uuid.uuid4().hex+'@test.invalid','password':'secure-password-123','pin':'123456','confirm_pin':'123456'})
  patient,doctor,doctor2,other=reg('PATIENT'),reg('DOCTOR'),reg('DOCTOR'),reg('PATIENT')
  pid=patient['user']['patient_id'];did=doctor['user']['doctor_id']
  card=req('GET','qr/identify/'+pid,doctor)
  assert card['patient_name'] and 'allergies' not in card and 'pin' not in str(card)
  req('GET','qr/patient/'+pid,doctor,code=403)
  request_body={'patient_id':pid,'doctor_id':did,'chief_complaint':'QR consultation'}
  req('POST','workflow/consultations',doctor,request_body,403)
  request=req('POST','security/requests',doctor,{'patient_id':pid})
  rid=request['id'];assert request['status']=='PENDING'
  assert any(x['id']==rid for x in req('GET','security/requests',patient))
  assert not any(x['id']==rid for x in req('GET','security/requests',other))
  req('POST','workflow/consultations',doctor,dict(request_body,access_request_id=rid),403)
  req('POST','security/requests/'+rid,other,{'action':'approve','pin':'123456'},404)
  req('POST','security/requests/'+rid,doctor,{'action':'approve','pin':'123456'},403)
  req('POST','security/requests/'+rid,patient,{'action':'approve','pin':'999999'},403)
  assert req('POST','security/requests/'+rid,patient,{'action':'approve','pin':'123456'})['status']=='APPROVED'
  req('POST','workflow/consultations',doctor2,dict(request_body,access_request_id=rid,doctor_id=doctor2['user']['doctor_id']),403)
  consult=req('POST','workflow/consultations',doctor,dict(request_body,access_request_id=rid))
  cid=consult['id'];assert req('GET','security/requests',doctor)[0]['status']=='APPROVED'
  req('POST','workflow/consultations',doctor,dict(request_body,access_request_id=rid),409)
  req('POST','security/requests/'+rid,patient,{'action':'revoke'})
  req('PATCH','workflow/consultations/'+cid,doctor,{'status':'IN_PROGRESS','reason':'Unauthorized'},403)
  req('GET','workflow/consultations/'+cid+'/plan',doctor,code=403)
  # A historical consultation cannot serve as access authorization on its own.
  with SessionLocal() as db:
   assert db.get(Consultation,cid)
  req('GET','workflow/history/'+pid,doctor,code=403)
  again=req('POST','security/requests',doctor,{'patient_id':pid})
  assert again['id']!=rid
  req('POST','security/requests/'+again['id'],patient,{'action':'deny'})
  req('POST','workflow/consultations',doctor,dict(request_body,access_request_id=again['id']),403)
  expired=req('POST','security/requests',doctor,{'patient_id':pid})
  with SessionLocal() as db:
   r=db.get(AccessRequest,expired['id']);r.expires_at=datetime.utcnow()-timedelta(seconds=1);db.commit()
  req('POST','security/requests/'+expired['id'],patient,{'action':'approve','pin':'123456'},409)
  assert next(x for x in req('GET','security/requests',patient) if x['id']==expired['id'])['status']=='EXPIRED'
