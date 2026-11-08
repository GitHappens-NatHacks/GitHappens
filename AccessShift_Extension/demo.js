(() => {
 const $=id=>document.getElementById(id),M=AccessShiftMath,controls=$('controls');
 window.addEventListener('message',e=>{if(e.source!==controls.contentWindow||e.data?.type!=='accessshift-demo')return;applyAction(e.data);});
 function applyAction(data){if(data.action==='restore')window.__accessShift.restore();else if(data.action==='apply'){const s=M.settings(data.settings);window.__accessShift.apply(s);if(!trial){$('testStrength').value=s.smoothing;labels();filter.configure(s.smoothing);}}}
 if(globalThis.chrome?.runtime?.onMessage&&globalThis.chrome?.tabs){let tabId=null;chrome.tabs.getCurrent(t=>tabId=t?.id);chrome.runtime.onMessage.addListener((msg,_sender,respond)=>{if(msg.type!=='accessshift-demo-action'||msg.target!==tabId)return;applyAction(msg);respond({ok:true});});}
 let choice='';document.querySelectorAll('.example').forEach(b=>b.addEventListener('click',()=>{choice=b.dataset.choice;$('formStatus').textContent='Selected '+choice+'. This is only a demo.';}));
 $('sampleForm').addEventListener('submit',e=>{e.preventDefault();$('formStatus').textContent=choice?'Demo confirmed for '+choice+'. Nothing was submitted.':'Choose a day first.';});
 const canvas=$('canvas'),arena=$('arena'),ctx=canvas.getContext('2d');let width=600,height=340,mouse=null,inside=false,raw=null,stable=null,filter=new M.PointerFilter(70),trial=null,results=[],trail=[],misses=[],epoch=performance.now();
 const sequence=[0,3,1,4,2,0,4,1,3,2],positions=[[.16,.3],[.5,.25],[.82,.35],[.3,.72],[.7,.7]],seed=314159;
 function resize(){
  const nextWidth=arena.clientWidth,nextHeight=arena.clientHeight;
  if(trial&&(nextWidth!==width||nextHeight!==height)){trial=null;lock(false);$('trialStatus').textContent='Layout changed. Incomplete trial discarded; start again at this size.';}
  width=nextWidth;height=nextHeight;const dpr=devicePixelRatio||1;canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);filter.reset();trail=[];
 }
 new ResizeObserver(resize).observe(arena);resize();
 function labels(){$('testAmplitudeValue').textContent=$('testAmplitude').value+' px';$('testStrengthValue').textContent=$('testStrength').value+'%';}
 $('testAmplitude').addEventListener('input',labels);$('testStrength').addEventListener('input',()=>{labels();filter.configure(Number($('testStrength').value));});
 function lock(value){for(const id of ['targetSize','testAmplitude','testStrength','baseline','smoothed'])$(id).disabled=value;$('abort').disabled=!value;}
 function start(mode){
  const t=performance.now();trial={mode,started:t,hits:0,misses:0,clicks:[],seed,amplitude:Number($('testAmplitude').value),strength:Number($('testStrength').value),size:Number($('targetSize').value)};
  epoch=t;filter.configure(trial.strength);trail=[];misses=[];lock(true);metrics(t);$('trialStatus').textContent=(mode==='baseline'?'Baseline: aim with the ORANGE dot.':'Smoothed: aim with the GREEN dot.')+' Click target 1 of 10.';
 }
 function metrics(now){$('nextTarget').textContent=trial?`${trial.hits+1} / 10`:'—';$('clicks').textContent=trial?trial.hits+' / '+trial.misses:'0 / 0';const n=trial?trial.hits+trial.misses:0;$('accuracy').textContent=n?Math.round(trial.hits/n*100)+'%':'—';$('elapsed').textContent=trial?((now-trial.started)/1000).toFixed(1)+' s':'0.0 s';}
 function step(now){if(!mouse)return;const offset=M.tremor((now-epoch)/1000,trial?trial.amplitude:Number($('testAmplitude').value),seed);raw={x:M.clamp(mouse.x+offset.x,0,width),y:M.clamp(mouse.y+offset.y,0,height)};stable=filter.update(raw.x,raw.y,now/1000);}
 function draw(now){
  step(now);ctx.clearRect(0,0,width,height);ctx.fillStyle='#cddbc9';for(let x=20;x<width;x+=24)for(let y=20;y<height;y+=24){ctx.beginPath();ctx.arc(x,y,.7,0,Math.PI*2);ctx.fill();}
  const size=trial?trial.size:Number($('targetSize').value),current=trial?sequence[trial.hits]:null;
  positions.forEach(([x,y],i)=>{x*=width;y*=height;ctx.fillStyle=i===current?'#165f4c':'#c5d2bf';ctx.fillRect(x-size/2,y-size/2,size,size);if(i===current){ctx.strokeStyle='#cb9e45';ctx.lineWidth=2;ctx.strokeRect(x-size/2-5,y-size/2-5,size+10,size+10);}ctx.fillStyle='#234b3b';ctx.font='600 12px system-ui';ctx.textAlign='center';ctx.fillText(String(i+1),x,y-size/2-12);});
  if(inside&&raw&&stable){trail.push({x:stable.x,y:stable.y});if(trail.length>45)trail.shift();ctx.strokeStyle='#34806a44';ctx.lineWidth=2;ctx.beginPath();trail.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();
   const dot=(p,color,filled)=>{ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=2;ctx.beginPath();ctx.arc(p.x,p.y,7,0,2*Math.PI);if(filled)ctx.fill();else ctx.stroke();};dot(raw,'#b54e25',trial?.mode==='baseline');dot(stable,'#087e68',trial?.mode!=='baseline');}
  for(const p of misses){ctx.strokeStyle='#b54e25';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(p.x-3,p.y-3);ctx.lineTo(p.x+3,p.y+3);ctx.moveTo(p.x+3,p.y-3);ctx.lineTo(p.x-3,p.y+3);ctx.stroke();}
  requestAnimationFrame(draw);
 }
 canvas.addEventListener('pointermove',e=>{if(e.pointerType!=='mouse')return;const r=canvas.getBoundingClientRect();mouse={x:e.clientX-r.left,y:e.clientY-r.top};inside=true;});canvas.addEventListener('pointerleave',()=>{inside=false;filter.reset();trail=[];});
 canvas.addEventListener('click',e=>{
  if(!trial||e.button!==0)return;const r=canvas.getBoundingClientRect();mouse={x:e.clientX-r.left,y:e.clientY-r.top};const now=performance.now();step(now);const p=trial.mode==='baseline'?raw:stable,target=sequence[trial.hits],[nx,ny]=positions[target],x=nx*width,y=ny*height;
  const hit=Math.abs(p.x-x)<=trial.size/2&&Math.abs(p.y-y)<=trial.size/2;
  trial.clicks.push({seconds:(now-trial.started)/1000,x:p.x,y:p.y,rawX:raw.x,rawY:raw.y,target:target+1,targetX:x,targetY:y,hit});
  if(hit)trial.hits++;else{trial.misses++;misses.push({...p});if(misses.length>50)misses.shift();}metrics(now);
  if(trial.hits===10){
   const item={mode:trial.mode,completed:true,hits:trial.hits,misses:trial.misses,accuracy:trial.hits/(trial.hits+trial.misses),seconds:(now-trial.started)/1000,seed:trial.seed,amplitude:trial.amplitude,smoothing:trial.strength,targetSize:trial.size,canvas:{width,height},clicks:trial.clicks};results.push(item);trial=null;lock(false);$('nextTarget').textContent='Done';$('trialStatus').textContent='Trial complete. Compare with the other mode; these are your measured results.';renderResults();
  }
 });
 function renderResults(){const box=$('results');box.replaceChildren();for(const item of results){const row=document.createElement('div');row.className='result-row';row.textContent=`${item.mode==='baseline'?'Baseline':'Smoothed'} · ${(item.accuracy*100).toFixed(0)}% accuracy · ${item.misses} misses · ${item.seconds.toFixed(1)} s · ${item.targetSize} px targets`;box.append(row);}}
 $('baseline').addEventListener('click',()=>start('baseline'));$('smoothed').addEventListener('click',()=>start('smoothed'));$('abort').addEventListener('click',()=>{trial=null;lock(false);$('trialStatus').textContent='Incomplete trial discarded.';});
 $('export').addEventListener('click',()=>{if(!results.length){$('trialStatus').textContent='Complete a trial before exporting results.';return;}const data={application:'AccessShift browser demo',scope:'seeded engineering tremor simulation; not a clinical assessment',created:new Date().toISOString(),trials:results};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='accessshift-trials.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
 lock(false);requestAnimationFrame(draw);
})();
