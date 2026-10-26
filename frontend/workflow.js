/* Patient-centred portal. Existing authentication and adaptive intake APIs are reused. */
const HF = (() => {
 let scannedPatient=null, scannedAccess=null;
 let user, page, patientId, providers=[], encounters=[], refs=[], meds=[], follow=[], familyMembers=[], map, regMap, epoch=0, navigationController;
 const $=id=>document.getElementById(id);
 const e=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const date=value=>value?new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(value)||/^\d{4}-\d{2}-\d{2}$/.test(value)?value:value+'Z').toLocaleString('en-IN',{day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}):'Not recorded';
 const tag=value=>`<span class="hf-status ${e(String(value).toLowerCase())}">${e(String(value).replaceAll('_',' '))}</span>`;
 const button=(text,fn,style='')=>`<button type="button" class="${style}" onclick="${fn}">${e(text)}</button>`;
 const options=(rows,key='name',blank='Select')=>`<option value="">${e(blank)}</option>`+rows.map(r=>`<option value="${e(r.id)}">${e(r[key])}</option>`).join('');
 const input=(label,name,type='text',value='',required=true)=>`<label>${e(label)}<input name="${e(name)}" type="${type}" value="${e(value)}" ${required?'required':''}></label>`;
 const select=(label,name,html)=>`<label>${e(label)}<select name="${e(name)}" required>${html}</select></label>`;
 const statuses=items=>items.map(x=>`<option value="${x}">${x.replaceAll('_',' ')}</option>`).join('');
 const empty=text=>`<div class="hf-empty">${e(text)}</div>`;
 const table=(heads,rows)=>HUI.table(heads,rows,e,empty);
 const form=(id,title,fields,label='Save')=>`<form id="${id}"><h2>${e(title)}</h2>${fields}<button class="primary" type="submit">${e(label)}</button><div class="form-message" role="status"></div></form>`;
 async function api(path,method='GET',body){
  const res=await fetch('/api/'+path,{method,...(method==='GET'&&navigationController?{signal:navigationController.signal}:{}),headers:{Authorization:'Bearer '+currentToken,...(body instanceof FormData?{}:body!==undefined?{'Content-Type':'application/json'}:{})},...(body!==undefined?{body:body instanceof FormData?body:JSON.stringify(body)}:{})});
  if(!res.ok){let d;try{d=await res.json()}catch{d={detail:'Request failed'}};throw new Error(typeof d.detail==='string'?d.detail:JSON.stringify(d.detail??d));}
  if(res.status===204)return null;return res.json();
 }
 function bind(id,handler){const node=$(id);if(!node)return;node.onsubmit=async ev=>{ev.preventDefault();const submit=node.querySelector('button[type=submit]');submit.disabled=true;const msg=node.querySelector('.form-message');msg.innerHTML='Saving…';try{await handler(Object.fromEntries(new FormData(node)),node);if(node.isConnected)msg.innerHTML='<p>Saved.</p>';}catch(error){msg.innerHTML=`<p class="hf-error">${e(error.message)}</p>`}finally{submit.disabled=false}}}
 function dialog(title,body){$('hf-dialog-content').innerHTML=`<h2>${e(title)}</h2>${body}`;QRTools.addDownloads($('hf-dialog-content'));$('hf-dialog').showModal();}
 function navItems(){return user.role==='PATIENT'?[['overview','Overview'],['history','Medical History'],['appointments','Appointments / Follow-ups'],['medications','Prescriptions'],['referrals','Referrals'],['documents','Documents'],['nearby','Nearby Care'],['profile','Profile'],['consent','Consent & QR'],['notifications','Notifications'],['audit','Access log']]:user.role==='DOCTOR'?[['overview','Overview'],['queue','Queue'],['consultations','Consultations'],['patients','Patients'],['referrals','Referrals'],['appointments','Follow-ups'],['notifications','Notifications'],['settings','Clinic settings']]:user.role==='HOSPITAL_ADMIN'?[['overview','Overview'],['referrals','Incoming Referrals'],['appointments','Outpatient appointments'],['patients','Patients'],['consultations','Specialist encounters'],['admissions','Admissions'],['beds','Beds / Wards'],['doctors','Doctors'],['notifications','Notifications'],['settings','Hospital settings']]:[['overview','Overview'],['prescriptions','Prescriptions'],['dispensing','Dispensing'],['inventory','Inventory'],['notifications','Notifications'],['settings','Store settings']];}
 
 async function loadFamily(){
  if(user.role==='PATIENT'){
   try{
    familyMembers=await api('workflow/family');
    const saved=localStorage.getItem('hf-active-patient:'+user.id);
    if(saved&&familyMembers.some(f=>f.patient_id===saved)){
     patientId=saved;
    }else if(!patientId&&familyMembers.length){
     patientId=familyMembers[0].patient_id;
    }
   }catch(err){familyMembers=[]}
  }
 }

 async function switchFamily(val){
  if(val==='__NEW__'){
   addFamilyModal();
   return;
  }
  patientId=val;
  localStorage.setItem('hf-active-patient:'+user.id,val);
  const m=familyMembers.find(f=>f.patient_id===val);
  showToast('Switched to profile: '+(m?m.full_name:'Active Patient'),'info');
  await go(page);
 }

 function shell(){
  const root=$('main-app-container');
  const collapsed=localStorage.getItem('hf-sidebar-collapsed')==='true';
  const familySwitcher=user.role==='PATIENT'&&familyMembers.length?`
   <div class="hf-family-switcher-wrap" title="Active Patient Profile">
    <label class="hf-family-switcher-label">
     <span>👤</span>
     <select class="hf-family-select" onchange="HF.switchFamily(this.value)" aria-label="Switch Profile">
       ${familyMembers.map(m=>`
         <option value="${e(m.patient_id)}" ${m.patient_id===patientId?'selected':''}>
           ${m.is_primary ? e(m.full_name) + ' (Myself)' : (m.relationship_type==='CHILD'?'👶 ':(m.relationship_type==='ELDERLY_PARENT'?'👵 ':'👤 ')) + e(m.full_name) + ' (' + e(m.relationship_type.replace('_',' ')) + ')'}
         </option>
       `).join('')}
       <option value="__NEW__">➕ Add Family…</option>
     </select>
    </label>
   </div>`:'';

  root.innerHTML=`<header class="hf-top"><div class="hf-brand"><button class="hf-nav-toggle" aria-label="Toggle navigation" aria-expanded="${!collapsed}" onclick="HUI.toggleNav()">${HUI.icon('menu')}</button><span class="hf-mark">${HUI.icon('pulse')}</span>PulseSync<span class="hf-meta">HEALTHFLOW</span></div><div class="hf-toolbar"><label class="hf-global-search">${HUI.icon('search')}<input aria-label="Search pages" placeholder="Search pages…" oninput="HUI.searchPages(this.value)"></label>${familySwitcher}${button('🔐 PIN',"PinAccess.settings()")}${button('QR Access',"PinAccess.requests()")}${button('🪪 My QR',"HF.myQR()")}${button('📷 Scan',"QRTools.open()")}${button('🔔',"HF.go('notifications')",'hf-notification-btn')}<div class="hf-account-chip"><div class="hf-account"><strong>${e(user.name)}</strong><span class="hf-meta">${e(user.role.replaceAll('_',' '))}</span></div>${button('Sign out','logout()','hf-logout-btn')}</div></div></header><div class="hf-layout ${collapsed?'is-collapsed':''}"><nav class="hf-sidebar" aria-label="Portal navigation"><small>${e(user.role==='PATIENT'?'Your health':'Clinical workspace')}</small>${navItems().map(([key,label])=>`<button title="${e(label)}" aria-label="${e(label)}" aria-current="${page===key?'page':'false'}" class="${page===key?'active':''}" onclick="HF.go('${key}')">${HUI.icon(key)}<span>${e(label)}</span></button>`).join('')}<p class="hf-nav-empty" hidden>No matching pages.</p></nav><main id="hf-content" class="hf-main" aria-live="polite"></main></div>`
 }
 function head(title,sub='',action=''){return `<div class="hf-breadcrumb">${button('Overview',"HF.go('overview')",'text-action')}<span>/</span><span>${e(title)}</span></div><div class="hf-page-head"><div><h1>${e(title)}</h1><div class="hf-muted">${e(sub)}</div></div><div class="hf-toolbar">${action}</div></div>`}
 async function mount(u){user=u;patientId=u.patient_id||null;providers=[];encounters=[];refs=[];meds=[];follow=[];familyMembers=[];if(u.role==='PATIENT')await loadFamily();const saved=localStorage.getItem('hf-page:'+u.id);page=navItems().some(x=>x[0]===saved)?saved:'overview';await go(page);void PinAccess.checkSetup()}
 async function go(next){window.QRTools?.close();navigationController?.abort();navigationController=new AbortController();page=next;localStorage.setItem('hf-page:'+user.id,next);const seq=++epoch;if(map){map.remove();map=null}shell();$('hf-content').classList.remove('hf-workspace');$('hf-content').innerHTML='<div class="hf-loading" role="status"><span>Loading care records…</span><div class="hf-skeleton"></div><div class="hf-skeleton"></div><div class="hf-skeleton"></div></div>';try{providers=await api('workflow/providers');if(seq!==epoch)return;await render(next)}catch(err){if(seq===epoch&&err.name!=='AbortError')$('hf-content').innerHTML=head('Unable to load this view')+`<div class="hf-error">${e(err.message)}</div><p>${button('Retry',`HF.go('${e(next)}')`)}</p>`}}
 function timeline(events,limit){return HUI.timeline(events.slice(0,limit||events.length),{e,date,tag,button,user});}
 async function render(which){
  if(which==='overview')return overview();
  if(which==='history')return history();
  if(which==='queue'||which==='consultations')return consultations();
  if(which==='appointments')return appointments();
  if(which==='medications'||which==='prescriptions'||which==='dispensing')return medications();
  if(which==='referrals')return referrals();
  if(which==='documents')return documents();
  if(which==='nearby')return nearby();
  if(which==='patients')return patients();
  if(which==='admissions')return admissions();
  if(which==='beds')return beds();
  if(which==='doctors')return doctors();
  if(which==='consent')return consent();
  if(which==='profile')return profile();
  if(which==='notifications')return notifications();
  if(which==='audit')return audit();
  if(which==='inventory')return inventory();
  return settings();
 }
 async function overview(){await HFDashboard.render({user,api,e,date,tag,button,empty,table,head,timeline,providers,medTable,rxTable,refActions,setEncounters:r=>encounters=r,setRefs:r=>refs=r});}
 let historyEvents=[];
 async function history(){const visitRows=await api('workflow/consultations');const data=await api('workflow/history/'+patientId);const vitalData=await api('workflow/vitals/'+patientId);historyEvents=data.events;$('hf-content').innerHTML=table(['Finalized consultation','Doctor','Record'],visitRows.filter(c=>c.status==='COMPLETED').map(c=>[e(c.chief_complaint)+' · '+date(c.created_at),e(c.doctor_name),button('View complete check-up record',`HF.completeVisit('${c.id}')`)]))+head('Medical history',data.patient.full_name+' · A connected record of your care',button('Generate history summary','HF.summarize()','primary'))+`<div class="hf-toolbar">${button('Saved summaries','HF.summaryHistory()')}${button('Correction history','HF.versions()')}${user.role==='DOCTOR'?button('Medication review','HF.medicationReview()'):''}</div><div class="hf-notice">${data.last_verified_at?'Profile last confirmed '+date(data.last_verified_at):'Profile information has not been reconfirmed.'} Patient-reported information is labelled by source. Draft assessments are excluded.</div><div class="hf-history-controls"><label>Search history<input id="history-search" type="search" oninput="HF.filterHistory()" placeholder="Event, clinician, facility…"></label><label>Event type<select id="history-kind" onchange="HF.filterHistory()"><option value="">All events</option>${['CONSULTATION','DIAGNOSIS','VITAL','PRESCRIPTION','REFERRAL','ADMISSION','DISCHARGE','DOCUMENT','FOLLOW_UP','DISPENSING','ALLERGY'].map(k=>`<option>${k}</option>`).join('')}</select></label><label>From<input id="history-from" type="date" onchange="HF.filterHistory()"></label><label>To<input id="history-to" type="date" onchange="HF.filterHistory()"></label><label>Display<select id="history-mode" onchange="HF.filterHistory()"><option value="summary">Summary</option><option value="detail">Detailed</option></select></label>${button('Reset filters','HF.resetHistory()')}</div><div id="hf-history-events">${timeline(data.events)}</div><section class="hf-panel"><h2>Historical measurements</h2>${HUI.vitals(vitalData,{e,date,empty})}${table(['Measured','Vital','Value','Source'],vitalData.map(v=>[date(v.measured_at),e(v.name),e(v.value+' '+v.unit),e(v.source)]))}</section>`;}
 function filterHistory(){const q=$('history-search').value.toLowerCase(),kind=$('history-kind').value,from=$('history-from').value,to=$('history-to').value;const rows=historyEvents.filter(x=>(!q||JSON.stringify(x).toLowerCase().includes(q))&&(!kind||x.kind.includes(kind))&&(!from||x.created_at.slice(0,10)>=from)&&(!to||x.created_at.slice(0,10)<=to));$('hf-history-events').innerHTML=`<p class="hf-muted">${rows.length} matching events</p>`+timeline(rows);if($('history-mode').value==='detail')$('hf-history-events').querySelectorAll('details').forEach(d=>d.open=true)}
 function resetHistory(){for(const id of ['history-search','history-kind','history-from','history-to'])$(id).value='';$('history-mode').value='summary';filterHistory()}
 async function relatedRecord(kind,id){try{if(kind==='medications'){const rows=await api('workflow/prescriptions');const record=rows.find(r=>r.id===id);dialog('Related prescription',record?rxTable([record]):empty('This event has no accessible prescription record.'))}else if(kind==='referrals'){refs=await api('workflow/referrals');if(refs.some(r=>r.id===id))referralDetail(id);else dialog('Related referral',empty('This event has no accessible referral record.'))}else if(kind==='documents'){const rows=await api('workflow/documents/'+patientId);const r=rows.find(x=>x.id===id);dialog('Related document',r?`<h3>${e(r.title)}</h3><p>${e(r.category)} · ${date(r.created_at)}</p>${button('Download document',`HF.download('${r.id}')`)}`:empty('This document is no longer an active uploaded record.'))}}catch(err){showToast(err.message,'emergency')}}
 async function linkedEncounter(id){try{encounters=await api('workflow/consultations');const c=encounters.find(x=>x.id===id);if(!c){showToast('This encounter is outside your assigned workspace. The linked event details remain available here.','info');return}if(user.role==='PATIENT'){await completeVisit(id)}else await encounter(id)}catch(err){showToast(err.message,'emergency')}}
 async function summarize(){try{dialog('Preparing summary','<p>Reading stored history…</p>');const d=await api('workflow/summary/'+patientId,'POST');$('hf-dialog-content').innerHTML=`<h2>${d.method==='AI_MODEL'?'AI history summary':'Medical record digest'}</h2><div class="hf-notice">${e(d.notice||'Generated from stored records. Clinician review required.')}</div><p class="hf-muted">${date(d.created_at)} · ${e(d.status)} · ${d.source_refs.length} source references</p><pre>${e(JSON.stringify(d.content,null,2))}</pre>${user.role==='DOCTOR'?button('Approve after review',`HF.approveSummary('${d.id}')`):''}`;}catch(err){$('hf-dialog-content').innerHTML=`<p class="hf-error">${e(err.message)}</p>`}}
 async function summaryHistory(){const rows=await api('workflow/summaries/'+patientId);dialog('Saved summaries',rows.map(s=>`<h3>${date(s.created_at)} · ${e(s.method)} · ${e(s.status)}</h3><pre>${e(JSON.stringify(s.content,null,2))}</pre>`).join('')||empty('No summaries yet.'))}
 async function approveSummary(id){const note=prompt('Clinician review note');if(!note)return;try{await api('workflow/summaries/'+id,'PATCH',{status:'CLINICIAN_APPROVED',review_note:note});$('hf-dialog').close();showToast('Summary review saved','success')}catch(err){showToast(err.message,'emergency')}}
 async function versions(){const rows=await api('workflow/versions/'+patientId);dialog('Record corrections',rows.map(v=>`<h3>${e(v.resource)} · ${date(v.created_at)}</h3><p>${e(v.reason)}</p><pre>${e(JSON.stringify({before:v.before,after:v.after},null,2))}</pre>`).join('')||empty('No corrections recorded.'))}
 async function appointments(){
  const outpatient=await outpatientPanel();
  follow=await api('workflow/follow-ups');
  const doctors=providers.filter(p=>p.role==='DOCTOR');
  const myConsultations = user.role==='PATIENT' ? await api('workflow/consultations') : [];
  let quota = null;
  if(user.role==='PATIENT' && patientId){
   try{quota=await api('intake/daily-quota/'+patientId)}catch(e){quota=null}
  }
  const quotaHtml = quota ? `
   <section class="hf-section" style="margin-bottom:18px;background:${quota.limit_reached?'#fef2f2':'#f0fdf4'};border:1.5px solid ${quota.limit_reached?'#fca5a5':'#86efac'};border-radius:12px;padding:14px 18px;">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
     <div>
      <h3 style="margin:0 0 4px 0;font-size:15px;color:${quota.limit_reached?'#991b1b':'#166534'};">📅 Daily Visit Quota: ${quota.visits_today} of ${quota.max_visits_per_day} visits used today</h3>
      <p style="margin:0;font-size:13px;color:#475569;">${quota.remaining_visits} consultation quota remaining for this patient today.</p>
     </div>
     <span class="hf-status" style="background:${quota.limit_reached?'#fee2e2':'#dcfce7'};color:${quota.limit_reached?'#dc2626':'#15803d'};font-weight:700;font-size:12px;padding:6px 12px;border-radius:9999px;">
      ${quota.limit_reached?'Limit Reached (Max '+quota.max_visits_per_day+'/day)':'Quota Available'}
     </span>
    </div>
    ${quota.limit_reached?`
     <div style="margin-top:10px;padding:10px;background:#fee2e2;border-radius:8px;font-size:12px;color:#991b1b;line-height:1.4;">
      ⚠️ <strong>Daily Limit Reached:</strong> Each patient is limited to ${quota.max_visits_per_day} consultations per calendar day to ensure provider availability. For medical emergencies (severe chest pain, respiratory distress, trauma), proceed immediately to an emergency department.
     </div>`:''}
   </section>`:'';

  const consultHistoryHtml = user.role==='PATIENT' && myConsultations.length ? `
   <section class="hf-section" style="margin-bottom:20px;">
    <h2>My Consultations & Visits (Visit History)</h2>
    ${table(['Visit Date','Doctor / Facility','Chief Complaint','Status','Action'],myConsultations.map(c=>[
     date(c.created_at),
     e(c.doctor_name||'Assigned Doctor'),
     e(c.chief_complaint),
     tag(c.status),
     c.status==='COMPLETED'?button('View complete check-up record',`HF.completeVisit('${c.id}')`,'primary'):button('Open encounter',`HF.encounter('${c.id}')`)
    ]))}
   </section>` : '';

  $('hf-content').innerHTML=head(user.role==='PATIENT'?'Appointments & follow-ups':'Follow-ups','Follow-up encounters remain linked to the original visit.')+
   quotaHtml+
   consultHistoryHtml+
   outpatient+
   table(['Due','Reason','Status','Action'],follow.map(f=>[date(f.due_at),e(f.reason),tag(f.status),f.status==='SCHEDULED'&&user.role==='PATIENT'&&f.doctor_id?button('Start linked intake',`HF.followIntake('${f.id}')`):'']))+
   (user.role==='PATIENT'?form('hf-intake','Request a consultation',`<div class="hf-form-grid">${select('Doctor','doctor_id',options(doctors))}${select('Primary complaint','complaint',statuses(['Fever','Cough','Blood Pressure','Joint Pain','Weakness','Allergy','Other']))}${input('Duration','duration','number','1')}${select('Duration unit','duration_unit',statuses(['Days','Hours','Weeks','Months']))}${select('Severity','severity',statuses(['Mild','Moderate','Severe']))}</div><label>Describe your symptoms<textarea name="notes"></textarea></label><label>Warning symptoms (comma-separated)<input name="warnings" placeholder="e.g. breathing_difficulty, chest_pain"></label><div id="hf-branch"></div>`,quota?.limit_reached?'Submit consultation (Emergency triage only)':'Submit intake'):empty('Choose an encounter to schedule a follow-up.'));
  bind('hf-intake',async(d)=>{const branch={};document.querySelectorAll('#hf-branch [name]').forEach(n=>branch[n.name]=n.value);await api('intake/submit','POST',{patient_id:patientId,doctor_id:d.doctor_id,q1_chief_complaint:d.complaint,q2_duration_value:Number(d.duration),q2_duration_unit:d.duration_unit,q3_severity:d.severity,q10_additional_notes:d.notes,q9_warning_symptoms:d.warnings?d.warnings.split(',').map(x=>x.trim()).filter(Boolean):[],branch_responses:branch});showToast('Consultation request submitted!','success');await go('overview')});
  if($('hf-intake')){$('hf-intake').insertAdjacentHTML('beforebegin',form('hf-assist','Describe symptoms in your language',select('Language','language',statuses(['en','hi','mr','hinglish']))+input('Describe symptoms','message'),'Suggest intake fields'));bind('hf-assist',async d=>{const result=await api('ai/chatbot','POST',d),p=result.parsed_symptoms;if(p?.chief_complaint&&Array.from($('hf-intake').elements.complaint.options).some(o=>o.value===p.chief_complaint)){$('hf-intake').elements.complaint.value=p.chief_complaint;await intakeBranch(p.chief_complaint)}$('hf-intake').elements.notes.value=d.message;if(p?.warning_symptoms)$('hf-intake').elements.warnings.value=p.warning_symptoms.join(', ');showToast('Suggested fields added. Review before submitting.','info')});$('hf-intake').elements.complaint.onchange=()=>intakeBranch($('hf-intake').elements.complaint.value);await intakeBranch('Fever')}
 }
 async function intakeBranch(complaint){try{const result=await api('intake/branch/'+encodeURIComponent(complaint));const questions=result.questions||result.branch?.questions||[];$('hf-branch').innerHTML='<h3>Additional intake details</h3>'+questions.map(q=>{const name=q.id||q.key||q.question_id;return q.options?select(q.label||q.text||q.question||name,name,q.options.map(x=>`<option value="${e(typeof x==='object'?x.value:x)}">${e(typeof x==='object'?x.label:x)}</option>`).join('')):input(q.label||q.text||q.question||name,name,'text','',false)}).join('')}catch{$('hf-branch').innerHTML='<p class="hf-muted">Additional questions unavailable; the core intake form remains usable.</p>'}}
 async function followIntake(id){const f=follow.find(x=>x.id===id);const complaint=prompt('Current symptoms / reason',f.reason);if(!complaint)return;try{await api('workflow/consultations','POST',{doctor_id:f.doctor_id,chief_complaint:complaint,follow_up_id:f.id,previous_consultation_id:f.consultation_id});await go('overview')}catch(err){showToast(err.message,'emergency')}}
 async function consultations(){
  const [rows,pts]=await Promise.all([api('workflow/consultations'),api('workflow/patients')]);
  encounters=rows;
  const active=encounters.filter(c=>!['COMPLETED','CANCELLED','NO_SHOW'].includes(c.status));
  const completed=encounters.filter(c=>c.status==='COMPLETED');
  const showCompleted = page==='completed';
  const showQueue = page==='queue';
  const filtered = showCompleted ? completed : (showQueue ? active : encounters);
  const activeTab = showCompleted ? 'completed' : (showQueue ? 'queue' : 'all');

  $('hf-content').innerHTML=head(showCompleted?'Completed Visit History':showQueue?'Consultation queue':'Consultations','Assigned encounters and their clinical status',button('Clinical overview',"HF.go('overview')"))+
   `<div class="hf-toolbar" style="margin-bottom:16px;">
    ${button('Active Queue ('+active.length+')',`HF.filterConsultationView('queue')`,activeTab==='queue'?'primary':'')}
    ${button('Completed Visits History ('+completed.length+')',`HF.filterConsultationView('completed')`,activeTab==='completed'?'primary':'')}
    ${button('All Consultations ('+encounters.length+')',`HF.filterConsultationView('all')`,activeTab==='all'?'primary':'')}
   </div>`+
   table(['Patient / age','Complaint','Urgency','Arrival / Date','Status','Action'],filtered.map(c=>[
    e(c.patient_name)+`<small>${e(pts.find(p=>p.id===c.patient_id)?.age??'Not recorded')} years</small>`,
    e(c.chief_complaint),
    tag(c.is_urgent?'URGENT':c.symptom_severity||'NOT_RECORDED'),
    date(c.created_at),
    tag(c.status),
    button('Open encounter',`HF.encounter('${c.id}')`)+(c.status==='COMPLETED'?' '+button('View record',`HF.completeVisit('${c.id}')`):'')
   ]));
 }
 function filterConsultationView(v){
  if(v==='queue')go('queue');
  else if(v==='completed'){page='completed';consultations();}
  else go('consultations');
 }
 async function encounter(id){
  const c=encounters.find(x=>x.id===id);
  if(!c)return;
  patientId=c.patient_id;
  const clinical=await api('workflow/consultations/'+id+'/clinical-records');
  const allergies=await api('workflow/allergies/'+patientId);
  const cmed=await api('workflow/medications/'+patientId);
  const hs=providers.filter(x=>x.role==='HOSPITAL_ADMIN'),ps=providers.filter(x=>x.role==='PHARMACY');

  // Medication and Prescription Changes Section
  let medSection='';
  const changes = clinical.plan?.changes || [];
  const rxList = clinical.prescriptions || [];
  const planMeds = clinical.plan?.medications || [];
  let medRows = [];
  if(changes.length){
   changes.forEach(ch=>{
    medRows.push([
     `<strong>${e(ch.action?.toUpperCase())}</strong>`,
     e(ch.revised?.name||'Medicine'),
     e([ch.revised?.frequency,ch.revised?.dosage].filter(Boolean).join(' · ')),
     e(ch.reason||'Prescription amendment')
    ]);
   });
  } else if(planMeds.length){
   planMeds.forEach(m=>{
    medRows.push([
     `<strong>${e(m.action?.toUpperCase())}</strong>`,
     e(m.name||'Medicine'),
     `${m.times_per_day} times/day · ${e(m.food||'Not specified')}${m.dosage?' · '+e(m.dosage):''}`,
     e(m.reason||(m.quantity?'Dispensing qty: '+m.quantity:'Instructions only'))
    ]);
   });
  }
  rxList.forEach(rx=>{
   (rx.medicines||[]).forEach(m=>{
    medRows.push([
     tag(rx.status),
     `<strong>${e(m.name)}</strong>`,
     e([m.dosage,m.frequency,m.food].filter(Boolean).join(' · ')),
     m.quantity?`Dispensing quantity: ${e(m.quantity)}`:'Instructions only'
    ]);
   });
  });
  if(medRows.length){
   medSection = `<section class="hf-section"><h2>Prescription & Medication Changes (Consultation Decisions)</h2>${table(['Action / Status','Medicine','Dosage & Frequency','Instructions / Reason'],medRows)}</section>`;
  } else {
   medSection = `<section class="hf-section"><h2>Prescription & Medication Decisions</h2>${empty('No prescription decisions recorded yet for this visit.')}</section>`;
  }

  // Hospital Referrals Section
  let refSection='';
  const refsList = clinical.referrals || [];
  const planRefs = clinical.plan?.referrals || [];
  let refRows = [];
  refsList.forEach(r=>{
   refRows.push([
    `<strong>${e(r.hospital_name||r.name)}</strong>`,
    e(r.specialty||'General'),
    tag(r.priority||'ROUTINE'),
    e(r.reason),
    tag(r.status||'SENT')
   ]);
  });
  planRefs.forEach(r=>{
   if(!refsList.some(x=>x.name===r.name||(r.hospital_id&&x.hospital_id===r.hospital_id))){
    refRows.push([
     `<strong>${e(r.name)}</strong>`,
     e(r.specialty||'Not specified'),
     tag(r.priority||'ROUTINE'),
     e(r.reason),
     tag(r.hospital_id?'REQUESTED':'EXTERNAL_LETTER')
    ]);
   }
  });
  if(refRows.length){
   refSection = `<section class="hf-section"><h2>Hospital Referrals</h2>${table(['Hospital Destination','Specialty','Priority','Referral Reason','Status'],refRows)}</section>`;
  } else {
   refSection = `<section class="hf-section"><h2>Hospital Referrals</h2>${empty('No hospital referrals recorded for this visit.')}</section>`;
  }

  // Doctor's Clinical Note & Assessment Section
  let noteSection='';
  const noteObj = clinical.doctor_note || (clinical.plan ? {
   confirmed_diagnosis: clinical.plan.assessment,
   clinical_observations: clinical.plan.observations,
   treatment_plan: clinical.plan.advice
  } : null);
  if(noteObj && (noteObj.confirmed_diagnosis || noteObj.clinical_observations || noteObj.treatment_plan)){
   noteSection = `<section class="hf-section"><h2>Doctor’s Clinical Note & Assessment</h2><p><strong>Confirmed Diagnosis / Assessment:</strong> ${e(noteObj.confirmed_diagnosis||'None recorded')}</p><p><strong>Observations:</strong> ${e(noteObj.clinical_observations||'None recorded')}</p><p><strong>Treatment Advice:</strong> ${e(noteObj.treatment_plan||'None recorded')}</p></section>`;
  }

  // Live Consultation Toolbar for Doctors
  let doctorToolbar = '';
  if(user.role==='DOCTOR' && !['COMPLETED','CANCELLED','NO_SHOW'].includes(c.status)){
   doctorToolbar = `<div class="hf-toolbar" style="margin:16px 0;padding:12px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;">
    <strong style="margin-right:8px;color:#166534;">Clinical Actions:</strong>
    ${button('Doctor’s Note Editor',`HF.doctorsNote('${id}')`,'primary')}
    ${button('Change Frequency',`HF.doctorsNote('${id}');setTimeout(()=>HF.decisionForm('frequency'),150);`)}
    ${button('Replace Medication',`HF.doctorsNote('${id}');setTimeout(()=>HF.decisionForm('replace'),150);`)}
    ${button('Add Medication',`HF.doctorsNote('${id}');setTimeout(()=>HF.decisionForm('add'),150);`)}
    ${button('Refer to Hospital',`HF.doctorsNote('${id}');setTimeout(()=>HF.referralForm(),150);`)}
    ${button('Finalize Check-up',`HF.doctorsNote('${id}');setTimeout(()=>HF.reviewNote(),150);`,'primary')}
   </div>`;
  }

  $('hf-content').innerHTML=head(c.patient_name,c.chief_complaint+' · '+c.id,button('Patient history',"HF.go('history')")+(user.role==='DOCTOR'&&!['COMPLETED','CANCELLED','NO_SHOW'].includes(c.status)?button('Doctor’s Note',`HF.doctorsNote('${id}')`,'primary'):'')+(c.status==='COMPLETED'?button('View check-up record',`HF.completeVisit('${id}')`,'primary'):'')+(c.previous_consultation_id?button('Previous encounter',`HF.linkedEncounter('${c.previous_consultation_id}')`):''))+
   `<div class="hf-notice">Allergies: ${e([...allergies.reported,...allergies.records.filter(x=>x.status==='ACTIVE').map(x=>`${x.substance} (${x.severity}; ${x.source})`)].join(', ')||'Not recorded')}<br>Active medication: ${e(cmed.filter(x=>x.status==='ACTIVE').map(x=>x.name).join(', ')||'None recorded')}</div>`+
   doctorToolbar+
   `<section class="hf-section"><h2>Patient intake</h2><p>${e(c.patient_notes||'No additional notes')}</p><pre>${e(JSON.stringify(c.branch_responses||{},null,2))}</pre>${button('Current consultation summary',`HF.currentSummary('${id}')`)} ${tag(c.status)}</section>`+
   medSection+
   refSection+
   noteSection+
   `<section class="hf-section"><h2>Recorded diagnoses and vitals</h2>${table(['Record','Status','Correction'],[...clinical.diagnoses.map(d=>[e(d.name),tag(d.status),button('Correct',`HF.correctRecord('diagnosis','${d.id}','${id}')`)]),...clinical.vitals.map(v=>[e(v.name+': '+v.value+' '+v.unit),tag(v.status),button('Correct',`HF.correctRecord('vital','${v.id}','${id}')`)])])}</section>`+
   form('hf-status','Consultation status',select('Status','status',statuses(['IN_PROGRESS','COMPLETED','CANCELLED','NO_SHOW']))+`<label>Clinical observations<textarea name="observations">${e(c.branch_responses?.clinical_observations||'')}</textarea></label>`+input('Reason for update','reason'))+
   `<div class="hf-split"><div>${form('hf-diagnosis','Diagnosis',input('Diagnosis','name')+select('Diagnostic certainty','status',statuses(['SUSPECTED','PROVISIONAL','CONFIRMED','RULED_OUT','RESOLVED'])))}${form('hf-vital','Record a vital',select('Measurement','name',statuses(['BP','temperature','pulse','SpO2','weight','glucose']))+input('Value','value')+input('Unit','unit','text','mmHg')+input('Measurement time (UTC; optional)','measured_at','datetime-local','',false))}</div><div>${form('hf-follow','Schedule a follow-up',input('Date and time (UTC)','due_at','datetime-local')+input('Follow-up reason','reason'))}</div></div>`+
   (c.status==='COMPLETED'?button('View complete check-up record',`HF.completeVisit('${id}')`,'primary'):'');
  HUI.workspace(user.role);
  if(user.role==='HOSPITAL_ADMIN'){$('hf-diagnosis').style.display='none';$('hf-status').style.display='none';}
  $('hf-status').elements.status.value=c.status==='COMPLETED'?'COMPLETED':'IN_PROGRESS';
  bind('hf-status',async d=>{if(d.status==='COMPLETED'){await doctorsNote(id);return;}await api('workflow/consultations/'+id,'PATCH',d);encounters=await api('workflow/consultations');await encounter(id)});
  bind('hf-diagnosis',async d=>{await api('workflow/consultations/'+id+'/diagnoses','POST',d);showToast('Diagnosis recorded','success')});
  bind('hf-vital',async d=>{if(!d.measured_at)delete d.measured_at;await api('workflow/consultations/'+id+'/vitals','POST',d);showToast('Vital recorded','success')});
  bind('hf-follow',async d=>{await api('workflow/follow-ups','POST',{...d,consultation_id:id});showToast('Follow-up scheduled','success')});

 }
 async function correctRecord(kind,rid,cid){const reason=prompt('Correction reason');if(!reason)return;const value=prompt(kind==='diagnosis'?'New diagnosis status: SUSPECTED, PROVISIONAL, CONFIRMED, RULED_OUT, RESOLVED, ENTERED_IN_ERROR':'Corrected vital value');if(!value)return;try{await api('workflow/records/'+kind+'/'+rid,'PATCH',{reason,...(kind==='diagnosis'?{status:value.trim().toUpperCase()}:{value})});await encounter(cid)}catch(err){showToast(err.message,'emergency')}}
 async function currentSummary(cid){try{const d=await api('ai/generate-summary','POST',{consultation_id:cid});dialog('Consultation draft · clinician review',`<pre>${e(d.structured_note_markdown)}</pre>`)}catch(err){showToast(err.message,'emergency')}}
 function medTable(rows){return table(['Medicine','Dose / frequency','Course','Status'],rows.map(m=>[e(m.name),e(m.dosage||'Not recorded')+`<small>${e([m.frequency,m.instructions?.food||'Not specified',m.instructions?.disease,m.instructions?.additional_instructions].filter(Boolean).join(' · '))}</small>`,date(m.start_date)+`<small>${m.end_date?'Until '+date(m.end_date):'Ongoing / end not recorded'}</small>`,tag(m.status)]));}
 async function medications(){const rx=await api('workflow/prescriptions');if(user.role==='PATIENT'){meds=await api('workflow/medications/'+patientId);$('hf-content').innerHTML=head('Prescriptions & medications','Medication course status is separate from pharmacy dispensing.')+`<section class="hf-section"><h2>Active medications</h2>${medTable(meds.filter(x=>x.status==='ACTIVE'))}</section><section class="hf-section"><h2>Past medications</h2>${medTable(meds.filter(x=>x.status!=='ACTIVE'))}</section><h2>Prescriptions</h2>`+rxTable(rx);return;}
  $('hf-content').innerHTML=head(page==='dispensing'?'Dispensing history':'Prescription queue','Only assigned prescriptions and patient-authorized dispensing records are shown.')+rxTable(page==='dispensing'?rx.filter(x=>x.status==='DISPENSED'):rx)+form('hf-redeem','Open patient-authorized prescription',input('Consent token / QR text','token'),'Redeem');bind('hf-redeem',async d=>{await api('workflow/access/redeem','POST',d);await go(page);void PinAccess.checkSetup()});
 }
 function rxTable(rows){return table(['Patient / clinician','Medicines','Issued / dispensed','Dispensing status','Action'],rows.map(r=>[e(r.patient_name||user.name)+`<small>${e(r.doctor_name||'')}</small>`,e(r.medicines.map(m=>`${m.name} · ${m.dosage} · ${m.frequency} · ${m.food||'Not specified'}${m.discontinued?' (superseded)':''}`).join('; '))+(r.allergies?`<small>Allergies: ${e(r.allergies.join(', ')||'Not recorded')}</small>`:''),date(r.created_at)+`<small>${r.dispensed_at?'Dispensed '+date(r.dispensed_at):'Not yet dispensed'}</small>`,tag(r.status),user.role==='PHARMACY'&&r.status==='PENDING'?button('Dispense',`HF.dispense('${r.id}')`):'']));}
 async function dispense(id){if(!confirm('Confirm dispensing? Inventory will be deducted and this action is recorded.'))return;try{await api('workflow/prescriptions/'+id+'/dispense','POST');await go(page);void PinAccess.checkSetup()}catch(err){showToast(err.message,'emergency')}}
 async function medicationReview(){meds=await api('workflow/medications/'+patientId);dialog('Medication review',table(['Medicine','Course status','Action'],meds.map(m=>[e(m.name),tag(m.status),m.status==='ACTIVE'?button('Discontinue',`HF.stopMedication('${m.id}')`):''])))}
 async function stopMedication(id){const reason=prompt('Reason for discontinuation');if(!reason)return;try{await api('workflow/medications/'+id,'PATCH',{status:'DISCONTINUED',reason});await medicationReview()}catch(err){showToast(err.message,'emergency')}}
 async function referrals(){const external=['PATIENT','DOCTOR'].includes(user.role)?await api('workflow/external-referrals'):[];refs=await api('workflow/referrals');$('hf-content').innerHTML=head(user.role==='HOSPITAL_ADMIN'?'Incoming referrals':'Referrals','From initial request to specialist outcome')+table(['External hospital','Reason','Letter'],external.map(r=>[e(r.name)+'<small>'+e(r.address)+'</small>',e(r.reason),button('Open printable referral letter',`HF.completeVisit('${r.consultation_id}')`)]))+table(['Patient / destination','Specialty / reason','Priority','Status','Action'],refs.map(r=>[e(r.patient_name)+`<small>${e(r.hospital_name)}</small>`,e(r.specialty)+`<small>${e(r.reason)}</small>`,tag(r.priority),tag(r.status),refActions(r)]))+refs.filter(r=>r.outcome_summary).map(r=>`<section class="hf-section"><h2>Outcome · ${e(r.patient_name)}</h2><p>${e(r.outcome_summary)}</p><small class="hf-muted">Linked specialist encounter ${e(r.outcome_consultation_id)}</small></section>`).join('');}
 function refActions(r){const acts=[];if(user.role==='HOSPITAL_ADMIN'){const next={SENT:'RECEIVED',RECEIVED:'ACCEPTED',ACCEPTED:'PATIENT_ARRIVED',SPECIALIST_CONSULTATION:'COMPLETED'}[r.status];if(next)acts.push(button(next.replaceAll('_',' '),`HF.advanceReferral('${r.id}','${next}')`));if(r.status==='RECEIVED')acts.push(button('Decline',`HF.advanceReferral('${r.id}','DECLINED')`));if(r.status==='PATIENT_ARRIVED')acts.push(button('Specialist encounter',`HF.specialist('${r.id}')`,'primary'));}else if(['SENT','RECEIVED','ACCEPTED','PATIENT_ARRIVED'].includes(r.status))acts.push(button('Cancel',`HF.advanceReferral('${r.id}','CANCELLED')`));acts.push(button('Referral detail',`HF.referralDetail('${r.id}')`));return `<div class="hf-row-actions">${acts.join('')}</div>`;}
 function referralDetail(id){const r=refs.find(x=>x.id===id);dialog('Referral record',`<p>${e(r.patient_name)} · ${e(r.hospital_name)}</p><p>${e(r.specialty)} · ${e(r.priority)} · ${e(r.status)}</p><p>Reason: ${e(r.reason)}</p><p>Clinical summary: ${e(r.clinical_summary||'Not recorded')}</p>${button('View complete check-up record',`HF.completeVisit('${r.consultation_id}')`)}`)}
 async function advanceReferral(id,status){const reason=prompt(status==='COMPLETED'?'Specialist outcome summary':'Reason / receipt note');if(!reason)return;try{await api('workflow/referrals/'+id,'PATCH',{status,reason,outcome_summary:status==='COMPLETED'?reason:null});await go('referrals')}catch(err){showToast(err.message,'emergency')}}
 async function specialist(id){const r=refs.find(x=>x.id===id);const ds=providers.filter(x=>x.role==='DOCTOR'&&x.hospital_id===user.hospital_id);dialog('Create specialist encounter',`<p>${e(r.patient_name)} · ${e(r.specialty)}</p><label>Assigned hospital clinician<select id="hf-specialist-doctor">${options(ds)}</select></label><p class="hf-muted">Use Doctors to invite a registered clinician into this hospital first.</p>${button('Create encounter',`HF.createSpecialist('${id}')`,'primary')}`)}
 async function createSpecialist(id){try{const r=refs.find(x=>x.id===id),did=$('hf-specialist-doctor').value;if(!did)throw new Error('Select an affiliated doctor');await api('workflow/consultations','POST',{patient_id:r.patient_id,doctor_id:did,referral_id:r.id,chief_complaint:r.reason});$('hf-dialog').close();await go('consultations')}catch(err){showToast(err.message,'emergency')}}
 async function patients(){const rows=await api('workflow/patients');$('hf-content').innerHTML=head('Patients','Only patients within your authorized care relationships')+table(['Patient','Age','Blood group','Action'],rows.map(p=>[e(p.full_name),e(p.age),e(p.blood_group||'Not recorded'),button('Medical history',`HF.patientHistory('${p.id}')`)]))+form('hf-redeem','Patient consent',input('Consent token / QR text','token'),'Redeem');bind('hf-redeem',async d=>{await api('workflow/access/redeem','POST',d);await go('patients')})}
 async function patientHistory(id){patientId=id;await go('history')}
 async function admissions(){const [rows,b,pts]=await Promise.all([api('workflow/admissions'),api('workflow/beds'),api('workflow/patients')]);const ds=providers.filter(x=>x.role==='DOCTOR'&&x.hospital_id===user.hospital_id);$('hf-content').innerHTML=head('Admissions','Bed allocation is checked atomically. Discharged beds enter cleaning.')+table(['Patient','Admitted','Status','Summary / action'],rows.map(a=>[e(a.patient_name),date(a.created_at),tag(a.status),a.status==='ADMITTED'?button('Discharge',`HF.discharge('${a.id}')`):e(a.discharge_summary)]))+form('hf-admit','Admit an authorized patient',select('Patient','patient_id',options(pts,'full_name'))+select('Available bed','bed_id',options(b.filter(x=>x.state==='AVAILABLE').map(x=>({id:x.id,name:x.ward_name+' · '+x.bed_number}))))+select('Responsible clinician','doctor_id',options(ds))+input('Admission reason','reason')+input('Consultation ID (optional)','consultation_id','text','',false)+input('Referral ID (optional)','referral_id','text','',false),'Allocate bed');bind('hf-admit',async d=>{d.consultation_id=d.consultation_id||null;d.referral_id=d.referral_id||null;await api('workflow/admissions','POST',d);await go('admissions')})}
 async function discharge(id){if(!confirm('Discharge this patient and move their bed to cleaning?'))return;const summary=prompt('Discharge summary and home-care / follow-up instructions');if(!summary)return;try{await api('workflow/admissions/'+id+'/discharge','POST',{summary});await go('admissions')}catch(err){showToast(err.message,'emergency')}}
 async function beds(){const rows=await api('workflow/beds');$('hf-content').innerHTML=head('Beds & wards','Available · reserved · occupied · cleaning')+table(['Ward','Bed','State','Action'],rows.map(b=>[e(b.ward_name),e(b.bed_number),tag(b.state),b.state==='CLEANING'||b.state==='RESERVED'?button('Mark available',`HF.bedStatus('${b.id}','AVAILABLE')`):b.state==='AVAILABLE'?button('Reserve',`HF.bedStatus('${b.id}','RESERVED')`):'Use Admissions to discharge']))+form('hf-bed','Add a bed',input('Ward name','ward_name')+select('Ward type','ward_type',statuses(['ICU','GENERAL','EMERGENCY','PEDIATRIC']))+input('Bed number','bed_number'));bind('hf-bed',async d=>{await api('workflow/beds','POST',d);await go('beds')})}
 async function bedStatus(id,status){try{await api('workflow/beds/'+id,'PATCH',{status,reason:'Hospital operations update'});await go('beds')}catch(err){showToast(err.message,'emergency')}}
 async function doctors(){const ds=providers.filter(x=>x.role==='DOCTOR'&&x.hospital_id===user.hospital_id);$('hf-content').innerHTML=head('Hospital doctors','Clinicians join using a hospital-issued invitation.')+table(['Doctor','Account'],ds.map(d=>[e(d.name),e(d.user_id)]))+button('Create invitation','HF.invitation()','primary')+`<p class="hf-muted">The doctor pastes the invitation in Clinic settings. It expires after one hour.</p>`}
 async function invitation(){try{const data=await api('workflow/hospital/invite','POST');dialog('Hospital invitation',`<p>Valid for 60 minutes. Share with your registered clinician.</p><textarea readonly style="width:100%;height:120px">${e(data.invitation)}</textarea>`)}catch(err){showToast(err.message,'emergency')}}
 async function documents(){const rows=await api('workflow/documents/'+patientId);HF.recordDocs=await api('workflow/record-documents/'+patientId);$('hf-content').innerHTML=head('Documents','Uploaded historical records retain their source and appear in the timeline.')+`<h2>Care documents</h2>${table(['Record','Type','Date','Action'],HF.recordDocs.map((r,i)=>[e(r.title),e(r.category),date(r.created_at),button('View / print',`HF.recordDoc(${i})`)]))}<h2>Uploaded records</h2>`+table(['Document','Category','Uploaded','Action'],rows.map(d=>[e(d.title)+`<small>${e(d.filename)}</small>`,e(d.category),date(d.created_at),button('Download',`HF.download('${d.id}')`)+button('Mark entered in error',`HF.documentError('${d.id}')`)]))+form('hf-upload','Upload a medical record',input('Title','title')+select('Category','category',statuses(['HISTORICAL','PRESCRIPTION','REFERRAL','DISCHARGE','INSURANCE','VACCINATION','OTHER']))+`<label>File (PDF, PNG, JPEG, text; maximum 10 MB)<input type="file" name="file" accept=".pdf,.png,.jpg,.jpeg,.txt" required></label>`,'Upload');bind('hf-upload',async(d,n)=>{const data=new FormData(n);data.append('patient_id',patientId);await api('workflow/documents','POST',data);await go('documents')})}
 function recordDoc(i){const r=HF.recordDocs[i];dialog(r.title,`<pre>${e(JSON.stringify(r.content,null,2))}</pre>${button('Print document',`HF.printRecord(${i})`)}`)}
 function printRecord(i){const r=HF.recordDocs[i],win=window.open('','_blank');if(!win){showToast('Allow popups to print this document','info');return}win.document.write('<!doctype html><title>'+e(r.title)+'</title><h1>'+e(r.title)+'</h1><pre style="white-space:pre-wrap">'+e(JSON.stringify(r.content,null,2))+'</pre>');win.document.close();win.print()}
 async function download(id){try{const r=await fetch('/api/workflow/document/'+id+'/download',{headers:{Authorization:'Bearer '+currentToken}});if(!r.ok)throw new Error('Download failed');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=r.headers.get('content-disposition')?.match(/filename="([^"]+)"/)?.[1]||'medical-record';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000)}catch(err){showToast(err.message,'emergency')}}
 async function documentError(id){const reason=prompt('Reason for correction');if(!reason)return;try{await api('workflow/records/document/'+id,'PATCH',{status:'ENTERED_IN_ERROR',reason});await go('documents')}catch(err){showToast(err.message,'emergency')}}
 async function nearby(){const coords=userCurrentCoords||{lat:user.latitude,lng:user.longitude};$('hf-content').innerHTML=head('Nearby care','Registered facilities and emergency medical centers near you.')+`<div class="hf-toolbar"><input id="hf-search" placeholder="Facility or address" aria-label="Search facilities"><select id="hf-type" aria-label="Facility type">${statuses(['all','hospital','pharmacy','clinic','registered'])}</select>${button('Search','HF.loadFacilities()')}${button('📍 Use current location','HF.locate()','primary')}<label>Latitude <input id="hf-lat" type="number" step="any" value="${e(coords.lat??'')}"></label><label>Longitude <input id="hf-lng" type="number" step="any" value="${e(coords.lng??'')}"></label></div><div id="hf-facilities">Loading facilities…</div><div id="hf-map" class="hf-map"></div>`;await loadFacilities();}
 async function loadFacilities(){try{const latEl=$('hf-lat'),lngEl=$('hf-lng');const lat=latEl?latEl.value.trim():'',lng=lngEl?lngEl.value.trim():'';const q=new URLSearchParams({search_query:$('hf-search')?$('hf-search').value:'',facility_type:$('hf-type')?$('hf-type').value:'all',radius_km:50});if(lat!==''&&lng!==''){q.set('lat',lat);q.set('lng',lng)}const data=await api('clinical/facilities/nearby?'+q);const rows=data.facilities||[];$('hf-facilities').innerHTML=table(['Facility','Address','Distance','Beds','Source','Action'],rows.map((f,i)=>[e(f.name)+`<small>${e(f.facility_type)}</small>`,e(f.address),e(f.distance||'Unavailable'),f.available_beds??'—',e(f.is_registered?'Registered':'Map listing'),button('View',`HF.facility(${i})`)]));HF.facilities=rows;
    if(window.L){if(map)map.remove();const hasUserCoord=(lat!==''&&lng!==''&&!isNaN(Number(lat))&&!isNaN(Number(lng)));const centerLat=hasUserCoord?Number(lat):19.0760;const centerLng=hasUserCoord?Number(lng):72.8777;map=L.map('hf-map').setView([centerLat,centerLng],hasUserCoord?13:12);L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',{attribution:'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, TomTom',maxZoom:18}).addTo(map);
    if(hasUserCoord){const userIcon=L.divIcon({className:'hf-user-pin',html:'<div style="display:flex;align-items:center;justify-content:center;width:30px;height:30px;background:#2563eb;color:#ffffff;border-radius:50%;border:3px solid #ffffff;box-shadow:0 0 12px rgba(37,99,235,0.9);font-size:14px;cursor:pointer;">📍</div>',iconSize:[30,30],iconAnchor:[15,15]});L.marker([centerLat,centerLng],{icon:userIcon,zIndexOffset:1000}).addTo(map).bindPopup(`<div style="padding:4px;"><strong>📍 Your Current Location</strong><br><small style="color:#64748b;">Latitude: ${centerLat.toFixed(5)}<br>Longitude: ${centerLng.toFixed(5)}</small></div>`).openPopup();L.circle([centerLat,centerLng],{radius:800,color:'#2563eb',fillColor:'#3b82f6',fillOpacity:0.15,weight:1.5}).addTo(map);}
    rows.filter(f=>f.latitude!=null&&f.longitude!=null).forEach(f=>{const popup=document.createElement('div');popup.innerHTML=`<strong>${e(f.name)}</strong><br><small style="color:#64748b;">${e(f.facility_type||'')} · ${e(f.address||'')}</small><br><b style="color:#2563eb;">Distance: ${e(f.distance||'')}</b>`;L.marker([f.latitude,f.longitude]).addTo(map).bindPopup(popup)});setTimeout(()=>map.invalidateSize(),200);}else $('hf-map').innerHTML=empty('Map unavailable. The facility list remains accessible.');
  }catch(err){$('hf-facilities').innerHTML=`<div class="hf-error">${e(err.message)}</div>`}}
 function facility(i){const f=HF.facilities[i];dialog(f.name,`<p>${e(f.facility_type)} · ${e(f.is_registered?'Registered in PulseSync':'External map listing')}</p><p>${e(f.address)}</p><p>Distance: ${e(f.distance||'Unavailable')}</p><p>Contact: ${e(f.phone||'Not recorded')}</p><p>${e((f.availableMeds||[]).join(' · '))}</p>`)}
 function locate(){if(!navigator.geolocation){showToast('Geolocation is not supported by your browser; enter coordinates manually.','info');return}showToast('Acquiring your current GPS location...','info');navigator.geolocation.getCurrentPosition(p=>{const lat=p.coords.latitude;const lng=p.coords.longitude;if($('hf-lat'))$('hf-lat').value=lat;if($('hf-lng'))$('hf-lng').value=lng;userCurrentCoords={lat,lng};showToast('Current GPS location detected!','success');loadFacilities()},err=>{let msg='Location permission denied. Please allow location permissions in your browser or enter coordinates manually.';if(err.code===2)msg='Location unavailable. Please check your device GPS.';else if(err.code===3)msg='Location request timed out.';showToast(msg,'info')},{enableHighAccuracy:true,timeout:10000,maximumAge:60000})}
 async function consent(){const grants=await api('workflow/access/'+patientId);$('hf-content').innerHTML=head('Consent & QR access','Identification, clinical access, dispensing, and emergency access are separate.')+`<div class="hf-notice">A patient identification QR does not grant medical access. Provider grants expire and can be revoked. Emergency tokens reveal a limited profile only.</div><div class="hf-toolbar">${button('Identification QR','HF.identityQR()')} ${button('🏥 Hospital Admission QR','HF.admissionQR()')} ${button('🛡️ Health Insurance QR','HF.insuranceQR()')}</div>`+form('hf-grant','Create temporary access',select('Scope','scope',statuses(['CLINICAL','PRESCRIPTION','EMERGENCY']))+`<label>Provider (not needed for emergency)<select name="provider_user_id"><option value="">Select provider</option>${providers.map(p=>`<option value="${e(p.user_id)}">${e(p.name)} · ${e(p.role)}</option>`).join('')}</select></label>`+PinAccess.field('Patient PIN (clinical / prescription consent)','pin')+input('Expiry in minutes (1–1440)','minutes','number','30'),'Create access QR')+table(['Scope','Provider','Expiry','State','Action'],grants.map(g=>[e(g.scope),e(providers.find(p=>p.user_id===g.user_id)?.name||'Emergency bearer'),date(g.expires_at),g.revoked_at?'Revoked':new Date(g.expires_at+'Z')<new Date()?'Expired':'Valid',!g.revoked_at?button('Revoke',`HF.revoke('${g.id}')`):'']));bind('hf-grant',async d=>{const data=await api('workflow/access/'+patientId,'POST',{pin:d.pin,scope:d.scope,provider_user_id:d.provider_user_id||null,minutes:Number(d.minutes)});dialog('Temporary access QR',`<img class="hf-qr" src="${e(data.qr_image_base64)}" alt="Temporary consent QR"><p>Expires ${date(data.grant.expires_at)}</p><textarea readonly style="width:100%;height:70px">${e(data.payload)}</textarea>`)});}
 async function myQR(){
  if(user.role!=='PATIENT')return providerQR();
  const m=familyMembers.find(f=>f.patient_id===patientId);
  const name=m?m.full_name:user.name;
  dialog('PulseSync Healthcare Passes & QR Codes',`
   <div style="text-align:center;margin-bottom:16px;">
    <h3 style="margin:0 0 6px 0;font-size:16px;color:#0f172a;">Active Profile: <strong>${e(name)}</strong></h3>
    <p style="margin:0;font-size:13px;color:#64748b;">Choose which healthcare QR code or digital pass to display or share:</p>
   </div>
   <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;">
    <div style="background:#f8fafc;border:1.5px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center;display:flex;flex-direction:column;justify-content:space-between;">
     <div>
      <div style="font-size:28px;margin-bottom:6px;">🪪</div>
      <h4 style="margin:0 0 6px 0;font-size:14px;color:#0f172a;">Patient ID QR</h4>
      <p style="margin:0 0 12px 0;font-size:12px;color:#64748b;">Standard identity QR code for doctor check-ins and provider verification.</p>
     </div>
     <button type="button" class="hf-button primary" onclick="HF.identityQR()" style="width:100%;">Show ID QR</button>
    </div>
    <div style="background:#eff6ff;border:1.5px solid #bfdbfe;border-radius:12px;padding:16px;text-align:center;display:flex;flex-direction:column;justify-content:space-between;">
     <div>
      <div style="font-size:28px;margin-bottom:6px;">🏥</div>
      <h4 style="margin:0 0 6px 0;font-size:14px;color:#1e40af;">Hospital Admission QR</h4>
      <p style="margin:0 0 12px 0;font-size:12px;color:#64748b;">Fast-track hospital admission pass with ward pre-intake and medical profile.</p>
     </div>
     <button type="button" class="hf-button primary" style="background:#2563eb;width:100%;" onclick="HF.admissionQR()">Admission QR & Form</button>
    </div>
    <div style="background:#f0fdf4;border:1.5px solid #bbf7d0;border-radius:12px;padding:16px;text-align:center;display:flex;flex-direction:column;justify-content:space-between;">
     <div>
      <div style="font-size:28px;margin-bottom:6px;">🛡️</div>
      <h4 style="margin:0 0 6px 0;font-size:14px;color:#166534;">Health Insurance QR</h4>
      <p style="margin:0 0 12px 0;font-size:12px;color:#64748b;">Digital health insurance card, policy verification and claim pre-authorization.</p>
     </div>
     <button type="button" class="hf-button primary" style="background:#059669;width:100%;" onclick="HF.insuranceQR()">Insurance QR & Pass</button>
    </div>
   </div>`);
 }
 async function admissionQR(targetId){
  const pid=targetId||patientId;
  try{
   const d=await api('qr/generate/'+pid+'/admission');
   dialog('Hospital Admission QR Code',`
    <div style="text-align:center;">
     <img class="hf-qr" src="${e(d.qr_image_base64)}" alt="Hospital Admission QR" style="max-width:240px;margin:10px auto;border:1px solid #e2e8f0;padding:6px;border-radius:8px;background:#fff;">
     <p style="font-weight:700;margin:8px 0;color:#0f172a;">${e(d.notice||'Fast-Track Hospital Admission Pass')}</p>
     <p style="font-size:13px;color:#64748b;margin-bottom:14px;">Scan at hospital triage / admission desk to open the pre-filled admission intake form.</p>
     <div style="margin-top:12px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
      <a href="/qr/admission/${pid}" target="_blank" rel="noopener" class="hf-button primary" style="display:inline-block;padding:8px 16px;text-decoration:none;border-radius:8px;font-weight:600;background:#2563eb;color:#fff;">Open Admission Form</a>
      <button type="button" class="hf-button" onclick="navigator.clipboard.writeText(location.origin+'/qr/admission/${pid}').then(()=>HF.showToast('Admission link copied!','success'))">Copy Direct Link</button>
     </div>
    </div>`);
  }catch(err){showToast(err.message,'emergency')}
 }
 async function insuranceQR(targetId){
  const pid=targetId||patientId;
  try{
   const d=await api('qr/generate/'+pid+'/insurance');
   dialog('Health Insurance Pass & QR',`
    <div style="text-align:center;">
     <img class="hf-qr" src="${e(d.qr_image_base64)}" alt="Insurance Pass QR" style="max-width:240px;margin:10px auto;border:1px solid #e2e8f0;padding:6px;border-radius:8px;background:#fff;">
     <p style="font-weight:700;margin:8px 0;color:#0f172a;">${e(d.notice||'Digital Health Insurance Pass')}</p>
     <p style="font-size:13px;color:#64748b;margin-bottom:14px;">Scan at billing or TPA desk for instant policy verification and pre-authorization claim filing.</p>
     <div style="margin-top:12px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
      <a href="/qr/insurance/${pid}" target="_blank" rel="noopener" class="hf-button primary" style="display:inline-block;padding:8px 16px;text-decoration:none;border-radius:8px;font-weight:600;background:#059669;color:#fff;">Open Digital Insurance Pass</a>
      <button type="button" class="hf-button" onclick="navigator.clipboard.writeText(location.origin+'/qr/insurance/${pid}').then(()=>HF.showToast('Insurance link copied!','success'))">Copy Direct Link</button>
     </div>
    </div>`);
  }catch(err){showToast(err.message,'emergency')}
 }
 async function scanResult(text){
  const admMatch=text.match(/^PULSESYNC:ADMISSION:([A-Za-z0-9_-]+)$/)||text.match(/\/qr\/admission\/([A-Za-z0-9_-]+)/);
  if(admMatch){
   QRTools.close();
   const pid=admMatch[1];
   dialog('Hospital Admission Card',`
    <p><strong>Fast-Track Admission Form</strong></p>
    <p>Patient ID: ${e(pid)}</p>
    <p>Open the verified Hospital Admission & Ward Pre-Admission form with one-touch bed admission and medical chart access.</p>
    <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap;">
     <a href="/qr/admission/${pid}" target="_blank" rel="noopener" class="primary" style="display:inline-block;padding:8px 16px;text-decoration:none;border-radius:8px;background:#2563eb;color:#fff;font-weight:600;">Open Admission Form</a>
     ${user.role==='HOSPITAL_ADMIN'?button('Admit to Ward',`HF.go('beds')`):''}
    </div>`);
   return 'Admission QR recognized.';
  }
  const insMatch=text.match(/^PULSESYNC:INSURANCE:([A-Za-z0-9_-]+)$/)||text.match(/\/qr\/insurance\/([A-Za-z0-9_-]+)/);
  if(insMatch){
   QRTools.close();
   const pid=insMatch[1];
   dialog('Digital Health Insurance Card',`
    <p><strong>Health Insurance Pass & Pre-Authorization</strong></p>
    <p>Patient ID: ${e(pid)}</p>
    <p>View verified policy credentials, coverage limits, TPA details, and submit direct pre-authorization claims.</p>
    <div style="margin-top:14px;">
     <a href="/qr/insurance/${pid}" target="_blank" rel="noopener" class="primary" style="display:inline-block;padding:8px 16px;text-decoration:none;border-radius:8px;background:#059669;color:#fff;font-weight:600;">Open Digital Insurance Pass</a>
    </div>`);
   return 'Insurance QR recognized.';
  }
  const identity=text.match(/^PULSESYNC:(?:INSURANCE:)?IDENTITY:([A-Za-z0-9_-]+)$/);
  if(identity){
   if(!['DOCTOR','HOSPITAL_ADMIN','PHARMACY'].includes(user.role))throw new Error('Access not authorized: patient identity requests are available to providers.');
   const identityCard=await api('qr/identify/'+identity[1]);
   scannedPatient=identityCard;scannedAccess=null;QRTools.close();
   dialog('Patient identification',`<p><strong>${e(identityCard.patient_name)}</strong></p><p>Patient ID: ${e(identityCard.patient_id)}</p><p>No clinical information is available until the patient authorizes access from their own account.</p><div id="scan-consent-state" role="status">Authorization required</div>${button('Request Consultation Access','HF.requestScannedAccess()','primary')} ${button('Check approval status','HF.checkScannedAccess()')}`);
   return 'Patient identified. Request consultation access before starting.';
  }
  if(/^PULSESYNC:CONSENT:[A-Za-z0-9_-]+$/.test(text)){
   if(user.role==='PATIENT')throw new Error('Consent QR codes must be scanned by the intended provider.');
   const result=await api('workflow/access/redeem','POST',{token:text});
   QRTools.close();if(result.scope==='CLINICAL')await patientHistory(result.patient_id);else await go(user.role==='PHARMACY'?'prescriptions':'patients');return;
  }
  let url;try{url=new URL(text,location.origin)}catch{throw new Error('Invalid PulseSync QR code.')}
  if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.search||url.hash)throw new Error('Unsupported QR URL.');
  // Recognize only allowlisted paths; resolve identifiers against THIS server. Never fetch the scanned host.
  const legacy=url.pathname.match(/^\/qr\/(patient|insurance)\/([A-Za-z0-9_-]+)$/);
  if(legacy)return scanResult('PULSESYNC:IDENTITY:'+legacy[2]);
  const provider=url.pathname.match(/^\/qr\/(doctor|hospital|pharmacy)\/([A-Za-z0-9_-]+)$/);
  if(provider){
   const role={doctor:'DOCTOR',hospital:'HOSPITAL_ADMIN',pharmacy:'PHARMACY'}[provider[1]];
   const list=await api('workflow/providers'),row=list.find(x=>x.id===provider[2]&&x.role===role);
   if(!row)throw new Error('This registered provider could not be found.');
   QRTools.close();
   const isDoc=user.role==='PATIENT'&&role==='DOCTOR';
   const consultForm=isDoc?`<form id="hf-doctor-scan-consult" style="margin-top:14px;padding:14px;background:#f8fafc;border:1px solid #cbd5e1;border-radius:10px;"><h3 style="font-size:14px;color:#0f172a;margin-bottom:6px;">Start Consultation with Dr. ${e(row.name)}</h3><p class="hf-muted" style="font-size:12px;margin-bottom:10px;">Enter your 6-digit PIN (entered during registration) to authorize clinical access and start consultation.</p><label>Reason / chief complaint<input name="chief_complaint" placeholder="e.g. Fever, Cough, Chest Pain, General Checkup" required></label><label>Severity<select name="severity"><option value="Mild">Mild</option><option value="Moderate" selected>Moderate</option><option value="Severe">Severe</option></select></label><label>Symptoms notes (optional)<textarea name="patient_notes" placeholder="Duration or details..." style="height:55px;"></textarea></label><label>Your 6-Digit Registration PIN<input type="password" name="pin" maxlength="6" pattern="\\d{6}" placeholder="••••••" required autocomplete="off" style="letter-spacing:4px;font-size:16px;"></label><button type="submit" class="primary" style="margin-top:10px;width:100%;">Authorize with PIN & Start Consultation</button><div class="form-message" role="status"></div></form>`:'';
   dialog('Registered provider',`<p><strong>${e(row.name)}</strong></p><p>${e(role.replaceAll('_',' '))}</p><a href="${e(url.pathname)}" target="_blank" rel="noopener">View provider details</a>${isDoc?consultForm:''}`);
   if(isDoc){
    bind('hf-doctor-scan-consult',async d=>{
     const res=await api('workflow/consultations/patient-scan-doctor','POST',{doctor_id:row.id,pin:d.pin,chief_complaint:d.chief_complaint,severity:d.severity,patient_notes:d.patient_notes});
     showToast(res.message||'Consultation authorized with PIN!','success');
     $('hf-dialog').close();
     await go('appointments');
    });
   }
   return;
  }
  if(/^\/api\/workflow\/emergency\/[A-Za-z0-9_-]+$/.test(url.pathname)){
   const result=await api(url.pathname.slice(5));QRTools.close();dialog('Limited emergency profile',`<pre>${e(JSON.stringify(result,null,2))}</pre>`);return;
  }
  throw new Error('Unsupported QR code. Scan a PulseSync patient, provider, consent or emergency QR.');
 }
 async function requestScannedAccess(){
  try{if(!scannedPatient)throw Error('Scan a patient QR first');scannedAccess=await api('security/requests','POST',{patient_id:scannedPatient.patient_id,minutes:30});await showScannedAccess()}catch(err){showToast(err.message,'emergency')}
 }
 async function checkScannedAccess(){
  try{if(!scannedAccess)throw Error('Request access first');const rows=await api('security/requests');scannedAccess=rows.find(r=>r.id===scannedAccess.id);if(!scannedAccess)throw Error('Request was not found');await showScannedAccess()}catch(err){showToast(err.message,'emergency')}
 }
 async function showScannedAccess(){
  const r=scannedAccess;dialogSafeClose();dialog('Consultation authorization',`<p><strong>${e(r.patient_name)}</strong></p><p>Access request: ${e(r.id)}</p><p role="status"><strong>${tag(r.status)}</strong></p><p>The patient must approve using their own authenticated session and registered six-digit PIN. Do not ask for their PIN.</p>${button('Refresh status','HF.checkScannedAccess()')}${user.role==='DOCTOR'&&r.status==='APPROVED'?button('Start Consultation','HF.startScannedConsultation()','primary'):''}`);
 }
 function dialogSafeClose(){const d=$('hf-dialog');if(d?.open)d.close()}
 async function startScannedConsultation(){
  try{await checkScannedAccess();if(scannedAccess.status!=='APPROVED')throw Error('Patient authorization is not approved');
   const complaint=prompt('Chief complaint / reason for consultation');if(!complaint?.trim())return;
   const c=await api('workflow/consultations','POST',{patient_id:scannedPatient.patient_id,access_request_id:scannedAccess.id,chief_complaint:complaint.trim()});
   dialogSafeClose();await go('consultations');showToast('Authorized consultation started','success');
  }catch(err){showToast(err.message,'emergency')}
 }
 async function scannedDoctor(id){$('hf-dialog').close();await go('appointments');const field=$('hf-request')?.querySelector('[name="doctor_id"]')||document.querySelector('#hf-content select[name="doctor_id"]');if(field){field.value=id;field.scrollIntoView({block:'center'});field.focus()}}
 async function identityQR(){try{const d=await api('qr/generate/'+patientId+'/identity');dialog('Patient identification',`<img class="hf-qr" src="${e(d.qr_image_base64)}" alt="Patient identification QR"><p>${e(d.notice)}</p><code>${e(d.token_payload)}</code>`)}catch(err){showToast(err.message,'emergency')}}
 async function revoke(id){if(!confirm('Revoke this access grant immediately?'))return;try{await api('workflow/access/'+id,'DELETE');await go('consent')}catch(err){showToast(err.message,'emergency')}}
 async function profile(){
  const [hist,al]=await Promise.all([api('workflow/history/'+patientId),api('workflow/allergies/'+patientId)]);
  const p=hist.patient;
  const familyHtml=user.role==='PATIENT'&&familyMembers.length?`
   <section class="hf-section" style="margin-top:24px;border:1.5px solid #cbd5e1;border-radius:12px;padding:16px;background:#f8fafc;">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px;">
     <div>
      <h2 style="margin:0 0 4px 0;font-size:17px;color:#0f172a;">👨‍👩‍👧‍👦 Family & Dependent Accounts</h2>
      <p class="hf-muted" style="margin:0;font-size:13px;">Manage linked accounts for your children (&lt;18) and elderly parents (60+) under this primary login.</p>
     </div>
     <button type="button" class="primary" onclick="HF.addFamilyModal()">+ Add Child / Elderly Profile</button>
    </div>
    ${table(['Profile Name','Relationship','Age','Blood Group','Active Profile','Passes & QR Codes'],familyMembers.map(m=>[
     `<strong>${e(m.full_name)}</strong>${m.is_primary?' <span style="font-size:10px;background:#e0e7ff;color:#3730a3;padding:2px 6px;border-radius:4px;font-weight:700;">PRIMARY</span>':''}`,
     tag(m.relationship_type),
     `${m.age} years`,
     e(m.blood_group||'Not recorded'),
     m.patient_id===patientId?'<span class="hf-status" style="background:#dcfce7;color:#15803d;font-weight:700;">Active Now</span>':button('Switch Profile',`HF.switchFamily('${m.patient_id}')`),
     `<div style="display:flex;gap:6px;flex-wrap:wrap;">
       ${button('🏥 Admission QR',`HF.admissionQR('${m.patient_id}')`)}
       ${button('🛡️ Insurance QR',`HF.insuranceQR('${m.patient_id}')`)}
      </div>`
    ]))}
   </section>`:'';
$('hf-content').innerHTML=head('Patient profile',p.full_name)+form('hf-profile','Current information',input('Blood group','blood_group','text',p.blood_group||'',false)+input('Chronic conditions (patient reported; comma-separated)','existing_conditions','text',(p.existing_conditions||[]).join(', '),false)+input('Emergency contact','emergency_contact_name','text',p.emergency_contact_name||'',false)+input('Emergency phone','emergency_contact_phone','tel',p.emergency_contact_phone||'',false)+input('Address','address','text',p.address||'',false)+input('City','city','text',p.city||'',false)+`<label><input name="confirm_current" type="checkbox">I confirm this information is current.</label>`)+familyHtml+`<section class="hf-section"><h2>Insurance information</h2><p>${e(p.insurance_provider||'Provider not recorded')} · Policy ${e(p.insurance_policy_no||'Not recorded')}</p><p class="hf-muted">${p.has_insurance?'Patient-reported coverage':'No coverage recorded'} · ${p.insurance_claimed?'Claim reported':'No claim reported'} · No external verification</p></section><h2>Allergy records</h2>${table(['Substance','Reaction','Severity','Source / confirmation'],al.records.map(a=>[e(a.substance),e(a.reaction||'Not recorded'),tag(a.severity),e(a.source)+`<small>${date(a.last_verified_at)}</small>`]))}<p class="hf-muted">Registration-reported allergies: ${e(al.reported.join(', ')||'Not recorded')}</p>`+form('hf-allergy','Add allergy',input('Substance','substance')+input('Reaction','reaction','text','',false)+select('Severity','severity',statuses(['UNKNOWN','MILD','MODERATE','SEVERE'])));bind('hf-profile',async d=>{d.existing_conditions=d.existing_conditions.split(',').map(x=>x.trim()).filter(Boolean);d.confirm_current=d.confirm_current==='on';await api('workflow/profile','PATCH',d);await go('profile')});bind('hf-allergy',async d=>{await api('workflow/allergies','POST',{...d,patient_id:patientId});await go('profile')})}
 function addFamilyModal(){
  dialog('Add Child or Elderly Family Account',`
   <form id="hf-add-family-form" style="display:flex;flex-direction:column;gap:12px;">
    <p class="hf-muted" style="font-size:13px;margin:0 0 8px 0;">Create a managed healthcare profile under your primary account. Both children and senior citizens can have dedicated admission forms, insurance passes, and independent medical histories.</p>
    <div class="hf-form-grid">
     <label>Relationship Type
      <select name="relationship_type" required onchange="HF.updateFamilyFields(this.value)">
       <option value="CHILD">Child / Minor (&lt;18 years)</option>
       <option value="ELDERLY_PARENT">Elderly Parent / Senior Citizen (60+ years)</option>
       <option value="SPOUSE">Spouse / Partner</option>
       <option value="OTHER_DEPENDENT">Other Dependent</option>
      </select>
     </label>
     <label>Full Legal Name<input name="full_name" placeholder="e.g. Aarav Sharma" required></label>
     <label>Age (years)<input name="age" id="family-form-age" type="number" min="0" max="130" value="8" required></label>
     <label>Gender
      <select name="gender" required>
       <option value="MALE">Male</option>
       <option value="FEMALE">Female</option>
       <option value="OTHER">Other</option>
      </select>
     </label>
     <label>Blood Group
      <select name="blood_group">
       <option value="UNKNOWN">Unknown</option>
       <option value="A+">A+</option>
       <option value="A-">A-</option>
       <option value="B+">B+</option>
       <option value="B-">B-</option>
       <option value="AB+">AB+</option>
       <option value="AB-">AB-</option>
       <option value="O+" selected>O+</option>
       <option value="O-">O-</option>
      </select>
     </label>
     <label>6-Digit PIN (for this profile)<input name="pin" type="password" maxlength="6" pattern="\\d{6}" value="123456" required style="letter-spacing:3px;"></label>
    </div>
    <div style="font-size:12px;color:#2563eb;margin-top:-4px;" id="family-form-hint">Tip: For children under 18, guardian consent is managed through your primary account.</div>
    <div class="hf-form-grid" style="margin-top:6px;">
     <label>Chronic / Existing Conditions (optional)<input name="existing_conditions" placeholder="e.g. Asthma, Childhood allergies"></label>
     <label>Allergies (comma-separated)<input name="allergies" placeholder="e.g. Peanuts, Penicillin"></label>
     <label>Insurance Provider (optional)<input name="insurance_provider" placeholder="e.g. Star Health, HDFC ERGO"></label>
     <label>Insurance Policy No. (optional)<input name="insurance_policy_no" placeholder="e.g. SH-9923842"></label>
    </div>
    <button type="submit" class="primary" style="margin-top:10px;padding:10px;">Create Profile & Link to My Account</button>
    <div class="form-message" role="status"></div>
   </form>`);
  bind('hf-add-family-form',async d=>{
   const payload={
    relationship_type:d.relationship_type,
    full_name:d.full_name,
    age:Number(d.age),
    gender:d.gender,
    blood_group:d.blood_group,
    pin:d.pin,
    existing_conditions:d.existing_conditions?d.existing_conditions.split(',').map(s=>s.trim()).filter(Boolean):[],
    allergies:d.allergies?d.allergies.split(',').map(s=>s.trim()).filter(Boolean):[],
    insurance_provider:d.insurance_provider||null,
    insurance_policy_no:d.insurance_policy_no||null
   };
   const res=await api('workflow/family','POST',payload);
   showToast('Family profile for '+d.full_name+' created!','success');
   await loadFamily();
   patientId=res.patient_id;
   localStorage.setItem('hf-active-patient:'+user.id,patientId);
   $('hf-dialog').close();
   await go('profile');
  });
 }
 function updateFamilyFields(rel){
  const ageInput=$('family-form-age'),hint=$('family-form-hint');
  if(!ageInput||!hint)return;
  if(rel==='CHILD'){
   ageInput.value='8';
   ageInput.max='17';
   ageInput.min='0';
   hint.textContent='Tip: Minor account (under 18). Guardian consent and intake are authorized by you.';
  }else if(rel==='ELDERLY_PARENT'){
   ageInput.value='68';
   ageInput.min='50';
   ageInput.max='130';
   hint.textContent='Tip: Senior Citizen profile (60+). Linked to your account for care coordination, admission forms, and visits.';
  }else{
   ageInput.value='35';
   ageInput.min='18';
   ageInput.max='120';
   hint.textContent='Tip: Managed family profile linked to your primary account.';
  }
 }
 async function notifications(){const ns=await api('workflow/notifications');$('hf-content').innerHTML=head('Notifications','Care updates and upcoming follow-ups')+table(['Date','Update','Status','Action'],ns.map(n=>[date(n.created_at),e(n.message),tag(n.status),n.status==='UNREAD'?button('Mark read',`HF.read('${n.id}')`):'']));}
 async function read(id){try{await api('workflow/notifications/'+id,'PATCH');await go('notifications')}catch(err){showToast(err.message,'emergency')}}
 async function audit(){const rows=await api('workflow/audit/'+patientId);$('hf-content').innerHTML=head('Record access log','Who accessed or changed your records')+table(['Time','Person','Action','Resource'],rows.map(a=>[date(a.created_at),e(a.user_name),e(a.action.replaceAll('_',' ')),e(a.resource||'')]));}
 async function inventory(){const data=await api('clinical/pharmacy/inventory');$('hf-content').innerHTML=head('Pharmacy inventory','Dispensing deducts actual inventory quantities.')+table(['Medicine','Form','Stock','Attention','Action'],data.inventory.map(i=>[e(i.medicine_name),e(i.category),e(i.stock_quantity),i.is_low_stock?tag('LOW_STOCK'):'',button('Restock',`HF.restock('${i.id}')`)]))+form('hf-inventory','Add medicine',input('Medicine name (exact prescription match)','medicine_name')+input('Dosage form','dosage_form','text','Tablet')+input('Quantity','stock_quantity','number','0')+input('Low stock threshold','low_stock_threshold','number','10')+input('Price','price','number','0'));bind('hf-inventory',async d=>{for(const k of ['stock_quantity','low_stock_threshold','price'])d[k]=Number(d[k]);await api('workflow/inventory','POST',d);await go('inventory')})}
 async function restock(id){const qty=prompt('Quantity to add');if(!qty)return;try{await api('clinical/pharmacy/restock','POST',{inventory_id:id,quantity_to_add:Number(qty)});await go('inventory')}catch(err){showToast(err.message,'emergency')}}
 async function settings(){const role=user.role;const fields=['name','email','phone',...role==='DOCTOR'?['specialization','clinic_name','clinic_address']:role==='HOSPITAL_ADMIN'?['hospital_name','address','city','emergency_phone']:['store_name','address','phone']];$('hf-content').innerHTML=head(role==='DOCTOR'?'Clinic settings':role==='HOSPITAL_ADMIN'?'Hospital settings':'Store settings','Registered account and provider information')+table(['Field','Value'],fields.map(k=>[e(k.replaceAll('_',' ')),e(user[k]||'Not recorded')]))+button('Provider QR','HF.providerQR()')+form('hf-provider','Provider location',input('Street address','address','text',user.address||user.clinic_address||'',false)+input('City','city','text',user.city||'',false)+input('Latitude (optional)','latitude','number',user.latitude??'',false)+input('Longitude (optional)','longitude','number',user.longitude??'',false))+(role==='DOCTOR'?form('hf-affiliation','Join a hospital',input('Hospital-issued invitation','invitation'),'Join hospital'):'');if($('hf-provider')){$('hf-provider').elements.latitude.step='any';$('hf-provider').elements.longitude.step='any';bind('hf-provider',async d=>{d.latitude=d.latitude===''?null:Number(d.latitude);d.longitude=d.longitude===''?null:Number(d.longitude);await api('workflow/provider-profile','PATCH',d);const me=await api('auth/me');currentUser=user=me.user;await go('settings')})}bind('hf-affiliation',async d=>{await api('workflow/doctor/affiliation','POST',d);const me=await api('auth/me');currentUser=user=me.user;await go('settings')})}
 async function providerQR(){try{const kind=user.role==='DOCTOR'?'doctor':user.role==='HOSPITAL_ADMIN'?'hospital':'pharmacy',id=user.doctor_id||user.hospital_id||user.pharmacy_id;const d=await api('qr/'+kind+'/'+id);dialog('Provider QR',`<img class="hf-qr" src="${e(d.qr_image_base64)}" alt="Provider QR"><p><a href="${e(d.web_url)}" target="_blank" rel="noopener">Open provider page</a></p>`)}catch(err){showToast(err.message,'emergency')}}
 function pickLocation(){const box=$('registration-map');box.style.display='block';if(!window.L){box.textContent='Map unavailable. Enter latitude and longitude manually.';return}if(!regMap){regMap=L.map('registration-map').setView([19.0760,72.8777],11);L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',{attribution:'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, TomTom',maxZoom:18}).addTo(regMap);let marker;regMap.on('click',ev=>{$('reg-lat').value=ev.latlng.lat.toFixed(6);$('reg-lng').value=ev.latlng.lng.toFixed(6);if(marker)marker.remove();marker=L.marker(ev.latlng).addTo(regMap);$('reg-location-status').textContent='Map location selected: '+ev.latlng.lat.toFixed(4)+', '+ev.latlng.lng.toFixed(4);})}setTimeout(()=>regMap.invalidateSize(),0)}
 async function emergencyAccess(){await go("consent");const form=$("hf-grant");if(form){form.elements.scope.value="EMERGENCY";form.elements.provider_user_id.value="";form.elements.minutes.value="30";form.scrollIntoView({block:"center"});form.elements.minutes.focus()}}

 let visitLocation={},visitDraft,visitMeds=[],visitCid,visitRevision=0,visitFacilities=[],lastRecord;
 const instructions=m=>[m?.dosage,m?.frequency,m?.instructions?.food||m?.food||'Not specified',m?.duration_days?m.duration_days+' days':null,m?.instructions?.timing,m?.instructions?.disease,m?.instructions?.additional_instructions].filter(Boolean).join(' · ');
 async function doctorsNote(cid){try{const d=await api('workflow/consultations/'+cid+'/plan');visitCid=cid;visitLocation=d.location||{};visitMeds=d.medications;visitRevision=d.revision;visitDraft={observations:'',assessment:'',advice:'',medications:[],referrals:[],acknowledge_warnings:false,...d.content};delete visitDraft.changes;delete visitDraft.warnings;delete visitDraft.active_medications;dialog('Doctor’s Note',`<p><strong>${e(d.patient_name)}</strong> · ${e(d.patient_id)}</p><p>Draft decisions stay private until the check-up is finalized.</p><div id="visit-editor"></div>`);renderNote()}catch(err){showToast(err.message,'emergency')}}
 function renderNote(){const d=visitDraft;$('visit-editor').innerHTML=`<h3>Actual active medications</h3>${visitMeds.length?visitMeds.map(m=>`<p><strong>${e(m.name)}</strong> · ${e(instructions(m))}<small> · ${e(m.source)}</small></p>`).join(''):empty('No active medicines. Use Add medication below.')}<div class="hf-toolbar">${button('Change prescription frequency',"HF.decisionForm('frequency')")}${button('Replace medication',"HF.decisionForm('replace')")}${button('Add medication',"HF.decisionForm('add')")}${button('Refer to another hospital','HF.referralForm()')}</div><div id="visit-action"></div><label>Observations<textarea id="visit-observations">${e(d.observations)}</textarea></label><label>Assessment<textarea id="visit-assessment">${e(d.assessment)}</textarea></label><label>Advice<textarea id="visit-advice">${e(d.advice)}</textarea></label><h3>Prepared decisions</h3>${decisionsReview(d)}<label><input type="checkbox" id="visit-ack" ${d.acknowledge_warnings?'checked':''}> I reviewed allergy and duplicate medicine warnings.</label><div id="visit-feedback" role="status"></div><div class="hf-toolbar">${button('Save draft','HF.saveNote()', 'primary')}${button('Review check-up','HF.reviewNote()')}</div>`;}
 function captureNote(){for(const k of ['observations','assessment','advice'])if($('visit-'+k))visitDraft[k]=$('visit-'+k).value;visitDraft.acknowledge_warnings=!!$('visit-ack')?.checked;}
 function decisionsReview(d){return d.medications.map((m,i)=>{const old=visitMeds.find(x=>x.id===m.medication_id);return `<section class="hf-notice"><strong>${e(m.action)}</strong><p>Previous: ${e(old?old.name+' · '+instructions(old):'No medicine replaced')}</p><p>Proposed: ${e(m.action==='frequency'?old?.name:m.name)} · ${e(m.times_per_day)} times per day · ${e(m.food??old?.instructions?.food??'Not specified')} · ${e(m.action==='frequency'?old?.dosage||'':m.dosage||'Dose not recorded')} ${e(m.duration_days?m.duration_days+' days':'')} ${e(m.timing||'')}</p><p>${e(m.reason||'')}${m.action==='frequency'?' Dose, duration and other instructions preserved. No refill order.':m.quantity?' Dispensing quantity: '+e(m.quantity):' Instructions only; no dispensing order.'}</p>${button('Remove decision',`HF.removeDecision('medications',${i})`)}</section>`}).join('')+d.referrals.map((r,i)=>`<section class="hf-notice"><strong>${e(r.name)}</strong><p>${e(r.address)} · ${e(r.specialty)} · ${e(r.priority)}</p><p>${e(r.reason)} · ${e(r.clinical_summary)}</p><p>${r.hospital_id?'Appointment requested / Pending hospital confirmation':'External referral letter only. No notification or booking.'}</p>${button('Remove referral',`HF.removeDecision('referrals',${i})`)}</section>`).join('');}
 function removeDecision(key,i){captureNote();visitDraft[key].splice(i,1);renderNote()}
 function foodSelect(value){return select('Take this medicine','food',statuses(['Not specified','Before food','After food'])).replace(`value="${e(value||'Not specified')}"`,`value="${e(value||'Not specified')}" selected`)}
 function decisionForm(action){captureNote();if(action!=='add'&&!visitMeds.length){$('visit-action').innerHTML=empty('No active medicines. Add medication to begin.')+button('Add medication',"HF.decisionForm('add')");return;}
 $('visit-action').innerHTML=form('visit-decision',action==='frequency'?'Change prescription frequency':action==='replace'?'Replace medication':'Add medication',`${action!=='add'?select('Active medicine','medication_id',options(visitMeds,'name'))+'<p id="visit-old"></p>':''}${action==='add'?input('How many medicines to add?','count','number','1')+button('Generate entry rows','HF.generateMedRows()'):''}<div id="visit-med-rows"></div><div id="visit-fields"></div>`,'Prepare decision');
 if(action==='add')generateMedRows();else{const sel=$('visit-decision').elements.medication_id;sel.onchange=()=>{const m=visitMeds.find(x=>x.id===sel.value);$('visit-old').textContent=m?m.name+' · '+instructions(m):'';$('visit-fields').innerHTML=medFields(action,m);};sel.selectedIndex=1;sel.onchange();}
 bind('visit-decision',async(d,node)=>{const rows=action==='add'?[...node.querySelectorAll('.visit-med-row')]:[$('visit-fields')];if(!rows.length)throw new Error('Add at least one medication row');const items=rows.map(row=>{const val=n=>row.querySelector(`[name="${n}"]`)?.value;return {action,medication_id:action==='add'?null:d.medication_id,name:val('name')||'',times_per_day:Number(val('times_per_day')),food:val('food'),...(action==='frequency'?{}:{dosage:val('dosage')||null,duration_days:val('duration_days')?Number(val('duration_days')):null,timing:val('timing')||null,reason:val('reason')||null,quantity:val('quantity')?Number(val('quantity')):null,pharmacy_id:val('pharmacy_id')||null})}});for(const m of items){if(!Number.isInteger(m.times_per_day)||m.times_per_day<1)throw new Error('Times per day must be a positive whole number');if(action!=='add'&&visitDraft.medications.some(x=>x.medication_id===m.medication_id))throw new Error('Remove the previous decision for this medicine first');}visitDraft.medications.push(...items);captureNote();renderNote();});}
 function medFields(action,m){return `${action!=='frequency'?input('Medicine name','name') :''}${input('How many times per day?','times_per_day','number',m?.instructions?.times_per_day||(action==='frequency'?'':'1'))}${foodSelect(m?.instructions?.food)}${action!=='frequency'?input('Strength / dose quantity (optional)','dosage','text','',false)+input('Duration days (optional)','duration_days','number','',false)+input('Timing (optional)','timing','text','',false)+input('Replacement reason (optional)','reason','text','',false)+input('Dispensing quantity (blank = instructions only)','quantity','number','',false)+`<label>Pharmacy (optional)<select name="pharmacy_id">${options(providers.filter(x=>x.role==='PHARMACY'),'name','No assigned pharmacy')}</select></label>`:''}`;}
 function generateMedRows(){const n=Number($('visit-decision').elements.count.value);if(!Number.isInteger(n)||n<1||n>50){showToast('Choose 1–50 medicines','emergency');return;}$('visit-med-rows').innerHTML=Array.from({length:n},()=>`<fieldset class="visit-med-row">${medFields('add')}${button('Remove row','this.parentElement.remove()')}</fieldset>`).join('')+button('Add row','HF.addMedRow()');}
 function addMedRow(){$('visit-med-rows').insertAdjacentHTML('afterbegin',`<fieldset class="visit-med-row">${medFields('add')}${button('Remove row','this.parentElement.remove()')}</fieldset>`)}
 async function referralForm(){captureNote();$('visit-action').innerHTML=`<h3>Hospital discovery</h3><p>Location: ${e(visitLocation.label)} (clinic/hospital profile). Change the coordinates below, or search without a location. Unknown distance is never labelled nearby.</p><div class="hf-form-grid"><label>Latitude<input id="visit-lat" type="number" step="any" value="${e(visitLocation.latitude??user.latitude??'')}"></label><label>Longitude<input id="visit-lng" type="number" step="any" value="${e(visitLocation.longitude??user.longitude??'')}"></label><label>Hospital or address<input id="visit-search" type="search"></label></div>${button('Search hospitals','HF.searchVisitHospitals()')}<div id="visit-hospitals"></div><div id="visit-referral-fields"></div>${button('Enter external hospital','HF.chooseVisitHospital(-1)')}`;await searchVisitHospitals();}
 async function searchVisitHospitals(){try{const q=new URLSearchParams({facility_type:'hospital',search_query:$('visit-search').value,radius_km:100});if($('visit-lat').value!==''&&$('visit-lng').value!==''){q.set('lat',$('visit-lat').value);q.set('lng',$('visit-lng').value)}visitFacilities=(await api('clinical/facilities/nearby?'+q)).facilities;$('visit-hospitals').innerHTML=table(['Hospital','Address','Distance','Specialties','Status','Action'],visitFacilities.map((h,i)=>[e(h.name),e(h.address),e(h.distance_km==null?'Distance unknown':h.distance_km+' km'),e((h.availableMeds||[]).join(', ')||'Not recorded'),h.is_registered?'Registered':'External',button('Choose',`HF.chooseVisitHospital(${i})`)]));}catch(err){$('visit-hospitals').innerHTML=empty(err.message+' — You can enter an external hospital below.')}}
 function chooseVisitHospital(i){const h=visitFacilities[i];$('visit-referral-fields').innerHTML=form('visit-referral','Referral details',input('Hospital name','name','text',h?.name||'')+input('Hospital address','address','text',h?.address||'')+input('Referral reason','reason')+input('Specialty (optional)','specialty','text','',false)+select('Priority','priority',statuses(['ROUTINE','URGENT','EMERGENCY']))+input('Preferred date/time (local, optional)','preferred_at','datetime-local','',false)+`<label>Doctor-reviewed clinical summary<textarea name="clinical_summary" required></textarea></label><p>${h?.is_registered?'Will request an outpatient appointment; hospital confirmation is required.':'External letter only. No hospital notification or appointment booking.'}</p>`,'Prepare referral');bind('visit-referral',async d=>{visitDraft.referrals.push({...d,hospital_id:h?.is_registered?h.id:null,specialty:d.specialty||'Not specified',preferred_at:d.preferred_at?new Date(d.preferred_at).toISOString():null});captureNote();renderNote()});}
 async function persistNote(){captureNote();const d=await api('workflow/consultations/'+visitCid+'/plan','PUT',{...visitDraft,revision:visitRevision});visitRevision=d.revision;return d}
 async function saveNote(){try{const d=await persistNote();$('visit-feedback').textContent='Draft saved. '+(d.warnings.join('; ')||'No allergy or duplicate-name warnings detected.');}catch(err){$('visit-feedback').textContent=err.message}}
 async function reviewNote(){try{const d=await persistNote();$('visit-editor').innerHTML=`<h3>Review check-up</h3><p>Observations: ${e(visitDraft.observations||'Not recorded')}</p><p>Assessment: ${e(visitDraft.assessment||'Not recorded')}</p><p>Advice: ${e(visitDraft.advice||'Not recorded')}</p>${decisionsReview(visitDraft)}<p class="hf-error">${e(d.warnings.join('; '))}</p><p>Warnings acknowledged: ${visitDraft.acknowledge_warnings?'Yes':'No'}</p><div id="visit-feedback" role="status"></div>${button('Back to draft','HF.renderNote()')}${button('Finalize check-up','HF.finalizeNote()','primary')}`;}catch(err){$('visit-feedback').textContent=err.message}}
 async function finalizeNote(){const buttons=$('visit-editor').querySelectorAll('button');buttons.forEach(b=>b.disabled=true);try{await api('workflow/consultations/'+visitCid,'PATCH',{status:'COMPLETED',reason:'Reviewed Doctor’s Note and connected decisions',observations:visitDraft.observations});$('hf-dialog').close();encounters=await api('workflow/consultations');await encounter(visitCid);showToast('Check-up finalized','success')}catch(err){$('visit-feedback').textContent=err.message;buttons.forEach(b=>b.disabled=false)}}
 async function completeVisit(cid){try{lastRecord=await api('workflow/consultations/'+cid+'/complete-record');dialog('Complete check-up record',`<div id="visit-print">${recordHTML(lastRecord)}</div>${button('Print / Save as PDF','HF.printVisit()')}${button('Download record','HF.downloadVisit()')}${(lastRecord.note.referrals||[]).map((r,i)=>!r.hospital_id?button('Print external referral letter: '+r.name,`HF.externalLetter(${i},false)`)+button('Download referral letter',`HF.externalLetter(${i},true)`):'').join('')}`)}catch(err){showToast(err.message,'emergency')}}
 function recordHTML(r){const v=r.visit,n=r.note;const lines=(rows,fn)=>rows.length?rows.map(fn).join(''):'<p>Not recorded.</p>';return `<h1>Check-up record</h1><p>${e(v.patient)} · ${date(v.date)}</p><p>${e(v.doctor||'Doctor not recorded')} · ${e(v.facility||'Facility not recorded')}</p><h2>Complaint & symptoms</h2><p>${e(v.complaint)} · ${e(v.symptoms||'Not recorded')}</p><p>Duration: ${e(v.duration||'Not recorded')} · Severity: ${e(v.severity)}</p><p>Warning symptoms: ${e((v.warning_symptoms||[]).join(', ')||'None recorded')}</p>${Object.entries(v.intake||{}).map(([k,val])=>`<p>${e(k.replaceAll('_',' '))}: ${e(val)}</p>`).join('')}<h2>Vitals</h2>${lines(r.vitals,x=>`<p>${e(x.name)}: ${e(x.value)} ${e(x.unit)}</p>`)}<h2>Assessment / diagnoses</h2><p>${e(n.assessment||'')}</p>${lines(r.diagnoses,x=>`<p>${e(x.name)} · ${e(x.status)}</p>`)}<h2>Finalized Doctor’s Note</h2><p>${e(n.observations||v.observations||'')}</p>${lines(r.legacy_notes,x=>`<p>${e(x.assessment)} · ${e(x.observations||'')} · ${e(x.advice||'')} · ${e(x.follow_up||'')}</p>${Object.entries(x.vitals||{}).map(([k,val])=>`<p>${e(k.replaceAll('_',' '))}: ${e(val)}</p>`).join('')}`)}<h2>Active medications at finalization</h2>${lines(n.active_medications||[],x=>`<p>${e(x.name)} · ${e(instructions(x))} · ${e(x.source==='PATIENT_REPORTED'?'Patient reported':'Clinician recorded')}</p>`)}<h2>Medication instructions & amendments</h2>${lines(n.changes||[],x=>`<p><strong>${e(x.action)}</strong><br>Previous: ${e(x.previous?x.previous.name+' · '+instructions(x.previous):'No medicine replaced')}<br>Revised: ${e(x.revised.name+' · '+instructions(x.revised))}<br>${e(x.reason||'')}</p>`)}${lines(r.prescriptions,x=>`<p>${e(x.medicines.map(m=>m.name+' · '+instructions(m)).join('; '))} · ${e(x.status==='INSTRUCTIONS_ONLY'?'Instructions only; no dispensing order':x.status.replaceAll('_',' '))}</p>`)}<h2>Referrals</h2>${lines(r.referrals,x=>`<p>${e(x.hospital_name)} · ${e(x.specialty)} · ${e(x.reason)} · ${e(x.status)}<br>${e(x.clinical_summary||'')}</p>`)}${(n.referrals||[]).filter(x=>!x.hospital_id).map(x=>`<section><h3>External referral letter: ${e(x.name)}</h3><p>${e(x.address)} · ${e(x.specialty)} · ${e(x.priority)}</p><p>${e(x.reason)}</p><p>${e(x.clinical_summary)}</p><p>No hospital notification or appointment booking occurred.</p></section>`).join('')}<h2>Appointments</h2>${lines(r.appointments,x=>`<p>${e(x.hospital_name)} · ${e(x.status==='REQUESTED'?'Appointment requested / Pending hospital confirmation':x.status)} · Preferred ${date(x.preferred_at)} · Scheduled ${date(x.scheduled_at)}<br>${e(x.response||'')}</p>`)}<h2>Tests & documents</h2>${lines(r.documents,x=>`<p>${e(x.category)} · ${e(x.title)}</p>`)}<h2>Advice & follow-up</h2><p>${e(n.advice||'')}</p>${lines(r.follow_up,x=>`<p>${date(x.due_at)} · ${e(x.reason)} · ${e(x.status)}</p>`)}`;}
 function printableHTML(){return '<!doctype html><html><head><meta charset="utf-8"><title>Check-up record</title><style>body{font:16px Arial;max-width:850px;margin:30px auto;padding:20px;line-height:1.5}h2{border-bottom:1px solid #ddd}p{white-space:pre-wrap}@media print{body{margin:0}}</style></head><body>'+recordHTML(lastRecord)+'</body></html>'}
 function printVisit(){const w=window.open('','_blank');if(!w){showToast('Allow pop-ups to print this record','info');return}w.document.write(printableHTML());w.document.close();w.focus();w.print()}
 function downloadVisit(){const a=document.createElement('a');const url=URL.createObjectURL(new Blob([printableHTML()],{type:'text/html'}));a.href=url;a.download='HealthFlow-check-up-'+lastRecord.visit.id+'.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
 async function outpatientPanel(){const aps=await api('workflow/outpatient-appointments');return '<h2>Outpatient appointment requests</h2>'+table(['Patient / hospital','Preferred time','Scheduled','Status','Action'],aps.map(a=>[e(a.patient_name)+'<small>'+e(a.hospital_name)+'</small>',date(a.preferred_at),date(a.scheduled_at),e(a.status==='REQUESTED'?'Appointment requested / Pending hospital confirmation':a.status),user.role==='HOSPITAL_ADMIN'?button('Confirm / reschedule / decline',`HF.respondAppointment('${a.id}','${a.consultation_id}')`):button('View complete check-up record',`HF.completeVisit('${a.consultation_id}')`)]));}
 async function respondAppointment(aid,cid){const r=await api('workflow/consultations/'+cid+'/complete-record');const a=r.appointments.find(x=>x.id===aid);dialog('Respond to outpatient request',form('visit-response',a.hospital_name,select('Decision','status',statuses(['CONFIRMED','RESCHEDULED','DECLINED']))+input('Date/time (local; required unless declined)','scheduled_at','datetime-local','',false)+input('Reason / message','reason'),'Send response'));bind('visit-response',async d=>{await api('workflow/outpatient-appointments/'+aid,'PATCH',{...d,scheduled_at:d.scheduled_at?new Date(d.scheduled_at).toISOString():null,revision:a.revision});$('hf-dialog').close();await go('appointments')});}


 function externalLetter(i,download){const r=lastRecord.note.referrals[i],v=lastRecord.visit;const content=`<h1>Hospital referral letter</h1><p>Patient: ${e(v.patient)} · Visit: ${date(v.date)}</p><p>Referring doctor: ${e(v.doctor)} · ${e(v.facility||'Facility not recorded')}</p><h2>${e(r.name)}</h2><p>${e(r.address)} · ${e(r.specialty)} · ${e(r.priority)}</p><p>Reason: ${e(r.reason)}</p><p>Clinical summary: ${e(r.clinical_summary)}</p><p>Preferred time: ${date(r.preferred_at)}</p><p>External hospital: no notification or appointment booking occurred.</p>`;const html='<!doctype html><meta charset="utf-8"><title>Referral letter</title><body style="font:16px Arial;margin:40px;line-height:1.6">'+content+'</body>';if(download){const url=URL.createObjectURL(new Blob([html],{type:'text/html'}));const a=document.createElement('a');a.href=url;a.download='HealthFlow-referral-letter.html';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}else{const w=window.open('','_blank');if(!w){showToast('Allow pop-ups to print','info');return}w.document.write(html);w.document.close();w.print();}}
 return {filterConsultationView,requestScannedAccess,checkScannedAccess,startScannedConsultation,externalLetter,doctorsNote,renderNote,decisionForm,generateMedRows,addMedRow,removeDecision,referralForm,searchVisitHospitals,chooseVisitHospital,saveNote,reviewNote,finalizeNote,completeVisit,printVisit,downloadVisit,respondAppointment,myQR,scanResult,scannedDoctor,mount,go,relatedRecord,emergencyAccess,filterHistory,resetHistory,linkedEncounter,encounter,recordDoc,printRecord,correctRecord,summarize,summaryHistory,approveSummary,versions,followIntake,currentSummary,dispense,medicationReview,stopMedication,advanceReferral,referralDetail,specialist,createSpecialist,patientHistory,discharge,bedStatus,invitation,download,documentError,loadFacilities,facility,locate,identityQR,revoke,read,restock,providerQR,pickLocation,admissionQR,insuranceQR,switchFamily,addFamilyModal,updateFamilyFields};
})();
