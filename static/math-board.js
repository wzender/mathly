/* Mathly's sketch board. On a desktop screen it sits beside the exercise (the student turns it on from the sheet's
   header; this browser remembers the choice). On a phone or a tablet it opens full screen over the exercise, from
   the same button, and closes back to the question. Used by a skill's exercise, the practice exam, the unit quiz,
   and the phone's answer to a photo request from the computer (openFull). Each question keeps its own sketch for
   as long as the page is open. Nothing is sent anywhere unless the student hands it in.

   Everything on the board is an element that can be moved or erased: a pen stroke (with a pen's pressure),
   a straight line, a circle (dragged from the center), and a copy of the question (its text and figures).
   Line ends and circle centers snap to the ends and centers already drawn, so a triangle closes neatly;
   lines that meet that way move together. The eraser removes the lines and circles it touches and cuts pen strokes;
   it leaves the question's copy alone (select it and delete it instead).
   The paper is endless downwards: the mouse wheel over the board scrolls it, and so do two fingers on a touch
   screen (one finger draws). Once a pen has touched the screen, a single finger is ignored: a hand resting on it.
   A sheet can let the board hand in a question's answer (the unit quiz): the sketch becomes a picture. */
(()=>{
const PREF="mathly.board";
const isOn=()=>{ try{ return localStorage.getItem(PREF)==="on"; }catch{ return false; } };
const setOn=on=>{ try{ localStorage.setItem(PREF,on?"on":"off"); }catch{} };

const INKS=[["#1B2140","שחור"],["#2563D9","כחול"],["#D3455B","אדום"]];
const ERASERS=[[16,"קטן"],[40,"בינוני"],[90,"גדול"]];
const TOOLS=[["move","✋","הזזה"],["pen","✏️","עט"],["line","╱","קו ישר"],["circle","◯","עיגול"],["eraser","🧽","מחק"]];
const PEN=2.6, SHAPE=2.4, SNAP=12, GRAB=9, STEP=2, HISTORY=100;
const PAPER_INK="#1B2140", PAPER_FAINT="#C5CBDF", SELECT="#2563D9";
const FONT='500 17px Rubik, system-ui, "Segoe UI", sans-serif', LINE_H=27, CARD_PAD=14;

/* sketch key -> {marks, past}: marks are drawn in order; past holds copies of marks for undo */
const sketches=new Map(), images=new Map();
let el=null, canvas=null, ctx=null, key="", base="", pages=0, page=0, layer=null, source=null, hand=null, onPage=null;
let tool="pen", ink=INKS[0][0], eraser=ERASERS[1][0], sendLabel="";
let draft=null, drag=null, rub=null, selection=[];
let full=null;   // the board open full screen: {saved: the context to go back to, done: called when it closes}
const touches=new Map(); let pan=null, penSeen=false;
const desk=()=>matchMedia("(min-width:1000px) and (any-pointer:fine)").matches;   // the same test as math.css
const context=()=>({layer,base,pages,page,source,hand,onPage,sendLabel,key});
function restore(c){ ({layer,base,pages,page,source,hand,onPage,sendLabel,key}=c); }

const sketch=()=>{ if(!sketches.has(key)) sketches.set(key,{marks:[],past:[],y:0}); return sketches.get(key); };   // y: how far down the paper is scrolled
const marks=()=>sketch().marks;
const copy=list=>JSON.parse(JSON.stringify(list));
function remember(before=copy(marks())){ const s=sketch(); s.past.push(before); if(s.past.length>HISTORY) s.past.shift(); }
const shown=()=>!!el?.isConnected&&canvas.clientWidth>0;
const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
const same=(a,b)=>dist(a,b)<.5;

function build(){
  el=document.createElement("aside"); el.className="mx-board"; el.setAttribute("aria-label","לוח טיוטה");
  el.innerHTML=`<div class="mx-board-head"><b data-title>לוח טיוטה</b><button type="button" data-do="hide" class="mx-board-back">↩ חזרה לשאלה</button></div>
    <div class="mx-board-bar" role="toolbar" aria-label="כלי הלוח">
      <span class="mx-board-group">${TOOLS.map(([t,icon,name])=>`<button type="button" data-tool="${t}" aria-pressed="${t===tool}" title="${name}"><i aria-hidden="true">${icon}</i><span>${name}</span></button>`).join("")}</span>
      <span class="mx-board-group mx-board-inks">${INKS.map(([c,name])=>`<button type="button" data-ink="${c}" aria-pressed="${c===ink}" aria-label="${name}" title="${name}" style="--dot:${c}"></button>`).join("")}</span>
      <span class="mx-board-group mx-board-sizes">${ERASERS.map(([w,name])=>`<button type="button" data-eraser="${w}" aria-pressed="${w===eraser}" aria-label="מחק ${name}" title="מחק ${name}" style="--d:${Math.round(6+w/6)}px"></button>`).join("")}</span>
      <span class="mx-board-gap"></span>
      <button type="button" data-do="question" title="העתקת השאלה לראש הלוח"><i aria-hidden="true">📋</i><span>השאלה</span></button>
      <button type="button" data-do="undo" title="ביטול (Ctrl+Z)"><i aria-hidden="true">↶</i></button>
      <button type="button" data-do="clear" title="ניקוי הלוח"><i aria-hidden="true">🗑</i></button>
      <button type="button" data-do="hide" aria-label="סגירת הלוח" title="סגירת הלוח">✕</button>
    </div><div class="mx-board-row"><div class="mx-board-pages" role="tablist" aria-label="הדף של כל שאלה"></div>
      <button type="button" data-do="send" class="mx-board-send" hidden></button></div>
    <div class="mx-board-stage"><canvas></canvas>
      <button type="button" data-do="delete" class="mx-board-del" title="מחיקת מה שנבחר (Delete)" hidden>✕ מחיקה</button>
      <button type="button" data-do="top" class="mx-board-top" hidden>⇡ לראש הדף</button></div>`;
  canvas=el.querySelector("canvas"); ctx=canvas.getContext("2d");
  el.addEventListener("click",e=>{
    const b=e.target.closest("button"); if(!b) return;
    if(b.dataset.tool) setTool(b.dataset.tool);
    if(b.dataset.ink){ ink=b.dataset.ink; if(tool==="eraser"||tool==="move") setTool("pen"); pressed("[data-ink]",b); }
    if(b.dataset.eraser){ eraser=+b.dataset.eraser; setTool("eraser"); pressed("[data-eraser]",b); }
    if(b.dataset.page){ turn(+b.dataset.page); onPage?.(page); }
    const act=b.dataset.do;
    if(act==="undo") undo();
    if(act==="clear"&&marks().length){ remember(); marks().length=0; select([]); paint(); drawPages(); }
    if(act==="delete") removeSelection();
    if(act==="question") copyQuestion();
    if(act==="send") send();
    if(act==="top"){ sketch().y=0; paint(); }
    if(act==="hide") full?closeFull():toggle();
  });
  canvas.addEventListener("pointerdown",down);
  canvas.addEventListener("pointermove",move);
  canvas.addEventListener("pointerup",up);
  canvas.addEventListener("pointercancel",up);
  canvas.addEventListener("contextmenu",e=>e.preventDefault());   // the pen's side button: no browser menu over the board
  canvas.addEventListener("wheel",e=>{   // endless paper: scrolls down as far as needed, never above the top
    if(e.ctrlKey) return;   // the browser's zoom
    e.preventDefault(); const s=sketch(), dy=e.deltaMode===1?e.deltaY*24:e.deltaMode===2?e.deltaY*canvas.clientHeight:e.deltaY;
    s.y=Math.max(0,s.y+dy); paint();
  },{passive:false});
  new ResizeObserver(fit).observe(canvas);
  setTool(tool);
}
function pressed(sel,b){ el.querySelectorAll(sel).forEach(x=>x.setAttribute("aria-pressed",x===b)); }
function reset(){ draft=drag=rub=null; select([]); }
function setTool(t){
  tool=t; el.querySelectorAll("[data-tool]").forEach(x=>x.setAttribute("aria-pressed",x.dataset.tool===t));
  el.dataset.tool=t; if(t!=="move"&&selection.length){ select([]); paint(); }
  // the eraser's cursor is a ring its own size, so the student sees what it will wipe
  const r=eraser/2, svg=`<svg xmlns='http://www.w3.org/2000/svg' width='${eraser+2}' height='${eraser+2}'><circle cx='${r+1}' cy='${r+1}' r='${r}' fill='rgba(255,255,255,.35)' stroke='%231B2140' stroke-width='1.2'/></svg>`;
  canvas.style.cursor=t==="eraser"?`url("data:image/svg+xml,${svg.replace(/</g,"%3C").replace(/>/g,"%3E")}") ${r+1} ${r+1}, cell`:t==="move"?"default":"";
}
function select(list){ selection=list; }
function turn(p){ page=p; key=`${base}:${page}`; reset(); drawPages(); drawSend(); paint(); }
function drawSend(){
  const b=el.querySelector(".mx-board-send"); b.hidden=!hand; el.querySelector(".mx-board-row").hidden=pages<2&&!hand; if(!hand) return;
  b.disabled=false; b.innerHTML=`<i aria-hidden="true">📤</i><span>${sendLabel||`הגשה לשאלה ${page+1}`}</span>`; b.title=sendLabel||`הגשת הלוח כתשובה לשאלה ${page+1}`;
}
function drawPages(){
  const box=el.querySelector(".mx-board-pages"); el.querySelector(".mx-board-row").hidden=pages<2&&!hand;
  box.innerHTML=pages<2?"":`<span>שאלה</span>${Array.from({length:pages},(_,i)=>{
    const has=(sketches.get(`${base}:${i}`)?.marks||[]).length>0;
    return `<button type="button" role="tab" data-page="${i}" aria-selected="${i===page}" class="${has?"has":""}">${i+1}</button>`; }).join("")}`;
}

/* ---------- drawing ---------- */
function fit(){
  if(!shown()) return;
  const d=devicePixelRatio||1, w=Math.round(canvas.clientWidth*d), h=Math.round(canvas.clientHeight*d);
  if(canvas.width!==w||canvas.height!==h){ canvas.width=w; canvas.height=h; }
  paint();
}
function paint(){
  if(!ctx) return;
  const d=devicePixelRatio||1, y=sketch().y; ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,canvas.width,canvas.height); ctx.setTransform(d,0,0,d,0,-y*d);
  canvas.style.backgroundPosition=`0 ${-y}px`;   // the grid scrolls with the paper
  el.querySelector(".mx-board-top").hidden=y<1;
  marks().forEach(draw);
  if(draft?.kind==="circle") guide(draft);
  if(selection.length) outline(selection);
  const del=el.querySelector(".mx-board-del"); del.hidden=!selection.length||!!drag?.before;
  if(selection.length){ const [x0,y0]=edges(selection); del.style.left=`${Math.max(4,x0)}px`; const top=y0-y; del.style.top=`${top>40?top-36:Math.max(4,top+4)}px`; }
}
function draw(m){
  ctx.save(); ctx.strokeStyle=m.color; ctx.lineCap="round"; ctx.lineJoin="round";
  if(m.kind==="line"){ ctx.lineWidth=SHAPE; ctx.beginPath(); ctx.moveTo(...m.a); ctx.lineTo(...m.b); ctx.stroke(); }
  else if(m.kind==="circle"){ ctx.lineWidth=SHAPE; ctx.beginPath(); ctx.arc(m.a[0],m.a[1],dist(m.a,m.b),0,Math.PI*2); ctx.stroke(); }
  else if(m.kind==="card") card(m);
  else{ for(let i=1;i<m.pts.length;i++) segment(m,i); if(m.pts.length===1) segment(m,0); }
  ctx.restore();
}
// one piece of a pen stroke, from point i-1 to point i; a pen's pressure sets the width
function segment(m,i){
  const a=m.pts[Math.max(0,i-1)], b=m.pts[i];
  ctx.lineWidth=PEN*(.35+1.3*(a[2]+b[2])/2);
  ctx.beginPath(); ctx.moveTo(a[0],a[1]); ctx.lineTo(b[0]+(i?0:.01),b[1]); ctx.stroke();
}
// while a circle is dragged: its center and radius, faintly, so it can be placed exactly
function guide(m){
  ctx.save(); ctx.strokeStyle=ctx.fillStyle="rgb(27 33 64/.45)"; ctx.lineWidth=1; ctx.setLineDash([4,4]);
  ctx.beginPath(); ctx.moveTo(...m.a); ctx.lineTo(...m.b); ctx.stroke();
  ctx.setLineDash([]); ctx.beginPath(); ctx.arc(m.a[0],m.a[1],2.5,0,Math.PI*2); ctx.fill(); ctx.restore();
}
function card(m){
  ctx.fillStyle="#EEF1FB"; ctx.strokeStyle=PAPER_FAINT; ctx.lineWidth=1;
  ctx.beginPath(); ctx.roundRect(m.x,m.y,m.w,m.h,12); ctx.fill(); ctx.stroke();
  ctx.fillStyle=PAPER_INK; ctx.font=FONT; ctx.direction="rtl"; ctx.textAlign="right"; ctx.textBaseline="top";
  m.lines.forEach((line,i)=>ctx.fillText(line,m.x+m.w-CARD_PAD,m.y+CARD_PAD+i*LINE_H+4));
  for(const f of m.figs){ const img=picture(f.src); if(img.complete&&img.naturalWidth) ctx.drawImage(img,m.x+f.x,m.y+f.y,f.w,f.h); }
}
function picture(src){
  if(!images.has(src)){ const img=new Image(); img.onload=()=>paint(); img.src=src; images.set(src,img); }
  return images.get(src);
}
function box(m){
  if(m.kind==="card") return [m.x,m.y,m.x+m.w,m.y+m.h];
  if(m.kind==="circle"){ const r=dist(m.a,m.b); return [m.a[0]-r,m.a[1]-r,m.a[0]+r,m.a[1]+r]; }
  const pts=m.kind==="line"?[m.a,m.b]:m.pts, xs=pts.map(p=>p[0]), ys=pts.map(p=>p[1]);
  return [Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];
}
// the box around the elements, a little outside their ink
function edges(list){ const bs=list.map(box); return [Math.min(...bs.map(b=>b[0]))-6,Math.min(...bs.map(b=>b[1]))-6,Math.max(...bs.map(b=>b[2]))+6,Math.max(...bs.map(b=>b[3]))+6]; }
function outline(list){
  const [x0,y0,x1,y1]=edges(list);
  ctx.save(); ctx.strokeStyle=SELECT; ctx.lineWidth=1.5; ctx.setLineDash([6,4]); ctx.strokeRect(x0,y0,x1-x0,y1-y0); ctx.restore();
}

/* ---------- geometry ---------- */
function toSegment(p,a,b){
  const dx=b[0]-a[0], dy=b[1]-a[1], l=dx*dx+dy*dy, t=l?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/l)):0;
  return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);
}
// how far p is from the element's ink
function reach(m,p){
  if(m.kind==="line") return toSegment(p,m.a,m.b);
  if(m.kind==="circle") return Math.min(Math.abs(dist(p,m.a)-dist(m.a,m.b)),dist(p,m.a));
  if(m.kind==="card"){ const [x0,y0,x1,y1]=box(m); return p[0]>=x0&&p[0]<=x1&&p[1]>=y0&&p[1]<=y1?0:Infinity; }
  if(m.pts.length===1) return dist(p,m.pts[0]);
  let d=Infinity; for(let i=1;i<m.pts.length;i++) d=Math.min(d,toSegment(p,m.pts[i-1],m.pts[i])); return d;
}
const hit=p=>{ const all=marks(); for(let i=all.length-1;i>=0;i--) if(reach(all[i],p)<=GRAB) return all[i]; return null; };
const joints=m=>m.kind==="line"?[m.a,m.b]:m.kind==="circle"?[m.a]:[];
// an element and everything joined to it by a shared end or center: a triangle moves as one
function group(m){
  const out=new Set([m]), todo=[m];
  while(todo.length){ const cur=todo.pop();
    for(const o of marks()) if(!out.has(o)&&joints(cur).some(p=>joints(o).some(q=>same(p,q)))){ out.add(o); todo.push(o); } }
  return [...out];
}
// a line's ends and a circle's center pull to the ends and centers already on the board
function snap(p,skip){
  let best=null, d=SNAP;
  for(const m of marks()){ if(m===skip) continue; for(const q of joints(m)){ const k=dist(p,q); if(k<d){ d=k; best=q; } } }
  return best?[best[0],best[1]]:[p[0],p[1]];
}
function shift(m,dx,dy){
  const by=p=>{ p[0]+=dx; p[1]+=dy; };
  if(m.kind==="card"){ m.x+=dx; m.y+=dy; } else if(m.kind==="free") m.pts.forEach(by); else { by(m.a); by(m.b); }
}
// the eraser at p: lines and circles it touches go; pen strokes are cut; the question's copy stays
function rubOut(p){
  const r=eraser/2, all=marks(); let changed=false;
  for(let i=all.length-1;i>=0;i--){ const m=all[i];
    if(m.kind==="line"||m.kind==="circle"){ if(reach(m,p)<=r+SHAPE/2){ all.splice(i,1); changed=true; } continue; }
    if(m.kind!=="free") continue;
    const gone=m.pts.map(q=>dist(p,q)<=r+PEN); if(!gone.some(Boolean)) continue;
    const runs=[]; let run=[]; m.pts.forEach((q,k)=>{ if(gone[k]){ if(run.length) runs.push(run); run=[]; } else run.push(q); }); if(run.length) runs.push(run);
    all.splice(i,1,...runs.map(pts=>({kind:"free",color:m.color,pts}))); changed=true;
  }
  return changed;
}
// points along a to b, close enough that nothing between two of them is skipped
function along(a,b,step){ const n=Math.max(1,Math.ceil(dist(a,b)/step)), out=[]; for(let k=1;k<=n;k++) out.push([a[0]+(b[0]-a[0])*k/n,a[1]+(b[1]-a[1])*k/n,a[2]+((b[2]??a[2])-a[2])*k/n]); return out; }

/* ---------- the pointer ---------- */
const at=e=>{ const r=canvas.getBoundingClientRect(); return [e.clientX-r.left,e.clientY-r.top+sketch().y,e.pointerType==="pen"?e.pressure:.5]; };   // a point on the paper, not on the screen
const capture=id=>{ try{ canvas.setPointerCapture(id); }catch{} };   // a pointer the browser no longer knows: draw anyway
const fingersY=()=>{ let t=0; touches.forEach(p=>t+=p[1]); return t/touches.size; };
// a second finger came down: what the first one started is taken back, and the two scroll the paper
function stopLive(){
  const s=sketch();
  if(draft){ s.marks.splice(s.marks.indexOf(draft),1); s.past.pop(); draft=null; }
  if(rub){ s.marks=rub.before; rub=null; }
  if(drag){ if(drag.before) s.marks=s.past.pop(); drag=null; select([]); }
  paint();
}
function down(e){
  if(e.pointerType==="pen") penSeen=true;
  if(e.pointerType==="touch"){
    touches.set(e.pointerId,[e.clientX,e.clientY]); capture(e.pointerId); e.preventDefault();
    if(touches.size===2){ stopLive(); pan={y:fingersY(),s:sketch().y}; return; }
    if(touches.size>2||pan||penSeen) return;   // a hand resting on the screen while a pen writes
  }
  if(e.button!==0&&e.button!==5) return;   // 5: the pen's eraser end
  const p=at(e), use=e.button===5||(e.buttons&32)>0?"eraser":tool;
  capture(e.pointerId); e.preventDefault();
  if(use==="move"){
    const m=hit(p);
    if(!m){ select([]); return paint(); }
    if(!selection.includes(m)) select(group(m));
    drag={id:e.pointerId,last:p,before:null}; return paint();
  }
  if(use==="eraser"){ rub={id:e.pointerId,last:p,before:copy(marks()),changed:rubOut(p)}; return paint(); }
  remember();
  draft=use==="pen"?{kind:"free",color:ink,pts:[p]}:{kind:use,color:ink,a:snap(p),b:null};
  if(draft.b===null) draft.b=[...draft.a];
  draft.id=e.pointerId; marks().push(draft); paint();
}
function move(e){
  if(touches.has(e.pointerId)){
    touches.set(e.pointerId,[e.clientX,e.clientY]);
    if(pan){ if(touches.size>=2){ sketch().y=Math.max(0,pan.s-(fingersY()-pan.y)); paint(); } return; }
  }
  if(tool==="move"&&!drag&&!e.buttons) canvas.style.cursor=hit(at(e))?"move":"default";
  if(drag&&e.pointerId===drag.id){
    const p=at(e), dx=p[0]-drag.last[0], dy=p[1]-drag.last[1]; if(!dx&&!dy) return;
    if(!drag.before){ drag.before=true; remember(); }
    selection.forEach(m=>shift(m,dx,dy)); drag.last=p; return paint();
  }
  if(rub&&e.pointerId===rub.id){
    const p=at(e); for(const q of along(rub.last,p,eraser/4)) rub.changed=rubOut(q)||rub.changed;
    rub.last=p; return paint();
  }
  if(!draft||e.pointerId!==draft.id) return;
  if(draft.kind==="free"){
    const all=e.getCoalescedEvents?.();
    for(const c of all?.length?all:[e]){ const p=at(c); draft.pts.push(...along(draft.pts.at(-1),p,STEP)); }
    ctx.save(); ctx.strokeStyle=draft.color; ctx.lineCap=ctx.lineJoin="round";
    for(let i=Math.max(1,draft.drawn||1);i<draft.pts.length;i++) segment(draft,i);
    draft.drawn=draft.pts.length; ctx.restore(); return;
  }
  const p=at(e); draft.b=draft.kind==="line"?snap(p,draft):[p[0],p[1]]; paint();
}
function up(e){
  if(touches.delete(e.pointerId)&&pan){ if(!touches.size) pan=null; return; }
  if(drag&&e.pointerId===drag.id){ drag=null; return paint(); }
  if(rub&&e.pointerId===rub.id){ if(rub.changed) remember(rub.before); rub=null; paint(); return pages>1&&drawPages(); }
  if(!draft||e.pointerId!==draft.id) return;
  const m=draft; draft=null; delete m.id; delete m.drawn;
  if(m.kind!=="free"&&dist(m.a,m.b)<3){ marks().pop(); sketch().past.pop(); }   // a tap, not a shape
  paint(); if(pages>1) drawPages();
}
function undo(){ const s=sketch(); if(!s.past.length) return; s.marks=s.past.pop(); reset(); paint(); if(pages>1) drawPages(); }
function removeSelection(){
  if(!selection.length) return;
  remember(); const all=marks(); for(const m of selection) all.splice(all.indexOf(m),1);
  select([]); paint(); if(pages>1) drawPages();
}

/* ---------- the question's copy ---------- */
// the question's words, with each piece of math kept left to right and in one piece
function words(node){
  const out=[]; let word="";
  const flush=()=>{ if(word) out.push(word); word=""; };
  (function walk(n){
    for(const c of n.childNodes){
      if(c.nodeType===3){ for(const ch of c.textContent){ if(/\s/.test(ch)) flush(); else word+=ch; } }
      else if(c.nodeName==="BR"){ flush(); out.push("\n"); }
      else if(c.classList?.contains("m")) word+="⁦"+c.textContent.trim()+"⁩";   // math kept left to right, stuck to the brackets and marks around it
      else walk(c);
    }
  })(node);
  flush(); return out;
}
function wrap(tokens,width){
  ctx.save(); ctx.font=FONT; ctx.direction="rtl";
  const lines=[]; let line="";
  for(const t of tokens){
    if(t==="\n"){ lines.push(line); line=""; continue; }
    const next=line?line+" "+t:t;
    if(line&&ctx.measureText(next).width>width){ lines.push(line); line=t; } else line=next;
  }
  if(line) lines.push(line); ctx.restore(); return lines;
}
// a figure drawn for the dark sheet, redrawn in ink for the white board
function paperColor(c){
  const m=String(c).match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/); if(!m) return c;
  if(m[4]!==undefined&&+m[4]===0) return "none";
  const l=(.299*m[1]+.587*m[2]+.114*m[3])/255;
  return l>.55?PAPER_INK:l<.3?PAPER_FAINT:c;
}
const STYLE=["fill","stroke","stroke-width","stroke-dasharray","stroke-linecap","stroke-linejoin","opacity","font-size","font-family","font-weight","font-style","text-anchor","dominant-baseline"];
function paperFigure(svg){
  const r=svg.getBoundingClientRect(); if(!r.width||!r.height) return null;
  const clone=svg.cloneNode(true), from=[svg,...svg.querySelectorAll("*")], to=[clone,...clone.querySelectorAll("*")];
  from.forEach((n,i)=>{ const cs=getComputedStyle(n);
    for(const prop of STYLE){ let v=cs.getPropertyValue(prop); if(prop==="fill"||prop==="stroke") v=paperColor(v); if(v) to[i].style.setProperty(prop,v); } });
  clone.setAttribute("xmlns","http://www.w3.org/2000/svg"); clone.setAttribute("width",r.width); clone.setAttribute("height",r.height);
  clone.removeAttribute("class"); clone.style.background="none";
  return {src:"data:image/svg+xml;charset=utf-8,"+encodeURIComponent(new XMLSerializer().serializeToString(clone)),w:r.width,h:r.height};
}
function copyQuestion(){
  const q=source?.(page); if(!q||!shown()) return;
  const text=q.querySelector(".mx-uq-text")||q.querySelector(":scope > p");
  const W=Math.min(canvas.clientWidth-32,600), inner=W-2*CARD_PAD;
  const lines=text?wrap(words(text),inner):[];
  let y=CARD_PAD+lines.length*LINE_H+(lines.length?6:0);
  const figs=[];
  for(const svg of q.querySelectorAll("svg")){
    if(svg.closest("button")) continue;   // the answers' buttons are not part of the question
    const f=paperFigure(svg); if(!f) continue;
    const s=Math.min(1,inner/f.w), w=f.w*s, h=f.h*s;
    figs.push({src:f.src,x:(W-w)/2,y,w,h}); y+=h+8;
  }
  if(!lines.length&&!figs.length) return;
  remember();
  const m={kind:"card",x:canvas.clientWidth-16-W,y:sketch().y+16,w:W,h:y+CARD_PAD-(figs.length?8:0),lines,figs};
  marks().push(m); setTool("move"); select([m]); paint(); if(pages>1) drawPages();
}

/* ---------- handing in ---------- */
// the whole sketch as a picture on white paper: as wide as the board, as tall as what is drawn
function snapshot(){
  const all=marks(); if(!all.some(m=>m.kind!=="card")) return null;
  const [,y0,,y1]=edges(all), top=Math.max(0,y0-24), W=canvas.clientWidth, H=Math.min(y1+24-top,8000), k=2;
  const out=document.createElement("canvas"); out.width=W*k; out.height=Math.round(H*k);
  const keep=ctx; ctx=out.getContext("2d");
  try{ ctx.fillStyle="#fff"; ctx.fillRect(0,0,out.width,out.height); ctx.setTransform(k,0,0,k,0,-top*k); all.forEach(draw); }
  finally{ ctx=keep; }
  return new Promise(ok=>out.toBlob(ok,"image/png"));
}
async function send(){
  const b=el.querySelector(".mx-board-send"), p=page, say=t=>{ if(page===p) b.innerHTML=t; };
  const blob=await snapshot();
  if(!blob){ say(`<span>הלוח ריק: אין מה להגיש</span>`); return setTimeout(()=>page===p&&drawSend(),2500); }
  b.disabled=true; say(`<span>מגישים…</span>`);
  let r; try{ r=await hand(p,blob); }catch(e){ r={error:e.message}; }
  b.disabled=false; say(r?.error?`<span>⚠ ${r.error}</span>`:`<i aria-hidden="true">✓</i><span>${sendLabel?"נשלחה":`הוגשה לשאלה ${p+1}`}</span>`);
  if(r?.close&&full) return setTimeout(closeFull,900);   // done: back to the window that asked
  setTimeout(()=>page===p&&!b.disabled&&drawSend(),3000);
}

document.addEventListener("keydown",e=>{
  if(full&&e.key==="Escape"){ e.preventDefault(); e.stopImmediatePropagation(); return closeFull(); }   // back to the question, not out of it
  if(!shown()||e.target.closest?.("input,textarea,[contenteditable]")) return;
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="z"&&!e.shiftKey){ e.preventDefault(); undo(); }
  else if((e.key==="Delete"||e.key==="Backspace")&&selection.length){ e.preventDefault(); removeSelection(); }
});

/* Shows the board in the sheet's layer when the student has it on (a desktop screen), and takes it away when not.
   sketchKey names the sketch; with pages>1 (a sheet with several questions at once) the board has a tab per question.
   question(page) gives the element the question is shown in, for the board's copy of it; submit(page, picture)
   hands a page in and resolves to {error} or {}; turned(page) is told when the student picks another tab.
   On a phone nothing shows until the header's button opens the board full screen. */
function mount(sheetLayer,sketchKey,{pages:n=1,question=null,submit=null,turned=null}={}){
  const was=full?full.saved:context(), same=sketchKey===was.base&&n===was.pages;
  const next={layer:sheetLayer,source:question,hand:submit,onPage:turned,sendLabel:"",
    base:sketchKey,pages:n,page:same?was.page:0};
  next.key=next.pages>1?`${next.base}:${next.page}`:next.base;
  if(full){ full.saved=next; return; }   // the sheet changed under the full-screen board: it is where the board goes back to
  restore(next);
  const sheet=layer.querySelector(".mx-sheet"), on=isOn()&&desk();
  layer.querySelector("[data-board-toggle]")?.setAttribute("aria-pressed",on);
  sheet?.classList.toggle("with-board",on);
  if(on) sheet?.removeAttribute("aria-modal"); else sheet?.setAttribute("aria-modal","true");   // the board is outside the dialog: still reachable
  if(!on){ el?.remove(); return; }
  if(!el) build();
  reset(); drawPages(); drawSend(); layer.append(el); fit();
}
const again=()=>mount(layer,base,{pages,question:source,submit:hand,turned:onPage});
const here=p=>({host:layer,key:base,pages,page:p,question:source,submit:hand,turned:onPage});
function toggle(){
  if(!desk()) return layer&&openFull(here(page));   // a phone: the board over the exercise
  setOn(!isOn()); if(layer) again();
}
// opens the board on one question's page (the unit quiz's own button under each question)
function show(p){
  if(!desk()) return layer&&openFull(here(p));
  setOn(true); if(!layer) return; again(); if(pages>1&&p!==page) turn(p);
}
/* The board full screen over everything in host, until the student goes back. Options as mount's, and:
   title (the head's words), sendLabel (the hand-in button's words), done (called when it closes).
   A submit answer with close:true closes it after the hand-in. */
function openFull({host,key:k,pages:n=1,page:p=0,question=null,submit=null,turned=null,title="לוח טיוטה",sendLabel:label="",done=null}){
  if(!el) build();
  if(full) full.done=done; else full={saved:context(),done};
  restore({layer:host,base:k,pages:n,page:p,source:question,hand:submit,onPage:turned,sendLabel:label,key:n>1?`${k}:${p}`:k});
  el.querySelector("[data-title]").textContent=title;
  el.classList.add("full"); el.setAttribute("role","dialog"); el.setAttribute("aria-modal","true");
  reset(); drawPages(); drawSend(); host.append(el); fit();
  el.querySelector(".mx-board-back").focus({preventScroll:true});
}
function closeFull(){
  if(!full) return; const f=full; full=null;
  el.classList.remove("full"); el.removeAttribute("role"); el.removeAttribute("aria-modal"); el.remove();
  restore(f.saved); f.done?.();
  if(layer?.isConnected&&desk()) again();
}
// the header's switch: beside the exercise on a desktop screen, full screen on a phone
const button=()=>`<button class="mx-board-btn" data-board-toggle aria-pressed="${isOn()&&desk()}" title="לוח טיוטה">✏️ לוח</button>`;

window.MathlyBoard={button,mount,toggle,show,openFull,closeFull,isOn};
})();
