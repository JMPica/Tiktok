/** Embed inside the existing Site. `getToken` MUST call authenticated Site backend. */
import React, { useEffect, useState } from 'react';

type Mode = 'automatic' | 'real' | 'creative';
type Job = {id:string; upload_id:string;status:string;mode:Mode;sha256?:string;error?:string};
type Detail = {id:string;status:string;sha256?:string;preview_path?:string;error?:string;qc?:Record<string,unknown>};
const BLOCK=4*1024*1024;
const statusText:Record<string,string>={queued:'En cola',processing:'Editando el vídeo',needs_approval:'Pendiente de aprobación',approved:'Aprobado',failed:'Error',rejected:'Descartado'};

export default function TikTokStudioV3({apiBase,getToken,isOwner=false}:{apiBase:string;getToken:()=>Promise<string>;isOwner?:boolean}) {
  const [file,setFile]=useState<File|null>(null),[mode,setMode]=useState<Mode>('automatic');
  const [busy,setBusy]=useState(false),[pct,setPct]=useState(0),[err,setErr]=useState('');
  const [jobs,setJobs]=useState<Job[]>([]),[selected,setSelected]=useState<Detail|null>(null);
  const [videoUrl,setVideoUrl]=useState('');
  async function req(path:string,options:RequestInit={}) {
    const auth=await getToken();
    const res=await fetch(`${apiBase.replace(/\/$/,'')}${path}`,{...options,headers:{...options.headers,Authorization:`Bearer ${auth}`}});
    if(!res.ok) throw Error(`${res.status}: ${(await res.text()).slice(0,180)}`);
    return res;
  }
  async function refresh(){
    try {const r=await req('/v3/renders');setJobs((await r.json()).items);}catch(e){setErr(String(e));}
  }
  useEffect(()=>{void refresh();const id=setInterval(()=>{void refresh()},6000);return ()=>clearInterval(id)},[apiBase]);
  useEffect(()=>{return ()=>{if(videoUrl)URL.revokeObjectURL(videoUrl)}},[videoUrl]);
  async function upload(){
    if(!file)return;
    setBusy(true);setErr('');setPct(0);
    try {
      if(!/\.(mov|mp4|m4v)$/i.test(file.name))throw Error('Selecciona un vídeo MOV o MP4');
      // Safari can resume an interrupted upload after reselecting the same local file.
      type Session = {id:string; filename:string;size:number;chunk_size:number;total_chunks:number};
      const savedRaw=window.localStorage.getItem('blau-v3-active-upload');
      let init:Session|null=null;
      let receivedChunks:number[]=[];
      if(savedRaw){
        try{
          const saved=JSON.parse(savedRaw) as Session;
          if(saved.filename===file.name && saved.size===file.size){
            const check=await req(`/v3/uploads/${saved.id}`);
            const info=await check.json();
            if(info.status==='uploading'||info.status==='uploaded'){
              init=saved;receivedChunks=info.received_chunks||[];
            }
          }
        }catch{window.localStorage.removeItem('blau-v3-active-upload');}
      }
      if(!init){
        const s=await req('/v3/uploads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:file.name,size_bytes:file.size})});
        const created=await s.json();
        init={id:created.id,filename:file.name,size:file.size,chunk_size:created.chunk_size,total_chunks:created.total_chunks};
        window.localStorage.setItem('blau-v3-active-upload',JSON.stringify(init));
      }
      for(let i=0;i<init.total_chunks;i++){
        if(receivedChunks.includes(i)){setPct(Math.round(100*(i+1)/init.total_chunks));continue;}
        let last:unknown;
        for(let tries=0;tries<3;tries++){
          try{
            await req(`/v3/uploads/${init.id}/chunks/${i}`,{method:'PUT',headers:{'Content-Type':'application/octet-stream'},body:file.slice(i*BLOCK,Math.min((i+1)*BLOCK,file.size))});
            last=null;break;
          }catch(e){last=e;}
        }
        if(last)throw last;
        setPct(Math.round(100*(i+1)/init.total_chunks));
      }
      await req(`/v3/uploads/${init.id}/finalize`,{method:'POST'});
      const render=await req(`/v3/uploads/${init.id}/renders`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});
      const info=await render.json();
      window.localStorage.removeItem('blau-v3-active-upload');
      setFile(null);const input=document.getElementById('blau-video-input') as HTMLInputElement|null;if(input)input.value='';
      await refresh();
      await choose(info.id);
    }catch(e){setErr(String(e));}
    finally{setBusy(false);}
  }
  async function choose(id:string){
    setErr('');if(videoUrl)URL.revokeObjectURL(videoUrl);setVideoUrl('');
    try{
      const response=await req(`/v3/renders/${id}`);const detail:Detail=await response.json();setSelected(detail);
      if(detail.preview_path){const media=await req(detail.preview_path);setVideoUrl(URL.createObjectURL(await media.blob()));}
    }catch(e){setErr(String(e));}
  }
  async function decision(accept:boolean){
    if(!selected||!isOwner)return;
    if(accept && (!selected.sha256||!confirm('¿Apruebas exactamente esta versión para revisión editorial final?')))return;
    try{
      await req(`/v3/renders/${selected.id}/${accept?'approve':'reject'}`,{method:'POST',
        ...(accept?{headers:{'Content-Type':'application/json'},body:JSON.stringify({sha256:selected.sha256,confirm:true})}:{})});
      await choose(selected.id);await refresh();
    }catch(e){setErr(String(e));}
  }
  return <main className="blau-v3" style={{maxWidth:660,margin:'auto',fontFamily:'system-ui',padding:18,color:'#17363a'}}>
    <header><small>BLAU DE MAR · TIKTOK STUDIO</small><h1>Crear vídeo</h1><p>Sube una grabación y revisa el montaje automático.</p></header>
    <section style={{background:'#f0f6f5',padding:20,borderRadius:18}}>
      <label htmlFor="blau-video-input"><strong>Vídeo original</strong></label>
      <input id="blau-video-input" type="file" accept="video/mp4,video/quicktime,.mov,.m4v" disabled={busy} onChange={e=>setFile(e.target.files?.[0]||null)} style={{display:'block',margin:'12px 0',width:'100%'}} />
      <fieldset style={{border:0,padding:0}}><legend>Estilo de edición</legend>
        {([['automatic','Automático'],['real','Solo material real'],['creative','Creativo (efectos IA solo con autorización)']] as [Mode,string][]).map(([v,label])=><label key={v} style={{display:'block',padding:'6px 0'}}><input type="radio" value={v} checked={mode===v} onChange={()=>setMode(v)} disabled={busy} /> {label}</label>)}
      </fieldset>
      <button type="button" disabled={!file||busy} onClick={()=>void upload()} style={{background:'#143a39',color:'white',padding:'12px 22px',border:0,borderRadius:9}}>{busy?`Subiendo ${pct}%`:'Subir y editar'}</button>
      {busy&&<progress value={pct} max={100} style={{display:'block',width:'100%',marginTop:12}} />}
      <p style={{fontSize:12}}>Los vídeos se guardan en un servidor privado. Los efectos de pago están desactivados. Si una subida se interrumpe, vuelve a seleccionar el mismo archivo para continuar.</p>
    </section>
    {err&&<p role="alert" style={{color:'#a12d22'}}>{err}</p>}
    <section><h2>Cola de vídeos</h2>
      {jobs.length===0?<p>Aún no hay vídeos.</p>:jobs.map(j=><button key={j.id} type="button" onClick={()=>void choose(j.id)} style={{display:'block',width:'100%',textAlign:'left',margin:'7px 0',padding:12,background:'#fff',border:'1px solid #d9e5e4',borderRadius:10}}><strong>{statusText[j.status]||j.status}</strong> · {j.mode}<small style={{display:'block'}}>ID: {j.id.slice(0,12)}</small></button>)}
    </section>
    {selected&&<section style={{border:'1px solid #cbdcda',borderRadius:14,padding:14}}><h2>Revisión</h2><p>{statusText[selected.status]||selected.status}</p>
      {videoUrl&&<video key={videoUrl} src={videoUrl} controls playsInline style={{width:'100%',maxHeight:500,background:'#111'}} />}
      {selected.error&&<p role="alert">{selected.error}</p>}
      {selected.qc&&<p style={{fontSize:12}}>Revisión técnica: {selected.qc.decode_ok?'archivo reproducible':'pendiente'} · Revisión editorial humana necesaria.</p>}
      {selected.status==='needs_approval'&&isOwner&&<div style={{display:'flex',gap:12}}><button onClick={()=>void decision(true)}>Aprobar esta versión</button><button onClick={()=>void decision(false)}>Descartar</button></div>}
      {selected.status==='approved'&&<p>Versión aprobada. No se ha publicado automáticamente.</p>}
      <button onClick={()=>void choose(selected.id)} style={{marginTop:10}}>Actualizar estado</button>
    </section>}
  </main>;
}
