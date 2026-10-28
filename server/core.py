"""Private, durable V3 service. No publisher and no paid generation by design."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets, sqlite3, subprocess, time, uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(os.environ.get('STUDIO_DATA_DIR', '/data')).resolve()
DB = ROOT / 'studio.db'
CHUNK = 4 * 1024 * 1024
MAX_BYTES = int(os.environ.get('STUDIO_MAX_UPLOAD_BYTES', str(2 * 1024 ** 3)))
JWT_SECRET = os.environ.get('STUDIO_JWT_SECRET', '')
ORIGIN = os.environ.get('STUDIO_ORIGIN', 'https://blau-de-mar-tiktok-studio.titus10.chatgpt.site')
STATUS = ('uploaded','queued','processing','needs_review','needs_approval','approved','rejected','failed')


def connect():
    ROOT.mkdir(parents=True, exist_ok=True)
    d = sqlite3.connect(DB, timeout=30)
    d.row_factory = sqlite3.Row
    d.execute('PRAGMA journal_mode=WAL')
    d.execute('PRAGMA foreign_keys=ON')
    return d


def init_db():
    with connect() as d:
        d.executescript('''
          CREATE TABLE IF NOT EXISTS uploads(
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, filename TEXT NOT NULL,
            bytes INTEGER NOT NULL, sha256 TEXT, received INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL, path TEXT, metadata TEXT, created INTEGER NOT NULL
          );
          CREATE TABLE IF NOT EXISTS parts(
            upload_id TEXT NOT NULL REFERENCES uploads(id), idx INTEGER NOT NULL,
            bytes INTEGER NOT NULL, sha256 TEXT NOT NULL,
            PRIMARY KEY(upload_id,idx)
          );
          CREATE TABLE IF NOT EXISTS renders(
            id TEXT PRIMARY KEY, upload_id TEXT NOT NULL REFERENCES uploads(id),
            owner TEXT NOT NULL, status TEXT NOT NULL, mode TEXT NOT NULL,
            plan TEXT, path TEXT, sha256 TEXT, qc TEXT, error TEXT,
            approved_by TEXT, approved_sha256 TEXT, approved_at INTEGER,
            created INTEGER NOT NULL, updated INTEGER NOT NULL
          );
        ''')


def hash_file(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def sign_token(sub: str, role: str, expires: int, secret: str | None = None):
    """Server-side Site integration helper; NEVER use in browser code."""
    s = secret or JWT_SECRET
    if len(s) < 32: raise ValueError('STUDIO_JWT_SECRET must be >=32 chars')
    hdr = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b'=').decode()
    p = base64.urlsafe_b64encode(json.dumps({'sub':sub,'role':role,'exp':expires,'aud':'blau-tiktok-studio-v3'},separators=(',',':')).encode()).rstrip(b'=').decode()
    inp = (hdr+'.'+p).encode(); sig=base64.urlsafe_b64encode(hmac.new(s.encode(),inp,hashlib.sha256).digest()).rstrip(b'=').decode()
    return hdr+'.'+p+'.'+sig


def verify_token(auth: str | None):
    if not auth or not auth.startswith('Bearer '): raise HTTPException(401,'Bearer token required')
    try:
        a,b,c=auth[7:].split('.')
        msg=(a+'.'+b).encode()
        expected=base64.urlsafe_b64encode(hmac.new(JWT_SECRET.encode(),msg,hashlib.sha256).digest()).rstrip(b'=').decode()
        if not hmac.compare_digest(c,expected): raise ValueError('bad signature')
        head=json.loads(base64.urlsafe_b64decode(a+'='*(-len(a)%4)))
        obj=json.loads(base64.urlsafe_b64decode(b+'='*(-len(b)%4)))
        if head.get('alg')!='HS256' or obj.get('aud')!='blau-tiktok-studio-v3' or int(obj.get('exp',0))<=time.time(): raise ValueError('bad token')
        if obj.get('role') not in ('owner','editor') or not obj.get('sub'): raise ValueError('bad user')
        return obj
    except Exception:
        raise HTTPException(401,'Invalid or expired token')


def user(authorization: str | None = Header(default=None)):
    return verify_token(authorization)


def own(row, identity):
    if not row or (identity['role']!='owner' and row['owner'] != identity['sub']):
        raise HTTPException(404,'Not found')


def probe(path: Path):
    try:
        r=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],capture_output=True,text=True,timeout=45,check=True)
        info=json.loads(r.stdout); streams=info.get('streams',[])
        vids=[s for s in streams if s.get('codec_type')=='video']
        if not vids: raise ValueError('no video stream')
        v=vids[0];duration=float(info['format']['duration'])
        if not 0.5 <= duration <= 7200: raise ValueError('invalid duration')
        if v.get('codec_name') not in ('h264','hevc','mpeg4','vp9','av1','prores','mjpeg'):
            raise ValueError('unsupported video codec')
        return {'duration':duration,'width':int(v['width']),'height':int(v['height']),
                'fps':v.get('avg_frame_rate','25/1'),
                'audio':any(s.get('codec_type')=='audio' for s in streams),
                'hdr':v.get('color_transfer') in ('arib-std-b67','smpte2084'),
                'codec':v.get('codec_name')}
    except (ValueError,KeyError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        raise HTTPException(422,'File is not a supported playable video: '+str(exc)[:180])


class Start(BaseModel):
    filename: str = Field(min_length=1,max_length=200)
    size_bytes: int = Field(gt=0)
    sha256: str | None = Field(default=None,pattern='^[0-9a-f]{64}$')

class RenderRequest(BaseModel):
    mode: str = 'automatic'
    # Each segment must reference original time. External AI clips require deliberate import step.
    segments: list[dict[str, Any]] | None = None
    captions: list[dict[str, Any]] | None = None


@asynccontextmanager
async def lifespan(application):
    if len(JWT_SECRET)<32: raise RuntimeError('Configure STUDIO_JWT_SECRET (>=32 characters)')
    init_db()
    yield

app=FastAPI(title='Blau de Mar TikTok Studio V3',docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[ORIGIN],allow_methods=['GET','POST','PUT'],allow_headers=['Authorization','Content-Type'])

@app.get('/v3/health')
def health(): return {'status':'ok','version':'3.0.0','generative_spend':False,'publishing':False}

@app.post('/v3/uploads')
def start(body:Start,identity=Depends(user)):
    if body.size_bytes>MAX_BYTES: raise HTTPException(413,'Video too large')
    extension=Path(body.filename).suffix.lower()
    if extension not in ('.mp4','.mov','.m4v'):raise HTTPException(422,'MOV or MP4 required')
    uid=uuid.uuid4().hex
    (ROOT/'parts'/uid).mkdir(parents=True)
    with connect() as d:
        d.execute('INSERT INTO uploads(id,owner,filename,bytes,sha256,status,created) VALUES(?,?,?,?,?,?,?)',
                  (uid,identity['sub'],Path(body.filename).name,body.size_bytes,body.sha256,'uploading',int(time.time())))
    return {'id':uid,'chunk_size':CHUNK,'total_chunks':(body.size_bytes+CHUNK-1)//CHUNK}

@app.get('/v3/uploads/{uid}')
def get_upload(uid:str,identity=Depends(user)):
    with connect() as d:
        r=d.execute('SELECT * FROM uploads WHERE id=?',(uid,)).fetchone();own(r,identity)
        parts=[p['idx'] for p in d.execute('SELECT idx FROM parts WHERE upload_id=?',(uid,))]
    return {'id':uid,'status':r['status'],'bytes':r['bytes'],'received_chunks':parts,'metadata':json.loads(r['metadata']) if r['metadata'] else None}

@app.put('/v3/uploads/{uid}/chunks/{idx}')
async def put_chunk(uid:str,idx:int,request:Request,identity=Depends(user)):
    with connect() as d:
        r=d.execute('SELECT * FROM uploads WHERE id=?',(uid,)).fetchone();own(r,identity)
        if r['status']!='uploading': raise HTTPException(409,'Upload is finalized')
        n=(r['bytes']+CHUNK-1)//CHUNK
        if idx<0 or idx>=n:raise HTTPException(422,'Invalid chunk index')
        expected=min(CHUNK,r['bytes']-idx*CHUNK)
        # Stream with cap; no request.body() huge unbounded read.
        data=bytearray()
        async for fragment in request.stream():
            data.extend(fragment)
            if len(data)>expected:raise HTTPException(413,'Chunk exceeds expected length')
        if len(data)!=expected:raise HTTPException(422,'Chunk wrong size')
        digest=hashlib.sha256(data).hexdigest()
        old=d.execute('SELECT sha256 FROM parts WHERE upload_id=? AND idx=?',(uid,idx)).fetchone()
        if old and old['sha256']!=digest:raise HTTPException(409,'Chunk content conflict')
        p=ROOT/'parts'/uid/str(idx)
        if not old:
            tmp=p.with_suffix('.tmp');tmp.write_bytes(data);tmp.replace(p)
            d.execute('INSERT INTO parts(upload_id,idx,bytes,sha256) VALUES(?,?,?,?)',(uid,idx,len(data),digest))
    return {'index':idx,'ok':True}

@app.post('/v3/uploads/{uid}/finalize')
def finalize(uid:str,identity=Depends(user)):
    with connect() as d:
        r=d.execute('SELECT * FROM uploads WHERE id=?',(uid,)).fetchone();own(r,identity)
        if r['status']=='uploaded': return {'id':uid,'status':'uploaded','metadata':json.loads(r['metadata'])}
        if r['status']!='uploading':raise HTTPException(409,'Wrong upload state')
        n=(r['bytes']+CHUNK-1)//CHUNK
        rows=d.execute('SELECT * FROM parts WHERE upload_id=? ORDER BY idx',(uid,)).fetchall()
        if len(rows)!=n or [x['idx'] for x in rows]!=list(range(n)):raise HTTPException(409,'Chunks missing')
        target=ROOT/'originals'/f'{uid}{Path(r["filename"]).suffix.lower()}'
        target.parent.mkdir(exist_ok=True)
        temp=target.with_suffix('.part');sha=hashlib.sha256()
        with temp.open('wb') as out:
            for i in range(n):
                part=ROOT/'parts'/uid/str(i)
                with part.open('rb') as inp:
                    while b:=inp.read(1024*1024):out.write(b);sha.update(b)
        if temp.stat().st_size!=r['bytes'] or (r['sha256'] and r['sha256']!=sha.hexdigest()):
            temp.unlink(missing_ok=True);raise HTTPException(422,'Checksum mismatch')
        try: meta=probe(temp)
        except Exception:
            temp.unlink(missing_ok=True);raise
        temp.replace(target)
        d.execute('UPDATE uploads SET status=?,path=?,metadata=?,sha256=? WHERE id=?',
                  ('uploaded',str(target),json.dumps(meta),sha.hexdigest(),uid))
    # Remove uploaded chunks only after final commit.
    import shutil;shutil.rmtree(ROOT/'parts'/uid,ignore_errors=True)
    return {'id':uid,'status':'uploaded','metadata':meta}

@app.post('/v3/uploads/{uid}/renders')
def new_render(uid:str,body:RenderRequest,identity=Depends(user)):
    if body.mode not in ('automatic','real','creative'):raise HTTPException(422,'Invalid edit mode')
    with connect() as d:
        u=d.execute('SELECT * FROM uploads WHERE id=?',(uid,)).fetchone();own(u,identity)
        if u['status']!='uploaded':raise HTTPException(409,'Upload not ready')
        meta=json.loads(u['metadata']); segments=body.segments
        if segments:
            if len(segments)>80:raise HTTPException(422,'Too many segments')
            for s in segments:
                try:a,b=float(s['in']),float(s['out'])
                except (TypeError,KeyError,ValueError):raise HTTPException(422,'Segment requires in/out')
                if not 0<=a<b<=meta['duration']+0.001 or b-a<0.1:raise HTTPException(422,'Invalid segment times')
        if body.captions:
            if len(body.captions)>250:raise HTTPException(422,'Too many captions')
            if not segments:raise HTTPException(422,'Captions require explicit segments')
            output_seconds=sum(float(t['out'])-float(t['in']) for t in segments)
            for caption in body.captions:
                try: cs,ce=float(caption['start']),float(caption['end']);ct=caption['text']
                except (KeyError,TypeError,ValueError):raise HTTPException(422,'Captions require numeric start/end and text')
                if not isinstance(ct,str) or len(ct)>140 or not 0<=cs<ce<=output_seconds+0.15:
                    raise HTTPException(422,'Invalid caption timing or length')
        # Same source upload/mode/plan should not enqueue repeated identical jobs.
        plan={'segments':segments,'captions':body.captions,'mode':body.mode}
        duplicate=d.execute('SELECT id,status FROM renders WHERE upload_id=? AND owner=? AND plan=? AND status NOT IN (?,?) ORDER BY created DESC LIMIT 1',
                            (uid,identity['sub'],json.dumps(plan,sort_keys=True),'failed','rejected')).fetchone()
        if duplicate:return {'id':duplicate['id'],'status':duplicate['status'],'reused':True}
        rid=uuid.uuid4().hex;now=int(time.time())
        d.execute('INSERT INTO renders(id,upload_id,owner,status,mode,plan,created,updated) VALUES(?,?,?,?,?,?,?,?)',
                  (rid,uid,identity['sub'],'queued',body.mode,json.dumps(plan,sort_keys=True),now,now))
    return {'id':rid,'status':'queued','reused':False}

@app.get('/v3/renders')
def list_renders(identity=Depends(user)):
    with connect() as d:
        if identity['role']=='owner': rows=d.execute('SELECT id,upload_id,status,mode,error,sha256,approved_at,created,updated FROM renders ORDER BY created DESC LIMIT 100').fetchall()
        else:rows=d.execute('SELECT id,upload_id,status,mode,error,sha256,approved_at,created,updated FROM renders WHERE owner=? ORDER BY created DESC LIMIT 100',(identity['sub'],)).fetchall()
    return {'items':[dict(x) for x in rows]}

@app.get('/v3/renders/{rid}')
def render_status(rid:str,identity=Depends(user)):
    with connect() as d:
        r=d.execute('SELECT * FROM renders WHERE id=?',(rid,)).fetchone();own(r,identity)
    return {'id':rid,'status':r['status'],'mode':r['mode'],'qc':json.loads(r['qc']) if r['qc'] else None,
            'error':r['error'],'sha256':r['sha256'],'approved_at':r['approved_at'],
            'preview_path':f'/v3/renders/{rid}/preview' if r['path'] else None}

@app.get('/v3/renders/{rid}/preview')
def preview(rid:str,identity=Depends(user)):
    with connect() as d:
        r=d.execute('SELECT * FROM renders WHERE id=?',(rid,)).fetchone();own(r,identity)
    if r['status'] not in ('needs_approval','approved') or not r['path']:raise HTTPException(409,'Preview not ready')
    p=Path(r['path'])
    if not p.is_file():raise HTTPException(404,'Render unavailable')
    return FileResponse(str(p),media_type='video/mp4',filename=f'{rid}.mp4',content_disposition_type='inline',headers={'Cache-Control':'private, no-store'})

class Approve(BaseModel):
    sha256:str=Field(pattern='^[0-9a-f]{64}$')
    confirm:bool

@app.post('/v3/renders/{rid}/approve')
def approve(rid:str,body:Approve,identity=Depends(user)):
    if identity['role']!='owner':raise HTTPException(403,'Owner approval required')
    if not body.confirm:raise HTTPException(422,'Explicit confirmation required')
    with connect() as d:
        r=d.execute('SELECT * FROM renders WHERE id=?',(rid,)).fetchone();own(r,identity)
        if r['status']=='approved' and r['approved_sha256']==body.sha256:return {'status':'approved','sha256':body.sha256}
        if r['status']!='needs_approval' or not hmac.compare_digest(r['sha256'] or '',body.sha256):raise HTTPException(409,'Preview version changed or not ready')
        p=Path(r['path'])
        if not p.is_file() or hash_file(p)!=body.sha256:raise HTTPException(409,'Render content changed')
        d.execute('UPDATE renders SET status=?,approved_by=?,approved_sha256=?,approved_at=?,updated=? WHERE id=?',
                  ('approved',identity['sub'],body.sha256,int(time.time()),int(time.time()),rid))
    return {'status':'approved','sha256':body.sha256}

@app.post('/v3/renders/{rid}/reject')
def reject(rid:str,identity=Depends(user)):
    if identity['role']!='owner':raise HTTPException(403,'Owner review required')
    with connect() as d:
        r=d.execute('SELECT * FROM renders WHERE id=?',(rid,)).fetchone();own(r,identity)
        if r['status']!='needs_approval':raise HTTPException(409,'Not pending review')
        d.execute('UPDATE renders SET status=?,updated=? WHERE id=?',('rejected',int(time.time()),rid))
    return {'status':'rejected'}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('sub');p.add_argument('role',choices=['owner','editor']);p.add_argument('--minutes',type=int,default=30);args=p.parse_args()
    print(sign_token(args.sub,args.role,int(time.time())+args.minutes*60))
