/* Role dashboards compose existing authorized APIs; no synthetic clinical values. */
const HFDashboard = (() => {
 async function render(c){
 const {user,api,e,date,tag,button,empty,table,head,timeline,providers,medTable,rxTable,refActions}=c;
 const link=(label,page,style='')=>button(label,`HF.go('${page}')`,style);
 const metric=(value,label,page,note='')=>`<button class="hf-metric" onclick="HF.go('${page}')"><span>${e(label)}</span><strong>${e(value)}</strong><small>${e(note||'Open records')} →</small></button>`;
 const panel=(title,body,page,span=8)=>`<section class="hf-panel hf-col-${span}"><div class="hf-panel-head"><h2>${e(title)}</h2>${page?link('View all',page,'text-action'):''}<button class="hf-panel-toggle" aria-label="Toggle ${e(title)}" aria-expanded="true" onclick="HUI.togglePanel(this)">−</button></div><div class="hf-panel-content">${body}</div></section>`;
 const list=(rows,fn,msg)=>rows.length?`<div class="hf-activity-list">${rows.map(fn).join('')}</div>`:empty(msg);
 const active=r=>!['COMPLETED','CANCELLED','DECLINED'].includes(r.status);
 const states=(rows,key,page)=>{const groups={};rows.forEach(x=>groups[x[key]]=(groups[x[key]]||0)+1);return rows.length?`<div class="hf-state-bars">${Object.entries(groups).map(([s,n])=>`<button onclick="HF.go('${page}')"><span>${tag(s)} <strong>${n}</strong></span><meter min="0" max="${rows.length}" value="${n}">${n} of ${rows.length}</meter></button>`).join('')}</div>`:empty('Activity will appear as records are added.')};
 const n=await api('workflow/notifications');const unread=n.filter(x=>x.status==='UNREAD');
 const notification=document.querySelector('.hf-notification');if(notification)notification.textContent='Notifications'+(unread.length?' ('+unread.length+')':'');
 const updates=()=>panel('Care updates',list(unread.slice(0,4),x=>`<button class="hf-list-action" onclick="HF.go('notifications')"><strong>${e(x.message)}</strong><small>${date(x.created_at)}</small></button>`,'You are up to date.'),'notifications',4);
 const today=new Date().toLocaleDateString('en-IN',{dateStyle:'full'});
 let html='';
 if(user.role==='PATIENT'){
  // History normalizes legacy medication records; load it before dependent lists.
  const hist=await api('workflow/history/'+user.patient_id);
  const [m,f,r,rx,v,docs]=await Promise.all([api('workflow/medications/'+user.patient_id),api('workflow/follow-ups'),api('workflow/referrals'),api('workflow/prescriptions'),api('workflow/vitals/'+user.patient_id),api('workflow/documents/'+user.patient_id)]);
  const scheduled=f.filter(x=>x.status==='SCHEDULED'),pending=r.filter(active),am=m.filter(x=>x.status==='ACTIVE'),p=hist.patient;
  const severe=(p.allergies||[]).join(', ');const allergies=await api('workflow/allergies/'+user.patient_id);const warnings=allergies.records.filter(x=>x.status==='ACTIVE'&&x.severity==='SEVERE');
  html=head('Hello, '+user.name.split(' ')[0],today,button('Emergency QR','HF.emergencyAccess()')+link('Find nearby care','nearby')+link('Start consultation','appointments','primary'))+
   `<div class="hf-summary-strip">${metric(am.length,'Active medicines','medications')}${metric(scheduled.length,'Scheduled follow-ups','appointments')}${metric(pending.length,'Active referrals','referrals')}${metric(unread.length,'Unread updates','notifications')}</div>`+
   (severe||warnings.length?`<div class="hf-clinical-alert"><strong>Allergy information</strong><p>${e(severe)} ${e(warnings.map(x=>x.substance+' · SEVERE · '+x.reaction).join('; '))}</p>${link('Review allergy records','profile','text-action')}</div>`:'')+
   `<div class="hf-dashboard-grid">`+
   panel('Next follow-up',scheduled.length?`<div class="hf-next"><div class="hf-date-block">${e(new Date(scheduled[0].due_at+'Z').toLocaleDateString('en-IN',{day:'numeric',month:'short'}))}</div><div><h3>${e(scheduled[0].reason)}</h3><p>${date(scheduled[0].due_at)}</p>${tag(scheduled[0].status)}</div>${link('Continue','appointments','primary')}</div>`:empty('No follow-up scheduled. Start a consultation when you need care.'),'appointments',8)+
   panel('Profile confirmation',`<p>${hist.last_verified_at?'Last confirmed '+date(hist.last_verified_at):'Your profile has not been confirmed.'}</p><p class="hf-muted">Keep allergies, emergency contact and chronic conditions current.</p>${link('Review profile','profile')}`,'profile',4)+
   panel('Active medications',medTable(am.slice(0,5)),'medications',8)+updates()+
   panel('Your care timeline',timeline(hist.events,6)+link('Explore complete history','history'),'history',8)+
   panel('Referrals in progress',list(pending.slice(0,4),x=>`<button class="hf-list-action" onclick="HF.go('referrals')"><strong>${e(x.hospital_name)}</strong><span>${e(x.specialty)}</span>${tag(x.status)}</button>`,'No active referrals.'),'referrals',4)+
   panel('Recent measurements',HUI.vitals(v,{e,date,empty})+list(v.slice(0,3),x=>`<div class="hf-measurement"><strong>${e(x.name)} ${e(x.value)} ${e(x.unit)}</strong><small>${date(x.measured_at)}</small></div>`,'No finalized measurements recorded.'),'history',8)+
   panel('Latest prescription',rx.length?`<h3>${e(rx[0].doctor_name||'Care team')}</h3><p>${e(rx[0].medicines.map(x=>x.name).join(', '))}</p><p>Dispensing: ${tag(rx[0].status)}</p>${link('Open prescription','medications')}`:empty('No prescription recorded.'),'medications',4)+
   panel('Recent documents',list(docs.slice(0,3),x=>`<button class="hf-list-action" onclick="HF.download('${e(x.id)}')"><strong>${e(x.title)}</strong><small>${e(x.category)} · ${date(x.created_at)}</small><span>Download →</span></button>`,'Upload previous medical records to keep them together.'),'documents',8)+
   panel('Registered care',list(providers.filter(x=>x.role==='HOSPITAL_ADMIN').slice(0,3),x=>`<button class="hf-list-action" onclick="HF.go('nearby')"><strong>${e(x.name)}</strong><span>View location and availability →</span></button>`,'No registered hospitals yet.')+link('Search nearby facilities','nearby'),'nearby',4)+
   panel('Manage your care',`<div class="hf-quick-actions">${link('Medical history','history')}${link('Documents','documents')}${link('Consent & QR','consent')}${link('Profile settings','profile')}${link('Record access log','audit')}</div>`,'',12)+'</div>';
 }else if(user.role==='DOCTOR'){
  const [rows,f,r,pts]=await Promise.all([api('workflow/consultations'),api('workflow/follow-ups'),api('workflow/referrals'),api('workflow/patients')]);c.setEncounters(rows);c.setRefs(r);
  const queue=rows.filter(active).sort((a,b)=>(b.symptom_severity==='Severe')-(a.symptom_severity==='Severe')||a.created_at.localeCompare(b.created_at));const urgent=queue.filter(x=>x.is_urgent||x.symptom_severity==='Severe'||x.warning_symptoms?.length);const inProgress=rows.filter(x=>x.status==='IN_PROGRESS');const age=id=>pts.find(x=>x.id===id)?.age??'Not recorded';
  html=head('Clinical overview',today,link('All consultations','consultations')+(queue.length?button('Open next patient',`HF.encounter('${queue[0].id}')`,'primary'):link('Review patients','patients','primary')))+
  `<div class="hf-summary-strip">${metric(queue.length,'Open queue','queue')}${metric(urgent.length,'Needs urgent review','queue','Recorded severity / warnings')}${metric(inProgress.length,'In consultation','queue')}${metric(f.filter(x=>x.status==='SCHEDULED').length,'Scheduled follow-ups','appointments')}</div><div class="hf-dashboard-grid">`+
  panel('Patient queue',table(['Patient / age','Complaint','Urgency','Arrival','Status','Action'],queue.map(x=>[e(x.patient_name)+`<small>${e(age(x.patient_id))} years</small>`,e(x.chief_complaint),tag(x.symptom_severity||'NOT_RECORDED'),date(x.created_at),tag(x.status),button('Open workspace',`HF.encounter('${x.id}')`)])),'queue',8)+
  panel('Active consultation',list(inProgress,x=>`<button class="hf-list-action" onclick="HF.encounter('${x.id}')"><strong>${e(x.patient_name)}</strong><span>${e(x.chief_complaint)}</span><small>Continue notes, vitals, prescription or referral →</small></button>`,'No consultation currently in progress.'),'queue',4)+
  panel('Urgent review',list(urgent,x=>`<button class="hf-list-action" onclick="HF.encounter('${x.id}')"><strong>${e(x.patient_name)}</strong><span>${e((x.warning_symptoms||[]).join(', ')||x.chief_complaint)}</span>${tag('URGENT')}</button>`,'No recorded urgent cases.'),'queue',8)+
  panel('Consultation states',states(rows,'status','consultations'),'consultations',4)+
  panel('Recently completed',table(['Patient','Complaint','Recorded','Action'],rows.filter(x=>x.status==='COMPLETED').slice(0,5).map(x=>[e(x.patient_name),e(x.chief_complaint),date(x.updated_at||x.created_at),button('Review',`HF.encounter('${x.id}')`)])),'consultations',8)+updates()+
  panel('Follow-up schedule',list(f.filter(x=>x.status==='SCHEDULED').slice(0,5),x=>`<button class="hf-list-action" onclick="HF.go('appointments')"><strong>${e(x.reason)}</strong><small>${date(x.due_at)}</small></button>`,'No scheduled follow-ups.'),'appointments',8)+
  panel('Referral activity',states(r,'status','referrals'),'referrals',4)+'</div>';
 }else if(user.role==='HOSPITAL_ADMIN'){
  const [r,a,b,rows]=await Promise.all([api('workflow/referrals'),api('workflow/admissions'),api('workflow/beds'),api('workflow/consultations')]);c.setEncounters(rows);c.setRefs(r);const incoming=r.filter(active),admitted=a.filter(x=>x.status==='ADMITTED'),ds=providers.filter(x=>x.role==='DOCTOR'&&x.hospital_id===user.hospital_id);const wards=[...new Set(b.map(x=>x.ward_name))];
  html=head(user.hospital_name||'Hospital operations',today,link('Manage beds','beds')+link('Allocate a bed','admissions','primary'))+`<div class="hf-summary-strip">${metric(incoming.length,'Open referrals','referrals')}${metric(admitted.length,'Active admissions','admissions')}${metric(b.filter(x=>x.state==='AVAILABLE').length,'Available beds','beds',b.length+' total beds')}${metric(ds.length,'Affiliated clinicians','doctors')}</div><div class="hf-dashboard-grid">`+
  panel('Incoming referrals',table(['Patient','Specialty','Priority','State','Action'],incoming.map(x=>[e(x.patient_name),e(x.specialty),tag(x.priority),tag(x.status),refActions(x)])),'referrals',8)+
  panel('Bed states',states(b,'state','beds'),'beds',4)+
  panel('Active admissions',table(['Patient','Admitted','Status','Action'],admitted.map(x=>[e(x.patient_name),date(x.created_at),tag(x.status),button('Open admission',`HFDashboard.admission('${e(x.id)}')`)])),'admissions',8)+
  panel('Ward occupancy',wards.length?wards.map(w=>{const beds=b.filter(x=>x.ward_name===w),used=beds.filter(x=>x.state==='OCCUPIED').length;return `<button class="hf-ward" onclick="HF.go('beds')"><strong>${e(w)}</strong><span>${used} / ${beds.length} occupied</span><meter min="0" max="${beds.length}" value="${used}">${used}/${beds.length}</meter></button>`}).join(''):empty('Add a bed to start managing ward capacity.'),'beds',4)+
  panel('Specialist encounters',table(['Patient','Clinician','Status','Action'],rows.slice(0,5).map(x=>[e(x.patient_name),e(x.doctor_name||'Unassigned'),tag(x.status),button('Open',`HF.encounter('${x.id}')`)])),'consultations',8)+
  panel('Referral pipeline',states(r,'status','referrals'),'referrals',4)+
  panel('Recent discharges',table(['Patient','Discharged','Summary'],a.filter(x=>x.status==='DISCHARGED').slice(0,5).map(x=>[e(x.patient_name),date(x.discharged_at),e(x.discharge_summary)])),'admissions',8)+
  panel('Urgent referrals / arrivals',list(incoming.filter(x=>x.priority!=='ROUTINE'),x=>`<button class="hf-list-action" onclick="HF.referralDetail('${x.id}')"><strong>${e(x.patient_name)}</strong>${tag(x.priority)}<span>${e(x.specialty)}</span></button>`,'No urgent referrals.'),'referrals',4)+
  panel('Hospital clinicians',table(['Clinician','Action'],ds.map(x=>[e(x.name),link('View affiliation','doctors')])),'doctors',8)+updates()+'</div>';
  HFDashboard.admissions=a;
 }else{
  const [rx,data]=await Promise.all([api('workflow/prescriptions'),api('clinical/pharmacy/inventory')]);const inventory=data.inventory,pending=rx.filter(x=>x.status==='PENDING'),dispensed=rx.filter(x=>x.status==='DISPENSED'),low=inventory.filter(x=>x.is_low_stock&&x.stock_quantity>0),out=inventory.filter(x=>x.stock_quantity===0);
  html=head(user.store_name||'Pharmacy operations',today,link('Add medicine / restock','inventory')+link('Process prescriptions','prescriptions','primary'))+`<div class="hf-summary-strip">${metric(pending.length,'Awaiting dispensing','prescriptions')}${metric(dispensed.length,'Dispensed prescriptions','dispensing')}${metric(low.length,'Low stock medicines','inventory')}${metric(out.length,'Out of stock','inventory')}</div><div class="hf-dashboard-grid">`+
  panel('Waiting for dispensing',rxTable(pending),'prescriptions',8)+
  panel('Inventory attention',table(['Medicine','Stock','Action'],[...out,...low].map(x=>[e(x.medicine_name),tag(x.stock_quantity===0?'OUT_OF_STOCK':'LOW_STOCK')+`<small>${x.stock_quantity} remaining</small>`,button('Restock',`HF.restock('${x.id}')`)])),'inventory',4)+
  panel('Recent dispensing',rxTable(dispensed.slice(0,5)),'dispensing',8)+
  panel('Inventory summary',states(inventory.map(x=>({status:x.stock_quantity===0?'OUT_OF_STOCK':x.is_low_stock?'LOW_STOCK':'IN_STOCK'})),'status','inventory'),'inventory',4)+
  panel('Prescription states',states(rx,'status','prescriptions'),'prescriptions',8)+updates()+'</div>';
 }
 document.getElementById('hf-content').innerHTML=html;
 }
 async function admission(id){const a=HFDashboard.admissions.find(x=>x.id===id);const box=document.getElementById('hf-dialog-content');box.textContent='';const h=document.createElement('h2');h.textContent=a.patient_name;box.append(h);for(const [label,value] of [['Admitted',a.created_at],['Reason',a.reason],['Bed',a.bed_id],['Status',a.status]]){const p=document.createElement('p');p.textContent=label+': '+(value||'Not recorded');box.append(p)}const btn=document.createElement('button');btn.textContent='Manage admission';btn.onclick=()=>{document.getElementById('hf-dialog').close();HF.go('admissions')};box.append(btn);document.getElementById('hf-dialog').showModal()}
 return {render,admission};
})();
