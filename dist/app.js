const STATES = [
 ['AL','Alabama','01'],['AK','Alaska','02'],['AZ','Arizona','04'],['AR','Arkansas','05'],['CA','California','06'],['CO','Colorado','08'],['CT','Connecticut','09'],['DE','Delaware','10'],['FL','Florida','12'],['GA','Georgia','13'],['HI','Hawaii','15'],['ID','Idaho','16'],['IL','Illinois','17'],['IN','Indiana','18'],['IA','Iowa','19'],['KS','Kansas','20'],['KY','Kentucky','21'],['LA','Louisiana','22'],['ME','Maine','23'],['MD','Maryland','24'],['MA','Massachusetts','25'],['MI','Michigan','26'],['MN','Minnesota','27'],['MS','Mississippi','28'],['MO','Missouri','29'],['MT','Montana','30'],['NE','Nebraska','31'],['NV','Nevada','32'],['NH','New Hampshire','33'],['NJ','New Jersey','34'],['NM','New Mexico','35'],['NY','New York','36'],['NC','North Carolina','37'],['ND','North Dakota','38'],['OH','Ohio','39'],['OK','Oklahoma','40'],['OR','Oregon','41'],['PA','Pennsylvania','42'],['RI','Rhode Island','44'],['SC','South Carolina','45'],['SD','South Dakota','46'],['TN','Tennessee','47'],['TX','Texas','48'],['UT','Utah','49'],['VT','Vermont','50'],['VA','Virginia','51'],['WA','Washington','53'],['WV','West Virginia','54'],['WI','Wisconsin','55'],['WY','Wyoming','56']
];
const $ = id => document.getElementById(id);
let plates = {}, selected = null, busy = false, ready = false, toastTimer;
const cards = new Map();
const svgNS = 'http://www.w3.org/2000/svg';
function svgElement(tag, attrs = {}) { const el = document.createElementNS(svgNS, tag); for (const [key,value] of Object.entries(attrs)) el.setAttribute(key,value); return el; }
function report(id, message) { $(id).textContent = message; $(id).hidden = !message; }
function toast(message) { clearTimeout(toastTimer); $('toast').textContent = message; $('toast').hidden = false; toastTimer = setTimeout(() => $('toast').hidden = true, 3500); }
async function api(path, options = {}) { const response = await fetch(path, options); const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Could not save this change. Please try again.'); return data; }
for (const [code,name] of STATES) {
  const button = document.createElement('button'); button.className = 'state-card'; button.disabled = true;
  button.addEventListener('click', () => openState(code)); $('grid').append(button); cards.set(code, button);
}
function render() {
  for (const [index,[code,name]] of STATES.entries()) {
    const card = cards.get(code), entry = plates[code];
    card.classList.toggle('collected',!!entry); card.disabled = !ready; card.setAttribute('aria-label',`${name}, ${entry ? 'collected. View photo' : 'not collected. Add photo'}`);
    card.replaceChildren(); const plate = document.createElement('div'); plate.className = 'plate';
    if (entry) { const img = document.createElement('img'); img.src = entry.url; img.alt = `${name} license plate`; img.loading = 'lazy'; plate.append(img); const badge = document.createElement('span'); badge.className='check-badge'; badge.textContent='✓'; plate.append(badge); }
    else { const abbr = document.createElement('span'); abbr.className='plate-abbr'; abbr.textContent=code; const plus=document.createElement('span'); plus.className='plate-add'; plus.textContent='+'; plate.append(abbr,plus); }
    const label=document.createElement('div'); label.className='card-label'; const stateName=document.createElement('span'); stateName.className='state-name'; stateName.textContent=name; const num=document.createElement('span'); num.className='state-number'; num.textContent=String(index+1).padStart(2,'0'); label.append(stateName,num); card.append(plate,label);
  }
  const count = STATES.filter(([code])=>plates[code]).length;
  $('count').textContent=count; $('percent').textContent=`${count*2}%`; $('progress-fill').style.width=`${count*2}%`; document.querySelector('[role=progressbar]').setAttribute('aria-valuenow',count);
  $('progress-caption').textContent=count===50?'All fifty. What a collection.':count===0?'Your next adventure starts with the first plate.':`${50-count} states still out there. Keep your eyes on the plates.`;
  for (const element of document.querySelectorAll('[data-state]')) { const code=element.dataset.state; element.classList.toggle('collected',!!plates[code]); if(element.matches('.map-state,button')) { const name=STATES.find(state=>state[0]===code)[1]; element.setAttribute('aria-label',`${name}, ${plates[code]?'collected, view photo':'not collected, add photo'}`); } }
}
function openState(code) {
  if (!ready || busy) return;
  selected=code; report('dialog-error',''); renderDialog(); $('photo-dialog').showModal();
}
function renderDialog() {
  const state=STATES.find(state=>state[0]===selected), entry=plates[selected];
  $('dialog-title').textContent=state[1]; $('dialog-code').textContent=`${selected} · ${entry?'COLLECTED':'STILL LOOKING'}`;
  $('photo-stage').replaceChildren();
  if(entry) { const img=document.createElement('img'); img.src=entry.url; img.alt=`${state[1]} license plate photo`; $('photo-stage').append(img); }
  else { const empty=document.createElement('div'); empty.className='empty-photo'; const abbr=document.createElement('strong'); abbr.textContent=selected; const label=document.createElement('span'); label.textContent='One more memory for the collection.'; empty.append(abbr,label); $('photo-stage').append(empty); }
  $('dialog-status').textContent=entry?'A little piece of the journey, saved.':'Found this one? Add your license plate photo.';
  $('upload-button').textContent=entry?'Replace photo':'Add photo'; $('remove-button').hidden=!entry;
}
function setBusy(value) { busy=value; $('upload-button').disabled=value; $('remove-button').disabled=value; $('close-dialog').disabled=value; }
$('close-dialog').onclick=()=>{if(!busy)$('photo-dialog').close();};
$('photo-dialog').addEventListener('cancel',event=>{if(busy)event.preventDefault();});
$('photo-dialog').addEventListener('click',event=>{if(event.target===$('photo-dialog')&&!busy){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close();}});
$('upload-button').onclick=()=>$('photo-input').click();
async function preparePhoto(file) {
  if(file.size>40*1024*1024) throw new Error('This photo is over 40 MB. Please choose a smaller image.');
  const url=URL.createObjectURL(file);
  try { const img=new Image(); img.src=url; try { await img.decode(); } catch { throw new Error('This image could not be opened. Please use JPG, PNG or WebP; export HEIC photos as JPG first.'); }
    const scale=Math.min(1,2000/Math.max(img.naturalWidth,img.naturalHeight)); const canvas=document.createElement('canvas'); canvas.width=Math.max(1,Math.round(img.naturalWidth*scale)); canvas.height=Math.max(1,Math.round(img.naturalHeight*scale)); const context=canvas.getContext('2d'); context.fillStyle='#ffffff'; context.fillRect(0,0,canvas.width,canvas.height); context.drawImage(img,0,0,canvas.width,canvas.height);
    return await new Promise((resolve,reject)=>canvas.toBlob(blob=>blob?resolve(blob):reject(new Error('Could not process this photo. Please try another.')),'image/jpeg',.9));
  } finally { URL.revokeObjectURL(url); }
}
$('photo-input').onchange=async event=>{
  const file=event.target.files[0]; event.target.value=''; if(!file||!selected||busy)return;
  setBusy(true); report('dialog-error',''); $('upload-button').textContent='Saving…';
  try { const blob=await preparePhoto(file); plates[selected]=await api(`/api/plates/${selected}`,{method:'PUT',headers:{'Content-Type':'image/jpeg'},body:blob}); render(); renderDialog(); toast('Photo saved to your collection.'); }
  catch(error){report('dialog-error',error.message);$('upload-button').textContent=plates[selected]?'Replace photo':'Add photo';}
  finally{setBusy(false);}
};
$('remove-button').onclick=async()=>{
  if(busy||!selected||!confirm('Remove this photo from your collection? Your original photo is unaffected.'))return;
  setBusy(true); report('dialog-error','');
  try{await api(`/api/plates/${selected}`,{method:'DELETE'});delete plates[selected];render();renderDialog();toast('Photo removed.');}catch(error){report('dialog-error',error.message);}finally{setBusy(false);}
};
function setView(view){const map=view==='map';$('grid').hidden=map;$('map-view').hidden=!map;$('grid-toggle').setAttribute('aria-pressed',!map);$('map-toggle').setAttribute('aria-pressed',map);$('view-caption').textContent=map?'YOUR FINDS, COAST TO COAST':'ALL 50 STATES · A–Z';if(map&&!mapPromise)mapPromise=loadMap();}
$('grid-toggle').onclick=()=>setView('grid');$('map-toggle').onclick=()=>setView('map');
let mapPromise;
async function loadMap(){
 try {
  const response=await fetch('states-topology.json');if(!response.ok)throw new Error('Map unavailable');const topology=await response.json();
  const decoded=topology.arcs.map(arc=>{let x=0,y=0;return arc.map(([dx,dy])=>{x+=dx;y+=dy;return [x*topology.transform.scale[0]+topology.transform.translate[0],y*topology.transform.scale[1]+topology.transform.translate[1]];});});
  const ringPath=ring=>{const points=ring.flatMap(index=>index<0?[...decoded[~index]].reverse():decoded[index]);return points.map(([x,y],i)=>`${i?'L':'M'}${x.toFixed(2)},${y.toFixed(2)}`).join('')+'Z';};
  const svg=svgElement('svg',{viewBox:'0 0 975 610',role:'group','aria-label':'Interactive map of the fifty US states'});
  for(const geometry of topology.objects.states.geometries){const state=STATES.find(state=>Number(state[2])===Number(geometry.id));if(!state)continue;const [code,name]=state;const polygons=geometry.type==='Polygon'?[geometry.arcs]:geometry.arcs;const path=svgElement('path',{d:polygons.flatMap(poly=>poly.map(ringPath)).join(''),class:'map-state',tabindex:'0',role:'button','data-state':code});const title=svgElement('title');title.textContent=name;path.append(title);path.addEventListener('click',()=>openState(code));path.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();openState(code);}});path.addEventListener('mouseenter',()=>$('map-hint').textContent=`${name} · ${plates[code]?'Collected — view photo':'Still looking — add photo'}`);path.addEventListener('focus',()=>$('map-hint').textContent=`${name} · ${plates[code]?'Collected — view photo':'Still looking — add photo'}`);svg.append(path);}
  $('map-container').replaceChildren(svg);
  const small=['CT','DE','MD','MA','NH','NJ','RI','VT'];
  for(const path of svg.querySelectorAll('path')){const code=path.dataset.state;if(small.includes(code))continue;const box=path.getBBox();const label=svgElement('text',{x:box.x+box.width/2,y:box.y+box.height/2+4,class:'map-label','data-state':code,'aria-hidden':'true'});label.textContent=code;svg.append(label);}
  $('small-states').replaceChildren();for(const [code,name] of STATES.filter(state=>small.includes(state[0]))){const button=document.createElement('button');button.textContent=name;button.dataset.state=code;button.onclick=()=>openState(code);$('small-states').append(button);}
  render();
 }catch(error){$('map-container').textContent='The map could not load. Use the grid, or reload the page to try again.';mapPromise=null;}
}
render();
api('/api/plates').then(data=>{plates=data;ready=true;render();}).catch(()=>report('page-error','Your collection could not load. Make sure the local server is running, then reload this page.'));
