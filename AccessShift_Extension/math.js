/* Local signal processing; no network or native mouse access. */
(() => {
  if (globalThis.AccessShiftMath) return;
  const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
  class LowPass {
    constructor(){this.value=null;}
    update(v,a){this.value=this.value===null?v:a*v+(1-a)*this.value;return this.value;}
  }
  class OneEuro {
    constructor(strength=70){this.configure(strength);this.reset();}
    configure(strength){this.strength=clamp(Number(strength)||0,0,100);const s=this.strength/100;this.cutoff=12*Math.pow(.08/12,s);this.beta=.012*Math.pow(.00005/.012,s);}
    reset(){this.signal=new LowPass();this.derivative=new LowPass();this.time=null;this.previous=null;}
    alpha(cutoff,dt){return 1/(1+1/(2*Math.PI*cutoff*dt));}
    update(v,t){
      if(!Number.isFinite(v)||!Number.isFinite(t))throw Error('Finite coordinates and timestamp required');
      if(this.time!==null&&t<=this.time)return this.signal.value;
      if(this.time===null||t-this.time>.5){this.reset();this.previous=v;this.time=t;return this.signal.update(v,1);}
      const dt=t-this.time,velocity=(v-this.previous)/dt;
      const d=this.derivative.update(velocity,this.alpha(1,dt));
      this.previous=v;this.time=t;
      if(this.strength===0)return this.signal.update(v,1);
      return this.signal.update(v,this.alpha(this.cutoff+this.beta*Math.abs(d),dt));
    }
  }
  class PointerFilter {
    constructor(s=70){this.x=new OneEuro(s);this.y=new OneEuro(s);}
    configure(s){this.x.configure(s);this.y.configure(s);this.reset();}
    reset(){this.x.reset();this.y.reset();}
    update(x,y,t){return {x:this.x.update(x,t),y:this.y.update(y,t)};}
  }
  function hash(i,seed){let n=(i^seed)>>>0;n=Math.imul(n^(n>>>16),0x7feb352d);n=Math.imul(n^(n>>>15),0x846ca68b);return ((n^(n>>>16))>>>0)/4294967296*2-1;}
  function noise(t,seed){const k=Math.floor(t),f=t-k,a=hash(k,seed),b=hash(k+1,seed);return a+(b-a)*(f*f*(3-2*f));}
  function tremor(t,amplitude=25,seed=314159){
    const a=clamp(Number(amplitude)||0,0,60),phase=(seed%1000)/157;
    if(a===0)return {x:0,y:0};
    const axis=(shift,offset)=>{
      const burst=Math.max(0,noise(t*1.7,seed+shift+1));
      return a*(.36*Math.sin(t*2*Math.PI*(5.3+offset)+phase)+.2*Math.sin(t*2*Math.PI*(9.7+offset)+1.3)+.75*noise(t*34,seed+shift)+.25*noise(t*3.2,seed+shift+9)+.65*burst*noise(t*61,seed+shift+42));
    };
    return {x:axis(17,0),y:axis(107,1.1)};
  }
  const simulations={
    protan:[[.152286,1.052583,-.204868],[.114503,.786281,.099216],[-.003882,-.048116,1.051998]],
    deutan:[[.367322,.860646,-.227968],[.280085,.672501,.047413],[-.011820,.042940,.968881]],
    tritan:[[1.255528,-.076749,-.178779],[-.078411,.930809,.147602],[.004733,.691367,.303900]]
  };
  function colorMatrix(mode,strength=70){
    const I=[[1,0,0],[0,1,0],[0,0,1]],S=simulations[mode];if(!S)return I;
    const R=mode==='tritan'?[[1,0,.7],[0,1,.7],[0,0,0]]:[[0,0,0],[.7,1,0],[.7,0,1]],s=clamp(Number(strength)||0,0,100)/100;
    return I.map((row,i)=>row.map((v,j)=>v+s*R[i].reduce((sum,r,k)=>sum+r*(I[k][j]-S[k][j]),0)));
  }
  function svgMatrix(mode,strength){return colorMatrix(mode,strength).map(row=>row.concat(0,0)).flat().concat(0,0,0,1,0).join(' ');}
  const defaults=Object.freeze({reading:true,font:'sans',size:20,line:1.7,letter:.04,word:.1,theme:'warm',column:true,ruler:false,motion:false,cues:true,color:'none',colorStrength:70,pointer:false,smoothing:70,simulate:false,amplitude:25,assisted:true});
  function settings(input={}){
    if(!input||typeof input!=='object')input={};
    const s={...defaults};for(const key of ['reading','column','ruler','motion','cues','pointer','simulate','assisted'])if(typeof input[key]==='boolean')s[key]=input[key];
    for(const [key,min,max] of [['size',14,36],['line',1.2,2.4],['letter',0,.2],['word',0,.3],['colorStrength',0,100],['smoothing',0,100],['amplitude',0,60]])if(Number.isFinite(Number(input[key])))s[key]=clamp(Number(input[key]),min,max);
    for(const [key,allowed] of [['font',['sans','verdana','system','serif']],['theme',['warm','light','dark']],['color',['none','protan','deutan','tritan','gray']]])if(allowed.includes(input[key]))s[key]=input[key];
    return s;
  }
  globalThis.AccessShiftMath=Object.freeze({clamp,OneEuro,PointerFilter,tremor,colorMatrix,svgMatrix,settings,defaults});
})();
