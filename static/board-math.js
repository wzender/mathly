/* Typed math on the sketch board (static/math-board.js).
   The student types with MathLive (static/vendor/mathlive, MIT, loaded only when first needed) and its on-screen
   math keyboard, set up here for ninth grade: digits, x and y, fractions, powers, roots, brackets, |x|, ± ≤ ≥ ≠, π,
   degrees, angles and triangles, plus a letters tab. What is typed is kept as LaTeX and drawn on the board's
   canvas by the small renderer below, so it moves, prints and is handed in with everything else. The renderer
   knows the LaTeX that keyboard makes; anything else is drawn as its plain name. */
(()=>{
const VENDOR="/static/vendor/mathlive/";
const SERIF='"STIX Two Text","Cambria Math","Times New Roman",serif';

/* ---------- MathLive ---------- */
let loading=null;
function load(){
  return loading||=new Promise((ok,no)=>{
    if(window.MathfieldElement||window.MathLive) return ok();
    const s=document.createElement("script"); s.src=VENDOR+"mathlive.min.js"; s.onload=ok; s.onerror=()=>{ loading=null; no(Error("mathlive")); };
    document.head.append(s);
  }).then(()=>{
    const M=window.MathfieldElement||window.MathLive?.MathfieldElement;
    M.fontsDirectory=VENDOR+"fonts"; M.soundsDirectory=null; M.keypressSound=null; M.plonkSound=null;
    const k=window.mathVirtualKeyboard; if(k&&!k.__mathly){ k.__mathly=true; k.layouts=[NINTH,"alphabetic"]; k.editToolbar="none"; }
  });
}
const key=(insert,label,tooltip,more={})=>({insert,label,tooltip,...more});
const NINTH={label:"123",tooltip:"מספרים ופעולות",rows:[
  ["[7]","[8]","[9]",key("\\div","÷","חילוק"),key("\\frac{#@}{#?}","a⁄b","שבר"),"x","y",key("\\pi","π","פאי"),"[backspace]"],
  ["[4]","[5]","[6]",key("\\times","×","כפל"),key("#@^2","x²","בריבוע"),key("#@^{#?}","xⁿ","חזקה"),"a","b",key("\\left(#0\\right)","( )","סוגריים")],
  ["[1]","[2]","[3]","[-]",key("\\sqrt{#0}","√","שורש"),key("\\sqrt[#?]{#0}","ⁿ√","שורש n"),key("\\left|#0\\right|","|x|","ערך מוחלט"),"[left]","[right]"],
  ["[0]","[.]","[=]","[+]",key("\\pm","±","פלוס מינוס"),key("\\le","≤","קטן או שווה"),key("\\ge","≥","גדול או שווה"),key("\\ne","≠","שונה"),"[return]"],
  [key("^{\\circ}","°","מעלות"),key("\\angle","∠","זווית"),key("\\triangle","△","משולש"),"<",">",",",key("\\perp","⊥","מאונך"),key("\\parallel","∥","מקביל"),"[hide-keyboard]"]]};

/* ---------- reading LaTeX ---------- */
const SYM={cdot:["⋅","op"],times:["×","op"],div:["÷","op"],pm:["±","op"],mp:["∓","op"],le:["≤","rel"],leq:["≤","rel"],ge:["≥","rel"],geq:["≥","rel"],
  ne:["≠","rel"],neq:["≠","rel"],approx:["≈","rel"],sim:["∼","rel"],cong:["≅","rel"],lt:["<","rel"],gt:[">","rel"],to:["→","rel"],
  Rightarrow:["⇒","rel"],Leftrightarrow:["⇔","rel"],in:["∈","rel"],perp:["⊥","rel"],parallel:["∥","rel"],mid:["|","rel"],
  pi:["π"],alpha:["α"],beta:["β"],gamma:["γ"],delta:["δ"],theta:["θ"],lambda:["λ"],mu:["μ"],sigma:["σ"],phi:["φ"],omega:["ω"],Delta:["Δ"],
  angle:["∠"],measuredangle:["∡"],triangle:["△"],circ:["°"],degree:["°"],infty:["∞"],cdots:["⋯"],ldots:["…"],dots:["…"],prime:["′"],
  vert:["|"],lvert:["|"],rvert:["|"],"%":["%"],"{":["{"],"}":["}"],lbrace:["{"],rbrace:["}"],colon:[":","punct"],",":[" ","space"],
  ":":[" ","space"],";":[" ","space"]," ":[" ","space"],quad:["  ","space"],qquad:["    ","space"],"!":["","space"],
  exponentialE:["e"],imaginaryI:["i"]};
const TEXT=new Set(["text","mathrm","textrm","operatorname","mbox","textit","mathit"]);
const WRAP=new Set(["mathbf","boldsymbol","mathsf","displaystyle","textstyle","mathnormal","bm"]);
const ANGLE_FREE=new Set(["(","[","|","{","−","+"]);

function tokens(s){
  const out=[]; let i=0;
  while(i<s.length){
    const c=s[i];
    if(c==="\\"){ let j=i+1; if(/[a-zA-Z]/.test(s[j]||"")) while(j<s.length&&/[a-zA-Z]/.test(s[j])) j++; else j++; out.push(s.slice(i,j)); i=j; }
    else if(/\s/.test(c)) i++;
    else{ out.push(c); i++; }
  }
  return out;
}
function parse(latex){
  const t=tokens(String(latex||"")); let i=0;
  const peek=()=>t[i], next=()=>t[i++];
  function list(stop){
    const items=[];
    while(i<t.length&&!stop.includes(peek())){
      const k=peek();
      if(k==="^"||k==="_"){ next(); const base=items.pop()||{t:"row",items:[]}; const s=base.t==="scripts"?base:{t:"scripts",base};
        s[k==="^"?"sup":"sub"]=arg(); items.push(s); continue; }
      if(k==="'"){ next(); items.push({t:"sym",s:"′"}); continue; }
      items.push(atom());
    }
    return items;
  }
  function group(close){ const items=list([close]); next(); return {t:"row",items}; }
  function arg(){
    if(peek()==="{"){ next(); return group("}"); }
    return i<t.length?atom():{t:"row",items:[]};
  }
  function raw(){   // a text argument, as written
    if(peek()!=="{") return next()||"";
    next(); let depth=1, s="";
    while(i<t.length){ const k=next(); if(k==="{") depth++; if(k==="}"&&!--depth) break;
      s+=k.startsWith("\\")?(SYM[k.slice(1)]?.[0]??(k.length===2?k[1]:k.slice(1))):k; }
    return s;
  }
  function delim(){ const k=next()||"."; if(k===".") return ""; if(k.startsWith("\\")) return SYM[k.slice(1)]?.[0]??k.slice(1); return k; }
  function atom(){
    const k=next();
    if(k==="{") return group("}");
    if(k==="}") return {t:"row",items:[]};
    if(k.startsWith("\\")){
      const c=k.slice(1);
      if(c==="frac"||c==="dfrac"||c==="tfrac"||c==="cfrac") return {t:"frac",n:arg(),d:arg()};
      if(c==="sqrt"){ let index=null; if(peek()==="["){ next(); index={t:"row",items:list(["]"])}; next(); } return {t:"sqrt",body:arg(),index}; }
      if(c==="left"){ const l=delim(), body={t:"row",items:list(["\\right"])}; next(); return {t:"fence",l,r:delim(),body}; }
      if(c==="right") return {t:"row",items:[]};
      if(TEXT.has(c)) return {t:"text",s:raw(),italic:c==="textit"||c==="mathit"};
      if(WRAP.has(c)) return peek()==="{"?arg():{t:"row",items:[]};
      if(c==="overline"||c==="bar"||c==="overrightarrow"||c==="vec"||c==="widehat"||c==="hat") return {t:"over",body:arg(),arrow:c==="overrightarrow"||c==="vec"};
      if(c==="placeholder"){ if(peek()==="["){ while(i<t.length&&next()!=="]"); } raw(); return {t:"ph"}; }
      if(SYM[c]){ const [s,kind]=SYM[c]; return kind==="space"?{t:"space",w:s.length*.17}:{t:"sym",s,kind}; }
      return {t:"text",s:c};   // unknown: its name, as text
    }
    if(/[a-zA-Z]/.test(k)) return {t:"sym",s:k,italic:true};
    if(k==="-") return {t:"sym",s:"−",kind:"op"};
    if(k==="+"||k==="*") return {t:"sym",s:k==="*"?"⋅":"+",kind:"op"};
    if(k==="="||k==="<"||k===">") return {t:"sym",s:k,kind:"rel"};
    if(k===","||k===";") return {t:"sym",s:k,kind:"punct"};
    return {t:"sym",s:k};
  }
  return {t:"row",items:list([])};
}

/* ---------- laying it out: each box has a width, a height above the baseline (a) and below it (d) ---------- */
const meter=document.createElement("canvas").getContext("2d");
const fontOf=(size,italic)=>`${italic?"italic ":""}${size}px ${SERIF}`;
function width(s,size,italic){ meter.font=fontOf(size,italic); return meter.measureText(s).width; }

function box(node,z){   // z: the font size
  switch(node.t){
    case "row": return row(node.items,z);
    case "sym":{ const w=width(node.s,z,node.italic);
      return {w,a:.72*z,d:.22*z,kind:node.kind,paint:(c,x,y)=>{ c.font=fontOf(z,node.italic); c.fillText(node.s,x,y); }}; }
    case "text":{ const w=width(node.s,z,node.italic);
      return {w,a:.72*z,d:.22*z,paint:(c,x,y)=>{ c.font=fontOf(z,node.italic); c.fillText(node.s,x,y); }}; }
    case "space": return {w:node.w*z,a:0,d:0,paint:()=>{}};
    case "ph": return {w:.5*z,a:.6*z,d:.1*z,paint:(c,x,y)=>{ c.save(); c.globalAlpha=.35; c.lineWidth=1; c.strokeRect(x+.05*z,y-.6*z,.4*z,.7*z); c.restore(); }};
    case "scripts": return scripts(node,z);
    case "frac": return frac(node,z);
    case "sqrt": return sqrt(node,z);
    case "fence": return fence(node,z);
    case "over":{ const b=box(node.body,z), lw=Math.max(1,.05*z);
      return {w:b.w,a:b.a+.14*z,d:b.d,paint:(c,x,y)=>{ b.paint(c,x,y); c.lineWidth=lw; c.beginPath(); c.moveTo(x,y-b.a-.08*z); c.lineTo(x+b.w,y-b.a-.08*z); c.stroke();
        if(node.arrow){ c.beginPath(); c.moveTo(x+b.w-.15*z,y-b.a-.15*z); c.lineTo(x+b.w,y-b.a-.08*z); c.lineTo(x+b.w-.15*z,y-b.a-.01*z); c.stroke(); } }}; }
  }
  return {w:0,a:0,d:0,paint:()=>{}};
}
function row(items,z){
  const parts=[]; let prev=null;
  for(const it of items){
    const b=box(it,z);
    // a little room around + − = and the like; a sign at the start, or after another sign or a bracket, is a unary one
    const unary=b.kind==="op"&&(!prev||prev.kind==="op"||prev.kind==="rel"||prev.open);
    const pad=b.kind==="rel"?.28*z:b.kind==="op"&&!unary?.2*z:b.kind==="punct"?0:0;
    const after=b.kind==="punct"?.2*z:pad;
    if(it.t==="frac"){ parts.push({b:{w:.08*z,a:0,d:0,paint:()=>{}}}); }
    parts.push({b,pre:pad,post:after});
    if(it.t==="frac") parts.push({b:{w:.08*z,a:0,d:0,paint:()=>{}}});
    prev=it.t==="sym"&&ANGLE_FREE.has(it.s)&&b.kind!=="op"?{open:true}:b;
  }
  let w=0, a=.72*z*(items.length?0:1), d=.22*z*(items.length?0:1);
  for(const p of parts){ w+=(p.pre||0)+p.b.w+(p.post||0); a=Math.max(a,p.b.a); d=Math.max(d,p.b.d); }
  return {w,a,d,paint:(c,x,y)=>{ let at=x; for(const p of parts){ at+=p.pre||0; p.b.paint(c,at,y); at+=p.b.w+(p.post||0); } }};
}
function scripts(node,z){
  const b=box(node.base,z), s=Math.max(9,.7*z);
  const sup=node.sup?box(node.sup,s):null, sub=node.sub?box(node.sub,s):null;
  const up=Math.max(.38*z,b.a-.38*z), down=Math.max(.2*z,b.d+.04*z-(sub?.a||0)*.2);
  const gap=.04*z, w=b.w+gap+Math.max(sup?.w||0,sub?.w||0);
  return {w,a:Math.max(b.a,sup?up+sup.a:0),d:Math.max(b.d,sub?down+sub.d:0),
    paint:(c,x,y)=>{ b.paint(c,x,y); sup?.paint(c,x+b.w+gap,y-up); sub?.paint(c,x+b.w+gap,y+down); }};
}
function frac(node,z){
  const s=Math.max(10,.85*z), n=box(node.n,s), d=box(node.d,s);
  const axis=.28*z, gap=.12*z, lw=Math.max(1,.055*z), w=Math.max(n.w,d.w)+.24*z;
  return {w,a:axis+gap+n.d+n.a,d:Math.max(0,d.a+d.d+gap-axis),
    paint:(c,x,y)=>{ const bar=y-axis;
      c.save(); c.lineWidth=lw; c.beginPath(); c.moveTo(x+.04*z,bar); c.lineTo(x+w-.04*z,bar); c.stroke(); c.restore();
      n.paint(c,x+(w-n.w)/2,bar-gap-n.d); d.paint(c,x+(w-d.w)/2,bar+gap+d.a); }};
}
function sqrt(node,z){
  const b=box(node.body,z), idx=node.index?.items?.length?box(node.index,Math.max(9,.55*z)):null;
  const top=Math.max(b.a,.72*z)+.16*z, hook=.58*z, shift=idx?Math.max(0,idx.w-.28*z):0, lw=Math.max(1,.055*z);
  return {w:shift+hook+b.w+.12*z,a:Math.max(top+.06*z,idx?.62*top+idx.a+idx.d:0),d:Math.max(b.d+.06*z,.22*z),
    paint:(c,x,y)=>{ const x0=x+shift, bottom=y+Math.max(b.d,.05*z)+.04*z, t=y-top;
      c.save(); c.lineWidth=lw; c.lineJoin="round"; c.beginPath();
      c.moveTo(x0,y-.32*z); c.lineTo(x0+.12*z,y-.4*z); c.lineTo(x0+.3*z,bottom); c.lineTo(x0+hook,t); c.lineTo(x0+hook+b.w+.1*z,t); c.stroke(); c.restore();
      b.paint(c,x0+hook+.04*z,y); idx?.paint(c,x0+.3*z-idx.w,y-.62*top); }};
}
function fence(node,z){
  const b=box(node.body,z), tall=b.a+b.d>1.15*z;
  const side=s=>{ if(!s) return {w:.05*z,paint:()=>{}};
    const w=width(s,z,false);
    return {w,paint:(c,x,y)=>{ c.save(); c.font=fontOf(z,false);
      if(tall){ const h=b.a+b.d+.12*z, k=h/(.98*z); c.translate(x,y-b.a-.06*z); c.scale(1,k); c.fillText(s,0,.76*z); }
      else c.fillText(s,x,y);
      c.restore(); }}; };
  const l=side(node.l), r=side(node.r), pad=.04*z;
  return {w:l.w+pad+b.w+pad+r.w,a:Math.max(b.a+.08*z,.75*z),d:Math.max(b.d+.08*z,.25*z),
    paint:(c,x,y)=>{ l.paint(c,x,y); b.paint(c,x+l.w+pad,y); r.paint(c,x+l.w+pad+b.w+pad,y); }};
}

const cache=new Map();
// the laid-out formula at this font size: w, a and d, and paint(context, x, baseline y) in the context's colors
function layout(latex,size){
  const k=size+"|"+latex;
  if(!cache.has(k)){ if(cache.size>500) cache.clear(); cache.set(k,box(parse(latex),size)); }
  return cache.get(k);
}
// widths are measured with the math font: when it arrives, measure again
document.fonts?.addEventListener?.("loadingdone",()=>{ cache.clear(); window.MathlyBoardMath.onFonts?.(); });

window.MathlyBoardMath={load,layout,parse};
})();
