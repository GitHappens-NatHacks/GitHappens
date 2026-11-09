const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),source=name=>fs.readFileSync(path.join(root,name),'utf8');
function context(markup){
 const d=new JSDOM(markup||'<!doctype html><html><head><style>p{color:blue}</style></head><body><main><h1>Original title</h1><p>Keep <strong>these words</strong> <a href="/next">next</a></p><form><label>Note<input value="not changed"></label><button>Submit</button></form></main></body></html>',{url:'https://example.org',runScripts:'outside-only',pretendToBeVisual:true});
 d.window.document.elementFromPoint=()=>null;d.window.eval(source('math.js'));return d;
}
function core(){const d=context();d.window.eval(source('content.js'));return d;}
const close=d=>d.window.close();

test('defaults sanitize invalid preferences and CSS injection',()=>{const d=context(),M=d.window.AccessShiftMath;assert.equal(M.settings(null).size,20);const s=M.settings({size:900,line:-1,color:'bad',font:'Arial;body{}',pointer:'true'});assert.equal(s.size,36);assert.equal(s.line,1.2);assert.equal(s.color,'none');assert.equal(s.font,'sans');assert.equal(s.pointer,false);close(d);});

test('zero-strength filter passes through, handles invalid input and stale samples',()=>{const d=context(),F=d.window.AccessShiftMath.OneEuro,f=new F(0);assert.equal(f.update(0,0),0);assert.equal(f.update(99,.01),99);assert.equal(f.update(30,.01),99);assert.equal(f.update(77,1),77);assert.throws(()=>f.update(NaN,2));close(d);});

test('strong filtering attenuates stationary seeded jitter at 30/60/120 Hz',()=>{const d=context(),M=d.window.AccessShiftMath;for(const fps of [30,60,120]){const f=new M.PointerFilter(90);let a=0,b=0;for(let i=0;i<fps*8;i++){const t=i/fps,n=M.tremor(t,35),p=f.update(500+n.x,300+n.y,t);if(i>fps*2){a+=n.x*n.x+n.y*n.y;b+=(p.x-500)**2+(p.y-300)**2;}}assert.ok(Math.sqrt(b/a)<.45);}close(d);});

test('filter eventually follows intentional movement and resets after a gap',()=>{const d=context(),f=new d.window.AccessShiftMath.PointerFilter(70);f.update(10,10,0);let p;for(let i=1;i<120;i++)p=f.update(500,300,i/60);assert.ok(p.x>490&&p.y>290);assert.equal(f.update(100,100,10).x,100);close(d);});

test('tremor is deterministic, varied, finite, bounded and amplitude controlled',()=>{const d=context(),M=d.window.AccessShiftMath;const a=M.tremor(.234,25,123);assert.deepEqual(a,M.tremor(.234,25,123));assert.notDeepEqual(a,M.tremor(.234,25,124));assert.equal(M.tremor(1,0).x,0);const xs=Array.from({length:1000},(_,i)=>M.tremor(i/120,60));assert.ok(xs.every(p=>Number.isFinite(p.x)&&Math.abs(p.x)<180&&Math.abs(p.y)<180));assert.ok(new Set(xs.map(p=>p.x.toFixed(1))).size>200);close(d);});

test('color transforms preserve neutral gray, identity at zero and valid SVG dimensions',()=>{const d=context(),M=d.window.AccessShiftMath;for(const mode of ['protan','deutan','tritan']){const matrix=M.colorMatrix(mode,100);for(const row of matrix)assert.ok(Math.abs(row.reduce((a,b)=>a+b,0)-1)<.00001);const identity=M.colorMatrix(mode,0);assert.equal(identity[0][0],1);assert.equal(identity[1][0],0);const values=M.svgMatrix(mode,70).split(' ').map(Number);assert.equal(values.length,20);assert.ok(values.every(Number.isFinite));}close(d);});

test('apply/restore does not rewrite source text, links, form values or inline styles',()=>{const d=core(),w=d.window,doc=w.document,body=doc.body.innerHTML,head=doc.head.innerHTML;const api=w.__accessShift;doc.body.style.filter='contrast(1.1)';const inline=doc.body.getAttribute('style');api.apply({reading:true,color:'deutan',ruler:true,pointer:true});assert.equal(doc.querySelector('input').value,'not changed');assert.equal(doc.querySelector('a').getAttribute('href'),'/next');assert.equal(doc.querySelector('p').textContent,'Keep these words next');assert.equal(doc.body.innerHTML,body);api.restore();assert.equal(doc.body.innerHTML,body);assert.equal(doc.head.innerHTML,head);assert.equal(doc.body.getAttribute('style'),inline);assert.equal(doc.documentElement.hasAttribute('data-accessshift-color'),false);close(d);});

test('repeated apply, restore and script injection are idempotent',()=>{const d=core(),w=d.window,api=w.__accessShift;for(let i=0;i<5;i++)api.apply({color:'tritan'});assert.equal(w.document.querySelectorAll('#accessshift-tools-86f3').length,1);assert.equal(w.document.querySelectorAll('#accessshift-tools-86f3-svg').length,1);assert.equal(w.document.querySelectorAll('#accessshift-tools-86f3-style').length,1);w.eval(source('content.js'));assert.equal(w.__accessShift,api);api.restore();api.restore();assert.equal(w.document.querySelectorAll('[id^="accessshift-tools-86f3"]').length,0);close(d);});

test('individual modules can be disabled and grayscale is explicitly available',()=>{const d=core(),w=d.window;w.__accessShift.apply({reading:false,cues:false,color:'gray',motion:false,pointer:false});assert.equal(w.document.documentElement.hasAttribute('data-accessshift-reading'),false);const css=w.document.getElementById('accessshift-tools-86f3-style').textContent;assert.match(css,/grayscale\(1\)/);assert.ok(!css.includes('font-size'));close(d);});

test('Escape pauses and the page toolbar resumes the pointer',()=>{const d=core(),w=d.window;w.__accessShift.apply({pointer:true});w.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape'}));assert.equal(w.__accessShift.status().paused,true);const shadow=w.document.getElementById('accessshift-tools-86f3').shadowRoot;shadow.querySelector('.pause').click();assert.equal(w.__accessShift.status().paused,false);shadow.querySelector('.restore').click();assert.equal(w.__accessShift.status().active,false);close(d);});

test('scripted clicks remain native and are not recursively redirected',()=>{const d=core(),w=d.window;w.__accessShift.apply({pointer:true,assisted:true});const b=w.document.querySelector('button');let count=0;b.addEventListener('click',()=>count++);b.type='button';b.click();assert.equal(count,1);close(d);});

test('scroll/resize clears pending pointer state without losing settings',()=>{const d=core(),w=d.window;w.__accessShift.apply({pointer:true,simulate:true});w.dispatchEvent(new w.Event('scroll'));w.dispatchEvent(new w.Event('resize'));assert.equal(w.__accessShift.status().active,true);assert.equal(w.__accessShift.status().settings.simulate,true);close(d);});

test('popup loads saved preferences without a Chrome API and has accessible sections',async()=>{const d=context(source('popup.html')),w=d.window;w.localStorage.setItem('accessshift-preferences',JSON.stringify({size:27,smoothing:88}));w.eval(source('popup.js'));await new Promise(r=>setImmediate(r));assert.equal(w.document.getElementById('size').value,'27');w.document.querySelector('[data-tab="steady"]').click();assert.equal(w.document.getElementById('steady').hidden,false);assert.equal(w.document.getElementById('read').hidden,true);assert.equal(w.document.querySelector('[data-tab="steady"]').getAttribute('aria-pressed'),'true');close(d);});

test('popup injects local scripts and applies sanitized preferences on a regular tab',async()=>{const d=context(source('popup.html')),w=d.window,calls=[];w.chrome={storage:{local:{get:async()=>({}),set:async s=>calls.push(['save',s])}},runtime:{getURL:p=>'chrome-extension://test/'+p},tabs:{query:async()=>[{id:9,url:'https://example.org'}]},scripting:{executeScript:async a=>{calls.push(a);return [];}}};w.eval(source('popup.js'));await new Promise(r=>setImmediate(r));w.document.getElementById('apply').click();await new Promise(r=>setImmediate(r));assert.deepEqual(Array.from(calls[0].files),['math.js','content.js']);assert.equal(calls[1].args[0],'apply');assert.equal(calls[1].args[1].simulate,false);assert.match(w.document.getElementById('status').textContent,/Applied/);close(d);});

test('extension manifest has no background network or blanket site permission',()=>{const m=JSON.parse(source('manifest.json'));assert.equal(m.manifest_version,3);assert.deepEqual(m.permissions,['activeTab','scripting','storage']);assert.equal(m.host_permissions,undefined);assert.equal(m.background,undefined);assert.equal(m.action.default_popup,'popup.html');});

function demoContext(){
 const d=context(source('demo.html')),w=d.window,canvas=w.document.getElementById('canvas'),arena=w.document.getElementById('arena');
 let now=0,blob=null;Object.defineProperty(w.performance,'now',{value:()=>now});
 w.ResizeObserver=class{constructor(cb){this.cb=cb;}observe(){this.cb();}};
 Object.defineProperty(arena,'clientWidth',{value:600});Object.defineProperty(arena,'clientHeight',{value:340});
 canvas.getBoundingClientRect=()=>({left:0,top:0,width:600,height:340,right:600,bottom:340});
 canvas.getContext=()=>new Proxy({}, {get:(o,k)=>o[k]||(o[k]=()=>{}),set:(o,k,v)=>(o[k]=v,true)});
 w.Blob=Blob;w.URL.createObjectURL=b=>{blob=b;return 'blob:demo';};w.URL.revokeObjectURL=()=>{};
 w.document.addEventListener('click',e=>{if(e.target.tagName==='A')e.preventDefault();});
 w.eval(source('content.js'));w.eval(source('demo.js'));
 return {d,w,canvas,setTime:t=>now=t,getBlob:()=>blob};
}

test('demo completes a baseline trial and exports actual hits, settings and coordinates',async()=>{
 const {d,w,canvas,setTime,getBlob}=demoContext(),doc=w.document;
 doc.getElementById('testAmplitude').value=0;doc.getElementById('baseline').click();
 assert.equal(doc.getElementById('smoothed').disabled,true);
 const seq=[0,3,1,4,2,0,4,1,3,2],pos=[[.16,.3],[.5,.25],[.82,.35],[.3,.72],[.7,.7]];
 for(let i=0;i<10;i++){setTime(100+i*200);const [x,y]=pos[seq[i]];canvas.dispatchEvent(new w.MouseEvent('click',{clientX:x*600,clientY:y*340,button:0,bubbles:true}));}
 assert.equal(doc.getElementById('nextTarget').textContent,'Done');assert.equal(doc.getElementById('clicks').textContent,'10 / 0');assert.equal(doc.getElementById('smoothed').disabled,false);
 doc.getElementById('export').click();const payload=JSON.parse(await getBlob().text());
 assert.equal(payload.trials.length,1);assert.equal(payload.trials[0].clicks.length,10);assert.equal(payload.trials[0].accuracy,1);assert.equal(payload.trials[0].amplitude,0);assert.ok(payload.trials[0].seconds>0);close(d);
});

test('demo records misses and discards an incomplete trial',()=>{const {d,w,canvas}=demoContext(),doc=w.document;doc.getElementById('baseline').click();canvas.dispatchEvent(new w.MouseEvent('click',{clientX:0,clientY:0,button:0}));assert.equal(doc.getElementById('clicks').textContent,'0 / 1');doc.getElementById('abort').click();assert.equal(doc.getElementById('baseline').disabled,false);assert.match(doc.getElementById('trialStatus').textContent,/discarded/);doc.getElementById('export').click();assert.match(doc.getElementById('trialStatus').textContent,/Complete a trial/);close(d);});

test('demo embedded controls apply and restore through the expected frame only',()=>{const {d,w}=demoContext(),doc=w.document;const msg={type:'accessshift-demo',action:'apply',settings:{reading:true,color:'protan',smoothing:82}};
 w.dispatchEvent(new w.MessageEvent('message',{source:w,data:msg}));assert.equal(w.__accessShift.status().active,false);
 w.dispatchEvent(new w.MessageEvent('message',{source:doc.getElementById('controls').contentWindow,data:msg}));assert.equal(w.__accessShift.status().active,true);assert.equal(doc.getElementById('testStrength').value,'82');
 w.dispatchEvent(new w.MessageEvent('message',{source:doc.getElementById('controls').contentWindow,data:{type:'accessshift-demo',action:'restore'}}));assert.equal(w.__accessShift.status().active,false);close(d);
});
