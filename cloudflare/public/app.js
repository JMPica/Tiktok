const $=id=>document.getElementById(id);
const PART=8*1024*1024;
let me=null,current=null,uploading=false;
const texts={queued:'En cua',processing:'Editant',needs_approval:'Per revisar',needs_review:'Cal revisar el material',approved:'Aprovat',rejected:'Descartat',failed:'Error'};
async function api(path,opts={}){
 const r=await fetch('/api'+path,{credentials:'same-origin',cache:'no-store',...opts});
 if(!r.ok){let e;try{e=await r.json()}catch{}throw new Error(`${r.status}: ${e?.error||'Error al servidor'}`)}
 return r;
}
const msg=(s)=>{$('alert').textContent=s};
const apiJSON=async(path,opts)=> (await api(path,opts)).json();
const post=(path,data={})=>apiJSON(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
async function boot(){try{me=await apiJSON('/me');$('user').textContent=`Sessió: ${me.email} · ${me.role==='owner'?'Administració':'Equip'}`;await refresh();setInterval(refresh,10000)}catch(e){msg(`No s'ha pogut iniciar la sessió: ${e.message}`)}}
async function refresh(){if(!me)return;try{const d=await apiJSON('/jobs');$('jobs').innerHTML='';if(!d.items.length){$('jobs').textContent='Encara no hi ha vídeos.';return;}for(const j of d.items){const b=document.createElement('button');b.className='job';b.innerHTML=`<strong>${texts[j.status]||j.status}</strong><span class="small"></span>`;b.querySelector('.small').textContent=`${j.mode} · ${new Date(j.created_at).toLocaleString('ca-ES')} · ${j.id.slice(0,8)}`;b.onclick=()=>choose(j.id);$('jobs').appendChild(b)}}catch(e){msg(e.message)}}
async function upload(){if(uploading)return;const f=$('videoInput').files?.[0];if(!f){msg('Selecciona un vídeo.');return}uploading=true;$('upload').disabled=true;msg('');$('uploadProgress').style.display='block';try{
 let session=null;const saved=JSON.parse(localStorage.getItem('blau-session')||'null');
 if(saved?.name===f.name&&saved?.size===f.size){try{const x=await apiJSON('/uploads/'+saved.id);if(['uploaded','uploading'].includes(x.status))session={...saved,uploaded_parts:x.uploaded_parts,status:x.status}}catch{}}
 if(!session){const x=await post('/uploads',{filename:f.name,size_bytes:f.size});session={id:x.id,name:f.name,size:f.size,uploaded_parts:[],status:'uploading'};localStorage.setItem('blau-session',JSON.stringify(session))}
 const total=Math.ceil(f.size/PART);
 for(let n=1;n<=total&&session.status==='uploading';n++){
  if(session.uploaded_parts.includes(n))continue;
  const chunk=f.slice((n-1)*PART,Math.min(n*PART,f.size));let err;
  for(let attempt=0;attempt<3;attempt++){try{await api(`/uploads/${session.id}/parts/${n}`,{method:'PUT',headers:{'Content-Type':'application/octet-stream'},body:chunk});err=null;break}catch(e){err=e;await new Promise(r=>setTimeout(r,500*(attempt+1)))}}
  if(err)throw err;
  session.uploaded_parts.push(n);
  const pct=Math.round(100*session.uploaded_parts.length/total);$('progress').value=pct;$('progressText').textContent=`Pujant ${pct}%`;
 }
 if(session.status!=='uploaded')await post(`/uploads/${session.id}/finalize`);
 const mode=document.querySelector('input[name="mode"]:checked').value;
 const job=await post(`/uploads/${session.id}/render`,{mode,style:$('style').value});localStorage.removeItem('blau-session');
 $('videoInput').value='';$('progressText').textContent='Vídeo enviat a la cua.';await refresh();await choose(job.id);
 }catch(e){msg('Error en la pujada: '+e.message)}finally{uploading=false;$('upload').disabled=false}}
async function choose(id){try{current=await apiJSON('/jobs/'+id);$('review').style.display='block';$('reviewStatus').textContent=(texts[current.status]||current.status)+(current.error?' · '+current.error:'');
 $('quality').textContent=current.qc?`Verificació: ${current.qc.decode_ok?'correcta':'pendent'} · Requereix revisió editorial`:'';
 const hasMedia=current.has_preview&&['approved','needs_approval'].includes(current.status);
 $('preview').hidden=!hasMedia;if(hasMedia){$('preview').src='/api/jobs/'+id+'/preview';$('preview').load()}else {$('preview').removeAttribute('src');$('preview').load()}
 $('download').hidden=!hasMedia;$('approve').hidden=current.status!=='needs_approval'||me.role!=='owner';$('reject').hidden=current.status!=='needs_approval'||me.role!=='owner';
 $('review').scrollIntoView({behavior:'smooth',block:'nearest'});
 }catch(e){msg(e.message)}}
async function review(approve){if(!current)return;try{if(approve&&!confirm('Aprovar exactament aquesta versió del vídeo? No es publicarà automàticament.'))return;
 await post(`/jobs/${current.id}/${approve?'approve':'reject'}`,approve?{sha256:current.sha256,confirm:true}:{});await choose(current.id);await refresh()}catch(e){msg(e.message)}}
$('upload').onclick=upload;$('refresh').onclick=refresh;$('approve').onclick=()=>review(true);$('reject').onclick=()=>review(false);$('download').onclick=()=>{if(current)window.location.assign('/api/jobs/'+current.id+'/download')};
boot();
