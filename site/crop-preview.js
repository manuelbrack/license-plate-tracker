/* Crop metadata frames grid thumbnails; the underlying photo is never changed. */
(() => {
  'use strict';
  const RATIO = 1.83;
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
  function apply(image, crop) {
    if (!crop) return;
    image.classList.add('cropped-thumbnail');
    image.style.width = `${100 / crop.width}%`;
    image.style.height = `${100 / crop.height}%`;
    image.style.left = `${-100 * crop.x / crop.width}%`;
    image.style.top = `${-100 * crop.y / crop.height}%`;
  }
  function create(image, viewport, controls) {
    const aspect = image.naturalWidth / image.naturalHeight;
    const baseWidth = Math.min(1, RATIO / aspect);
    const baseHeight = Math.min(1, aspect / RATIO);
    let zoom = 1, crop = {x:(1-baseWidth)/2,y:(1-baseHeight)/2,width:baseWidth,height:baseHeight};
    let drag = null;
    const {zoomInput, xInput, yInput, resetButton} = controls;
    const sync = () => {
      apply(image, crop);
      zoomInput.value = String(zoom);
      zoomInput.setAttribute('aria-valuetext', `${zoom.toFixed(1)} times`);
      xInput.value = String(crop.width >= 1 ? 50 : 100 * crop.x / (1-crop.width));
      yInput.value = String(crop.height >= 1 ? 50 : 100 * crop.y / (1-crop.height));
    };
    const move = (x,y) => {
      crop.x = clamp(x,0,1-crop.width); crop.y = clamp(y,0,1-crop.height); sync();
    };
    const setZoom = value => {
      const centerX=crop.x+crop.width/2, centerY=crop.y+crop.height/2;
      zoom=clamp(Number(value)||1,1,6);
      crop.width=baseWidth/zoom;crop.height=baseHeight/zoom;
      move(centerX-crop.width/2,centerY-crop.height/2);
    };
    zoomInput.oninput=()=>setZoom(zoomInput.value);
    xInput.oninput=()=>move(Number(xInput.value)/100*(1-crop.width),crop.y);
    yInput.oninput=()=>move(crop.x,Number(yInput.value)/100*(1-crop.height));
    resetButton.onclick=()=>{zoom=1;crop={x:(1-baseWidth)/2,y:(1-baseHeight)/2,width:baseWidth,height:baseHeight};sync();};
    viewport.onpointerdown=event=>{
      if(event.button!==0 || zoomInput.disabled)return;
      const bounds=viewport.getBoundingClientRect();
      drag={id:event.pointerId,x:event.clientX,y:event.clientY,crop:{...crop},width:bounds.width,height:bounds.height};
      viewport.setPointerCapture(event.pointerId);viewport.classList.add('dragging');event.preventDefault();
    };
    viewport.onpointermove=event=>{
      if(!drag||event.pointerId!==drag.id)return;
      move(drag.crop.x-(event.clientX-drag.x)/drag.width*drag.crop.width,
           drag.crop.y-(event.clientY-drag.y)/drag.height*drag.crop.height);
    };
    const release=()=>{drag=null;viewport.classList.remove('dragging');};
    viewport.onpointerup=release;viewport.onpointercancel=release;viewport.onlostpointercapture=release;
    viewport.onkeydown=event=>{
      if(zoomInput.disabled)return;
      const steps={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
      const step=steps[event.key];if(!step)return;
      event.preventDefault();const scale=event.shiftKey ? 0.1 : 0.02;
      move(crop.x+step[0]*crop.width*scale,crop.y+step[1]*crop.height*scale);
    };
    image.draggable=false;sync();
    return {
      getCrop:()=>Object.fromEntries(Object.entries(crop).map(([key,value])=>[key,Number(value.toFixed(6))])),
      destroy:()=>{
        release(); viewport.onpointerdown=viewport.onpointermove=viewport.onpointerup=viewport.onpointercancel=viewport.onlostpointercapture=viewport.onkeydown=null;
        zoomInput.oninput=xInput.oninput=yInput.oninput=resetButton.onclick=null;
      }
    };
  }
  window.PlateCrop=Object.freeze({apply,create,RATIO});
})();
