"""Local, outbound-only editing agent for Cloudflare Workers Free.
Works on Windows/macOS/Linux through Docker. No public ports, no paid APIs.
Prerequisite: signed-in Cloudflare Access service token + independent agent token.
"""
from __future__ import annotations
import hashlib,json,os,sys,time,traceback,subprocess,tempfile
from pathlib import Path
from fractions import Fraction
import requests

BASE=os.environ.get('STUDIO_PUBLIC_URL','').rstrip('/')
TOKEN=os.environ.get('STUDIO_AGENT_TOKEN','')
CLIENT_ID=os.environ.get('CF_ACCESS_CLIENT_ID','')
CLIENT_SECRET=os.environ.get('CF_ACCESS_CLIENT_SECRET','')
POLL_SECONDS=max(10,int(os.environ.get('STUDIO_POLL_SECONDS','30')))
PART=8*1024*1024
HEADERS={'Authorization':f'Bearer {TOKEN}', 'CF-Access-Client-Id': CLIENT_ID, 'CF-Access-Client-Secret':CLIENT_SECRET}

if not BASE.startswith('https://') or not all([TOKEN,CLIENT_ID,CLIENT_SECRET]):
    print('Faltan STUDIO_PUBLIC_URL HTTPS, STUDIO_AGENT_TOKEN o token Cloudflare Access.',file=sys.stderr)
    sys.exit(2)

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.core import probe,hash_file
from server.worker import ffmpeg_render, apply_captions
from creative_engine.director import build_plan
from creative_engine.transcribe import transcribe_local

session=requests.Session()
session.headers.update(HEADERS)

def api(method,path,**opts):
    r=session.request(method,BASE+path,timeout=opts.pop('timeout',80),**opts)
    r.raise_for_status()
    return r

def download(path,dest):
    with api('GET',path,stream=True,timeout=900) as r, dest.open('wb') as out:
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk:out.write(chunk)

def qc_video(path):
    m=probe(path)
    if m['width']!=1080 or m['height']!=1920 or m['duration']<=0 or not m['audio']:
        raise ValueError(f'Render QC not passed: {m}')
    check=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],capture_output=True,text=True,timeout=600)
    if check.returncode or check.stderr.strip():raise ValueError('Video decoding failed: '+check.stderr[:300])
    return {'decode_ok':True,'audio_present':True,'width':m['width'],'height':m['height'],
            'duration':m['duration'],'fps':m['fps'],'source':'real_original','automatic_edit':'speech_based_heuristic_draft',
            'ai_effects':'disabled','editorial_review':'human_required'}

def upload_output(jobid,out):
    api('POST',f'/api/agent/jobs/{jobid}/output/start',json={})
    with out.open('rb') as f:
        n=0
        while True:
            data=f.read(PART)
            if not data:break
            n+=1
            api('PUT',f'/api/agent/jobs/{jobid}/output/parts/{n}',data=data,
                headers={'Content-Type':'application/octet-stream'},timeout=300)
    return api('POST',f'/api/agent/jobs/{jobid}/output/finish',json={'sha256':hash_file(out),'qc':qc_video(out)}).json()

def process(job):
    id=job['id'];print(f'[job {id[:10]}] descargando fuente',flush=True)
    with tempfile.TemporaryDirectory(prefix='blau-local-') as folder:
        tmp=Path(folder);input=tmp/'original.mp4';output=tmp/'editado.mp4'
        download(f'/api/agent/jobs/{id}/source',input)
        metadata=probe(input)
        # V4: NEVER use `segments=None` (fixed first-18s legacy fallback).
        # Speech-driven selection is a provisional director, not multimodal AI.
        lang=os.environ.get('BLAU_DEFAULT_LANGUAGE','ca')
        transcription=transcribe_local(input,language=lang)
        plan=build_plan(transcription['segments'],metadata['duration'],style=job.get('style','auto'),language=lang)
        if plan['status']!='drafts':
            api('POST',f'/api/agent/jobs/{id}/needs-review',json={'reason':plan['reason'][:350]})
            print(f'[job {id[:10]}] requiere revisión humana: {plan["reason"]}',flush=True)
            return
        first=plan['candidates'][0]
        (tmp/'edit_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
        ffmpeg_render(input,output,metadata,segments=first['segments'])
        apply_captions(output,first['captions'])
        qc=qc_video(output)
        qc.update({'edit_style':first['style'],'edit_segments':first['segments'],
                   'selection':'speech_heuristic_not_multimodal','captions':'auto_unverified',
                   'editorial_review':'pending','consent_review':'pending'})
        print(f'[job {id[:10]}] exportado {qc["duration"]:.1f}s / enviando a revisión',flush=True)
        upload_output(id,output)
        print(f'[job {id[:10]}] pendiente de aprobación',flush=True)

def main():
    print('Blau de Mar Local Agent · Sin puertos entrantes · IA de pago desactivada',flush=True)
    while True:
        try:
            result=api('POST','/api/agent/claim',json={}).json();job=result.get('job')
            if job:
                try:process(job)
                except Exception as e:
                    print('Error de edición:',repr(e),flush=True)
                    try:api('POST',f'/api/agent/jobs/{job["id"]}/fail',json={'error':str(e)[:350]})
                    except Exception as ex:print('No se pudo reportar el error:',repr(ex),flush=True)
            else:time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:return
        except Exception as e:
            print('Conexión al servicio:',repr(e),flush=True);time.sleep(min(POLL_SECONDS*2,120))

if __name__=='__main__':main()
