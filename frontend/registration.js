/* Registration drafts live only in these DOM controls, never persistent storage. */
const Registration=(()=>{
 const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let form,panels=[],index=0,visited=new Set(),saving=false,role='',serial=0;
 const titles=()=>role==='PATIENT'?['Account details','Personal details','Medical background','Insurance','Security and review']:['Account details',role==='DOCTOR'?'Professional details':role==='PHARMACY'?'Store details':'Hospital details','Security and review'];
 function wrap(nodes){const d=document.createElement('section');d.className='registration-step';nodes.forEach(n=>d.append(n));return d;}
 function init(){form=$('auth-register-form');form.noValidate=true;form.querySelectorAll('.role-specific-section').forEach(n=>n.classList.add('registration-step'));
 const common=[...form.children];const account=wrap(common.slice(0,3));const location=common[3],address=common[4];
 const patient=$('role-fields-patient'),kids=[...patient.children];const personal=wrap(kids.slice(0,3)),medical=wrap(kids.slice(3,8)),insurance=wrap(kids.slice(8));
 personal.append(location);address.querySelector('input').id='reg-provider-address';
 // Separate patient address retains the existing city field and provider address.
 const patAddr=document.createElement('label');patAddr.innerHTML='Address (optional)<input class="form-control" id="reg-pat-address">';personal.append(patAddr);
 const providerLocation=wrap([address]);const locPlaceholder=document.createElement('div');providerLocation.append(locPlaceholder);
 const security=wrap([$('reg-pin').closest('.form-group')]);const review=document.createElement('div');review.id='registration-review';security.append(review);
 form.prepend(account,personal,medical,insurance,$('role-fields-doctor'),$('role-fields-hospital'),$('role-fields-pharmacy'),providerLocation,security);
 patient.remove();form.querySelectorAll('.form-section-title').forEach(n=>n.remove());
 $('reg-has-meds').innerHTML='<option value="">Choose Yes or No</option><option value="yes">Yes</option><option value="no">No</option>';$('reg-has-meds').required=true;$('reg-has-meds').parentElement.firstChild.textContent='Are you currently taking any medicines?';
 $('reg-has-meds').onchange=()=>{const yes=$('reg-has-meds').value==='yes';$('reg-med-block').hidden=!yes;if(yes&&!form.querySelector('.reg-med-row'))addMedicine();update();};
 $('reg-med-count').onchange=resizeMedicines;
 $('reg-med-block').querySelector('button').textContent='Update medicine count';
 const add=document.createElement('button');add.type='button';add.textContent='Add another medicine';add.onclick=()=>{addMedicine();update()};$('reg-med-block').append(add);
 const hint=document.createElement('p');hint.id='med-answer-hint';medical.append(hint);
 const top=document.createElement('div');top.id='registration-progress';form.prepend(top);
 const nav=document.createElement('div');nav.className='registration-actions';nav.innerHTML='<button type="button" id="registration-back">Back</button><button type="button" id="registration-next">Continue</button>';form.append(nav);nav.append($('register-submit-button'));
 const error=document.createElement('p');error.id='registration-error';error.setAttribute('role','alert');form.append(error);
 $('registration-back').onclick=()=>go(index-1);$('registration-next').onclick=()=>{if(validate(index,true)){visited.add(index);go(index+1)}};
 form.addEventListener('input',()=>{clearErrors();update()});form.addEventListener('change',update);
 form.querySelectorAll('input,select').forEach(i=>{if(!i.id)i.id='reg-field-'+(++serial);const l=i.closest('label')||i.parentElement.querySelector('label');if(l&&!i.closest('label'))l.htmlFor=i.id;});
 $('reg-pin').required=$('reg-confirm-pin').required=true;
 form.querySelectorAll('.form-group').forEach(g=>{const f=g.querySelector('input,select');if(f&&!f.required)g.querySelectorAll('.req').forEach(n=>n.remove());});
 $('reg-pat-has-insurance').setAttribute('aria-label','Active health insurance');
 form._parts={account,personal,medical,insurance,providerLocation,security,location,locPlaceholder};
 roleChanged();
 }
 function roleChanged(){if(!form)return;role=selectedAuthRole;index=0;visited.clear();const p=form._parts;p.providerLocation.hidden=role==='PATIENT';panels=role==='PATIENT'?[p.account,p.personal,p.medical,p.insurance,p.security]:[p.account,$(role==='DOCTOR'?'role-fields-doctor':role==='PHARMACY'?'role-fields-pharmacy':'role-fields-hospital'),p.security];
 if(role==='PATIENT')p.personal.append(p.location);else {panels[1].append(p.providerLocation);p.providerLocation.append(p.location)}
 render();}
 function fields(i){return [...panels[i].querySelectorAll('input,select,textarea')].filter(f=>!(f.closest('#reg-med-block')&&$('reg-has-meds').value!=='yes')&&!(f.closest('#patient-insurance-details-block')&&!$('reg-pat-has-insurance').checked));}
 function message(f){f.setCustomValidity('');if(f.id==='reg-confirm-password'&&f.value!==$('reg-password').value)return 'Passwords do not match.';if(f.id==='reg-confirm-pin'&&f.value!==$('reg-pin').value)return 'PINs do not match.';if(f.id==='reg-pin'&&!/^\d{6}$/.test(f.value))return 'Enter exactly six digits.';if(['reg-lat','reg-lng'].includes(f.id)&&!!$('reg-lat').value!==!!$('reg-lng').value)return 'Enter both coordinates or leave both blank.';if(f.required&&!f.value.trim())return 'Complete this field.';if(!f.checkValidity())return f.validationMessage;return '';}
 function validate(i,show=false){let first=null;if(role==='PATIENT'&&i===2&&$('reg-has-meds').value==='yes'&&!form.querySelector('.reg-med-row')){if(show){failure('Add at least one medicine.');$('reg-med-count').focus();}return false;}fields(i).forEach(f=>{const msg=message(f);if(msg){first ||= f;if(show){f.setAttribute('aria-invalid','true');const e=document.createElement('small');e.className='registration-field-error';e.id=f.id+'-error';e.textContent=msg;f.after(e);f.setAttribute('aria-describedby',e.id)}}});if(first&&show)first.focus();return !first;}
 function clearErrors(){form.querySelectorAll('.registration-field-error').forEach(n=>n.remove());form.querySelectorAll('[aria-invalid]').forEach(n=>{n.removeAttribute('aria-invalid');n.removeAttribute('aria-describedby')});$('registration-error').textContent='';}
 function go(i){clearErrors();index=Math.max(0,Math.min(panels.length-1,i));render();$('registration-heading').focus();}
 function render(){const p=form._parts;[p.account,p.personal,p.medical,p.insurance,p.security,$('role-fields-doctor'),$('role-fields-hospital'),$('role-fields-pharmacy')].forEach(n=>{n.hidden=true;n.style.display='none'});panels[index].hidden=false;panels[index].style.display='block';$('registration-back').hidden=index===0;$('registration-next').hidden=index===panels.length-1;$('register-submit-button').hidden=index!==panels.length-1;$('register-submit-text').textContent='Create account';if(index===panels.length-1)review();update();}
 function update(){if(!form)return;if(index===panels.length-1)review();const complete=[...visited].filter(i=>validate(i)).length,percent=Math.min(99,Math.floor(complete/panels.length*100));const required=fields(index).filter(f=>f.required),done=required.filter(f=>!message(f)).length;
 $('registration-progress').innerHTML=`<p aria-live="polite">Step ${index+1} of ${panels.length} · ${percent}% complete</p><h2 id="registration-heading" tabindex="-1">${titles()[index]}</h2><progress max="100" value="${percent}" aria-label="Validated registration progress"></progress><nav aria-label="Registration steps">${titles().map((t,i)=>`<button type="button" data-step="${i}" ${i>index&&!visited.has(i)?'disabled':''} ${i===index?'aria-current="step"':''}>${visited.has(i)&&validate(i)?'✓ ':''}${i+1}. ${esc(t)}</button>`).join('')}</nav><p role="status">${done} of ${required.length} required fields completed</p>`;
 $('registration-progress').querySelectorAll('button').forEach(b=>b.onclick=()=>go(Number(b.dataset.step)));
 $('med-answer-hint').textContent=$('reg-has-meds').value==='no'?'No active medicines will be submitted. Previously entered cards remain available if you switch to Yes.':$('reg-has-meds').value==='yes'?'These medicines will be saved as patient-reported, not as prescriptions or dispensing orders.':'Choose Yes or No before continuing.';
 const names=new Map();form.querySelectorAll('.reg-med-row').forEach(row=>{const name=row.querySelector('[name=med-name]').value.trim().toLowerCase();const warning=row.querySelector('.med-duplicate');warning.textContent=name&&names.has(name)?'Duplicate medicine name: review this entry.':'';names.set(name,true)});
 }
 function addMedicine(){const row=document.createElement('fieldset');row.className='reg-med-row';row.innerHTML='<legend></legend>'+[['name','Medicine name',true],['disease','Disease / reason',true],['times','Times per day',true],['dosage','Strength / dose (optional)',false],['instructions','Additional instructions (optional)',false]].map(([n,l,r])=>`<label>${l}<input id="reg-med-${++serial}" name="med-${n}" ${r?'required':''} ${n==='times'?'type="number" min="1" max="24" step="1"':''}></label>`).join('')+'<label>Food instructions<select name="med-food"><option>Not specified</option><option>Before food</option><option>After food</option></select></label><small class="med-duplicate" role="status"></small><button type="button">Remove medicine</button>';
 row.querySelector('button').onclick=()=>{row.remove();renumber();update()};$('reg-med-rows').append(row);renumber();}
 function renumber(){const rows=[...form.querySelectorAll('.reg-med-row')];rows.forEach((r,i)=>r.querySelector('legend').textContent='Medicine '+(i+1));$('reg-med-count').value=rows.length;}
 function resizeMedicines(){const n=Number($('reg-med-count').value);if(!Number.isInteger(n)||n<1||n>50){$('reg-med-count').reportValidity();return}const rows=[...form.querySelectorAll('.reg-med-row')];if(n<rows.length){$('reg-med-count').value=rows.length;$('med-answer-hint').textContent='Use Remove medicine on individual cards to reduce the count without losing other entries.';return}while(form.querySelectorAll('.reg-med-row').length<n)addMedicine();update();}
 function medicines(){if($('reg-has-meds').value==='no')return [];const rows=[...form.querySelectorAll('.reg-med-row')];if(!rows.length)throw Error('Add at least one medicine.');return rows.map(row=>{const v=n=>row.querySelector(`[name="med-${n}"]`).value.trim();return {name:v('name'),disease:v('disease'),times_per_day:Number(v('times')),frequency:v('times')+' times per day',food:v('food'),dosage:v('dosage'),additional_instructions:v('instructions')}});}
 function labelText(f){const l=(f.closest('label')||form.querySelector(`label[for="${f.id}"]`))?.cloneNode(true);if(!l)return f.getAttribute('aria-label')||f.id;l.querySelectorAll('input,select,textarea,button').forEach(n=>n.remove());return l.textContent.trim();}
 function review(){$('registration-review').innerHTML=panels.slice(0,-1).map((p,i)=>`<section><h3>${titles()[i]} <button type="button" data-edit="${i}">Edit</button></h3><dl>${fields(i).filter(f=>!f.closest('.reg-med-row')&&f.type!=='password').map(f=>`<dt>${esc(labelText(f))}</dt><dd>${esc(f.type==='checkbox'?(f.checked?'Yes':'No'):f.tagName==='SELECT'?f.selectedOptions[0]?.textContent||'Not provided':f.value||'Not provided')}</dd>`).join('')}</dl>${i===0?'<p>Password: '+($('reg-password').value?'Completed':'Not completed')+'</p>':''}${role==='PATIENT'&&i===2&&$('reg-has-meds').value?medicines().map((m,j)=>`<p>Medicine ${j+1}: ${esc(m.name)} · ${esc(m.disease)} · ${m.times_per_day} times per day · ${esc(m.food)} · ${esc(m.dosage)} · ${esc(m.additional_instructions)}</p>`).join(''):''}</section>`).join('')+'<p>PIN: '+(/^\d{6}$/.test($('reg-pin').value)&&$('reg-pin').value===$('reg-confirm-pin').value?'Completed':'Not completed')+' (values hidden)</p>';$('registration-review').querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>go(Number(b.dataset.edit)));}
 function beforeSubmit(){if(saving)return false;if(index!==panels.length-1){$('registration-next').click();return false}clearErrors();for(let i=0;i<panels.length;i++){if(!validate(i)){go(i);validate(i,true);return false}}saving=true;form.querySelectorAll('button').forEach(b=>b.disabled=true);return true;}
 function settled(){saving=false;form.querySelectorAll('button').forEach(b=>b.disabled=false);update();}
 function success(){$('registration-progress').querySelector('progress').value=100;visited.clear();$('reg-med-rows').replaceChildren();index=0;}
 function failure(msg){$('registration-error').textContent=msg;}
 document.addEventListener('DOMContentLoaded',init);
 return {roleChanged,beforeSubmit,settled,success,failure,medicines,resizeMedicines};
})();

window.Registration = Registration;
