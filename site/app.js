'use strict';
let PLATES = {}, editor = null, selectedPhoto = null;

const $ = id => document.getElementById(id);
const svgNS = 'http://www.w3.org/2000/svg';
function svgElement(tag, attrs = {}) {
  const el = document.createElementNS(svgNS, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
  return el;
}
function openState(code) {
  const entry = PLATES[code];
  if (!entry) { if (editor) openUpload(code); return; }
  const name = STATES.find(state => state[0] === code)[1];
  $('dialog-title').textContent = name;
  $('dialog-code').textContent = `${code} · COLLECTED`;
  const img = document.createElement('img');
  img.src = entry.url; img.alt = `${name} license plate photo`;
  $('photo-stage').replaceChildren(img);
  $('dialog-status').textContent = 'A little piece of Joleen’s journey.';
  selectedPhoto = code;
  $('replace-photo').hidden = !editor;
  $('photo-dialog').showModal();
}
$('close-dialog').onclick = () => $('photo-dialog').close();
$('photo-dialog').addEventListener('click', event => {
  if (event.target !== $('photo-dialog')) return;
  const r = event.target.getBoundingClientRect();
  if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.target.close();
});
function renderCollection() {
$('grid').replaceChildren();
for (const [index, [code, name]] of STATES.entries()) {
  const entry = PLATES[code];
  const card = document.createElement(entry || editor ? 'button' : 'div');
  card.className = 'state-card' + (entry ? ' collected' : '');
  card.setAttribute('aria-label', `${name}, ${entry ? 'collected. View photo' : 'not collected'}`);
  if (entry || editor) card.onclick = () => openState(code);
  const plate = document.createElement('div'); plate.className = 'plate';
  if (entry) {
    const img = document.createElement('img'); img.src = entry.url;
    img.alt = `${name} license plate`; img.loading = 'lazy'; PlateCrop.apply(img, entry.crop); plate.append(img);
    const badge = document.createElement('span'); badge.className = 'check-badge';
    badge.textContent = '✓'; plate.append(badge);
  } else {
    const abbr = document.createElement('span'); abbr.className = 'plate-abbr';
    abbr.textContent = code; plate.append(abbr);
  }
  const label = document.createElement('div'); label.className = 'card-label';
  const stateName = document.createElement('span'); stateName.className = 'state-name'; stateName.textContent = name;
  const number = document.createElement('span'); number.className = 'state-number'; number.textContent = String(index + 1).padStart(2, '0');
  label.append(stateName, number); card.append(plate, label); $('grid').append(card);
}
const count = Object.keys(PLATES).length;
$('count').textContent = count;
$('percent').textContent = `${count * 2}%`;
$('progress-fill').style.width = `${count * 2}%`;
document.querySelector('[role=progressbar]').setAttribute('aria-valuenow', count);
$('progress-caption').textContent = count === 50 ? 'All fifty. What a collection.' : `${50 - count} states still out there. The adventure continues.`;

if (mapLoaded) loadMap();
}
let mapLoaded = false;
function setView(view) {
  const map = view === 'map';
  $('grid').hidden = map; $('map-view').hidden = !map;
  $('grid-toggle').setAttribute('aria-pressed', !map); $('map-toggle').setAttribute('aria-pressed', map);
  $('view-caption').textContent = map ? 'JOLEEN’S FINDS, COAST TO COAST' : 'ALL 50 STATES · A–Z';
  if (map && !mapLoaded) { loadMap(); mapLoaded = true; }
}
$('grid-toggle').onclick = () => setView('grid');
$('map-toggle').onclick = () => setView('map');
function loadMap() {
  const decoded = TOPOLOGY.arcs.map(arc => {
    let x = 0, y = 0;
    return arc.map(([dx, dy]) => {
      x += dx; y += dy;
      return [x * TOPOLOGY.transform.scale[0] + TOPOLOGY.transform.translate[0], y * TOPOLOGY.transform.scale[1] + TOPOLOGY.transform.translate[1]];
    });
  });
  const ringPath = ring => {
    const points = ring.flatMap(index => index < 0 ? [...decoded[~index]].reverse() : decoded[index]);
    return points.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`).join('') + 'Z';
  };
  const svg = svgElement('svg', {viewBox: '0 0 975 610', role: 'group', 'aria-label': 'Interactive map of the fifty US states'});
  for (const geometry of TOPOLOGY.objects.states.geometries) {
    const state = STATES.find(state => Number(state[2]) === Number(geometry.id));
    if (!state) continue;
    const [code, name] = state, collected = !!PLATES[code], interactive = collected || !!editor;
    const polygons = geometry.type === 'Polygon' ? [geometry.arcs] : geometry.arcs;
    const path = svgElement('path', {
      d: polygons.flatMap(poly => poly.map(ringPath)).join(''),
      class: 'map-state' + (collected ? ' collected' : ''),
      role: interactive ? 'button' : 'img', 'data-state': code,
      'aria-label': `${name}, ${collected ? 'collected, view photo' : 'not collected'}`
    });
    const title = svgElement('title'); title.textContent = name; path.append(title);
    const hint = () => $('map-hint').textContent = `${name} · ${collected ? 'Collected — view photo' : 'Still looking'}`;
    path.addEventListener('mouseenter', hint);
    if (interactive) {
      path.setAttribute('tabindex', '0');
      path.addEventListener('click', () => openState(code)); path.addEventListener('focus', hint);
      path.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openState(code); }
      });
    }
    svg.append(path);
  }
  $('map-container').replaceChildren(svg);
  const small = ['CT', 'DE', 'MD', 'MA', 'NH', 'NJ', 'RI', 'VT'];
  for (const path of svg.querySelectorAll('path')) {
    const code = path.dataset.state;
    if (small.includes(code)) continue;
    const box = path.getBBox();
    const label = svgElement('text', {x: box.x + box.width / 2, y: box.y + box.height / 2 + 4, class: 'map-label' + (PLATES[code] ? ' collected' : ''), 'aria-hidden': 'true'});
    label.textContent = code; svg.append(label);
  }
  $('small-states').replaceChildren();
  for (const [code, name] of STATES.filter(state => small.includes(state[0]))) {
    const button = document.createElement('button'); button.textContent = name;
    button.classList.toggle('collected', !!PLATES[code]); button.disabled = !PLATES[code] && !editor;
    button.setAttribute('aria-label', `${name}, ${PLATES[code] ? 'collected, view photo' : 'not collected'}`);
    if (PLATES[code] || editor) button.onclick = () => openState(code);
    $('small-states').append(button);
  }
}

let cropEditor = null;
let envelope = null, uploadBlob = null, previewUrl = null, busy = false, idleTimer, publishTimer;
const pendingKey = 'joleen-pending-publication-v1';
const apiRoot = 'https://api.github.com/repos/manuelbrack/license-plate-tracker';
function message(id, text) { $(id).textContent = text; $(id).hidden = !text; }
function banner(text, kind = '') { $('publish-banner').textContent = text; $('publish-banner').dataset.kind = kind; $('publish-banner').hidden = !text; }
function setBusy(value) {
  busy = value;
  for (const id of ['save-photo','choose-photo','upload-state','cancel-upload','lock-editor','crop-zoom','crop-x','crop-y','crop-reset']) $(id).disabled = value;
}
async function jsonFetch(url) {
  const response = await fetch(url, {cache:'no-store', signal:AbortSignal.timeout(20000)});
  if (!response.ok) throw new Error('The collection could not be loaded. Please try again.');
  return response.json();
}
function refreshEditor() {
  $('unlock-editor').hidden = !!editor || !envelope;
  $('editor-controls').hidden = !editor;
  document.body.classList.toggle('editing', !!editor);
  renderCollection();
}
function keepUnlocked() {
  clearTimeout(idleTimer);
  if (editor) idleTimer = setTimeout(() => { if (busy) keepUnlocked(); else lockEditor(); }, 15 * 60 * 1000);
}
function lockEditor() {
  if (busy) return;
  editor = null; clearTimeout(idleTimer);
  $('unlock-passphrase').value = '';
  $('replace-photo').hidden = true;
  clearUpload(); $('upload-dialog').close(); refreshEditor();
}
for (const event of ['pointerdown','keydown']) document.addEventListener(event, keepUnlocked, {passive:true});
$('lock-editor').onclick = lockEditor;
$('unlock-editor').onclick = () => {
  message('unlock-error',''); $('unlock-dialog').showModal(); $('unlock-passphrase').focus();
};
$('cancel-unlock').onclick = () => {$('unlock-passphrase').value='';$('unlock-dialog').close();};
$('unlock-dialog').addEventListener('cancel', event => {if($('submit-unlock').disabled)event.preventDefault();});
$('unlock-dialog').addEventListener('close', () => $('unlock-passphrase').value='');
$('unlock-form').onsubmit = async event => {
  event.preventDefault();
  const button = $('submit-unlock'); button.disabled = true; $('cancel-unlock').disabled=true; button.textContent='Unlocking…';
  message('unlock-error','');
  try {
    const token = await PlateGitHub.decryptToken(envelope, $('unlock-passphrase').value);
    $('unlock-passphrase').value='';
    const candidate = PlateGitHub.createClient(token);
    await candidate.validate();
    const latest = await candidate.readCollection();
    editor = candidate; PLATES = latest.manifest.plates;
    // Newly committed photos may not be live on Pages yet. Keep the published
    // view until the associated deployment completes; uploads still re-read Git.
    try { PLATES = PlateGitHub.validateManifest(await jsonFetch('collection.json?t='+Date.now())).plates; } catch {}
    $('unlock-dialog').close(); refreshEditor(); keepUnlocked();
  } catch (error) { message('unlock-error', error.message || 'Could not unlock editing. Check the passphrase and try again.'); }
  finally { $('unlock-passphrase').value=''; button.disabled=false; $('cancel-unlock').disabled=false; button.textContent='Unlock'; }
};
for (const [code,name] of STATES) {
  const option=document.createElement('option'); option.value=code; option.textContent=name; $('upload-state').append(option);
}
function clearUpload() {
  cropEditor?.destroy(); cropEditor=null; $('crop-editor').hidden=true;
  if(previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl=null; uploadBlob=null; $('upload-file').value=''; $('upload-preview').replaceChildren(); $('save-photo').disabled=true;
}
function openUpload(code) {
  if (!editor || busy) return;
  clearUpload(); message('upload-error',''); message('upload-note','JPG, PNG, WebP, HEIC or HEIF · Up to 40 MB');
  $('upload-state').value = code || STATES.find(([state])=>!PLATES[state])?.[0] || 'AL';
  $('photo-dialog').close(); $('upload-dialog').showModal();
}
$('add-find').onclick = () => openUpload();
$('replace-photo').onclick = () => openUpload(selectedPhoto);
$('choose-photo').onclick = () => $('upload-file').click();
$('cancel-upload').onclick = () => { if(!busy){clearUpload();$('upload-dialog').close();} };
$('upload-dialog').addEventListener('cancel', event => {if(busy)event.preventDefault();});
$('upload-dialog').addEventListener('close', () => {if(!busy)clearUpload();});
$('upload-file').onchange = async event => {
  const file=event.target.files[0]; if(!file)return;
  clearUpload();setBusy(true);message('upload-error','');message('upload-note','Preparing your photo…');
  try {
    uploadBlob=await PlatePhotos.prepare(file);previewUrl=URL.createObjectURL(uploadBlob);
    const img=document.createElement('img');img.src=previewUrl;img.alt='Grid thumbnail preview';await img.decode();$('upload-preview').append(img);
    cropEditor=PlateCrop.create(img,$('upload-preview'),{zoomInput:$('crop-zoom'),xInput:$('crop-x'),yInput:$('crop-y'),resetButton:$('crop-reset')});
    $('crop-editor').hidden=false;
    message('upload-note','Ready to publish · '+Math.round(uploadBlob.size/1024)+' KB');
  } catch(error){message('upload-error',error.message||'This photo could not be opened.');}
  finally{setBusy(false);$('save-photo').disabled=!uploadBlob;keepUnlocked();}
};
function rememberPending(pending) {try{sessionStorage.setItem(pendingKey,JSON.stringify(pending));}catch{}}
function forgetPending(){try{sessionStorage.removeItem(pendingKey);}catch{}}
$('save-photo').onclick = async () => {
  if(!editor||busy||!uploadBlob)return;
  const state=$('upload-state').value;
  if(PLATES[state]&&!confirm('Replace the published photo for '+STATES.find(s=>s[0]===state)[1]+'?'))return;
  setBusy(true);message('upload-error','');banner('Saving photo…');
  try {
    const result=await editor.uploadPhoto({state,blob:uploadBlob,expectedEntry:PLATES[state]||null,crop:cropEditor.getCrop()});
    const pending={commit:result.commit,revision:result.manifest.revision,state,url:result.manifest.plates[state].url,started:Date.now()};
    rememberPending(pending);
    // Preview only; the public JSON remains authoritative after the next load.
    PLATES={...result.manifest.plates,[state]:{...result.manifest.plates[state],url:previewUrl}}; previewUrl=null;
    $('upload-dialog').close();renderCollection();
    banner('Photo saved · Publishing…');watchPublication(pending);
  }catch(error){
    message('upload-error',error.message||'Could not save your photo. Please try again.');
    banner('The upload could not be confirmed. Your selected photo is still here.','error');
  }finally{setBusy(false);$('save-photo').disabled=!uploadBlob;keepUnlocked();}
};
async function watchPublication(pending, attempt=0) {
  clearTimeout(publishTimer);
  try {
    const published=PlateGitHub.validateManifest(await jsonFetch('collection.json?revision='+encodeURIComponent(pending.revision)+'&t='+Date.now()));
    if(published.plates[pending.state]?.url===pending.url){
      // Verify the photo itself too: manifest propagation alone is insufficient.
      const check=new Image();check.src=pending.url+'?revision='+encodeURIComponent(pending.revision);await check.decode();
      PLATES=published.plates;renderCollection();forgetPending();banner('Published · Your collection is up to date.','success');return;
    }
    if(attempt%3===0){
      const response=await fetch(apiRoot+'/pages/builds/latest',{cache:'no-store',signal:AbortSignal.timeout(10000)});
      if(response.ok){const build=await response.json();if(build.commit===pending.commit&&build.status==='errored'){banner('Photo saved, but publishing failed. Check the GitHub deployment and try publishing again.','error');return;}}
    }
  }catch{ /* Keep the saved upload pending when the network or Pages is delayed. */ }
  if(attempt>=40){banner('Photo saved. Publishing is taking longer than usual; refresh later to check.');return;}
  publishTimer=setTimeout(()=>watchPublication(pending,attempt+1),15000);
}
async function checkBuild(attempt=0) {
  try {
    const response=await fetch(apiRoot+'/pages/builds/latest',{cache:'no-store',signal:AbortSignal.timeout(10000)});
    if(!response.ok)return;
    const build=await response.json();
    if(['building','queued'].includes(build.status)){
      banner('The collection is being updated. New photos will appear after publishing.');
      if(attempt<20)publishTimer=setTimeout(()=>checkBuild(attempt+1),30000);
    }else if(attempt>0&&build.status==='built'){
      PLATES=PlateGitHub.validateManifest(await jsonFetch('collection.json?t='+Date.now())).plates;
      renderCollection();banner('Published · Your collection is up to date.','success');
    }else if(attempt>0&&build.status==='errored')banner('The latest update could not publish. The previous collection is still available.','error');
  }catch{}
}
(async()=>{
  try {
    const manifest=PlateGitHub.validateManifest(await jsonFetch('collection.json'));
    PLATES=manifest.plates;renderCollection();
  }catch(error){message('collection-error',error.message);return;}
  try {
    const response=await fetch('upload-config.json',{cache:'no-store'});
    if(response.ok){const config=await response.json();if(config.version===1){envelope=config;$('unlock-editor').hidden=false;}}
  }catch{}
  let pending=null;try{pending=JSON.parse(sessionStorage.getItem(pendingKey)||'null');}catch{}
  if(pending&&typeof pending.commit==='string'&&typeof pending.url==='string'&&/^photos\/[A-Za-z0-9_-]+\.jpg$/.test(pending.url)&&STATES.some(s=>s[0]===pending.state)&&Date.now()-pending.started<86400000){banner('Photo saved · Checking publication…');watchPublication(pending);}
  else{forgetPending();checkBuild();}
})();
