"""The live 3D colony graph — a self-contained, dependency-free page.

Renders the engine's activity as a rotating 3D "living colony": foragers spawn,
forage (think), bring home harvests (outputs), lay pheromone (knowledge), and
die (prune). Seeded from ``/graph/state`` then updated live from ``/events``.
Ant-colony display names sit over the real node ids; click a node to reveal the
real thing. No build chain, no CDN.
"""
from __future__ import annotations


def page() -> str:
    return _HTML


_HTML = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Ormica — Live Colony</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root{--bg:#080b12;--root:#f4b942;--dept:#38e2c8;--agent:#5b9dff;
    --know:#a3e635;--out:#f472b6;--msg:#f59e0b;--text:#c9d4e3;--muted:#5f7088}
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;color:var(--text);overflow:hidden;
    font-family:ui-sans-serif,-apple-system,"Segoe UI",sans-serif;
    background:
      radial-gradient(ellipse at 50% 46%,transparent 30%,rgba(0,0,0,.62) 100%),
      radial-gradient(ellipse at 44% 34%,rgba(66,104,190,.12),transparent 60%),
      radial-gradient(ellipse at 72% 70%,rgba(90,70,150,.07),transparent 58%),
      radial-gradient(ellipse at 50% 46%,#0b1526 0%,#060c18 55%,#01030a 100%)}
  #hud{position:fixed;top:0;left:0;right:0;height:50px;display:flex;align-items:center;
    gap:15px;padding:0 16px;z-index:6;background:linear-gradient(180deg,rgba(6,9,16,.92),rgba(6,9,16,.35) 75%,transparent)}
  .brand{font-weight:600;letter-spacing:.4px;font-size:11.5px}.brand b{color:var(--root)}
  .blink{animation:blink 1.1s infinite}@keyframes blink{0%,100%{opacity:1}50%{opacity:.12}}
  .stat{display:flex;flex-direction:column;line-height:1.05}
  .stat .n{font-size:12px;font-weight:700;font-variant-numeric:tabular-nums}
  .stat .l{font-size:7px;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}
  .n.agents{color:var(--agent)}.n.know{color:var(--know)}.n.out{color:var(--out)}
  .n.energy{color:var(--root)}.n.eps{color:var(--dept)}
  .mode{margin-left:auto;font-size:10px;padding:3px 10px;border-radius:12px;cursor:pointer;user-select:none;
    background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.09);color:var(--text)}
  .mode:hover{background:rgba(255,255,255,.13)}
  #hud a{margin-left:12px;color:var(--muted);text-decoration:none;font-size:12px}#hud a:hover{color:var(--text)}
  #tabs{position:fixed;top:50px;left:0;right:346px;z-index:6;display:flex;flex-wrap:wrap;gap:5px;padding:6px 16px}
  .tab{font-size:9px;padding:3px 8px;border-radius:12px;cursor:pointer;user-select:none;
    background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.06);color:var(--muted)}
  .tab:hover{color:var(--text)}
  .tab.on{color:#08111a;font-weight:700;border-color:transparent}
  canvas{position:fixed;inset:0;display:block}
  #log{position:fixed;top:56px;right:0;bottom:0;width:340px;z-index:5;
    background:transparent;border-left:1px solid rgba(150,170,200,.05);display:flex;flex-direction:column}
  #ins{padding:10px 14px;border-bottom:1px solid rgba(150,170,200,.08)}
  #ins h3,#log h3{margin:0 0 6px;font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted)}
  #ins .i{font-size:11px;padding:2px 0;color:#96a2b4}#ins .i b{color:var(--root)}
  #logwrap{flex:1;display:flex;flex-direction:column;min-height:0;padding:10px 14px}
  #rows{flex:1;overflow:hidden;font:10px/1.5 ui-monospace,"SF Mono",monospace;opacity:.62}
  #rows .r{display:flex;gap:7px;padding:2px 0;opacity:0;animation:in .3s forwards}
  @keyframes in{to{opacity:1}}
  #rows .d{flex:none;width:7px;height:7px;border-radius:50%;margin-top:5px}
  #rows .k{flex:none;width:78px;color:var(--muted)}
  #rows .m{color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  #legend{position:fixed;left:16px;bottom:14px;z-index:5;display:flex;gap:15px;font-size:11px;
    color:var(--muted);background:rgba(12,18,30,.6);padding:8px 12px;border-radius:8px;backdrop-filter:blur(6px)}
  #legend i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;vertical-align:middle}
  #tip{position:fixed;z-index:8;pointer-events:none;background:rgba(12,18,30,.95);
    border:1px solid rgba(150,170,200,.15);border-radius:6px;padding:5px 9px;font-size:12px;display:none}
  #tip .s{color:var(--muted);font-size:11px}
  #detail{position:fixed;left:16px;top:104px;width:320px;max-height:70vh;overflow:auto;z-index:9;
    display:none;background:rgba(12,18,30,.97);border:1px solid rgba(150,170,200,.18);
    border-radius:10px;padding:14px 16px;box-shadow:0 12px 40px rgba(0,0,0,.5)}
  #detail .close{float:right;cursor:pointer;color:var(--muted)}
  #detail .ph{font-size:20px;font-weight:700}
  #detail .kv{font-size:12px;color:var(--muted);margin:2px 0}
  #detail .kv b{color:var(--text);font-weight:600}
  #detail .out{margin-top:8px;padding:8px;background:rgba(255,255,255,.03);border-radius:6px;
    font:12px/1.5 ui-monospace,monospace;white-space:pre-wrap;color:#dbe4f0}
</style></head><body>
<div id="hud">
  <div class="brand"><span class="blink" style="color:var(--root)">◆</span> <b>ORMICA</b> · live colony</div>
  <div class="stat"><span class="n agents" id="s-agents">0</span><span class="l">foragers</span></div>
  <div class="stat"><span class="n know" id="s-know">0</span><span class="l">pheromone</span></div>
  <div class="stat"><span class="n out" id="s-out">0</span><span class="l">harvests</span></div>
  <div class="stat"><span class="n energy" id="s-energy">0</span><span class="l">energy (tok)</span></div>
  <div class="stat"><span class="n eps" id="s-eps">0</span><span class="l">events/s</span></div>
  <div class="mode" id="mode">✋ move</div>
  <a href="/">← dashboard</a>
</div>
<div id="tabs"></div>
<canvas id="cv"></canvas>
<aside id="log">
  <div id="ins"><h3>what to look at</h3><div id="insrows"><div class="i">watching…</div></div></div>
  <div id="logwrap"><h3>live log</h3><div id="rows"></div></div>
</aside>
<div id="legend">
  <span><i style="background:#f4b942"></i>queen</span>
  <span><i style="background:#38e2c8"></i>nest</span>
  <span><i style="background:#5b9dff"></i>forager</span>
  <span><i style="background:#a3e635"></i>pheromone</span>
  <span><i style="background:#f472b6"></i>harvest</span>
  <span style="color:#3a4a60">· ants crawl · fat abdomen = more work done · toggle move/rotate · drag · scroll zoom · click</span>
</div>
<div id="tip"></div>
<div id="detail"></div>
<script>
const CV=document.getElementById('cv'),X=CV.getContext('2d');
const COL={root:'#f4b942',dept:'#38e2c8',agent:'#5b9dff',knowledge:'#a3e635',output:'#f472b6',msg:'#f59e0b'};
const RAD={root:16,dept:11,agent:6,knowledge:5,output:7};
let W=0,H=0,DPR=Math.min(devicePixelRatio||1,2);
function resize(){W=innerWidth;H=innerHeight;CV.width=W*DPR;CV.height=H*DPR;X.setTransform(DPR,0,0,DPR,0,0);}
addEventListener('resize',resize);resize();
const now=()=>performance.now();

// ant-colony display name over the real node
function nameFor(n){
  if(n.kind==='root')return'Queen';if(n.kind==='dept')return'Nest';
  if(n.kind==='knowledge')return'Pheromone';if(n.kind==='output')return'Harvest';
  const r=(n.role||'').toLowerCase();
  if(r.includes('scout')||r.includes('research'))return'Scout';
  if(r.includes('worker'))return'Worker';return'Forager';
}

// --- 3D camera (user-driven: drag rotate, shift-drag pan, scroll zoom) ---
const LOGW=340,TOPH=100;                 // right log rail + top bars → center in the rest
let yaw=.3,pitch=-.35,camDist=900,focal=800,panX=0,panY=0,userView=false,
    dragging=false,panning=false,moved=false,lastX=0,lastY=0,autorot=false;
function vcx(){return (W-LOGW)/2+panX;}
function vcy(){return TOPH+(H-TOPH)/2+panY;}
function project(x,y,z){const cy=Math.cos(yaw),sy=Math.sin(yaw);
  const x1=x*cy-z*sy,z1=x*sy+z*cy,cp=Math.cos(pitch),sp=Math.sin(pitch);
  const y1=y*cp-z1*sp,z2=y*sp+z1*cp;let zc=camDist-z2;if(zc<1)zc=1;
  const sc=focal/zc;return{sx:vcx()+x1*sc,sy:vcy()+y1*sc,sc,z:z2};}
let lastInteract=0;                       // idle auto-rotate pauses while you interact
let mode='move';const modeEl=document.getElementById('mode');
modeEl.onclick=()=>{mode=mode==='move'?'rotate':'move';modeEl.textContent=mode==='move'?'✋ move':'⟳ rotate';};
CV.style.cursor='grab';
CV.oncontextmenu=e=>e.preventDefault();
CV.addEventListener('mousedown',e=>{dragging=true;moved=false;userView=true;lastInteract=now();
  const flip=e.shiftKey||e.button===1||e.button===2;   // mode toggle sets default; modifier flips
  panning=flip?(mode!=='move'):(mode==='move');
  lastX=e.clientX;lastY=e.clientY;CV.style.cursor=panning?'move':'grabbing';});
addEventListener('mouseup',()=>{dragging=false;panning=false;CV.style.cursor='grab';});
CV.addEventListener('mousemove',e=>{if(!dragging)return;lastInteract=now();
  const dx=e.clientX-lastX,dy=e.clientY-lastY;
  if(Math.abs(dx)+Math.abs(dy)>3)moved=true;
  if(panning){panX+=dx;panY+=dy;}
  else{yaw+=dx*.008;pitch=Math.max(-1.4,Math.min(1.4,pitch+dy*.008));}
  lastX=e.clientX;lastY=e.clientY;});
CV.addEventListener('wheel',e=>{e.preventDefault();userView=true;lastInteract=now();  // focal fixed → real zoom
  camDist=Math.max(300,Math.min(2400,camDist+e.deltaY*.9));},{passive:false});

const nodes=new Map(),edges=new Map(),pulses=[];
const ekey=(s,t,k)=>s+'>'+t+':'+k;
function addNode(id,label,kind,role){if(nodes.has(id))return nodes.get(id);const R=150;
  const n={id,label,kind,role:role||'',x:(Math.random()-.5)*R,y:(Math.random()-.5)*R,z:(Math.random()-.5)*R,
    vx:0,vy:0,vz:0,born:now(),think:0,dying:0,energy:0,lastText:'',text:'',owner:'',risk:false,
    head:0,_psx:0,_psy:0,_sx:0,_sy:0,_sc:1,_z:0};nodes.set(id,n);return n;}
function addEdge(s,t,kind){const k=ekey(s,t,kind);if(!edges.has(k)&&nodes.has(s)&&nodes.has(t))edges.set(k,{s,t,kind});}
function subtree(id){const kill=new Set([id]),st=[id];while(st.length){const c=st.pop();
  for(const e of edges.values())if(e.kind==='spawn'&&e.s===c&&!kill.has(e.t)){kill.add(e.t);st.push(e.t);}}return kill;}
function killNode(id){nodes.delete(id);for(const[k,e]of edges)if(e.s===id||e.t===id)edges.delete(k);
  const o='o:'+id;if(nodes.has(o))killNode(o);}
function pulse(s,t,kind){pulses.push({s,t,kind,t0:now()});}
function flash(id){const n=nodes.get(id);if(n)n.think=now();}

fetch('/graph/state').then(r=>r.json()).then(d=>{d.nodes.forEach(n=>addNode(n.id,n.label,n.kind,n.role));
  d.edges.forEach(e=>addEdge(e.s,e.t,e.kind));}).catch(()=>{});

// --- filters ---
const FILTERS=[['all','all','#8fa3bd'],['queen','queen',COL.root],['nests','nests',COL.dept],
  ['agents','foragers',COL.agent],['harvest','harvests',COL.output],['pheromone','pheromone',COL.knowledge],
  ['hi','high-energy','#f4b942'],['lo','low-energy','#5b9dff'],['recent','new','#e8eefc'],
  ['isolated','isolated','#8899aa'],['risk','at-risk','#f87171']];
let filter='all';const tabsEl=document.getElementById('tabs');
FILTERS.forEach(([id,label,col])=>{const b=document.createElement('div');b.className='tab'+(id==='all'?' on':'');
  b.textContent=label;b.dataset.id=id;b.dataset.col=col;if(id==='all')b.style.background=col;
  b.onclick=()=>{filter=id;[...tabsEl.children].forEach(x=>{const on=x.dataset.id===id;
    x.classList.toggle('on',on);x.style.background=on?x.dataset.col:'';});};
  tabsEl.appendChild(b);});
let hiThresh=1,loThresh=0,connSet=new Set();
function matchF(n){switch(filter){
  case'queen':return n.kind==='root';case'nests':return n.kind==='dept';
  case'agents':return n.kind==='agent';case'harvest':return n.kind==='output';
  case'pheromone':return n.kind==='knowledge';
  case'hi':return n.kind==='agent'&&n.energy>=hiThresh;
  case'lo':return n.kind==='agent'&&n.energy<=loThresh;
  case'recent':return now()-n.born<8000;
  case'isolated':return !connSet.has(n.id);
  case'risk':return n.risk;default:return true;}}

// --- live stream ---
let evTotal=0,evWindow=[],totalEnergy=0;
const cnt={fail:0,retry:0,death:0,harvest:0};
const rows=document.getElementById('rows');
const LOGCOL={'node.spawned':'#5b9dff','node.pruned':'#f87171','memory.write':'#a3e635',
  'memory.read':'#7dd3fc','think.recorded':'#e5e7eb','message.sent':'#f59e0b',
  'task.done':'#38e2c8','task.failed':'#f87171','verify.retry':'#fbbf24','verify.failed':'#f87171'};
function log(type,msg){const r=document.createElement('div');r.className='r';
  r.innerHTML='<span class="d" style="background:'+(LOGCOL[type]||'#5f7088')+'"></span><span class="k">'+
    type.replace(/^[a-z]+\./,'')+'</span><span class="m"></span>';
  r.querySelector('.m').textContent=msg;rows.insertBefore(r,rows.firstChild);
  while(rows.childElementCount>90)rows.removeChild(rows.lastChild);}
const short=id=>(id||'').slice(0,6);
function kindByDepth(d){return d===0?'root':d===1?'dept':'agent';}

const es=new EventSource('/events');
es.onmessage=ev=>{let e;try{e=JSON.parse(ev.data);}catch(_){return;}
  const p=e.payload||{};evTotal++;evWindow.push(now());
  switch(e.type){
    case'node.spawned':addNode(p.node_id,p.name,kindByDepth(p.depth),p.role);
      if(p.parent_id)addEdge(p.parent_id,p.node_id,'spawn');flash(p.node_id);
      log(e.type,(p.parent_name||'?')+' → '+p.name);break;
    case'node.pruned':{const s=subtree(p.node_id);for(const id of s){const n=nodes.get(id);if(n)n.dying=now();}
      cnt.death++;log(e.type,p.name+' (-'+p.removed+')');break;}
    case'memory.write':{const kid='k:'+p.key;addNode(kid,p.key,'knowledge');addEdge(p.node,kid,'memory');
      pulse(p.node,kid,'memory');log(e.type,short(p.node)+' ✎ '+p.key);break;}
    case'memory.read':if(p.key){pulse(p.node,'k:'+p.key,'read');log(e.type,short(p.node)+' → '+p.key);}
      else{flash(p.node);log(e.type,short(p.node)+' ?'+(p.query||''));}break;
    case'think.recorded':{const a=nodes.get(p.node_id);if(a){flash(p.node_id);a.energy+=(p.tokens_used||0);
      totalEnergy+=(p.tokens_used||0);a.lastText=p.response_content||'';
      if(a.lastText){const oid='o:'+p.node_id;const o=addNode(oid,'harvest','output');o.text=a.lastText;
        o.owner=p.node_id;addEdge(p.node_id,oid,'output');pulse(p.node_id,oid,'memory');cnt.harvest++;}}
      log(e.type,short(p.node_id)+' “'+(p.response_content||'').slice(0,30)+'”');break;}
    case'message.sent':addEdge(p.sender,p.recipient,'msg');pulse(p.sender,p.recipient,'msg');
      log(e.type,short(p.sender)+' ✉ '+short(p.recipient));break;
    case'task.failed':{const n=[...nodes.values()].find(x=>x.label===p.target);if(n)n.risk=true;cnt.fail++;
      log(e.type,(p.target||'')+' failed');break;}
    case'verify.retry':cnt.retry++;log(e.type,summary(p));break;
    case'verify.failed':cnt.fail++;log(e.type,summary(p));break;
    default:log(e.type,summary(p));}
};
function summary(p){return p.name||p.task_id||p.target||'';}

// --- physics + render (3D) ---
function step(){const N=[...nodes.values()];
  for(const n of N){n.vx*=.86;n.vy*=.86;n.vz*=.86;}
  for(let i=0;i<N.length;i++)for(let j=i+1;j<N.length;j++){const a=N[i],b=N[j];
    let dx=a.x-b.x,dy=a.y-b.y,dz=a.z-b.z,d2=dx*dx+dy*dy+dz*dz||1;
    if(d2<160000){const f=2000/d2,d=Math.sqrt(d2);dx/=d;dy/=d;dz/=d;
      a.vx+=dx*f;a.vy+=dy*f;a.vz+=dz*f;b.vx-=dx*f;b.vy-=dy*f;b.vz-=dz*f;}}
  for(const e of edges.values()){const a=nodes.get(e.s),b=nodes.get(e.t);if(!a||!b)continue;
    const rest=e.kind==='spawn'?70:e.kind==='output'?38:e.kind==='memory'?46:120;
    const k=e.kind==='spawn'?.02:e.kind==='output'?.02:e.kind==='memory'?.012:.004;
    let dx=b.x-a.x,dy=b.y-a.y,dz=b.z-a.z,d=Math.hypot(dx,dy,dz)||1,f=(d-rest)*k;
    dx/=d;dy/=d;dz/=d;a.vx+=dx*f;a.vy+=dy*f;a.vz+=dz*f;b.vx-=dx*f;b.vy-=dy*f;b.vz-=dz*f;}
  for(const n of N){n.vx+=-n.x*.0022;n.vy+=-n.y*.0022;n.vz+=-n.z*.0022;
    n.x+=Math.max(-9,Math.min(9,n.vx));n.y+=Math.max(-9,Math.min(9,n.vy));n.z+=Math.max(-9,Math.min(9,n.vz));}
  // recenter on the centroid so the cloud always sits at the view center
  // (never drifts right under the log panel), regardless of force imbalance
  let mx=0,my=0,mz=0;for(const n of N){mx+=n.x;my+=n.y;mz+=n.z;}
  if(N.length){mx/=N.length;my/=N.length;mz/=N.length;
    for(const n of N){n.x-=mx;n.y-=my;n.z-=mz;}}
  yaw+=.003;}   // always spinning on its own; you can still drag/move/rotate on top
function fog(sc){return Math.max(.8,Math.min(1,(sc-.15)/.55));}
function hexagon(cx,cy,r){X.beginPath();for(let i=0;i<6;i++){const a=Math.PI/3*i-Math.PI/2;
  const px=cx+Math.cos(a)*r,py=cy+Math.sin(a)*r;i?X.lineTo(px,py):X.moveTo(px,py);}X.closePath();}
// draw a stylised ant, nose pointing along +x (rotate to heading). ``fed`` (>=1)
// swells the abdomen so a hard-working forager literally carries more mass.
function ant(cx,cy,s,a,col,alpha,fed){
  fed=fed||1;X.save();X.translate(cx,cy);X.rotate(a||0);
  X.lineCap='round';X.strokeStyle=col;X.fillStyle=col;
  const t=now()*.012;
  X.globalAlpha=alpha*.9;X.lineWidth=Math.max(.4,s*.18);
  for(let i=0;i<3;i++){const bx=(i-1)*s*.5,sw=Math.sin(t+i*1.7)*.28;    // 3 leg pairs, walking
    for(const sd of[-1,1]){X.beginPath();X.moveTo(bx,0);
      X.lineTo(bx+Math.cos(1.2+sw)*s*.6,sd*Math.sin(1.2+sw)*s*1.3);X.stroke();}}
  for(const sd of[-1,1]){X.beginPath();X.moveTo(s*1.15,0);             // antennae
    X.lineTo(s*1.9,sd*s*.8);X.stroke();}
  X.globalAlpha=alpha;
  const seg=(x,rx,ry)=>{X.beginPath();X.ellipse(x,0,rx,ry,0,0,7);X.fill();};
  const ab=s*.72*fed;                  // abdomen radius — grows a lot with task energy
  seg(-(s*.45+ab*.85),ab,ab*.82);      // abdomen trails behind, swelling backward
  seg(0,s*.55,s*.5);                   // thorax (middle, legs attach here)
  seg(s*1.05,s*.5,s*.46);              // head (front, antennae)
  X.restore();}
function draw(){X.clearRect(0,0,W,H);const t=now();const N=[...nodes.values()];
  // cull the dead
  for(const n of N)if(n.dying&&t-n.dying>800)killNode(n.id);
  for(const n of N){const p=project(n.x,n.y,n.z);n._sx=p.sx;n._sy=p.sy;n._sc=p.sc;n._z=p.z;}
  connSet.clear();for(const e of edges.values()){connSet.add(e.s);connSet.add(e.t);}  // for 'isolated' filter
  // keep the DENSE BODY centered in the LEFT region every frame. Use the median
  // node position (robust to a few nodes flung far out) — bbox-centering let the
  // core sink to the bottom. Rotate/zoom stay user-controlled.
  if(!userView&&N.length){const xs=[],ys=[];for(const n of N){xs.push(n._sx);ys.push(n._sy);}
    xs.sort((a,b)=>a-b);ys.sort((a,b)=>a-b);const md=k=>k[k.length>>1];
    const mx=md(xs),my=md(ys),tcx=(W-LOGW)/2,tcy=TOPH+(H-TOPH)/2;
    panX+=(tcx-mx)*.2;panY+=(tcy-my)*.2;                     // recenter on the median (until you grab it)
    const lo=Math.floor(xs.length*.1),hi=Math.floor(xs.length*.9);
    const over=Math.max(((xs[hi]-xs[lo])||1)/((W-LOGW)*.7),((ys[hi]-ys[lo])||1)/((H-TOPH)*.7));
    camDist+=(camDist*over-camDist)*.06;camDist=Math.max(300,Math.min(2400,camDist));}
  const rt=[...nodes.values()].find(n=>n.kind==='root');
  const cx=rt?rt._sx:(W-LOGW)/2,cy=rt?rt._sy:TOPH+(H-TOPH)/2;
  for(const e of edges.values()){const a=nodes.get(e.s),b=nodes.get(e.t);if(!a||!b)continue;
    const dim=(filter!=='all'&&!(matchF(a)||matchF(b)))?.12:1;
    const al=fog((a._sc+b._sc)/2)*(e.kind==='memory'?.6:e.kind==='output'?.6:e.kind==='msg'?.7:.45)*dim;
    const c=e.kind==='memory'?'163,230,53':e.kind==='output'?'244,114,182':e.kind==='msg'?'245,158,11':'150,170,200';
    const md=Math.hypot((a._sx+b._sx)/2-cx,(a._sy+b._sy)/2-cy);
    X.lineWidth=Math.max(.28,.95-md/320);        // spider-web: thinner the farther from the Queen
    X.beginPath();X.moveTo(a._sx,a._sy);X.lineTo(b._sx,b._sy);X.strokeStyle='rgba('+c+','+al+')';X.stroke();}
  for(let i=pulses.length-1;i>=0;i--){const pl=pulses[i],a=nodes.get(pl.s),b=nodes.get(pl.t);
    const age=(t-pl.t0)/900;if(age>=1||!a||!b){pulses.splice(i,1);continue;}
    const p=project(a.x+(b.x-a.x)*age,a.y+(b.y-a.y)*age,a.z+(b.z-a.z)*age);
    X.beginPath();X.arc(p.sx,p.sy,3.2*p.sc,0,7);
    X.fillStyle=pl.kind==='memory'?COL.knowledge:pl.kind==='msg'?COL.msg:'#7dd3fc';X.globalAlpha=1-age;X.fill();X.globalAlpha=1;}
  N.sort((a,b)=>a._z-b._z);
  for(const n of N){const c=COL[n.kind]||'#89a';let r=(RAD[n.kind]||6)*n._sc;
    const grow=Math.min(1,(t-n.born)/350);r*=(.3+.7*grow);
    let dp=fog(n._sc);if(n.dying)dp*=Math.max(0,1-(t-n.dying)/800),r*=Math.max(.2,1-(t-n.dying)/800);
    if(filter!=='all'&&!matchF(n))dp*=.12;
    X.globalAlpha=dp;
    // heading: point the ant along its screen-space travel (the colony keeps drifting/spinning)
    const hdx=n._sx-(n._psx||n._sx),hdy=n._sy-(n._psy||n._sy);
    if(hdx*hdx+hdy*hdy>.35)n.head=Math.atan2(hdy,hdx);n._psx=n._sx;n._psy=n._sy;
    if(n.think&&t-n.think<650){const a=1-(t-n.think)/650;X.beginPath();X.arc(n._sx,n._sy,r+6+a*10,0,7);
      X.strokeStyle='rgba(255,255,255,'+(a*.6)+')';X.lineWidth=1.5;X.stroke();}
    X.shadowBlur=0;X.fillStyle=c;X.strokeStyle=c;   // crisp shapes, no glow
    if(n.kind==='knowledge'){X.save();X.translate(n._sx,n._sy);X.rotate(.785);X.fillRect(-r,-r,r*2,r*2);X.restore();}
    else if(n.kind==='output'){hexagon(n._sx,n._sy,r);X.fill();}
    else{ // root / dept / agent → a TINY crawling ant; abdomen swells with task load
      const fed=.8+Math.min(2.8,Math.log2(1+n.energy)/2.2);   // energy → abdomen mass (wide, obvious range)
      const s=(n.kind==='root'?r*.5:n.kind==='dept'?r*.46:r*.42);
      if(s<1.5){X.beginPath();X.arc(n._sx,n._sy,Math.max(1,r*.6),0,7);X.fill();}   // LOD: far/small → dot
      else ant(n._sx,n._sy,s,n.head,c,dp,fed);}
    X.shadowBlur=0;
    if((n.kind==='root'||n.kind==='dept')&&dp>.35){X.globalAlpha=dp*.8;X.fillStyle='#b7c2d2';X.font='8px ui-sans-serif';
      X.textAlign='center';X.fillText(nameFor(n),n._sx,n._sy-r-5);X.globalAlpha=dp;}}
  X.globalAlpha=1;}
function loop(){step();draw();requestAnimationFrame(loop);}loop();

// --- stats + insights ---
setInterval(()=>{let a=0,k=0,o=0,es=[];for(const n of nodes.values()){
  if(n.kind==='agent'){a++;es.push(n.energy);}else if(n.kind==='knowledge')k++;else if(n.kind==='output')o++;}
  es.sort((x,y)=>y-x);hiThresh=es.length?(es[Math.floor(es.length*.2)]||1):1;
  loThresh=es.length?(es[Math.floor(es.length*.8)]||0):0;
  document.getElementById('s-agents').textContent=a;document.getElementById('s-know').textContent=k;
  document.getElementById('s-out').textContent=o;document.getElementById('s-energy').textContent=totalEnergy;
  const cut=now()-1000;evWindow=evWindow.filter(x=>x>cut);document.getElementById('s-eps').textContent=evWindow.length;
  // insights: what to look at / improve
  const busy=[...nodes.values()].filter(n=>n.kind==='agent').sort((x,y)=>y.energy-x.energy)[0];
  const ins=[];
  if(cnt.fail)ins.push('<div class="i">⚠ <b>'+cnt.fail+'</b> failures — review those branches</div>');
  if(cnt.retry)ins.push('<div class="i">↻ <b>'+cnt.retry+'</b> verify retries — outputs needed correcting</div>');
  ins.push('<div class="i">🪶 <b>'+o+'</b> harvests brought home</div>');
  if(busy&&busy.energy)ins.push('<div class="i">🔥 busiest: <b>'+busy.label+'</b> ('+busy.energy+' tok)</div>');
  ins.push('<div class="i">🐜 <b>'+a+'</b> foragers · <b>'+cnt.death+'</b> expired</div>');
  document.getElementById('insrows').innerHTML=ins.join('');
},500);

// --- tooltip + click-to-reveal-real ---
const tip=document.getElementById('tip'),detail=document.getElementById('detail');
function hit(mx,my){let best=null,bd=1e9;for(const n of nodes.values()){
  const d=Math.hypot(n._sx-mx,n._sy-my);if(d<((RAD[n.kind]||6)*n._sc)+12&&d<bd){bd=d;best=n;}}return best;}
CV.addEventListener('mousemove',ev=>{if(dragging)return;lastInteract=now();const n=hit(ev.clientX,ev.clientY);
  if(n){tip.style.display='block';tip.style.left=(ev.clientX+12)+'px';tip.style.top=(ev.clientY+12)+'px';
    tip.innerHTML='<b>'+nameFor(n)+'</b><div class="s">click to reveal</div>';}else tip.style.display='none';});
CV.addEventListener('click',ev=>{if(moved)return;const n=hit(ev.clientX,ev.clientY);if(!n){detail.style.display='none';return;}
  const owner=n.owner?nodes.get(n.owner):null;
  let h='<span class="close" onclick="document.getElementById(\'detail\').style.display=\'none\'">✕</span>';
  h+='<div class="ph" style="color:'+(COL[n.kind]||'#89a')+'">'+nameFor(n)+'</div>';
  h+='<div class="kv">real: <b>'+esc(n.label)+'</b></div>';
  h+='<div class="kv">id: <b>'+n.id.replace(/^[ko]:/,'')+'</b></div>';
  h+='<div class="kv">kind: <b>'+n.kind+'</b></div>';
  if(n.role)h+='<div class="kv">role: <b>'+esc(n.role)+'</b></div>';
  if(n.kind==='agent')h+='<div class="kv">energy: <b>'+n.energy+' tokens</b></div>';
  if(n.kind==='output'&&owner)h+='<div class="kv">brought by: <b>'+esc(owner.label)+'</b></div>';
  const body=n.kind==='output'?n.text:(n.lastText||'');
  if(body)h+='<div class="kv" style="margin-top:8px">output:</div><div class="out">'+esc(body)+'</div>';
  detail.innerHTML=h;detail.style.display='block';});
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
</script></body></html>"""
