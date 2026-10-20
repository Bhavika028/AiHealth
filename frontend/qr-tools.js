/* Local QR decoding; never follow arbitrary URLs or send tokens to another origin. */
const QRTools=(()=>{
 let dialog,stream,frame,session=0,busy=false;
 const $=id=>document.getElementById(id);
 function status(text){if($('qr-status'))$('qr-status').textContent=text}
 function stop(){session++;if(frame)cancelAnimationFrame(frame);frame=null;stream?.getTracks().forEach(t=>t.stop());stream=null;const video=$('qr-video');if(video)video.srcObject=null}
 function close(){stop();if(dialog?.open)dialog.close()}
 async function accept(text){if(busy)return;busy=true;stop();status('QR recognized. Checking access…');try{const result=await HF.scanResult(text.trim());status(result||'QR recognized and processed.')}catch(err){status((/authorized|consent|permitted/i.test(err.message)?'Access not authorized. ':'')+err.message+' You can scan again or paste another code.')}finally{busy=false}}
 function decode(source){const canvas=document.createElement('canvas');const width=source.videoWidth||source.naturalWidth||source.width,height=source.videoHeight||source.naturalHeight||source.height;if(!width||!height)return null;const scale=Math.min(1,1600/Math.max(width,height));canvas.width=Math.round(width*scale);canvas.height=Math.round(height*scale);const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(source,0,0,canvas.width,canvas.height);const pixels=ctx.getImageData(0,0,canvas.width,canvas.height);return jsQR(pixels.data,canvas.width,canvas.height,{inversionAttempts:'attemptBoth'})?.data}
 async function start(){
  stop();const run=session;
  if(!window.isSecureContext){status('Camera access requires HTTPS or localhost. A phone accessing an HTTP LAN address cannot use the camera. Upload an image or paste QR text below.');return}
  if(!navigator.mediaDevices?.getUserMedia){status('Camera access is unavailable in this browser. Upload an image or paste QR text.');return}
  if(typeof jsQR!=='function'){status('Local QR decoder could not load. Reload the app or paste QR text.');return}
  status('Requesting camera access…');
  try{
   const id=$('qr-camera').value;
   const acquired=await navigator.mediaDevices.getUserMedia({video:id?{deviceId:{exact:id}}:{facingMode:{ideal:'environment'},width:{ideal:1920},height:{ideal:1080}},audio:false});
   if(run!==session||!dialog.open){acquired.getTracks().forEach(t=>t.stop());return}stream=acquired;
   const video=$('qr-video');video.srcObject=stream;await video.play();
   if(run!==session||!dialog.open){acquired.getTracks().forEach(t=>t.stop());return}
   const track=stream.getVideoTracks()[0],caps=track.getCapabilities?.();
   if(caps?.focusMode?.includes('continuous'))try{await track.applyConstraints({advanced:[{focusMode:'continuous'}]})}catch{}
   const devices=(await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='videoinput');
   const select=$('qr-camera');select.replaceChildren(new Option('Prefer rear camera',''));devices.forEach((d,i)=>select.add(new Option(d.label||'Camera '+(i+1),d.deviceId)));select.value=id;
   if(run!==session||!dialog.open)return;
   status('No QR detected yet. Keep the entire code and white margin in view; hold steady and avoid glare.');
   let last=0;
   const tick=()=>{if(run!==session||!stream)return;try{if(video.readyState<2){frame=requestAnimationFrame(tick);return}const now=performance.now();if(now-last<120){frame=requestAnimationFrame(tick);return}last=now;const text=decode(video);if(text){void accept(text);return}}catch(err){stop();status('Unable to decode camera frames. Try uploading an image.');return}frame=requestAnimationFrame(tick)};tick();
  }catch(err){if(run!==session)return;stop();status(({NotAllowedError:'Camera permission was denied. Allow camera access in your browser settings, then try again.',NotFoundError:'No camera was found.',NotReadableError:'The camera is busy or unavailable. Close other camera apps and try again.',OverconstrainedError:'That camera is unavailable. Select another camera.'})[err.name]||'Camera could not start. Upload an image or paste QR text instead.')}
 }
 function open(){
  close();if(!dialog){dialog=document.createElement('dialog');dialog.id='qr-scanner';dialog.setAttribute('aria-labelledby','qr-title');document.body.append(dialog);dialog.addEventListener('close',stop);dialog.addEventListener('cancel',stop)}
  dialog.innerHTML=`<h2 id="qr-title">Scan QR</h2><p>Scan a patient, provider, consent or emergency QR. Existing access permissions still apply.</p><video id="qr-video" autoplay muted playsinline aria-label="Camera preview"></video><div class="qr-actions"><select id="qr-camera" aria-label="Camera"><option value="">Prefer rear camera</option></select><button type="button" id="qr-start">Scan again / Start camera</button><button type="button" id="qr-stop">Stop camera</button></div><p id="qr-status" role="status" aria-live="polite">Choose camera scanning, upload an image, or paste QR text.</p><label>QR image<input id="qr-image" type="file" accept="image/*"></label><label>QR text or application URL<textarea id="qr-text" rows="3" spellcheck="false" autocomplete="off"></textarea></label><div class="qr-actions"><button type="button" id="qr-read">Read QR text</button><button type="button" id="qr-close">Close scanner</button></div>`;
  $('qr-start').onclick=start;$('qr-stop').onclick=()=>{stop();status('Camera stopped.')};$('qr-close').onclick=close;$('qr-camera').onchange=start;$('qr-read').onclick=()=>accept($('qr-text').value);
  $('qr-image').onchange=async ev=>{stop();const run=session;const file=ev.target.files[0];if(!file)return;status('Reading image…');const image=new Image(),url=URL.createObjectURL(file);try{image.src=url;await image.decode();if(run!==session||!dialog.open)return;const text=decode(image);if(!text)throw new Error('No QR detected. Try a clear image containing the full QR.');await accept(text)}catch(err){status(err.message)}finally{URL.revokeObjectURL(url)}};
  dialog.showModal();void start();
 }
 function addDownloads(root){root.querySelectorAll('img.hf-qr').forEach((img,i)=>{if(img.nextElementSibling?.classList.contains('qr-download'))return;const link=document.createElement('a');link.className='qr-download';link.href=img.src;link.download='PulseSync-QR-'+(i+1)+'.png';link.textContent='Download QR (PNG)';img.after(link)})}
 document.addEventListener('visibilitychange',()=>{if(document.hidden)stop()});window.addEventListener('pagehide',stop);
 // Changing portal pages or signing out also releases the camera.
 document.addEventListener('click',ev=>{if(ev.target.closest('.hf-sidebar button'))close()});
 return {open,close,stop,addDownloads};
})();
// Navigation/logout hooks use the window property; top-level const is not a window property.
window.QRTools=QRTools;
