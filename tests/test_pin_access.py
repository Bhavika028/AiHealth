"""PIN/QR consent security tests against isolated SQLite, including legacy migration."""
import uuid
from datetime import datetime,timedelta
from fastapi.testclient import TestClient
# Reuse the regression suite's isolated test database configuration.
from test_journey import app,SessionLocal
from backend.models import User,Patient
from backend.workflow_models import AccessRequest,AccessGrant
from backend.database import init_db
from backend.pin_security import hash_pin

def test_pin_and_request_lifecycle():
 with TestClient(app) as c:
  def call(path,a=None,body=None,code=200):
   r=c.request('POST' if body is not None else 'GET','/api/'+path,headers={'Authorization':'Bearer '+a['access_token']} if a else {},json=body)
   assert r.status_code==code,(path,r.status_code,r.text)
   return r.json()
  def reg(role,**extra):
   return call('auth/register',body=dict(role=role,name='Test '+role,email=uuid.uuid4().hex+'@test.invalid',password='test-password',pin='012345',confirm_pin='012345',**extra))
  actors=[reg(r) for r in ['PATIENT','DOCTOR','HOSPITAL_ADMIN','PHARMACY']];p,d,h,ph=actors
  p2=reg('PATIENT');d2=reg('DOCTOR');pid=p['user']['patient_id']
  for a in actors:
   assert call('security/pin',a)['has_pin']
   assert 'pin_hash' not in str(call('auth/me',a))
   with SessionLocal() as db:
    u=db.get(User,a['user']['id']);assert u.pin_hash.startswith('pbkdf2_sha256$600000$') and '012345' not in u.pin_hash
  for pin,confirm in [('12345','12345'),('123456','000000'),('abcdef','abcdef'),('１２３４５６','１２３４５６')]:
   call('auth/register',body=dict(role='PATIENT',name='Invalid',email=uuid.uuid4().hex+'@test.invalid',password='safe-password',pin=pin,confirm_pin=confirm),code=400)
  response=call('auth/register',body={'role':'PATIENT','pin':123456},code=422);assert '123456' not in str(response)
  call('security/pin',body={},code=401)
  # Existing account: additive migration does not replace identity, password, or profile.
  with SessionLocal() as db:
   u=db.get(User,p['user']['id']);u.pin_hash=None;db.commit()
  init_db();assert not call('security/pin',p)['has_pin']
  call('security/pin',p,{'action':'setup','pin':'000001','confirm_pin':'000001','password':'wrong'},403)
  call('security/pin',p,{'action':'setup','pin':'000001','confirm_pin':'000001','password':'test-password'})
  call('security/pin',p,{'action':'setup','pin':'000001','confirm_pin':'000001','password':'test-password'},409)
  call('security/pin',p,{'action':'change','current_pin':'000001','pin':'000002','confirm_pin':'000002','password':'test-password'})
  call('security/pin',p,{'action':'reset','pin':'012345','confirm_pin':'012345','password':'test-password'})
  call('workflow/history/'+pid,d,code=403)
  request=call('security/requests',d,{'patient_id':pid,'minutes':30});rid=request['id']
  assert request['status']=='PENDING' and 'medical' not in request and request['scope']=='CLINICAL'
  assert call('security/requests',d,{'patient_id':pid})['id']==rid
  assert any(r['id']==rid for r in call('security/requests',p))
  assert not any(r['id']==rid for r in call('security/requests',p2))
  call('security/requests/'+rid,d,{'action':'approve','pin':'012345'},403)
  call('security/requests/'+rid,p2,{'action':'approve','pin':'012345'},404)
  # Provider's own valid PIN cannot authorize in the provider session.
  call('security/requests/'+rid,h,{'action':'approve','pin':'012345'},403)
  for i in range(5):call('security/requests/'+rid,p,{'action':'approve','pin':'999999'},429 if i==4 else 403)
  call('security/requests/'+rid,p,{'action':'approve','pin':'012345'},429)
  call('security/pin',p,{'action':'reset','pin':'000000','confirm_pin':'000000','password':'test-password'},429)
  with SessionLocal() as db:
   u=db.get(User,p['user']['id']);u.pin_locked_until=datetime.utcnow()-timedelta(seconds=1);db.commit()
  assert call('security/requests/'+rid,p,{'action':'approve','pin':'012345'})['status']=='APPROVED'
  call('workflow/history/'+pid,d)
  call('workflow/history/'+pid,d2,code=403)
  call('security/requests/'+rid,p,{'action':'approve','pin':'012345'},409)
  assert call('security/requests/'+rid,p,{'action':'revoke'})['status']=='REVOKED'
  call('workflow/history/'+pid,d,code=403)
  for actor,status in [(h,'DENIED'),(d2,'EXPIRED')]:
   req=call('security/requests',actor,{'patient_id':pid})
   if status=='DENIED':call('security/requests/'+req['id'],p,{'action':'deny'})
   else:
    with SessionLocal() as db:r=db.get(AccessRequest,req['id']);r.expires_at=datetime.utcnow()-timedelta(seconds=1);db.commit()
    call('security/requests/'+req['id'],p,{'action':'approve','pin':'012345'},409)
   assert next(r for r in call('security/requests',actor) if r['id']==req['id'])['status']==status
  rx=call('security/requests',ph,{'patient_id':pid});assert rx['scope']=='PRESCRIPTION'
  call('security/requests/'+rx['id'],p,{'action':'approve','pin':'012345'})
  call('workflow/history/'+pid,ph,code=403)
  # Non-emergency direct grant path cannot bypass patient PIN verification.
  call('workflow/access/'+pid,p,{'scope':'CLINICAL','provider_user_id':d['user']['id']},403)
  g=call('workflow/access/'+pid,p,{'scope':'CLINICAL','provider_user_id':d['user']['id'],'pin':'012345','minutes':1})
  with SessionLocal() as db:grant=db.get(AccessGrant,g['grant']['id']);grant.expires_at=datetime.utcnow()-timedelta(seconds=1);db.commit()
  call('workflow/history/'+pid,d,code=403)
  # Reset guesses share the same persistent attempt limit.
  for i in range(5):call('security/pin',d2,{'action':'reset','pin':'000000','confirm_pin':'000000','password':'wrong'},429 if i==4 else 403)
  assert call('security/pin',d2)['locked_until']
