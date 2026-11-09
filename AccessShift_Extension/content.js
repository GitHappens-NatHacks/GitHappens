(() => {
  if (window.__accessShift) return;
  const M=globalThis.AccessShiftMath;if(!M)throw Error('AccessShift math must load first');
  const ID='accessshift-tools-86f3',STYLE=ID+'-style',SVG=ID+'-svg',FILTER=ID+'-filter';
  let prefs=null,host=null,shadow=null,dot=null,rawDot=null,ring=null,ruler=null,note=null,style=null,svg=null;
  let raf=0,filter=null,last=null,smooth=null,start=0,paused=false,candidate=null,blocked=false,pressed=null,blockUntil=0,lastActivation=-Infinity,cache=[],cacheAt=-Infinity,pickAt=-Infinity,pressPoint=null;
  const selectors='button,a[href],input[type="button"],input[type="submit"],input[type="reset"],[role="button"]';
  const editable='textarea,select,input:not([type="button"]):not([type="submit"]):not([type="reset"]),[contenteditable]:not([contenteditable="false"]),[role="textbox"]';
  function own(event){return event.composedPath().includes(host);}
  function nativeZone(target){return target instanceof Element&&target.closest('[data-accessshift-native]');}
  function eligible(el){if(!(el instanceof Element)||!el.isConnected||el.closest('[hidden],[inert],[aria-hidden="true"],[aria-disabled="true"]')||el.disabled||el.getAttribute('aria-disabled')==='true')return false;
    const r=el.getBoundingClientRect(),css=getComputedStyle(el);return r.width>1&&r.height>1&&r.right>0&&r.bottom>0&&r.left<innerWidth&&r.top<innerHeight&&css.visibility!=='hidden'&&css.display!=='none'&&css.pointerEvents!=='none';}
  function nearest(p){
    const now=performance.now();if(now-cacheAt>250){cache=Array.from(document.querySelectorAll(selectors)).slice(0,1000);cacheAt=now;}
    const direct=document.elementFromPoint(p.x,p.y)?.closest(selectors);
    if(direct&&eligible(direct))return direct;
    let best=null,distance=22;
    for(const el of cache){if(!eligible(el))continue;const r=el.getBoundingClientRect(),d=Math.hypot(Math.max(r.left-p.x,0,p.x-r.right),Math.max(r.top-p.y,0,p.y-r.bottom));if(d<distance){distance=d;best=el;}}
    // Do not choose a covered element behind a dialog, menu or overlay.
    if(best){const r=best.getBoundingClientRect(),x=M.clamp(p.x,r.left+1,r.right-1),y=M.clamp(p.y,r.top+1,r.bottom-1),top=document.elementFromPoint(x,y);if(top!==best&&!best.contains(top))return null;}
    return best;
  }
  function ensureUI(){
    host=document.createElement('div');host.id=ID;
    host.style.cssText='all:initial!important;position:fixed!important;inset:0!important;pointer-events:none!important;z-index:2147483647!important;';
    shadow=host.attachShadow({mode:'open'});
    shadow.innerHTML=`<style>:host{all:initial}*{box-sizing:border-box}.dot,.raw,.target,.ruler{position:fixed;pointer-events:none;display:none}.dot{width:18px;height:18px;border:3px solid #fff;border-radius:50%;background:#087e68;box-shadow:0 0 0 2px #163d39;transform:translate(-50%,-50%)}.raw{width:14px;height:14px;border:2px dashed #b44622;border-radius:50%;transform:translate(-50%,-50%)}.target{border:3px solid #087e68;outline:2px solid white;border-radius:8px;background:rgba(0,128,96,.08)}.ruler{left:0;right:0;height:72px;border-block:2px solid #26796c;box-shadow:0 0 0 100vmax #12272c36}.bar{position:fixed;bottom:16px;right:16px;background:#123c35;color:white;border:2px solid white;border-radius:14px;padding:10px;max-width:330px;pointer-events:auto;font:14px/1.4 system-ui;box-shadow:0 6px 24px #0003}.bar p{margin:0 0 8px}.bar button{font:600 14px system-ui;min-height:38px;border:0;border-radius:8px;padding:8px 12px;margin:2px;background:#fff;color:#163e35;cursor:pointer}.bar button:focus-visible{outline:3px solid #ffcb79;outline-offset:2px}</style><div class="ruler"></div><div class="target"></div><div class="raw"></div><div class="dot"></div><div class="bar" role="region" aria-label="AccessShift page controls"><p></p><button class="pause">Pause pointer</button><button class="restore">Restore page</button></div>`;
    dot=shadow.querySelector('.dot');rawDot=shadow.querySelector('.raw');ring=shadow.querySelector('.target');ruler=shadow.querySelector('.ruler');note=shadow.querySelector('p');
    shadow.querySelector('.pause').addEventListener('click',()=>setPaused(!paused));shadow.querySelector('.restore').addEventListener('click',restore);
    document.documentElement.appendChild(host);
  }
  function setPaused(value){paused=value;blocked=false;pressed=null;pressPoint=null;blockUntil=0;candidate=null;filter?.reset();if(paused){for(const n of [dot,rawDot,ring])if(n)n.style.display='none';}
    if(shadow)shadow.querySelector('.pause').textContent=paused?'Resume pointer':'Pause pointer';updateNote();}
  function updateNote(){if(!note)return;note.textContent=prefs.pointer?(paused?'Virtual pointer paused.':`${prefs.simulate?'DEMO tremor · ':''}Green = virtual pointer. ${prefs.assisted?'Click activates its highlighted control.':'Visual preview only.'} Esc pauses.`):'Reading / color preferences applied.';
    shadow.querySelector('.pause').style.display=prefs.pointer?'inline-block':'none';}
  function move(event){if(!prefs||own(event))return;if(event.pointerType&&event.pointerType!=='mouse')return;last={x:event.clientX,y:event.clientY,native:!!nativeZone(event.target)};
    if(prefs.ruler){ruler.style.display='block';ruler.style.top=M.clamp(last.y-36,0,Math.max(0,innerHeight-72))+'px';}}
  function hide(){last=null;smooth=null;candidate=null;blocked=false;pressed=null;filter?.reset();for(const n of [dot,rawDot,ring])if(n)n.style.display='none';}
  function frame(now){
    if(!prefs)return;
    if(prefs.pointer&&!paused&&last&&!last.native&&!document.hidden){
      const offset=prefs.simulate?M.tremor((now-start)/1000,prefs.amplitude):{x:0,y:0},x=M.clamp(last.x+offset.x,0,innerWidth-1),y=M.clamp(last.y+offset.y,0,innerHeight-1);
      smooth=filter.update(x,y,now/1000);dot.style.display='block';dot.style.left=smooth.x+'px';dot.style.top=smooth.y+'px';
      rawDot.style.display=prefs.simulate?'block':'none';rawDot.style.left=x+'px';rawDot.style.top=y+'px';
      if(now-pickAt>80){candidate=prefs.assisted?nearest(smooth):null;pickAt=now;}
      if(candidate){const r=candidate.getBoundingClientRect();Object.assign(ring.style,{display:'block',left:r.left+'px',top:r.top+'px',width:r.width+'px',height:r.height+'px'});}else ring.style.display='none';
    }else{for(const n of [dot,rawDot,ring])if(n)n.style.display='none';candidate=null;}
    raf=requestAnimationFrame(frame);
  }
  function canAssist(e){return prefs?.pointer&&!paused&&prefs.assisted&&last&&!last.native&&!own(e)&&e.isTrusted&&e.button===0&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!e.shiftKey;}
  function down(e){
    if(e.isTrusted&&e.button===0){blockUntil=0;blocked=false;pressed=null;}
    if(!canAssist(e)||e.pointerType&&e.pointerType!=='mouse'||e.target.closest?.(editable)||nativeZone(e.target))return;
    blockUntil=0;
    if(smooth)candidate=nearest(smooth);
    if(!candidate&&!e.target.closest?.(selectors))return;
    // Keep assistance local even when strong smoothing trails the real mouse.
    if(candidate){const r=candidate.getBoundingClientRect(),distance=Math.hypot(Math.max(r.left-e.clientX,0,e.clientX-r.right),Math.max(r.top-e.clientY,0,e.clientY-r.bottom));if(distance>90)return;}
    blocked=true;pressed=candidate;pressPoint={x:e.clientX,y:e.clientY,time:performance.now()};e.preventDefault();e.stopImmediatePropagation();
  }
  function up(e){
    if(!blocked||e.pointerType&&e.pointerType!=='mouse'||e.button!==0)return;
    const chosen=pressed;blocked=false;pressed=null;blockUntil=performance.now()+600;e.preventDefault();e.stopImmediatePropagation();
    const clickGesture=pressPoint&&Math.hypot(e.clientX-pressPoint.x,e.clientY-pressPoint.y)<40&&performance.now()-pressPoint.time<1500;
    if(clickGesture&&chosen&&eligible(chosen)&&performance.now()-lastActivation>450){lastActivation=performance.now();chosen.click();}
  }
  function suppress(e){if(e.isTrusted&&(blocked||performance.now()<blockUntil)&&!own(e)&&!nativeZone(e.target)&&e.button===0){e.preventDefault();e.stopImmediatePropagation();}}
  function cancel(){blocked=false;pressed=null;blockUntil=performance.now()+600;}
  function keys(e){if(!prefs?.pointer||e.repeat)return;if(e.key==='Escape'){setPaused(true);}else if(e.code==='KeyS'&&e.altKey&&e.shiftKey&&!e.ctrlKey&&!e.metaKey){e.preventDefault();setPaused(!paused);}}
  function changed(){hide();cacheAt=-Infinity;cancel();}
  const listeners=[['pointermove',move,true],['pointerdown',down,true],['pointerup',up,true],['pointercancel',cancel,true],['mousedown',suppress,true],['mouseup',suppress,true],['click',suppress,true],['dblclick',suppress,true],['keydown',keys,true],['scroll',changed,true],['resize',changed,true],['blur',hide,true],['pointerout',e=>{if(!e.relatedTarget)hide();},true]];
  function apply(input){
    restore();prefs=M.settings(input);filter=new M.PointerFilter(prefs.smoothing);start=performance.now();paused=false;cacheAt=pickAt=-Infinity;lastActivation=-Infinity;ensureUI();
    const palette={warm:['#fff8e9','#25332f'],light:['#ffffff','#182f2b'],dark:['#15251f','#f5f5e9']}[prefs.theme];
    const fonts={sans:'Arial,Helvetica,sans-serif',verdana:'Verdana,Arial,sans-serif',system:'system-ui,sans-serif',serif:'Georgia,serif'};
    style=document.createElement('style');style.id=STYLE;
    const text=':where(p,li,blockquote,dd,dt)',headings=':where(h1,h2,h3,h4,h5,h6)';
    style.textContent=(prefs.reading?`
      html[data-accessshift-reading] body{background:${palette[0]}!important;color:${palette[1]}!important;}
      html[data-accessshift-reading] ${text}{font-family:${fonts[prefs.font]}!important;font-size:${prefs.size}px!important;line-height:${prefs.line}!important;letter-spacing:${prefs.letter}em!important;word-spacing:${prefs.word}em!important;background-color:${palette[0]}!important;color:${palette[1]}!important;text-align:start!important;overflow:visible!important;max-height:none!important;}
      html[data-accessshift-reading] :where(p,blockquote){margin-block-end:1.1em!important;${prefs.column?'max-width:70ch!important;':''}}
      html[data-accessshift-reading] ${text} :where(span,strong,em,b,i,a):not([class*="icon"]):not([aria-hidden="true"]){font-size:inherit!important;line-height:inherit!important;letter-spacing:inherit!important;word-spacing:inherit!important;color:inherit!important;background-color:transparent!important;}
      html[data-accessshift-reading] ${headings}{font-family:${fonts[prefs.font]}!important;line-height:1.4!important;color:${palette[1]}!important;background-color:${palette[0]}!important;}
      html[data-accessshift-reading] h1{font-size:${prefs.size*1.7}px!important;}html[data-accessshift-reading] h2{font-size:${prefs.size*1.4}px!important;}
    `:'')+(prefs.cues?`html[data-accessshift-cues] a[href]{text-decoration:underline!important;text-underline-offset:.18em!important;}html[data-accessshift-cues] :where(button,input,select,textarea,[role="button"]){outline:2px solid currentColor!important;outline-offset:2px!important;}html[data-accessshift-cues] :focus-visible{outline:3px dashed currentColor!important;outline-offset:4px!important;}`:'')+(prefs.motion?'html[data-accessshift-motion] *,html[data-accessshift-motion] *::before,html[data-accessshift-motion] *::after{animation:none!important;transition:none!important;scroll-behavior:auto!important;}':'');
    if(prefs.color!=='none'){
      if(prefs.color==='gray')style.textContent+='html[data-accessshift-color]{filter:grayscale(1)!important;}';
      else{
        svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.id=SVG;svg.setAttribute('width','0');svg.setAttribute('height','0');svg.setAttribute('aria-hidden','true');svg.style.cssText='position:fixed;pointer-events:none;';
        const defs=document.createElementNS(svg.namespaceURI,'defs'),f=document.createElementNS(svg.namespaceURI,'filter'),matrix=document.createElementNS(svg.namespaceURI,'feColorMatrix');f.id=FILTER;f.setAttribute('color-interpolation-filters','linearRGB');matrix.setAttribute('type','matrix');matrix.setAttribute('values',M.svgMatrix(prefs.color,prefs.colorStrength));f.append(matrix);defs.append(f);svg.append(defs);document.documentElement.append(svg);
        style.textContent+=`html[data-accessshift-color]{filter:url("#${FILTER}")!important;}`;
      }
    }
    (document.head||document.documentElement).append(style);
    for(const [attr,enabled] of [['reading',prefs.reading],['cues',prefs.cues],['motion',prefs.motion],['color',prefs.color!=='none']])if(enabled)document.documentElement.setAttribute('data-accessshift-'+attr,'on');
    listeners.forEach(([name,fn,capture])=>window.addEventListener(name,fn,{capture,passive:false}));
    if(prefs.ruler){ruler.style.display='block';ruler.style.top=Math.max(0,innerHeight/2-36)+'px';}
    updateNote();if(prefs.pointer)raf=requestAnimationFrame(frame);return status();
  }
  function restore(){
    cancelAnimationFrame(raf);listeners.forEach(([name,fn,capture])=>window.removeEventListener(name,fn,capture));
    host?.remove();style?.remove();svg?.remove();for(const key of ['reading','cues','motion','color'])document.documentElement.removeAttribute('data-accessshift-'+key);
    prefs=null;host=shadow=dot=rawDot=ring=ruler=note=style=svg=null;last=smooth=candidate=null;pressed=null;blocked=false;blockUntil=0;cache=[];
    return {active:false};
  }
  function status(){return {active:!!prefs,paused,settings:prefs?{...prefs}:null};}
  window.__accessShift=Object.freeze({apply,restore,status,pause:()=>setPaused(true)});
})();
