(() => {
 const $=id=>document.getElementById(id),M=AccessShiftMath,embed=new URLSearchParams(location.search).has('embed')&&parent!==window;
 const numeric=['size','line','letter','word','smoothing','amplitude','colorStrength'],checks=['reading','column','ruler','motion','cues','pointer','simulate','assisted'],selects=['font','theme','color'];
 function values(){const s={};numeric.forEach(k=>s[k]=Number($(k).value));checks.forEach(k=>s[k]=$(k).checked);selects.forEach(k=>s[k]=$(k).value);return M.settings(s);}
 function labels(){for(const k of numeric){const v=Number($(k).value);$(k+'Value').textContent=['size','amplitude'].includes(k)?v+' px':['line'].includes(k)?v.toFixed(2)+'×':['letter','word'].includes(k)?v.toFixed(2)+' em':v+'%';}}
 function fill(input){const s=M.settings(input);numeric.concat(selects).forEach(k=>$(k).value=s[k]);checks.forEach(k=>$(k).checked=s[k]);labels();}
 async function load(){try{if(globalThis.chrome?.storage?.local){const r=await chrome.storage.local.get('preferences');fill(r.preferences);}else fill(JSON.parse(localStorage.getItem('accessshift-preferences')||'{}'));}catch{fill({});}}
 async function save(s){try{if(globalThis.chrome?.storage?.local)await chrome.storage.local.set({preferences:s});else localStorage.setItem('accessshift-preferences',JSON.stringify(s));}catch{}}
 async function call(action,s){
  if(embed){parent.postMessage({type:'accessshift-demo',action,settings:s},'*');return;}
  if(!globalThis.chrome?.scripting)throw Error('Install this folder as an extension, or open demo.html to try it without installation.');
  const [tab]=await chrome.tabs.query({active:true,currentWindow:true});if(!tab?.id)throw Error('No active webpage.');
  if(tab.url?.startsWith(chrome.runtime.getURL('demo.html'))){await chrome.runtime.sendMessage({type:'accessshift-demo-action',target:tab.id,action,settings:s});return;}
  await chrome.scripting.executeScript({target:{tabId:tab.id},files:['math.js','content.js']});
  await chrome.scripting.executeScript({target:{tabId:tab.id},func:(a,input)=>window.__accessShift[a](input),args:[action,s??null]});
 }
 async function action(name){const apply=$('apply'),restore=$('restore');apply.disabled=restore.disabled=true;
  try{const s=values();await call(name,s);if(name==='apply')await save(s);$('status').textContent=name==='restore'?'Original page restored. Preferences are kept for next time.':`${s.simulate&&s.pointer?'DEMO tremor is on. ':''}Applied. Esc pauses the virtual pointer. Restore undoes page changes.`;}
  catch(e){$('status').textContent='Could not apply: '+e.message+' Try a regular webpage; browser settings, stores and some PDF viewers are protected. For local files, allow file URL access.';}
  finally{apply.disabled=restore.disabled=false;}
 }
 for(const b of document.querySelectorAll('[data-tab]'))b.addEventListener('click',()=>{document.querySelectorAll('[data-tab]').forEach(n=>{const on=n===b;n.classList.toggle('selected',on);n.setAttribute('aria-pressed',String(on));});document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!==b.dataset.tab);});
 numeric.forEach(k=>$(k).addEventListener('input',labels));$('apply').addEventListener('click',()=>action('apply'));$('restore').addEventListener('click',()=>action('restore'));
 $('demo').addEventListener('click',()=>{if(embed){$('status').textContent='You are already on the demo. Try the controls, then Apply.';return;}if(globalThis.chrome?.tabs)chrome.tabs.create({url:chrome.runtime.getURL('demo.html')});else location.href='demo.html';});
 if(embed){document.body.classList.add('embedded');$('demo').hidden=true;$('apply').textContent='Apply to demo';}
 load();
})();
