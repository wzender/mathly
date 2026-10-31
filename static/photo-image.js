/* Shared camera preparation for answer scans and photographed-problem help. */
window.MathlyPhoto={async prepare(file){
  let bitmap,temporary;
  try{bitmap=await createImageBitmap(file,{imageOrientation:"from-image"});}
  catch{
    temporary=URL.createObjectURL(file);
    bitmap=new Image();
    try{await new Promise((ok,no)=>{bitmap.onload=ok;bitmap.onerror=no;bitmap.src=temporary;});}
    finally{URL.revokeObjectURL(temporary);}
  }
  try{
    const scale=Math.min(1,1600/Math.max(bitmap.width,bitmap.height)),canvas=document.createElement("canvas");
    canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
    canvas.getContext("2d").drawImage(bitmap,0,0,canvas.width,canvas.height);
    return await new Promise((ok,no)=>canvas.toBlob(blob=>blob?ok(blob):no(Error("image")),"image/jpeg",.85));
  }finally{bitmap.close?.();}
}};
