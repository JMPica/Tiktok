/** Blau de Mar TikTok Studio V3: Cloudflare Free + local FFmpeg worker.
 * All studio routes require verified Cloudflare Access JWT; agent uses its own secret.
 * This is a migration foundation, NOT a production deployment.
 */
import { createRemoteJWKSet, jwtVerify } from 'jose';

const PART = 8 * 1024 * 1024;
const MAX_NAME = 180;
const jwksCache = new Map();
const json = (obj, code=200) => Response.json(obj,{status:code,headers:{'Cache-Control':'no-store'}});
function fail(code,msg){return json({error:msg},code);}
function filename(n){return String(n??'').split(/[\\/]/).pop().replace(/[^\w .()À-ÿ-]/g,'_').slice(0,MAX_NAME);}
function goodMode(m){return ['automatic','real','creative'].includes(m);}
const ALLOWED_STYLES = new Set(['auto','tacho_humano','tacho_humor','backstage','microvlog','pov','fast_cuts','clean_talking','educativo','respuesta_comentario','premium','asmr','cinematic','before_after','reveal','loop','trend_adaptation','service_conversion']);
function randomId(){return crypto.randomUUID().replaceAll('-','');}
function bearer(req,env){const s=req.headers.get('Authorization')??'';return s.startsWith('Bearer ')&&env.AGENT_TOKEN&&s.slice(7)===env.AGENT_TOKEN;}
function requireAgent(req,env){if(!bearer(req,env))throw {status:401,message:'Agent unauthorized'};return 'agent';}
async function who(req,env){
  if(!env.ACCESS_TEAM_DOMAIN||!env.ACCESS_AUD||env.ACCESS_AUD.startsWith('REPLACE_'))throw {status:503,message:'Cloudflare Access not configured'};
  const token=req.headers.get('Cf-Access-Jwt-Assertion');if(!token)throw {status:401,message:'Sign in with Cloudflare Access'};
  const team=env.ACCESS_TEAM_DOMAIN.replace(/^https?:\/\//,'').replace(/\/$/,'');
  let jwks=jwksCache.get(team);if(!jwks){jwks=createRemoteJWKSet(new URL(`https://${team}/cdn-cgi/access/certs`));jwksCache.set(team,jwks);}
  const verified=await jwtVerify(token,jwks,{audience:env.ACCESS_AUD,issuer:`https://${team}`});
  const email=String(verified.payload.email??'').toLowerCase().trim();
  if(!email||!email.includes('@'))throw {status:403,message:'No verified user email'};
  return {email,role:email===String(env.OWNER_EMAIL||'').toLowerCase().trim()?'owner':'editor'};
}
async function requireOwner(user){if(user.role!=='owner')throw {status:403,message:'Owner required'};}
async function getUpload(env,id){return env.DB.prepare('SELECT * FROM uploads WHERE id=?').bind(id).first();}
async function getJob(env,id){return env.DB.prepare('SELECT * FROM jobs WHERE id=?').bind(id).first();}
function assertOwner(row,user){if(!row||(user.role!=='owner'&&row.owner!==user.email))throw {status:404,message:'Not found'};}
async function bodyJSON(req){try{return await req.json()}catch{throw {status:400,message:'JSON required'}}}
async function objectStream(bucket,key){const obj=await bucket.get(key);if(!obj)throw {status:404,message:'Object missing'};return new Response(obj.body,{headers:{'Content-Type':obj.httpMetadata?.contentType||'video/mp4','Cache-Control':'private, no-store','Accept-Ranges':'none'}});}

async function beginUpload(req,env,user){
 const b=await bodyJSON(req);const name=filename(b.filename);const size=Number(b.size_bytes);
 const max=Number(env.MAX_UPLOAD_BYTES||1073741824);
 if(!name||!(/\.(mp4|mov|m4v)$/i).test(name))throw {status:422,message:'Solo vídeos MP4/MOV'};
 if(!Number.isSafeInteger(size)||size<1||size>max)throw {status:413,message:'Tamaño no permitido'};
 const id=randomId();const key=`originals/${id}/${name}`;const multi=await env.BUCKET.createMultipartUpload(key,{httpMetadata:{contentType:name.toLowerCase().endsWith('.mov')?'video/quicktime':'video/mp4'}});
 await env.DB.prepare('INSERT INTO uploads (id,owner,filename,size_bytes,r2_key,multipart_id,status,created_at) VALUES (?,?,?,?,?,?,?,?)')
 .bind(id,user.email,name,size,key,multi.uploadId,'uploading',Date.now()).run();
 return json({id,chunk_size:PART,total_parts:Math.ceil(size/PART)});
}
async function uploadPart(req,env,user,id,partNo){
 const row=await getUpload(env,id);assertOwner(row,user);
 if(row.status!=='uploading')throw {status:409,message:'Subida ya finalizada'};
 const count=Math.ceil(row.size_bytes/PART);if(!Number.isInteger(partNo)||partNo<1||partNo>count)throw {status:400,message:'Parte no válida'};
 const expected=Math.min(PART,row.size_bytes-(partNo-1)*PART);
 if(req.headers.get('Content-Length')&&Number(req.headers.get('Content-Length'))!==expected)throw {status:422,message:'Tamaño de parte incorrecto'};
 const chunk=await req.arrayBuffer();if(chunk.byteLength!==expected)throw {status:422,message:'Parte incompleta'};
 const mpu=env.BUCKET.resumeMultipartUpload(row.r2_key,row.multipart_id);
 const uploaded=await mpu.uploadPart(partNo,chunk);
 await env.DB.prepare('INSERT INTO upload_parts(upload_id,part_no,etag,size_bytes) VALUES(?,?,?,?) ON CONFLICT(upload_id,part_no) DO UPDATE SET etag=excluded.etag,size_bytes=excluded.size_bytes')
 .bind(id,partNo,uploaded.etag,expected).run();
 return json({part_no:partNo,ok:true});
}
async function finalizeUpload(env,user,id){
 const row=await getUpload(env,id);assertOwner(row,user);
 if(row.status==='uploaded')return json({id,status:'uploaded'});
 if(row.status!=='uploading')throw {status:409,message:'Estado no válido'};
 const {results}=await env.DB.prepare('SELECT part_no,etag,size_bytes FROM upload_parts WHERE upload_id=? ORDER BY part_no').bind(id).all();
 if(results.length!==Math.ceil(row.size_bytes/PART)||results.reduce((a,b)=>a+b.size_bytes,0)!==row.size_bytes)
 throw {status:422,message:'Faltan partes del vídeo'};
 await env.BUCKET.resumeMultipartUpload(row.r2_key,row.multipart_id).complete(results.map(p=>({partNumber:p.part_no,etag:p.etag})));
 await env.DB.prepare("UPDATE uploads SET status='uploaded' WHERE id=? AND status='uploading'").bind(id).run();
 return json({id,status:'uploaded'});
}
async function createJob(req,env,user,uid){
 const row=await getUpload(env,uid);assertOwner(row,user);
 if(row.status!=='uploaded')throw {status:409,message:'Termina primero la subida'};
 const b=await bodyJSON(req);const mode=b.mode||'automatic';if(!goodMode(mode))throw {status:422,message:'Modo no válido'};
 const style=b.style||'auto';if(!ALLOWED_STYLES.has(style))throw {status:422,message:'Estilo no válido'};
 const id=randomId();await env.DB.prepare('INSERT INTO jobs(id,upload_id,owner,mode,style,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)')
  .bind(id,uid,user.email,mode,style,'queued',Date.now(),Date.now()).run();
 return json({id,status:'queued'},201);
}
async function userJobs(env,user){const q=user.role==='owner'? 'SELECT id,upload_id,owner,status,mode,style,error,created_at,updated_at FROM jobs ORDER BY created_at DESC LIMIT 80':
  'SELECT id,upload_id,owner,status,mode,style,error,created_at,updated_at FROM jobs WHERE owner=? ORDER BY created_at DESC LIMIT 80';
 const {results}=await (user.role==='owner'?env.DB.prepare(q):env.DB.prepare(q).bind(user.email)).all();return json({items:results});}
async function userJob(env,user,id){const j=await getJob(env,id);assertOwner(j,user);return json({id:j.id,status:j.status,mode:j.mode,style:j.style,owner:j.owner,sha256:j.result_sha256,error:j.error,qc:j.qc?JSON.parse(j.qc):null,has_preview:!!j.r2_key,approved_at:j.approved_at});}
async function review(req,env,user,id,approve){await requireOwner(user);const j=await getJob(env,id);assertOwner(j,user);
 if(j.status!=='needs_approval')throw {status:409,message:'Este vídeo no espera revisión'};
 const b=approve?await bodyJSON(req):{};
 if(approve&&(!b.confirm||b.sha256!==j.result_sha256))throw {status:409,message:'Confirma el hash del archivo exacto'};
 await env.DB.prepare('UPDATE jobs SET status=?, approved_by=?, approved_sha256=?, approved_at=?,updated_at=? WHERE id=? AND status=\'needs_approval\'')
 .bind(approve?'approved':'rejected',user.email,approve?j.result_sha256:null,approve?Date.now():null,Date.now(),id).run();
 return json({status:approve?'approved':'rejected',published:false});}

// Agent has dedicated token, always uses outbound HTTPS, and never needs direct database or R2 credentials.
async function claim(env){
 const now=Date.now(),lease=now+2*60*60*1000, id=randomId();
 const selected=await env.DB.prepare("UPDATE jobs SET status='processing',lease_until=?,agent_id=?,updated_at=? WHERE id=(SELECT id FROM jobs WHERE status='queued' OR (status='processing' AND lease_until<?) ORDER BY created_at LIMIT 1) RETURNING *")
 .bind(lease,id,now,now).first();
 if(!selected)return json({job:null});
 return json({job:{id:selected.id,upload_id:selected.upload_id,mode:selected.mode,style:selected.style||'auto',lease_until:lease,agent_id:id}});
}
async function agentJob(env,id){const j=await getJob(env,id);if(!j||j.status!=='processing')throw {status:404,message:'Not processing'};return j;}
async function agentSource(env,id){const j=await agentJob(env,id);const u=await getUpload(env,j.upload_id);return objectStream(env.BUCKET,u.r2_key);}
async function startOutput(req,env,id){const j=await agentJob(env,id);if(j.output_multipart_id)throw {status:409,message:'Output already started'};
 const key=`renders/${id}.mp4`,mpu=await env.BUCKET.createMultipartUpload(key,{httpMetadata:{contentType:'video/mp4'}});
 await env.DB.prepare('UPDATE jobs SET r2_key=?,output_multipart_id=?,updated_at=? WHERE id=? AND status=\'processing\'').bind(key,mpu.uploadId,Date.now(),id).run();
 return json({chunk_size:PART});}
async function outputPart(req,env,id,partNo){const j=await agentJob(env,id);
 if(!j.output_multipart_id)throw {status:409,message:'Output not started'};
 if(!Number.isInteger(partNo)||partNo<1||partNo>500)throw {status:422,message:'Invalid part number'};
 const chunk=await req.arrayBuffer();if(!chunk.byteLength||chunk.byteLength>PART)throw {status:422,message:'Invalid part size'};
 const mpu=env.BUCKET.resumeMultipartUpload(j.r2_key,j.output_multipart_id);
 const part=await mpu.uploadPart(partNo,chunk);
 await env.DB.prepare('INSERT INTO job_output_parts(job_id,part_no,etag,size_bytes) VALUES(?,?,?,?) ON CONFLICT(job_id,part_no) DO UPDATE SET etag=excluded.etag,size_bytes=excluded.size_bytes')
  .bind(id,partNo,part.etag,chunk.byteLength).run();
 return json({part_no:partNo});}
async function outputFinish(req,env,id){const j=await agentJob(env,id);if(!j.output_multipart_id)throw {status:409,message:'No output'};
 const b=await bodyJSON(req);if(!/^[0-9a-f]{64}$/.test(String(b.sha256||'')))throw {status:422,message:'sha256 missing'};
 if(!b.qc?.decode_ok||!b.qc?.audio_present)throw {status:422,message:'QC did not pass'};
 const {results}=await env.DB.prepare('SELECT part_no,etag,size_bytes FROM job_output_parts WHERE job_id=? ORDER BY part_no').bind(id).all();
 if(!results.length||results.some((p,i)=>p.part_no!==i+1)||results.slice(0,-1).some(p=>p.size_bytes!==PART))throw {status:422,message:'Incomplete output parts'};
 await env.BUCKET.resumeMultipartUpload(j.r2_key,j.output_multipart_id).complete(results.map(p=>({partNumber:p.part_no,etag:p.etag})));
 await env.DB.prepare("UPDATE jobs SET status='needs_approval',result_sha256=?,qc=?,updated_at=? WHERE id=? AND status='processing'")
 .bind(b.sha256,JSON.stringify(b.qc).slice(0,3000),Date.now(),id).run();return json({status:'needs_approval'});}
async function jobNeedsReview(req,env,id){const j=await agentJob(env,id);const b=await bodyJSON(req);
 await env.DB.prepare("UPDATE jobs SET status='needs_review',error=?,updated_at=? WHERE id=? AND status='processing'").bind(String(b.reason||'No hay escenas fiables').slice(0,400),Date.now(),id).run();
 return json({status:'needs_review'});}
async function jobError(req,env,id){const j=await agentJob(env,id);const b=await bodyJSON(req);
 await env.DB.prepare("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE id=? AND status='processing'").bind(String(b.error||'Unknown error').slice(0,400),Date.now(),id).run();return json({status:'failed'});}

async function router(req,env){
 const u=new URL(req.url),p=u.pathname,m=req.method;
 if(p==='/api/health')return json({status:'ok',version:'4.0-dev-cloudflare-local',paid_ai:false,autopublish:false});
 if(p.startsWith('/api/agent/')){
  requireAgent(req,env);
  if(m==='POST'&&p==='/api/agent/claim')return claim(env);
  let x=p.match(/^\/api\/agent\/jobs\/([0-9a-f]{32})(?:\/(source|output\/start|output\/parts\/(\d+)|output\/finish|needs-review|fail))?$/);
  if(!x)throw {status:404,message:'No agent route'};
  const id=x[1],action=x[2];
  if(m==='GET'&&action==='source')return agentSource(env,id);
  if(m==='POST'&&action==='output/start')return startOutput(req,env,id);
  if(m==='PUT'&&action?.startsWith('output/parts/'))return outputPart(req,env,id,Number(x[3]));
  if(m==='POST'&&action==='output/finish')return outputFinish(req,env,id);
  if(m==='POST'&&action==='needs-review')return jobNeedsReview(req,env,id);
  if(m==='POST'&&action==='fail')return jobError(req,env,id);
  throw {status:404,message:'Invalid agent endpoint'};
 }
 const user=await who(req,env);
 // Forbid cross-site form requests using the Access session cookie.
 if(!['GET','HEAD','OPTIONS'].includes(m)){const origin=req.headers.get('Origin');if(origin&&origin!==u.origin)throw {status:403,message:'Cross-origin mutation denied'};}
 if(m==='GET'&&p==='/api/me')return json(user);
 if(m==='POST'&&p==='/api/uploads')return beginUpload(req,env,user);
 const up=p.match(/^\/api\/uploads\/([0-9a-f]{32})(?:\/(parts\/(\d+)|finalize|render))?$/);
 if(up){const id=up[1];
  if(m==='GET'&&!up[2]){const row=await getUpload(env,id);assertOwner(row,user);const {results}=await env.DB.prepare('SELECT part_no FROM upload_parts WHERE upload_id=?').bind(id).all();return json({id,status:row.status,uploaded_parts:results.map(x=>x.part_no),size_bytes:row.size_bytes})}
  if(m==='PUT'&&up[2]?.startsWith('parts/'))return uploadPart(req,env,user,id,Number(up[3]));
  if(m==='POST'&&up[2]==='finalize')return finalizeUpload(env,user,id);
  if(m==='POST'&&up[2]==='render')return createJob(req,env,user,id);
 }
 if(m==='GET'&&p==='/api/jobs')return userJobs(env,user);
 const job=p.match(/^\/api\/jobs\/([0-9a-f]{32})(?:\/(preview|download|approve|reject))?$/);
 if(job){const id=job[1],j=await getJob(env,id);assertOwner(j,user);
  if(m==='GET'&&!job[2])return userJob(env,user,id);
  if(m==='GET'&&['preview','download'].includes(job[2])){
   if(!j.r2_key||!['needs_approval','approved'].includes(j.status))throw {status:404,message:'Preview unavailable'};
   const resp=await objectStream(env.BUCKET,j.r2_key);
   if(job[2]==='download')resp.headers.set('Content-Disposition',`attachment; filename="blau-${id.slice(0,8)}.mp4"`);
   return resp;
  }
  if(m==='POST'&&job[2]==='approve')return review(req,env,user,id,true);
  if(m==='POST'&&job[2]==='reject')return review(req,env,user,id,false);
 }
 throw {status:404,message:'Not found'};
}

export default {async fetch(req,env,ctx){
 try{
   const pathname=new URL(req.url).pathname;
   if(pathname.startsWith('/api/'))return await router(req,env);
   // IMPORTANT: protect static assets via Cloudflare Access application policy.
   return await env.ASSETS.fetch(req);
 }catch(e){return fail(e?.status||500,(e?.status?e.message:'Server error'));}
}};
