const {chromium}=require('playwright');
const {spawn,execFileSync}=require('node:child_process');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),assert=require('node:assert/strict');
const dir=fs.mkdtempSync(path.join(os.tmpdir(),'qr-tools-')),base='http://127.0.0.1:8136';
const server=spawn('python',['-m','uvicorn','backend.main:app','--port','8136'],{cwd:path.resolve(__dirname,'..'),env:{...process.env,DATABASE_URL:'sqlite:///'+dir+'/test.db',JWT_SECRET:'isolated-qr-tests-secret',ENABLE_EXTERNAL_MAPS:'false'},stdio:'ignore'});
let browser;
(async()=>{try{
 for(let i=0;i<60;i++){try{if((await fetch(base+'/api/health')).ok)break}catch{}await new Promise(r=>setTimeout(r,200))}
 async function api(p,a,body){const r=await fetch(base+'/api/'+p,{method:body?'POST':'GET',headers:{...(a?{Authorization:'Bearer '+a.access_token}:{}),...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined});assert.equal(r.status,200,await r.clone().text());return r.json()}
 const actors={};for(const role of ['PATIENT','DOCTOR','HOSPITAL_ADMIN','PHARMACY'])actors[role]=await api('auth/register',null,{role,name:role,email:role+'@qr.invalid',pin:'012345',confirm_pin:'012345',password:'testing-secure-123',age:25,gender:'Male',hospital_name:'Test Hospital',store_name:'Test Pharmacy'});
 const qr=await api('qr/generate/'+actors.PATIENT.user.patient_id+'/PROFILE_INTAKE',actors.PATIENT);fs.writeFileSync(dir+'/qr.png',Buffer.from(qr.qr_image_base64.split(',')[1],'base64'));
 execFileSync('ffmpeg',['-y','-loop','1','-i',dir+'/qr.png','-vf','scale=640:480:force_original_aspect_ratio=decrease,pad=640:480:(ow-iw)/2:(oh-ih)/2:color=white','-t','2','-pix_fmt','yuv420p',dir+'/qr.y4m'],{stdio:'ignore'});
 browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{}),args:['--no-sandbox','--disable-dev-shm-usage','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--use-file-for-fake-video-capture='+dir+'/qr.y4m']});
 const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('https://**',r=>r.abort());
 async function open(role){await page.goto(base);await page.waitForTimeout(400);await page.evaluate(a=>{localStorage.setItem('pulsesync_jwt_token',a.access_token);localStorage.removeItem('hf-page:'+a.user.id)},actors[role]);await page.reload();await page.waitForSelector('.hf-dashboard-grid').catch(async e=>{console.log('open failed',role,await page.locator('body').innerText());throw e})}
 console.log("START downloads");
 // All role downloads decode using the bundled jsQR decoder.
 for(const role of Object.keys(actors)){
  await open(role);await page.getByRole('button',{name:'My QR',exact:true}).click();await page.waitForSelector('.qr-download');
  const wait=page.waitForEvent('download');await page.locator('.qr-download').click();await (await wait).saveAs(dir+'/'+role+'.png');
  const decoded=await page.evaluate(async()=>{const img=document.querySelector('img.hf-qr');await img.decode();const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;const x=c.getContext('2d');x.drawImage(img,0,0);return jsQR(x.getImageData(0,0,c.width,c.height).data,c.width,c.height)?.data});assert.ok(decoded,role+' download decoded');
 }
 console.log('scanner');await open('DOCTOR');await page.getByRole('button',{name:'Scan QR',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#qr-status').textContent.includes('Access request PENDING')); // real decoder; simulated camera
 assert.equal(await page.locator('#qr-video').evaluate(v=>v.srcObject),null);
 await page.locator('#qr-image').setInputFiles(dir+'/qr.png');await page.waitForFunction(()=>document.querySelector('#qr-status').textContent.includes('Access request PENDING'));
 // Blank image and unsupported text are distinct from recognized, unauthorized access.
 execFileSync('python',['-c',`from PIL import Image;Image.new('RGB',(300,300),'white').save('${dir}/blank.png')`]);
 await page.locator('#qr-image').setInputFiles(dir+'/blank.png');await page.waitForFunction(()=>document.querySelector('#qr-status').textContent.includes('No QR detected'));
 await page.locator('#qr-text').fill('not a qr');await page.locator('#qr-read').click();await page.waitForFunction(()=>document.querySelector('#qr-status').textContent.includes('Unsupported'));
 let foreignRequests=0;page.on('request',r=>{if(r.url().includes('evil.invalid'))foreignRequests++});
 await page.locator('#qr-text').fill('https://evil.invalid/collect-token');await page.locator('#qr-read').click();await page.waitForFunction(()=>document.querySelector('#qr-status').textContent.includes('Unsupported'));assert.equal(foreignRequests,0);
 // Old localhost patient URL is parsed locally into a provider-specific request.
 await page.locator('#qr-text').fill('http://localhost:9999/qr/patient/'+actors.PATIENT.user.patient_id);await page.locator('#qr-read').click();await page.waitForFunction(()=>document.querySelector('#qr-status').textContent.includes('Access request PENDING'));
 await page.locator('#qr-close').click();
 console.log('separate sessions');
 // A separate browser context is the patient's authenticated approval session.
 const patientContext=await browser.newContext();const pp=await patientContext.newPage();await pp.route('https://**',r=>r.abort());await pp.goto(base);await pp.evaluate(a=>localStorage.setItem('pulsesync_jwt_token',a.access_token),actors.PATIENT);await pp.reload();await pp.waitForSelector('.hf-dashboard-grid');await pp.getByRole('button',{name:'QR requests',exact:true}).click();await pp.waitForSelector('[data-request]');await pp.locator('.pin-panel input[name=pin]').fill('012345');await pp.getByRole('button',{name:'Approve access',exact:true}).click();await pp.waitForFunction(()=>document.querySelector('.pin-panel')?.textContent.includes('APPROVED'));
 await page.getByRole('button',{name:'QR requests',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.pin-panel')?.textContent.includes('APPROVED'));await page.locator('#pin-close').click();
 await pp.getByRole('button',{name:'Revoke',exact:true}).click();await pp.waitForFunction(()=>document.querySelector('.pin-panel')?.textContent.includes('REVOKED'));await patientContext.close();
 console.log('cleanup');
 // Camera cleanup on close, page navigation, and logout, using fake video track.
 for(const action of ['close','navigate','logout']){
  console.log('scanner');await open('DOCTOR');await page.getByRole('button',{name:'Scan QR',exact:true}).click();await page.waitForFunction(()=>document.querySelector('#qr-video').srcObject!==null);
  const track=await page.locator('#qr-video').evaluateHandle(v=>v.srcObject.getVideoTracks()[0]);
  if(action==='close')await page.locator('#qr-close').click();else if(action==='navigate')await page.evaluate(()=>HF.go('patients'));else await page.evaluate(()=>logout());
  assert.equal(await track.evaluate(t=>t.readyState),'ended',action);
 }
 actors.DOCTOR=await api('auth/login',null,{email:'DOCTOR@qr.invalid',password:'testing-secure-123',role:'DOCTOR'});
 console.log('denied');
 // Camera denied/unavailable; upload/text controls and retry remain usable.
 for(const failure of ['NotAllowedError','NotFoundError']){
  const ctx=await browser.newContext();await ctx.addInitScript(name=>Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:()=>Promise.reject(new DOMException('camera failure',name))}),failure);
  const cp=await ctx.newPage();await cp.route('https://**',r=>r.abort());await cp.goto(base);await cp.evaluate(a=>localStorage.setItem('pulsesync_jwt_token',a.access_token),actors.DOCTOR);await cp.reload();await cp.waitForSelector('.hf-dashboard-grid').catch(async e=>{console.log('camera context failure',failure,await cp.locator('body').innerText());throw e});await cp.getByRole('button',{name:'Scan QR',exact:true}).click();await cp.waitForFunction(()=>/permission was denied|No camera was found/.test(document.querySelector('#qr-status').textContent));assert.ok(await cp.locator('#qr-start').isVisible());await ctx.close();
 }
 console.log('registration');
 // Registration UI: PIN shared across all roles, mismatch feedback, leading zero and show/hide.
 await page.goto(base);await page.evaluate(()=>localStorage.clear());await page.reload();
 const colors=[];
 for(const role of Object.keys(actors)){
  console.log('UI role',role);await page.locator('.auth-role-card[data-role='+role+']').click();await page.locator('#btn-auth-mode-register').click();
  await page.locator('#reg-name').fill('UI '+role);await page.locator('#reg-email').fill(role+Date.now()+'@ui.invalid');await page.locator('#reg-phone').fill('9999999999');await page.locator('#reg-password').fill('testing-secure-123');await page.locator('#reg-confirm-password').fill('testing-secure-123');
  await page.locator('#registration-next').click();
  if(role==='PATIENT'){await page.locator('#reg-pat-age').fill('25');await page.locator('#registration-next').click();await page.locator('#reg-has-meds').selectOption('no');await page.locator('#registration-next').click();}
  await page.locator('#registration-next').click();
  await page.locator('#reg-pin').fill('012345');await page.locator('#reg-confirm-pin').fill('012346');assert.match(await page.locator('#reg-pin-error').textContent(),/does not match/);await page.locator('#reg-confirm-pin').fill('012345');assert.equal(await page.locator('#reg-pin').getAttribute('type'),'password');
  await page.getByRole('button',{name:'Show Create six-digit PIN',exact:true}).click();assert.equal(await page.locator('#reg-pin').getAttribute('type'),'text');await page.getByRole('button',{name:'Hide Create six-digit PIN',exact:true}).click();
  colors.push(await page.locator('#register-submit-button').evaluate(b=>getComputedStyle(b).backgroundColor));
  console.log('validity',await page.locator('#auth-register-form').evaluate(f=>[...f.querySelectorAll('input,select')].filter(i=>!i.checkValidity()).map(i=>[i.id,i.validationMessage])));const response=page.waitForResponse(r=>r.url().endsWith('/api/auth/register'),{timeout:8000}).catch(async e=>{console.log('registration errors',errors,await page.locator('#toast-banner').textContent());throw e});await page.locator('#register-submit-button').click();assert.equal((await response).status(),200);await page.waitForSelector('.hf-dashboard-grid');
  await page.getByRole('button',{name:'Account PIN',exact:true}).click();await page.waitForSelector('#pin-settings');assert.equal(await page.locator('.pin-panel input[name=pin]').getAttribute('inputmode'),'numeric');await page.locator('#pin-close').click();
  for(const width of [1400,390]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),role+' viewport '+width)}
  await page.evaluate(()=>logout());await page.waitForSelector('#auth-portal-page-view',{state:'visible'});await page.setViewportSize({width:1400,height:1000});
 }
 // Consent/emergency formats and safe provider routing, including cross-device URLs.
 const consentGrant=await api('workflow/access/'+actors.PATIENT.user.patient_id,actors.PATIENT,{scope:'CLINICAL',provider_user_id:actors.DOCTOR.user.id,pin:'012345',minutes:30});
 const emergencyGrant=await api('workflow/access/'+actors.PATIENT.user.patient_id,actors.PATIENT,{scope:'EMERGENCY',minutes:30});
 for(const grant of [consentGrant,emergencyGrant]){
  await open('HOSPITAL_ADMIN');const decoded=await page.evaluate(async data=>{const img=new Image();img.src=data;await img.decode();const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;const ctx=c.getContext('2d');ctx.drawImage(img,0,0);return jsQR(ctx.getImageData(0,0,c.width,c.height).data,c.width,c.height)?.data},grant.qr_image_base64);assert.equal(decoded,grant.payload);
 }
 await page.getByRole('button',{name:'Scan QR',exact:true}).click();await page.locator('#qr-stop').click();await page.locator('#qr-text').fill(consentGrant.payload);await page.locator('#qr-read').click();await page.waitForFunction(()=>document.querySelector('#qr-status').textContent.includes('scan again'));assert.ok(await page.locator('#qr-start').isVisible());await page.locator('#qr-close').click();
 await open('DOCTOR');await page.getByRole('button',{name:'Scan QR',exact:true}).click();await page.locator('#qr-stop').click();await page.locator('#qr-text').fill(consentGrant.payload);await page.locator('#qr-read').click();await page.waitForSelector('#history-search');
 await page.getByRole('button',{name:'Scan QR',exact:true}).click();await page.locator('#qr-stop').click();await page.locator('#qr-text').fill(emergencyGrant.payload.replace(base,'http://localhost:9999'));await page.locator('#qr-read').click();await page.waitForFunction(()=>document.querySelector('#hf-dialog-content').textContent.includes('Limited emergency profile'));await page.locator('#hf-dialog button').last().click();
 await open('PATIENT');await page.getByRole('button',{name:'Scan QR',exact:true}).click();await page.locator('#qr-stop').click();await page.locator('#qr-text').fill('http://localhost:9999/qr/doctor/'+actors.DOCTOR.user.doctor_id);await page.locator('#qr-read').click();await page.waitForFunction(()=>document.querySelector('#hf-dialog-content').textContent.includes('Registered provider'));await page.locator('#hf-dialog button').last().click();
 // UI setup/change/reset for an existing account without a PIN.
 execFileSync('python',['-c',`import sqlite3;db=sqlite3.connect('${dir}/test.db');db.execute("UPDATE users SET pin_hash=NULL WHERE id=?",('${actors.PATIENT.user.id}',));db.commit()`]);
 await open('PATIENT');await page.waitForSelector('#pin-settings');
 for(const action of ['setup','change','reset']){
  if(action!=='setup'){await page.getByRole('button',{name:'Account PIN',exact:true}).click();await page.waitForSelector('#pin-settings');await page.locator('#pin-settings select[name=action]').selectOption(action)}
  await page.locator('#pin-settings input[name=password]').fill('testing-secure-123');
  if(action==='change')await page.locator('#pin-settings input[name=current_pin]').fill('000001');
  await page.locator('#pin-settings input[name=pin]').fill(action==='setup'?'000001':action==='change'?'000002':'012345');
  await page.locator('#pin-settings input[name=confirm_pin]').fill(action==='setup'?'000001':action==='change'?'000002':'012345');
  await page.getByRole('button',{name:'Save PIN',exact:true}).click();await page.waitForSelector('#pin-settings',{state:'detached'});
 }
 await page.evaluate(()=>logout());actors.PATIENT=await api('auth/login',null,{email:'PATIENT@qr.invalid',password:'testing-secure-123',role:'PATIENT'});
 await page.setViewportSize({width:390,height:844});await page.locator('#btn-auth-mode-register').click();await page.screenshot({path:'/tmp/healthflow-pin-mobile.png',fullPage:true});await open('PATIENT');await page.getByRole('button',{name:'Account PIN',exact:true}).click();await page.waitForSelector('#pin-settings');await page.screenshot({path:'/tmp/healthflow-pin-settings.png'});
 assert.equal(new Set(colors).size,4);assert.deepEqual(errors,[]);
 console.log('PASS: four-role registration/PIN UI, downloads decoded locally, simulated live camera, uploads, blank image, text, safe cross-device routing, separate patient approval/revocation sessions, camera denial/unavailable/cleanup, mobile and desktop widths, no JS page errors.');
 }finally{await browser?.close();server.kill();fs.rmSync(dir,{recursive:true,force:true})}})().catch(e=>{console.error(e);process.exitCode=1});
