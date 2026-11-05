/* Mathly's sketch board. On a desktop screen it sits beside the exercise (the student turns it on from the sheet's
   header; this browser remembers the choice). On a phone or a tablet it opens full screen over the exercise, from
   the same button, and closes back to the question. Used by a skill's exercise, the practice exam, the unit quiz,
   and the phone's answer to a photo request from the computer (openFull). Each question keeps its own sketch for
   as long as the page is open. Nothing is sent anywhere unless the student hands it in.

   Everything on the board is an element that can be moved or erased: a pen stroke (with a pen's pressure),
   a straight line, a circle (dragged from the center), an angle's arc with its words (the angle tool: pointing at a
   corner where two lines meet shows the arc; a click adds it and asks for its words, and a number gets a degree
   sign), typed math (the math keyboard, static/board-math.js), and a
   copy of the question (its text and figures).
   Line ends and circle centers snap to the ends and centers already drawn, so a triangle closes neatly;
   lines that meet that way move together. The eraser removes the lines and circles it touches and cuts pen strokes;
   it leaves the question's copy alone (select it and delete it instead).
   The paper is endless downwards: the mouse wheel over the board scrolls it, and so do two fingers on a touch
   screen (one finger draws), and so does dragging empty paper with the move tool. Once a pen has touched the screen,
   a single finger is ignored: a hand resting on it.
   A sheet can let the board hand in a question's answer (the unit quiz): the sketch becomes a picture. */
(()=>{
const PREF="mathly.board";
const isOn=()=>{ try{ return localStorage.getItem(PREF)==="on"; }catch{ return false; } };
const setOn=on=>{ try{ localStorage.setItem(PREF,on?"on":"off"); }catch{} };

const INKS=[["#1B2140","שחור"],["#2563D9","כחול"],["#D3455B","אדום"]];
const ERASERS=[[16,"קטן"],[40,"בינוני"],[90,"גדול"]];
const TOOLS=[["move","הזזה"],["pen","עט"],["line","קו ישר"],["circle","עיגול"],["angle","זווית"],["math","נוסחה"],["eraser","מחק"]];
/* one line-drawn icon set (24×24, the button's text colour), so every button looks alike on every device and
   follows the button's hover and pressed colours; "flip" icons point the other way in a right-to-left page */
const DOT='fill="currentColor" stroke="none"';
const ICONS={
  move:'<path d="M18 11V6.5a1.5 1.5 0 0 0-3 0V11M15 10V4.5a1.5 1.5 0 0 0-3 0V10M12 10V5.5a1.5 1.5 0 0 0-3 0V13M18 9.5a1.5 1.5 0 0 1 3 0V14a7 7 0 0 1-7 7h-1.5c-2.2 0-3.7-.8-5-2.1l-3.3-3.3a1.5 1.5 0 0 1 2.1-2.1L9 15.2"/>',
  pen:'<path d="M4 20l1.2-4.2L16.5 4.5a2.1 2.1 0 0 1 3 3L8.2 18.8z"/><path d="M14.5 6.5l3 3"/>',
  line:`<path d="M6 18L18 6"/><circle cx="6" cy="18" r="2" ${DOT}/><circle cx="18" cy="6" r="2" ${DOT}/>`,
  circle:`<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="1.6" ${DOT}/>`,
  angle:'<path d="M20 19H4l11-14"/><path d="M10.5 19a6.5 6.5 0 0 0-2.5-5.1"/>',
  math:'<path d="M17.5 5.5V4H6.5l6 8-6 8h11v-1.5"/>',
  eraser:'<path d="M20 20H9.5M4.6 15.4l9.8-9.8a2 2 0 0 1 2.8 0l2.2 2.2a2 2 0 0 1 0 2.8L11 19H8.2l-3.6-3.6"/><path d="M9.5 10.5l5 5"/>',
  question:'<rect x="5.5" y="5" width="13" height="16" rx="2"/><path d="M9 5V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M9 11h6M9 15h4"/>',
  undo:'<path d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
  clear:'<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12.2A2 2 0 0 0 9 21h6a2 2 0 0 0 2-1.8L18 7M9 7V4.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1V7"/>',
  close:'<path d="M6 6l12 12M18 6L6 18"/>',
  send:'<path d="M12 15V4M7 9l5-5 5 5M5 15v4a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-4"/>',
  done:'<path d="M5 12.5l4.5 4.5L19 7"/>',
  back:'<path d="M19 12H5M11 6l-6 6 6 6"/>',
  top:'<path d="M12 19V5M6 11l6-6 6 6"/>',
  calc:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8.5 7.5h7M8.5 12h.01M12 12h.01M15.5 12h.01M8.5 16h.01M12 16h.01M15.5 16h.01"/>'};
const FLIP=new Set(["undo","back"]);
const ic=n=>`<svg class="mx-ic${FLIP.has(n)?" mx-ic-flip":""}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n]}</svg>`;
const MATH_SIZE=26;
const GREEK=["α","β","γ"], ARC_GAP=4;   // the angle box's letters; how far apart a double or triple arc's arcs are
const ARCS=[[1,"קשת אחת"],[2,"קשת כפולה"],[3,"קשת משולשת"],["right","זווית ישרה (ריבוע)"]];
// a corner with one, two or three arcs: equal angles are marked alike
const arcsIcon=n=>n==="right"?'<svg class="mx-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20h18M3 20V4M3 12.5h7.5V20"/></svg>'
  :`<svg class="mx-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20h18M3 20l12-14"/>${[7,10.5,14].slice(0,n).map(r=>`<path d="M${3+r} 20A${r} ${r} 0 0 0 ${(3+r*.65).toFixed(2)} ${(20-r*.76).toFixed(2)}"/>`).join("")}</svg>`;
const ANGLE_FONT='500 18px "STIX Two Text","Cambria Math","Times New Roman",serif', CORNER=32, CORNER_TOUCH=40;   // how near a corner the angle tool reaches: about as far as an arc
const ON=3;   // how close a point is to count as on a line: where an angle's corner is, and what moves with what
const PEN=2.6, SHAPE=2.4, SNAP=12, GRAB=9, STEP=2, HISTORY=100;
const PAPER="#F8F7F2", PAPER_INK="#1B2140", PAPER_FAINT="#C5CBDF", SELECT="#2563D9";
const FONT='500 17px Rubik, system-ui, "Segoe UI", sans-serif', LINE_H=27, CARD_PAD=14;

/* sketch key -> {marks, past}: marks are drawn in order; past holds copies of marks for undo */
const sketches=new Map(), images=new Map();
let el=null, canvas=null, ctx=null, key="", base="", pages=0, page=0, layer=null, source=null, hand=null, onPage=null;
let tool="pen", ink=INKS[0][0], eraser=ERASERS[1][0], sendLabel="";
let draft=null, drag=null, rub=null, slide=null, selection=[];   // slide: the move tool dragging empty paper, which scrolls it
let paper=PAPER;   // the paper's colour: the board's, or white in the picture handed in
let naming=null, hover=null;   // naming: an angle's words being typed {mark, node, input, fresh, was, key}; hover: the corner the angle tool points at
let editing=null;   // the formula being typed: {mark (null for a new one), at, node, field, key}
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

/* The calculator: a scientific one in the layout of the Casio fx-991ES PLUS, on a panel over the paper's corner
   (the toolbar's calculator button). SHIFT gives the second function printed above a key (sin⁻¹, 10ˣ, x³, nCr, ...),
   DEG/RAD/GRA is the angle unit, S⇔D turns an answer into a fraction and back, Ans is the last answer.
   The expression is read by a small parser, never evaluated as code. */
// [label, what it types (or an @command), shift label, what shift types, class]
const CALC_KEYS=[
  ["SHIFT","@shift",,,"fn shift"],["DEG","@mode",,,"fn"],["S⇔D","@sd",,,"fn"],["nPr","nPr","nCr","nCr","fn"],["%","%",,,"fn"],
  ["sin","sin(","sin⁻¹","sin⁻¹(","fn"],["cos","cos(","cos⁻¹","cos⁻¹(","fn"],["tan","tan(","tan⁻¹","tan⁻¹(","fn"],["log","log(","10ˣ","10^(","fn"],["ln","ln(","eˣ","e^(","fn"],
  ["(","(",,,"fn"],[")",")",,,"fn"],["x²","^2","x³","^3","fn"],["xʸ","^",,,"fn"],["√","√(","³√","³√(","fn"],
  ["x⁻¹","^(−1)","x!","!","fn"],["|x|","Abs(",,,"fn"],["π","π","e","e","fn"],["(−)","−",,,"fn"],["Ans","Ans",,,"fn"],
  ["7","7"],["8","8"],["9","9"],["DEL","@del",,,"del"],["AC","@ac",,,"del"],
  ["4","4"],["5","5"],["6","6"],["×","×",,,"op"],["÷","÷",,,"op"],
  ["1","1"],["2","2"],["3","3"],["+","+",,,"op"],["−","−",,,"op"],
  ["0","0"],[".","."],["ᴇ","ᴇ",,,"fn"],["=","@eq",,,"eq"]];
const cs={expr:"",res:null,done:false,shift:false,mode:"DEG",ans:0,frac:false};
const CALC_FUNS=["sin⁻¹(","cos⁻¹(","tan⁻¹(","sin(","cos(","tan(","log(","ln(","³√(","√(","Abs("];
const CALC_NAMES=[...CALC_FUNS,"Ans","nPr","nCr","π"];
function calcTrig(k,x,inv){
  const d=cs.mode, full=d==="DEG"?360:d==="GRA"?400:2*Math.PI, f={s:"sin",c:"cos",t:"tan"}[k];
  if(inv){ const r=Math[`a${f}`](x); return d==="DEG"?r*180/Math.PI:d==="GRA"?r*200/Math.PI:r; }
  if(d!=="RAD"){   // whole turns, halves and quarters give exact answers (sin 180 is 0, not 1.2e-16)
    const q=((x%full)+full)%full, half=full/2, quarter=full/4;
    if(k==="s"){ if(q%half===0) return 0; if(q===quarter) return 1; if(q===3*quarter) return -1; }
    if(k==="c"){ if(q===0) return 1; if(q===half) return -1; if(q===quarter||q===3*quarter) return 0; }
    if(k==="t"){ if(q%half===0) return 0; if(q%half===quarter) throw 0; }
  }
  return Math[f](d==="DEG"?x*Math.PI/180:d==="GRA"?x*Math.PI/200:x);
}
const calcFact=n=>{ if(!Number.isInteger(n)||n<0||n>170) throw 0; let r=1; for(let k=2;k<=n;k++) r*=k; return r; };
function calcValue(text){
  const T=[], src=text.replace(/\s+/g,"").replace(/-/g,"−").replace(/\*/g,"×").replace(/\//g,"÷");
  for(let i=0;i<src.length;){
    const r=src.slice(i); let m=/^(?:\d+\.?\d*|\.\d+)(?:ᴇ[−]?\d+)?/.exec(r);
    if(m){ T.push({n:parseFloat(m[0].replace("ᴇ","e").replace("−","-"))}); i+=m[0].length; continue; }
    const nm=CALC_NAMES.find(x=>r.startsWith(x))||("+−×÷()^!%e".includes(r[0])?r[0]:null);
    if(!nm) throw 0; T.push(nm); i+=nm.length;
  }
  let p=0; const nx=()=>T[p];
  const starts=t=>t!==undefined&&(typeof t==="object"||t==="("||t==="e"||t==="π"||t==="Ans"||CALC_FUNS.includes(t));
  const close=()=>{ if(nx()===")") p++; else if(p<T.length) throw 0; };   // a bracket left open at the end is fine
  function atom(){
    const t=T[p++]; if(t===undefined) throw 0;
    if(typeof t==="object") return t.n;
    if(t==="π") return Math.PI;
    if(t==="e") return Math.E;
    if(t==="Ans") return cs.ans;
    if(t==="(" ){ const v=sum(); close(); return v; }
    if(!CALC_FUNS.includes(t)) throw 0;
    const x=sum(); close();
    switch(t){
      case "sin(": return calcTrig("s",x); case "cos(": return calcTrig("c",x); case "tan(": return calcTrig("t",x);
      case "sin⁻¹(": return calcTrig("s",x,1); case "cos⁻¹(": return calcTrig("c",x,1); case "tan⁻¹(": return calcTrig("t",x,1);
      case "log(": return Math.log10(x); case "ln(": return Math.log(x);
      case "√(": return Math.sqrt(x); case "³√(": return Math.cbrt(x); default: return Math.abs(x);
    }
  }
  function post(){ let v=atom(); for(;;){ if(nx()==="!"){ p++; v=calcFact(v); } else if(nx()==="%"){ p++; v/=100; } else return v; } }
  function power(){ const b=post(); if(nx()==="^"){ p++; return Math.pow(b,unary()); } return b; }
  function unary(){ if(nx()==="−"){ p++; return -unary(); } if(nx()==="+"){ p++; return unary(); } return power(); }
  function perm(){ let v=unary(); while(nx()==="nPr"||nx()==="nCr"){
    const c=T[p++]==="nCr", r=unary();
    if(!Number.isInteger(v)||!Number.isInteger(r)||r<0||r>v) throw 0;
    v=calcFact(v)/calcFact(v-r)/(c?calcFact(r):1); } return v; }
  function prod(){ let v=perm(); for(;;){ const t=nx();
    if(t==="×"){ p++; v*=perm(); } else if(t==="÷"){ p++; v/=perm(); } else if(starts(t)) v*=perm(); else return v; } }   // 2π and 2(3+4) multiply
  function sum(){ let v=prod(); for(;;){ if(nx()==="+"){ p++; v+=prod(); } else if(nx()==="−"){ p++; v-=prod(); } else return v; } }
  const v=sum(); if(p<T.length||!Number.isFinite(v)) throw 0; return v;
}
const calcShow=v=>String(+v.toPrecision(10)).replace("e+","ᴇ").replace("e-","ᴇ−").replace("-","−");
function calcFrac(v){   // a decimal answer as a fraction with a denominator up to 10000, when it is one
  if(!Number.isFinite(v)||Number.isInteger(v)) return null;
  const x=Math.abs(v); let h0=0,h1=1,k0=1,k1=0,b=x;
  for(let n=0;n<24;n++){
    const a=Math.floor(b), h2=a*h1+h0, k2=a*k1+k0; h0=h1; h1=h2; k0=k1; k1=k2;
    if(k1>10000) return null;
    if(Math.abs(x-h1/k1)<1e-11*Math.max(1,x)) return `${v<0?"−":""}${h1}/${k1}`;
    const f=b-a; if(f<1e-14) return null; b=1/f;
  }
  return null;
}
function calcDraw(){
  const box=el.querySelector(".mx-calc"), ex=box.querySelector("[data-calc-expr]"), out=box.querySelector("[data-calc-out]");
  let text="", cls="";
  if(cs.res?.err) text="שגיאה";
  else if(cs.res){ text=(cs.frac&&calcFrac(cs.res.v))||calcShow(cs.res.v); }
  else if(cs.expr){ try{ if(/[^0-9.]/.test(cs.expr)) text=calcShow(calcValue(cs.expr)); }catch{} cls="live"; }
  ex.textContent=cs.expr||"0"; ex.scrollLeft=ex.scrollWidth;
  out.textContent=text||" "; out.className=cls;
  box.querySelector("[data-calc-flags]").textContent=[cs.shift?"S":"",cs.mode==="DEG"?"D":cs.mode==="RAD"?"R":"G"].filter(Boolean).join(" ");
  box.querySelector('[data-calc-do="mode"]').textContent=cs.mode;
  box.querySelectorAll("[data-calc]").forEach(b=>b.classList.toggle("shifted",cs.shift));
  box.querySelector(".shift").setAttribute("aria-pressed",cs.shift);
}
function calcAct(act){
  if(act==="@shift"){ cs.shift=!cs.shift; return calcDraw(); }
  cs.shift=false;
  if(act==="@mode"){ cs.mode=cs.mode==="DEG"?"RAD":cs.mode==="RAD"?"GRA":"DEG"; if(cs.res&&!cs.res.err&&cs.done) calcAct("@eq"); return calcDraw(); }
  if(act==="@sd"){ if(cs.res&&!cs.res.err&&calcFrac(cs.res.v)) cs.frac=!cs.frac; return calcDraw(); }
  if(act==="@ac"){ cs.expr=""; cs.res=null; cs.done=false; cs.frac=false; return calcDraw(); }
  if(act==="@del"){
    if(cs.done){ cs.done=false; cs.res=null; }
    else cs.expr=cs.expr.replace(/(?:sin⁻¹\(|cos⁻¹\(|tan⁻¹\(|sin\(|cos\(|tan\(|log\(|ln\(|³√\(|√\(|Abs\(|Ans|nPr|nCr|.)$/u,"");
    return calcDraw();
  }
  if(act==="@eq"){
    if(!cs.expr) return calcDraw();
    try{ const v=calcValue(cs.expr); cs.res={v}; cs.ans=v; }catch{ cs.res={err:true}; }
    cs.done=true; cs.frac=false; return calcDraw();
  }
  if(cs.done){ cs.expr=/^(?:\^|!|%|nPr|nCr|[+−×÷])/.test(act)?"Ans"+act:act; cs.done=false; cs.res=null; cs.frac=false; }   // an operator goes on from the answer
  else cs.expr+=act;
  calcDraw();
}
function calcPress(i){ const [,ins,,sins]=CALC_KEYS[i]; calcAct(cs.shift&&sins!==undefined?sins:ins); }
const calcKeysHtml=()=>CALC_KEYS.map(([label,,sl,,cls="num"],i)=>
  `<button type="button" data-calc="${i}" class="${cls}"${label==="DEG"?' data-calc-do="mode"':""}>${sl?`<i>${sl}</i>`:""}<b>${label}</b></button>`).join("");
function toggleCalc(){
  const box=el.querySelector(".mx-calc"), on=box.hidden;
  box.hidden=!on; el.querySelector('[data-do="calc"]').setAttribute("aria-pressed",on);
  if(on){ calcDraw(); box.querySelector("button").focus({preventScroll:true,focusVisible:false}); }
}
document.addEventListener("keydown",e=>{
  const box=el?.querySelector(".mx-calc");
  if(!box||box.hidden||!box.contains(document.activeElement)||e.ctrlKey||e.metaKey||e.altKey) return;
  const k={"*":"×","/":"÷","-":"−"}[e.key]||e.key;
  if(/^[0-9.+−×÷()^!%]$/.test(k)) calcAct(k);
  else if(k==="Enter"||k==="=") calcAct("@eq");
  else if(k==="Backspace") calcAct("@del");
  else if(k==="Escape"&&(cs.expr||cs.res)) calcAct("@ac");
  else return;
  e.preventDefault(); e.stopImmediatePropagation();
},true);

function build(){
  el=document.createElement("aside"); el.className="mx-board"; el.setAttribute("aria-label","לוח טיוטה");
  el.innerHTML=`<div class="mx-board-head"><b data-title>לוח טיוטה</b><button type="button" data-do="hide" class="mx-board-back">${ic("back")}<span>חזרה לשאלה</span></button></div>
    <div class="mx-board-bar" role="toolbar" aria-label="כלי הלוח">
      <span class="mx-board-group">${TOOLS.map(([t,name])=>`<button type="button" data-tool="${t}" aria-pressed="${t===tool}" title="${name}">${ic(t)}<span>${name}</span></button>`).join("")}</span>
      <span class="mx-board-group mx-board-inks">${INKS.map(([c,name])=>`<button type="button" data-ink="${c}" aria-pressed="${c===ink}" aria-label="${name}" title="${name}" style="--dot:${c}"></button>`).join("")}</span>
      <span class="mx-board-group mx-board-sizes">${ERASERS.map(([w,name])=>`<button type="button" data-eraser="${w}" aria-pressed="${w===eraser}" aria-label="מחק ${name}" title="מחק ${name}" style="--d:${Math.round(6+w/6)}px"></button>`).join("")}</span>
      <span class="mx-board-group mx-board-acts">
        <button type="button" data-do="calc" aria-pressed="false" title="מחשבון">${ic("calc")}<span>מחשבון</span></button>
        <button type="button" data-do="question" title="העתקת השאלה לראש הלוח">${ic("question")}<span>השאלה</span></button>
        <button type="button" data-do="undo" title="ביטול (Ctrl+Z)">${ic("undo")}<span>ביטול</span></button>
        <button type="button" data-do="clear" title="ניקוי הלוח">${ic("clear")}<span>ניקוי</span></button></span>
      <button type="button" data-do="hide" class="mx-board-close" aria-label="סגירת הלוח" title="סגירת הלוח">${ic("close")}</button>
    </div><div class="mx-board-row"><div class="mx-board-pages" role="tablist" aria-label="הדף של כל שאלה"></div>
      <button type="button" data-do="send" class="mx-board-send" hidden></button></div>
    <div class="mx-board-stage"><canvas></canvas>
      <button type="button" data-do="delete" class="mx-board-del" title="מחיקת מה שנבחר (Delete)" hidden>${ic("clear")}מחיקה</button>
      <button type="button" data-do="top" class="mx-board-top" hidden>${ic("top")}לראש הדף</button>
      <div class="mx-calc" dir="ltr" role="group" aria-label="מחשבון מדעי" hidden>
        <div class="mx-calc-screen"><span class="mx-calc-flags" data-calc-flags></span><div class="mx-calc-expr" data-calc-expr>0</div><output data-calc-out>&nbsp;</output></div>
        <div class="mx-calc-keys">${calcKeysHtml()}</div></div></div>`;
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
    if(b.dataset.calc) calcPress(+b.dataset.calc);
    if(act==="calc") toggleCalc();
    if(act==="top"){ sketch().y=0; paint(); }
    if(act==="hide") full?closeFull():toggle();
  });
  canvas.addEventListener("pointerdown",down);
  canvas.addEventListener("pointermove",move);
  canvas.addEventListener("pointerup",up);
  canvas.addEventListener("pointercancel",up);
  canvas.addEventListener("contextmenu",e=>e.preventDefault());
  canvas.addEventListener("dblclick",e=>{ const m=hit(at(e)); if(m?.kind==="math") editMath(m,at(e)); else if(m?.kind==="angle") startAngle(at(e),0); });
  canvas.addEventListener("pointerleave",()=>{ if(hover){ hover=null; paint(); } });   // typed math is edited where it is   // the pen's side button: no browser menu over the board
  canvas.addEventListener("wheel",e=>{   // endless paper: scrolls down as far as needed, never above the top
    if(e.ctrlKey) return;   // the browser's zoom
    e.preventDefault(); const s=sketch(), dy=e.deltaMode===1?e.deltaY*24:e.deltaMode===2?e.deltaY*canvas.clientHeight:e.deltaY;
    s.y=Math.max(0,s.y+dy); paint();
  },{passive:false});
  new ResizeObserver(fit).observe(canvas);
  setTool(tool);
}
function pressed(sel,b){ el.querySelectorAll(sel).forEach(x=>x.setAttribute("aria-pressed",x===b)); }
function reset(){ draft=drag=rub=slide=null; hover=null; select([]); if(editing) finishMath(false); if(naming) finishAngle(true); }
function setTool(t){
  tool=t; if(hover){ hover=null; paint(); } el.querySelectorAll("[data-tool]").forEach(x=>x.setAttribute("aria-pressed",x.dataset.tool===t));
  el.dataset.tool=t; if(t!=="move"&&selection.length){ select([]); paint(); }
  // the eraser's cursor is a ring its own size, so the student sees what it will wipe
  const r=eraser/2, svg=`<svg xmlns='http://www.w3.org/2000/svg' width='${eraser+2}' height='${eraser+2}'><circle cx='${r+1}' cy='${r+1}' r='${r}' fill='rgba(255,255,255,.35)' stroke='%231B2140' stroke-width='1.2'/></svg>`;
  canvas.style.cursor=t==="eraser"?`url("data:image/svg+xml,${svg.replace(/</g,"%3C").replace(/>/g,"%3E")}") ${r+1} ${r+1}, cell`:t==="move"?"grab":"";
}
function select(list){ selection=list; }
function turn(p){ if(editing) finishMath(true); if(naming) finishAngle(true); page=p; key=`${base}:${page}`; reset(); drawPages(); drawSend(); paint(); }
function drawSend(){
  const b=el.querySelector(".mx-board-send"); b.hidden=!hand; el.querySelector(".mx-board-row").hidden=pages<2&&!hand; if(!hand) return;
  b.disabled=false; b.innerHTML=`${ic("send")}<span>${sendLabel||`הגשה לשאלה ${page+1}`}</span>`; b.title=sendLabel||`הגשת הלוח כתשובה לשאלה ${page+1}`;
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
  if(hover&&!naming) aimed(hover);
  if(selection.length) outline(selection);
  const del=el.querySelector(".mx-board-del"); del.hidden=!selection.length||!!drag?.before;
  if(selection.length){ const [x0,y0]=edges(selection); del.style.left=`${Math.max(4,x0)}px`; const top=y0-y; del.style.top=`${top>40?top-36:Math.max(4,top+4)}px`; }
}
function draw(m){
  ctx.save(); ctx.strokeStyle=m.color; ctx.lineCap="round"; ctx.lineJoin="round";
  if(m.kind==="line"){ ctx.lineWidth=SHAPE; ctx.beginPath(); ctx.moveTo(...m.a); ctx.lineTo(...m.b); ctx.stroke(); }
  else if(m.kind==="circle"){ ctx.lineWidth=SHAPE; ctx.beginPath(); ctx.arc(m.a[0],m.a[1],dist(m.a,m.b),0,Math.PI*2); ctx.stroke(); }
  else if(m.kind==="angle") angleMark(m);
  else if(m.kind==="card") card(m);
  else if(m.kind==="math"){ const L=mathBox(m); if(L){ ctx.fillStyle=m.color; ctx.direction="ltr"; ctx.textAlign="left"; ctx.textBaseline="alphabetic"; L.paint(ctx,m.x,m.y+L.a); } }
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
// an angle: the arc between its two edges, and its words just outside the arc (hidden while they are typed)
const arcsOf=m=>naming?.mark===m?naming.arcs:m.arcs||1;   // while its box is open: the arcs picked there
// a right angle is marked with a little square in its corner: its sides along the edges, its far corner on the line splitting the angle
const square=m=>{
  const k=Math.max(8,Math.min(14,arcR(m)*.5)), u=[Math.cos(m.s),Math.sin(m.s)], w=[Math.cos(m.s+m.w),Math.sin(m.s+m.w)];
  return [[m.v[0]+k*u[0],m.v[1]+k*u[1]],[m.v[0]+k*(u[0]+w[0]),m.v[1]+k*(u[1]+w[1])],[m.v[0]+k*w[0],m.v[1]+k*w[1]]];
};
const rim=m=>arcsOf(m)==="right"?dist(square(m)[1],m.v):arcR(m)+ARC_GAP*(arcsOf(m)-1);   // how far out the mark reaches
const colorOf=m=>naming?.mark===m?naming.color:m.color;   // while its box is open: the colour picked there
function angleMark(m){
  ctx.lineWidth=1.8; ctx.strokeStyle=colorOf(m);
  if(arcsOf(m)==="right"){ const [a,b,c]=square(m); ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.lineTo(...c); ctx.stroke(); }
  else for(let k=0;k<arcsOf(m);k++){ ctx.beginPath(); ctx.arc(m.v[0],m.v[1],arcR(m)+k*ARC_GAP,m.s,m.s+m.w); ctx.stroke(); }
  if(!m.text||naming?.mark===m) return;
  const [x,y]=labelAt(m); ctx.font=ANGLE_FONT; ctx.direction="ltr"; ctx.textAlign="center"; ctx.textBaseline="middle";
  ctx.strokeStyle=paper; ctx.lineWidth=5; ctx.strokeText(m.text,x,y);   // a rim of paper, where the words cross a line
  ctx.fillStyle=m.color; ctx.fillText(m.text,x,y);
}
// the corner the angle tool points at: the arc it would add (or the angle it would retype), dashed
function aimed(c){
  ctx.save(); ctx.strokeStyle=ctx.fillStyle=SELECT; ctx.lineWidth=2; ctx.setLineDash([4,3]);
  ctx.beginPath(); ctx.arc(c.v[0],c.v[1],c.r,c.s,c.s+c.w); ctx.stroke();
  ctx.setLineDash([]); ctx.beginPath(); ctx.arc(c.v[0],c.v[1],3.5,0,TAU); ctx.fill(); ctx.restore();
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
const mathBox=m=>window.MathlyBoardMath?.layout(m.latex,m.size||MATH_SIZE);
function box(m){
  if(m.kind==="card") return [m.x,m.y,m.x+m.w,m.y+m.h];
  if(m.kind==="math"){ const L=mathBox(m)||{w:0,a:0,d:0}; return [m.x,m.y,m.x+L.w,m.y+L.a+L.d]; }
  if(m.kind==="angle"){ const [x,y,w]=labelAt(m), r=rim(m); return [Math.min(m.v[0]-r,x-w/2),Math.min(m.v[1]-r,y-10),Math.max(m.v[0]+r,x+w/2),Math.max(m.v[1]+r,y+10)]; }
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
function nearestOn(p,a,b){
  const dx=b[0]-a[0], dy=b[1]-a[1], l=dx*dx+dy*dy, t=l?Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/l)):0;
  return [a[0]+t*dx,a[1]+t*dy];
}
const toSegment=(p,a,b)=>dist(p,nearestOn(p,a,b));
// how far p is from the element's ink
function reach(m,p){
  if(m.kind==="line") return toSegment(p,m.a,m.b);
  if(m.kind==="circle") return Math.min(Math.abs(dist(p,m.a)-dist(m.a,m.b)),dist(p,m.a));
  if(m.kind==="angle"&&arcsOf(m)==="right"){ const [a,b,c]=square(m); return Math.min(toSegment(p,a,b),toSegment(p,b,c),toWords(m,p)); }
  if(m.kind==="angle") return Math.min(inWedge(Math.atan2(p[1]-m.v[1],p[0]-m.v[0]),m.s,m.w)?Math.max(0,Math.abs(dist(p,m.v)-(arcR(m)+rim(m))/2)-(rim(m)-arcR(m))/2):Infinity,toWords(m,p));
  if(m.kind==="card"||m.kind==="math"){ const [x0,y0,x1,y1]=box(m), dx=Math.max(x0-p[0],0,p[0]-x1), dy=Math.max(y0-p[1],0,p[1]-y1);
    return m.kind==="card"?(dx||dy?Infinity:0):Math.hypot(dx,dy); }
  if(m.pts.length===1) return dist(p,m.pts[0]);
  let d=Infinity; for(let i=1;i<m.pts.length;i++) d=Math.min(d,toSegment(p,m.pts[i-1],m.pts[i])); return d;
}
const hit=p=>{ const all=marks(); for(let i=all.length-1;i>=0;i--) if(reach(all[i],p)<=GRAB) return all[i]; return null; };
const joints=m=>m.kind==="line"?[m.a,m.b]:m.kind==="circle"?[m.a]:m.kind==="angle"?[m.v]:[];   // an angle moves with its corner
// an element and everything joined to it by a shared end or center: a triangle moves as one
function group(m){
  const out=new Set([m]), todo=[m];
  while(todo.length){ const cur=todo.pop();
    for(const o of marks()) if(!out.has(o)&&linked(cur,o)){ out.add(o); todo.push(o); } }
  return [...out];
}
// joined: a shared end or center, a line's end on another line (drawn from a side), or an angle on a line through it
const lies=(m,o)=>o.kind==="line"&&(m.kind==="line"||m.kind==="angle")&&joints(m).some(p=>toSegment(p,o.a,o.b)<=ON);
const linked=(m,o)=>joints(m).some(p=>joints(o).some(q=>same(p,q)))||lies(m,o)||lies(o,m);
// a line's ends and a circle's center pull to the ends and centers already on the board, or else onto a line
function snap(p,skip){
  let best=null, d=SNAP;
  for(const m of marks()){ if(m===skip) continue; for(const q of joints(m)){ const k=dist(p,q); if(k<d){ d=k; best=q; } } }
  if(!best) for(const m of marks()) if(m!==skip&&m.kind==="line"){ const q=nearestOn(p,m.a,m.b), k=dist(p,q); if(k<d){ d=k; best=q; } }
  return best?[best[0],best[1]]:[p[0],p[1]];
}
function shift(m,dx,dy){
  const by=p=>{ p[0]+=dx; p[1]+=dy; };
  if(m.kind==="card"||m.kind==="math"){ m.x+=dx; m.y+=dy; } else if(m.kind==="free") m.pts.forEach(by); else if(m.kind==="angle") by(m.v); else { by(m.a); by(m.b); }
}
// the eraser at p: lines, circles and typed math it touches go; pen strokes are cut; the question's copy stays
function rubOut(p){
  const r=eraser/2, all=marks(); let changed=false;
  for(let i=all.length-1;i>=0;i--){ const m=all[i];
    if(m.kind==="line"||m.kind==="circle"||m.kind==="math"||m.kind==="angle"){ if(reach(m,p)<=r+SHAPE/2){ all.splice(i,1); changed=true; } continue; }
    if(m.kind!=="free") continue;
    const gone=m.pts.map(q=>dist(p,q)<=r+PEN); if(!gone.some(Boolean)) continue;
    const runs=[]; let run=[]; m.pts.forEach((q,k)=>{ if(gone[k]){ if(run.length) runs.push(run); run=[]; } else run.push(q); }); if(run.length) runs.push(run);
    all.splice(i,1,...runs.map(pts=>({kind:"free",color:m.color,pts}))); changed=true;
  }
  return changed;
}
/* ---------- angles at corners ---------- */
const TAU=Math.PI*2, turnOf=a=>(a%TAU+TAU)%TAU, inWedge=(t,s,w)=>turnOf(t-s)<=w;
const gap=(a,b)=>Math.abs(turnOf(a-b+Math.PI)-Math.PI);
// where two lines cross, or null (an end on the other line counts)
function cross(m,o){
  const r=[m.b[0]-m.a[0],m.b[1]-m.a[1]], q=[o.b[0]-o.a[0],o.b[1]-o.a[1]], den=r[0]*q[1]-r[1]*q[0];
  if(Math.abs(den)<1e-9) return null;
  const ex=o.a[0]-m.a[0], ey=o.a[1]-m.a[1], t=(ex*q[1]-ey*q[0])/den, u=(ex*r[1]-ey*r[0])/den, k=.01;
  return t>=-k&&t<=1+k&&u>=-k&&u<=1+k?[m.a[0]+t*r[0],m.a[1]+t*r[1]]:null;
}
// the points where lines meet: shared ends, an end partway along another line, and crossings
function meets(){
  const lines=marks().filter(m=>m.kind==="line"), out=lines.flatMap(m=>[m.a,m.b]);
  lines.forEach((m,i)=>lines.slice(i+1).forEach(o=>{ const c=cross(m,o); if(c) out.push(c); }));
  return out;
}
// every line through v, as rays going out of v: one for a line ending there, two for a line passing through
function raysAt(v){
  const rays=[], add=b=>{
    if(dist(b,v)<=ON) return;
    const t=turnOf(Math.atan2(b[1]-v[1],b[0]-v[0])), len=dist(v,b), twin=rays.find(r=>gap(r.t,t)<.02);
    if(twin) twin.len=Math.min(twin.len,len); else rays.push({t,len});
  };
  for(const m of marks()) if(m.kind==="line"){
    if(dist(m.a,v)<=ON) add(m.b); else if(dist(m.b,v)<=ON) add(m.a); else if(toSegment(v,m.a,m.b)<=ON){ add(m.a); add(m.b); }
  }
  return rays.sort((a,b)=>a.t-b.t);
}
/* A corner near p where lines meet, and the angle (under half a turn) between two of its rays that p points into:
   the inside of a triangle's corner, either side of a line drawn from a side, or the smallest one when p is on the
   corner itself. Pointing along a line that splits an angle picks the whole angle, its arc a little wider, and
   its words go in the widest gap the inner lines leave. */
function corner(p,near){
  let v=null, d=near;
  for(const q of meets()){ const k=dist(p,q); if(k<d){ d=k; v=q; } }
  if(!v) return null;
  const rays=raysAt(v); if(rays.length<2) return null;
  const wedges=[];
  rays.forEach(r=>rays.forEach(n=>{
    const w=turnOf(n.t-r.t); if(r===n||w<.02||w>Math.PI-.01) return;
    wedges.push({s:r.t,w,len:Math.min(r.len,n.len),inner:rays.filter(x=>x!==r&&x!==n&&turnOf(x.t-r.t)<w)});
  }));
  if(!wedges.length) return null;
  wedges.sort((a,b)=>a.w-b.w);
  const t=Math.atan2(p[1]-v[1],p[0]-v[0]), far=dist(p,v)>6, along=far&&rays.find(r=>gap(r.t,t)<.1);
  const off=x=>inWedge(t,x.s,x.w)?0:Math.min(gap(t,x.s),gap(t,x.s+x.w))+(x.inner.length?1:0);   // outside them all: the nearest
  const w=(along&&wedges.find(x=>x.inner.includes(along)))||(far&&wedges.reduce((a,b)=>off(b)<off(a)?b:a))||wedges[0];
  const cuts=[0,...w.inner.map(x=>turnOf(x.t-w.s)).sort((a,b)=>a-b),w.w];
  let f=w.w/2, g=w.w;
  if(w.inner.length){ g=0; for(let k=1;k<cuts.length;k++) if(cuts[k]-cuts[k-1]>g){ g=cuts[k]-cuts[k-1]; f=(cuts[k]+cuts[k-1])/2; } }
  return {v:[v[0],v[1]],s:w.s,w:w.w,r:Math.max(12,Math.min(30,w.len*.3))+10*w.inner.length,f:w.s+f};
}
// what the angle tool would act on at p: an angle already there (to retype its words), or a corner to add one to
// (an angle's words come first; then the corner decides, so pointing along a middle line over a half's arc still
// gives the whole angle; an arc whose corner is gone is still there to retype)
function aim(p,near){
  const all=marks().filter(m=>m.kind==="angle").reverse(), as=m=>({mark:m,v:m.v,s:m.s,w:m.w,r:arcR(m)});
  const named=all.find(m=>toWords(m,p)<=4); if(named) return as(named);
  const c=corner(p,near);
  if(c){ c.mark=all.find(m=>dist(m.v,c.v)<=ON&&gap(m.s,c.s)<.05&&Math.abs(m.w-c.w)<.05)||null; if(c.mark) c.r=arcR(c.mark); return c; }
  const old=all.find(m=>reach(m,p)<=GRAB); return old?as(old):null;
}
// how far p is from an angle's words
function toWords(m,p){
  if(!m.text) return Infinity;
  const [x,y,w]=labelAt(m); return Math.hypot(Math.max(Math.abs(p[0]-x)-w/2,0),Math.max(Math.abs(p[1]-y)-10,0));
}
// where an angle's words sit: on the line splitting the angle, just past the arc, and far enough out to clear the edges
// (right by the arc, even in a narrow angle: they are drawn over a line's ink with a rim of paper)
function labelAt(m,text=m.text){
  ctx.save(); ctx.font=ANGLE_FONT; const w=text?ctx.measureText(text).width:0; ctx.restore();
  const f=m.f??m.s+m.w/2, out=Math.abs(w/2*Math.cos(f))+Math.abs(10*Math.sin(f)), c=Math.cos(f), s=Math.sin(f);   // f: the words' way
  // words of an angle beside it at the same corner, added before it: these move out until they are clear of them
  const all=marks(), i=all.indexOf(m), mine=inside(m);
  const near=i<0?[]:all.slice(0,i).filter(o=>o.kind==="angle"&&o.text&&dist(o.v,m.v)<=ON&&!mine.includes(o)&&!inside(o).includes(m)).map(o=>labelAt(o));
  let d=rim(m)+5+out;
  for(let k=0;k<30&&near.some(([x,y,ow])=>Math.abs(m.v[0]+d*c-x)<(w+ow)/2+4&&Math.abs(m.v[1]+d*s-y)<20);k++) d+=3;
  return [m.v[0]+d*c,m.v[1]+d*s,w,out];
}
// the angles inside m at its corner (the halves of an angle a line splits)
const inside=m=>marks().filter(o=>o!==m&&o.kind==="angle"&&dist(o.v,m.v)<=ON&&o.w<m.w-.01&&turnOf(o.s-m.s)<=m.w-o.w+.01);
// an angle's arc goes around the arcs and words of the angles inside it, so each angle's words sit by its own arc
function arcR(m){
  let r=m.r;
  for(const o of inside(m)){ r=Math.max(r,rim(o)+8); if(o.text){ const [x,y,,out]=labelAt(o); r=Math.max(r,dist([x,y],m.v)+out+4); } }
  return r;
}
// a number on its own or added to the rest ("60", "β+90", "180-α-β") is a size in degrees; a factor ("2β") is not
const TERM=/(^|[+\-−=]\s*)(\d+(?:[.,]\d+)?)°?(?=\s*(?:$|[+\-−=]))/g;
const NAMES={alpha:"α",beta:"β",gamma:"γ"};
const degrees=v=>v.trim().replace(/(?<![a-z])(alpha|beta|gamma)(?![a-z])/gi,w=>NAMES[w.toLowerCase()]).replace(TERM,"$1$2°");
const bare=t=>t.replace(TERM,"$1$2");   // for retyping: the signs degrees() puts back by itself
// adds the angle at p (or opens one already there), with a box over its words
function startAngle(p,near){
  const c=aim(p,near); if(!c) return;
  hover=null;
  let m=c.mark; const fresh=!m;
  if(fresh){ remember(); m={kind:"angle",color:ink,v:c.v,s:c.s,w:c.w,r:c.r,f:c.f,text:""}; marks().push(m); }
  // the box for the words, with the usual names of a triangle's angles a tap away
  const node=document.createElement("div"); node.className="mx-board-angleedit";
  // two rows, to fit a phone: the words and the letters; the arcs and the colour
  node.innerHTML=`<div class="mx-board-anglerow"><input type="text" class="mx-board-anglein" dir="auto" maxlength="16" placeholder="°" enterkeyhint="done"
      aria-label="מה כתוב בזווית (מספר מקבל סימן מעלות)">${GREEK.map(g=>`<button type="button" tabindex="-1" data-letter title="${g}">${g}</button>`).join("")}</div>
    <div class="mx-board-anglerow"><span class="mx-board-arcs">${ARCS.map(([n,name])=>`<button type="button" tabindex="-1" data-arcs="${n}" aria-pressed="${n===(m.arcs||1)}" title="${name}" aria-label="${name}">${arcsIcon(n)}</button>`).join("")}</span>
    <span class="mx-board-colors">${INKS.map(([c,name])=>`<button type="button" tabindex="-1" data-color="${c}" aria-pressed="${c===m.color}" title="${name}" aria-label="${name}" style="--dot:${c}"></button>`).join("")}</span></div>`;
  const input=node.querySelector("input"); input.value=bare(m.text);
  naming={mark:m,node,input,fresh,was:m.text,arcs:m.arcs||1,color:m.color,key};
  input.addEventListener("keydown",ev=>{
    if(ev.key==="Enter"){ ev.preventDefault(); finishAngle(true); }
    else if(ev.key==="Escape"){ ev.preventDefault(); ev.stopPropagation(); finishAngle(false); }
  });
  input.addEventListener("blur",()=>naming?.node===node&&finishAngle(true));
  // a letter's button types it where the cursor is ("β+90" takes a tap and a few keys); the box keeps its focus
  node.querySelectorAll("[data-letter]").forEach(b=>b.addEventListener("pointerdown",ev=>{
    ev.preventDefault(); input.setRangeText(b.textContent,input.selectionStart??input.value.length,input.selectionEnd??input.value.length,"end");
  }));
  // one, two or three arcs: shown at once, kept with the words
  node.querySelectorAll("[data-arcs]").forEach(b=>b.addEventListener("pointerdown",ev=>{
    ev.preventDefault(); naming.arcs=b.dataset.arcs==="right"?"right":+b.dataset.arcs; node.querySelectorAll("[data-arcs]").forEach(x=>x.setAttribute("aria-pressed",x===b)); paint();
  }));
  // the angle's colour, its arcs and words together: shown at once on the arcs and in the box, kept with the words
  const tint=()=>{ input.style.color=naming.color; paint(); };
  node.querySelectorAll("[data-color]").forEach(b=>b.addEventListener("pointerdown",ev=>{
    ev.preventDefault(); naming.color=b.dataset.color; node.querySelectorAll("[data-color]").forEach(x=>x.setAttribute("aria-pressed",x===b)); tint();
  }));
  input.style.color=m.color;
  el.querySelector(".mx-board-stage").append(node);
  const [x,y]=labelAt(m,"000°"), W=canvas.clientWidth, bw=node.offsetWidth;
  node.style.left=`${Math.max(4,Math.min(W-4-bw,x-bw/2))}px`; node.style.top=`${Math.max(4,y-sketch().y-21)}px`;
  paint(); input.focus({preventScroll:true});
  if(pages>1) drawPages();
}
// keep: the words go in (a new angle with none keeps just its arc); otherwise a new angle is taken back
function finishAngle(keep){
  const n=naming; if(!n) return; naming=null; n.node.remove();
  const s=sketches.get(n.key), m=n.mark; if(!s) return;
  if(keep){
    const t=degrees(n.input.value); if(!n.fresh&&(t!==n.was||n.arcs!==(m.arcs||1)||n.color!==m.color)) remember();
    m.text=t; m.color=n.color; if(n.arcs!==1) m.arcs=n.arcs; else delete m.arcs;   // 2, 3, or "right"
  }
  else if(n.fresh){ const i=s.marks.indexOf(m); if(i>=0){ s.marks.splice(i,1); s.past.pop(); } }
  paint(); if(pages>1) drawPages();
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
  slide=null; paint();
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
  if(editing){ e.preventDefault(); return finishMath(true); }   // a tap beside the formula being typed: it is done
  if(naming){ e.preventDefault(); return finishAngle(true); }   // the same for an angle's words
  if(use==="angle"){ e.preventDefault(); return startAngle(p,e.pointerType==="mouse"?CORNER:CORNER_TOUCH); }
  if(use==="math"){ e.preventDefault(); const m=hit(p); return editMath(m?.kind==="math"?m:null,p); }
  capture(e.pointerId); e.preventDefault();
  if(use==="move"){
    const m=hit(p);
    if(!m){ select([]); slide={id:e.pointerId,y:e.clientY,s:sketch().y}; canvas.style.cursor="grabbing"; return paint(); }   // empty paper: scroll it
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
  if(slide&&e.pointerId===slide.id){ sketch().y=Math.max(0,slide.s-(e.clientY-slide.y)); return paint(); }
  if(tool==="move"&&!drag&&!e.buttons) canvas.style.cursor=hit(at(e))?"move":"grab";
  if(tool==="angle"&&!e.buttons&&e.pointerType!=="touch"){   // a mouse or a pen over a corner: its arc, dashed
    const c=naming?null:aim(at(e),CORNER), was=hover; hover=c; canvas.style.cursor=c?"pointer":"";
    if(c?.v[0]!==was?.v[0]||c?.v[1]!==was?.v[1]||c?.s!==was?.s) paint();
    return;
  }
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
  if(slide&&e.pointerId===slide.id){ slide=null; canvas.style.cursor="grab"; return; }
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

/* ---------- typed math ---------- */
// a bar over the board's top with the math field; the math keyboard opens with it
async function editMath(mark,p){
  const M=window.MathlyBoardMath; if(!M||editing) return;
  const node=document.createElement("div"); node.className="mx-board-mathedit"; node.dir="ltr";
  node.innerHTML='<span class="mx-board-mathwait" dir="rtl">טוענים את מקלדת המתמטיקה…</span>';
  el.querySelector(".mx-board-stage").append(node);
  const e=editing={mark,at:p,node,field:null,key};
  try{ await M.load(); }
  catch{ node.querySelector("span").textContent="לא הצלחנו לטעון את מקלדת המתמטיקה. נסו שוב."; return setTimeout(()=>editing===e&&finishMath(false),2500); }
  if(editing!==e) return;
  node.innerHTML=`<math-field aria-label="נוסחה"></math-field>
    <button type="button" data-math="ok" title="הוספה ללוח">✓</button><button type="button" data-math="cancel" title="ביטול">✕</button>`;
  const f=e.field=node.querySelector("math-field");
  f.mathVirtualKeyboardPolicy="manual";
  f.value=mark?.latex||"";
  f.addEventListener("change",()=>editing===e&&finishMath(true));   // the keyboard's return key, Enter, or leaving the field
  f.addEventListener("focusin",()=>window.mathVirtualKeyboard?.show());
  // the buttons keep the field's focus, so leaving it does not count as done before the tap is read
  node.querySelectorAll("button").forEach(b=>b.addEventListener("pointerdown",ev=>{ ev.preventDefault(); finishMath(b.dataset.math==="ok"); }));
  f.focus(); window.mathVirtualKeyboard?.show();
}
function finishMath(keep){
  const e=editing; if(!e) return; editing=null;
  const latex=keep&&e.field?String(e.field.getValue?.("latex")??e.field.value??"").trim():null;
  try{ window.mathVirtualKeyboard?.hide(); }catch{}
  e.node.remove();
  if(latex===null||e.key!==key) return;   // cancelled, or another page by now
  const all=marks();
  if(e.mark){
    if(!all.includes(e.mark)||latex===e.mark.latex) return;
    remember(); if(latex) e.mark.latex=latex; else all.splice(all.indexOf(e.mark),1);   // emptied: gone
  }else if(latex){
    const L=window.MathlyBoardMath.layout(latex,MATH_SIZE), W=canvas.clientWidth;
    remember();
    all.push({kind:"math",latex,color:ink,size:MATH_SIZE,x:Math.max(8,Math.min(e.at[0],W-8-L.w)),y:Math.max(0,e.at[1]-(L.a+L.d)/2)});
  }else return;
  paint(); if(pages>1) drawPages();
}
if(window.MathlyBoardMath) window.MathlyBoardMath.onFonts=()=>el&&paint();

/* ---------- handing in ---------- */
// the whole sketch as a picture on white paper: as wide as the board, as tall as what is drawn
function snapshot(){
  const all=marks(); if(!all.some(m=>m.kind!=="card")) return null;
  const [,y0,,y1]=edges(all), top=Math.max(0,y0-24), W=canvas.clientWidth, H=Math.min(y1+24-top,8000), k=2;
  const out=document.createElement("canvas"); out.width=W*k; out.height=Math.round(H*k);
  const keep=ctx; ctx=out.getContext("2d"); paper="#fff";
  try{ ctx.fillStyle="#fff"; ctx.fillRect(0,0,out.width,out.height); ctx.setTransform(k,0,0,k,0,-top*k); all.forEach(draw); }
  finally{ ctx=keep; paper=PAPER; }
  return new Promise(ok=>out.toBlob(ok,"image/png"));
}
async function send(){
  const b=el.querySelector(".mx-board-send"), p=page, say=t=>{ if(page===p) b.innerHTML=t; };
  const blob=await snapshot();
  if(!blob){ say(`<span>הלוח ריק: אין מה להגיש</span>`); return setTimeout(()=>page===p&&drawSend(),2500); }
  b.disabled=true; say(`<span>מגישים…</span>`);
  let r; try{ r=await hand(p,blob); }catch(e){ r={error:e.message}; }
  b.disabled=false; say(r?.error?`<span>⚠ ${r.error}</span>`:`${ic("done")}<span>${sendLabel?"נשלחה":`הוגשה לשאלה ${p+1}`}</span>`);
  if(r?.close&&full) return setTimeout(closeFull,900);   // done: back to the window that asked
  setTimeout(()=>page===p&&!b.disabled&&drawSend(),3000);
}

document.addEventListener("keydown",e=>{
  if(editing&&e.key==="Escape"){ e.preventDefault(); e.stopImmediatePropagation(); return finishMath(false); }
  if(full&&e.key==="Escape"){ e.preventDefault(); e.stopImmediatePropagation(); return closeFull(); }   // back to the question, not out of it
  if(!shown()||editing||e.target.closest?.("input,textarea,[contenteditable],math-field")) return;
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
  el.querySelector(".mx-board-back").focus({preventScroll:true,focusVisible:false});   // reachable by keyboard, without a ring on a tap
}
function closeFull(){
  if(!full) return; if(editing) finishMath(true); if(naming) finishAngle(true); const f=full; full=null;
  el.classList.remove("full"); el.removeAttribute("role"); el.removeAttribute("aria-modal"); el.remove();
  restore(f.saved); f.done?.();
  if(layer?.isConnected&&desk()) again();
}
// the header's switch: beside the exercise on a desktop screen, full screen on a phone
const button=()=>`<button class="mx-board-btn" data-board-toggle aria-pressed="${isOn()&&desk()}" title="לוח טיוטה">${ic("pen")}<span>לוח</span></button>`;

window.MathlyBoard={button,mount,toggle,show,openFull,closeFull,isOn};
})();
