/* Math as pictures. The content writes math as plain text between $…$ (math.js shows it as <span class="m">), e.g.
   "1/(2x) + x² ≥ √3". This file turns that text into TeX (a/b becomes a stacked fraction, √ a root, ² a raised
   exponent) and MathJax draws it as an SVG image in place of the text. The text stays as the picture's label, and
   whatever cannot be read (Hebrew words, unknown signs), or everything when MathJax does not load, keeps showing as text. */
(()=>{
const SUP={"⁰":"0","¹":"1","²":"2","³":"3","⁴":"4","⁵":"5","⁶":"6","⁷":"7","⁸":"8","⁹":"9","⁻":"-","⁺":"+","ⁿ":"n","ᵐ":"m"};
const SUB={"₀":"0","₁":"1","₂":"2","₃":"3","₄":"4","₅":"5","₆":"6","₇":"7","₈":"8","₉":"9"};
const OPS={"−":"-","–":"-","·":"\\cdot ","×":"\\times ","÷":"\\div ","≠":"\\neq ","≥":"\\geq ","≤":"\\leq ","±":"\\pm ",
  "⇒":"\\Rightarrow ","→":"\\to ","↔":"\\leftrightarrow ","∥":"\\parallel ","⊥":"\\perp ","△":"\\triangle ",
  "∢":"\\measuredangle ","∼":"\\sim ","…":"\\ldots ","%":"\\%","π":"\\pi ","α":"\\alpha ","β":"\\beta ","∞":"\\infty ",
  "+":"+","-":"-","=":"=","<":"<",">":">",",":",",":":":","?":"?","!":"!","|":"|","'":"'",".":"."};
const TOKEN=/\d+(?:\.\d+)?|[A-Za-z]|[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺ⁿᵐ]+|[₀₁₂₃₄₅₆₇₈₉]+|\s+|./gu;

// plain math text to TeX, or null when it cannot be read
function toTex(src){
  const toks=String(src).match(TOKEN)||[];
  if(!toks.length) return null;
  let i=0;
  const fail=()=>{ throw new Error("unreadable"); };
  // one atom: a number, a letter, a (group) or a √atom; `inner` is a group's content, used inside a fraction or root
  function atom(){
    const k=toks[i++];
    if(k===undefined) fail();
    if(/^[\d.]/.test(k)||/^[A-Za-zΔ]$/.test(k)) return {kind:"a",t:k==="Δ"?"\\Delta ":k};
    if(k==="("||k==="["){
      const c=k==="("?")":"]", inner=join(seq(c)), big=inner.includes("\\frac");
      return {kind:"a",t:big?`\\left${k}${inner}\\right${c}`:`${k}${inner}${c}`,inner};
    }
    if(k==="√"){ const a=atom(); return {kind:"a",t:`\\sqrt{${a.inner??a.t}}`}; }
    i--; return null;
  }
  function seq(close){
    const out=[];
    while(i<toks.length){
      const k=toks[i];
      if(k===close){ i++; return out; }
      if(k===")"||k==="]") fail();
      const a=atom();
      if(a){ out.push(a); continue; }
      i++;
      const prev=out[out.length-1];
      if(/^\s+$/.test(k)) out.push({kind:"s"});
      else if(SUP[k[0]]!==undefined||k==="^"||k==="°"){
        if(prev?.kind!=="a"||prev.sup) fail();
        let up;
        if(k==="°") up="\\circ";
        else if(k==="^"){ const b=atom(); if(!b) fail(); up=b.inner??b.t; }
        else up=[...k].map(c=>SUP[c]).join("");
        prev.t=`${prev.t}^{${up}}`; prev.sup=true; delete prev.inner;
      }
      else if(SUB[k[0]]!==undefined){
        if(prev?.kind!=="a"||prev.sup||prev.sub) fail();
        prev.t=`${prev.t}_{${[...k].map(c=>SUB[c]).join("")}}`; prev.sub=true; delete prev.inner;
      }
      else if(k==="/") out.push({kind:"/"});
      else if(OPS[k]!==undefined) out.push({kind:"o",t:OPS[k]});
      else fail();
    }
    if(close) fail();
    return out;
  }
  // atoms side by side make one term (2x, 3(x + 1)); a / between two terms is a fraction
  function join(items){
    const terms=[];
    for(const it of items){
      const prev=terms[terms.length-1];
      if(it.kind==="a"&&prev?.kind==="a"){ prev.t+=it.t; delete prev.inner; prev.sup=it.sup; }
      else terms.push({...it});
    }
    const near=(j,step)=>{ while(terms[j]?.kind==="s") j+=step; return j; };
    for(let j=0;j<terms.length;j++){
      if(terms[j].kind!=="/") continue;
      const a=near(j-1,-1), b=near(j+1,1), num=terms[a], den=terms[b];
      if(num?.kind!=="a"||den?.kind!=="a") continue;
      terms.splice(a,b-a+1,{kind:"a",t:`\\frac{${num.inner??num.t}}{${den.inner??den.t}}`});
      j=a;
      // a fraction followed by a term (1/2x) already took it as its denominator; one before it is a coefficient
    }
    return terms.map(x=>x.kind==="s"?" ":x.kind==="/"?"/":x.t).join("").replace(/\s+/g," ").trim();
  }
  try{ const tex=join(seq(null)); return tex||null; }catch{ return null; }
}

/* drawing: each span.m once, the same picture reused for the same text */
const cache=new Map();
function picture(text){
  if(cache.has(text)) return cache.get(text);
  const tex=toTex(text);
  let svg=null;
  if(tex) try{
    const out=window.MathJax.tex2svg(tex.includes("\\frac")?`\\displaystyle ${tex}`:tex,{display:false}).querySelector("svg");
    if(out&&!out.querySelector("[data-mml-node=merror]")){ out.setAttribute("aria-hidden","true"); out.removeAttribute("role"); svg=out; }
  }catch{}
  cache.set(text,svg);
  return svg;
}
function render(scope=document.body){
  if(!window.MathJax?.tex2svg) return;
  for(const el of scope.querySelectorAll("span.m:not([data-tex])")){
    const text=el.textContent, svg=picture(text);
    el.dataset.tex=svg?"1":"0";
    if(!svg) continue;
    el.replaceChildren(svg.cloneNode(true));
    el.setAttribute("role","img"); el.setAttribute("aria-label",text); el.classList.add("m-img");
  }
}
globalThis.MathlyTex={toTex,render};
if(typeof document==="undefined") return;
let queued=false;
const watch=new MutationObserver(()=>{ if(queued) return; queued=true; queueMicrotask(()=>{ queued=false; render(); }); });
window.MathJax={tex:{packages:{"[+]":["ams"]}},svg:{fontCache:"none"},options:{enableMenu:false},
  startup:{typeset:false,ready(){ window.MathJax.startup.defaultReady(); render(); watch.observe(document.body,{childList:true,subtree:true}); }}};
const s=document.createElement("script");
s.src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js"; s.async=true;
document.head.append(s);
})();
