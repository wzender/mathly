(()=>{
// Keep the pairing through a refresh without leaving its secret in the URL.
const incomingToken=location.hash.slice(1);
let token=incomingToken;
try{
  if(incomingToken)sessionStorage.setItem("mathly.phone-token",incomingToken);
  else token=sessionStorage.getItem("mathly.phone-token")||"";
  history.replaceState(null,"",location.pathname);
}catch{} // Private browsers may disable storage; keep the fragment in that case.
const camera=document.getElementById("camera"),take=document.getElementById("take"),send=document.getElementById("send"),
  preview=document.getElementById("preview"),status=document.getElementById("status");
let photo=null,previewURL=null;
if(!token){status.textContent="סרקו שוב את הקוד שמופיע במחשב כדי להתחבר.";take.disabled=true;return;}
take.onclick=()=>camera.click();
camera.onchange=async()=>{
  const file=camera.files[0];camera.value=""; if(!file)return;
  photo=null;take.disabled=true;send.hidden=true;status.textContent="מכינים את התמונה…";
  try{
    photo=await window.MathlyPhoto.prepare(file);
    if(!photo)throw Error("image");
  }catch{
    if(["image/jpeg","image/png","image/webp"].includes(file.type))photo=file;
  }
  if(!photo||photo.size>5000000){
    preview.hidden=true;take.disabled=false;
    status.textContent="לא הצלחנו להכין את התמונה. נסו לצלם שוב או לבחור תמונת JPEG, PNG או WebP קטנה מ־5MB.";
    photo=null;return;
  }
  if(previewURL)URL.revokeObjectURL(previewURL);
  preview.src=previewURL=URL.createObjectURL(photo);preview.hidden=false;
  send.hidden=false;take.disabled=false;status.textContent="בדקו שהתרגיל ברור ואז שלחו למחשב.";
};
send.onclick=async()=>{
  if(!photo)return;
  send.disabled=take.disabled=true;status.textContent="שולחים ופותרים… השאירו את העמוד פתוח.";
  try{
    const form=new FormData();form.append("photo",photo,"problem.jpg");
    const response=await fetch("/api/math/phone-photo",{method:"POST",headers:{"X-Photo-Token":token},body:form});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"לא הצלחנו לשלוח. נסו שוב.");
    status.textContent=data.readable?"הפתרון מוכן במחשב!":"התמונה התקבלה, אך אינה קריאה. פתחו קישור חדש במחשב וצלמו שוב.";
    send.hidden=take.hidden=true;
  }catch(error){status.textContent=error.message;send.disabled=take.disabled=false;}
};
})();
