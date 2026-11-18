import {credentials} from "./auth";
const base=(import.meta.env.VITE_API_URL||"http://localhost:8000").replace(/\/$/,"");
export async function request(path,options={}){
const identity=await credentials();if(!identity)throw Error("Sign in required");
const {body,...opts}=options;const form=body instanceof FormData;
const r=await fetch(base+path,{...opts,headers:{Authorization:"Bearer "+identity.token,...(!form&&body?{"Content-Type":"application/json"}:{})},body:form?body:body?JSON.stringify(body):undefined});
const result=await r.json().catch(()=>({}));if(!r.ok)throw Error(typeof result.detail==="string"?result.detail:"Request failed ("+r.status+")");return result;
}
export async function uploadDocument(cid,file){
const r=await request("/claims/"+cid+"/documents/presign",{method:"POST",body:{filename:file.name}});
const id=r.document.id,form=new FormData();
if(r.upload.mode==="local"){form.append("file",file);return request("/claims/"+cid+"/documents/"+id+"/local-upload",{method:"POST",body:form});}
Object.entries(r.upload.fields).forEach(([k,v])=>form.append(k,v));form.append("file",file);
const s=await fetch(r.upload.url,{method:"POST",body:form});if(!s.ok)throw Error("S3 upload failed "+s.status);
return request("/claims/"+cid+"/documents/"+id+"/complete",{method:"POST"});
}