import hashlib, io, os, subprocess, sys, time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

@pytest.fixture
def env(tmp_path,monkeypatch):
    monkeypatch.setenv('STUDIO_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('STUDIO_JWT_SECRET','demo-only-strong-secret-00000000000000000000000000000')
    from server import core,worker
    core.ROOT=tmp_path;core.DB=tmp_path/'studio.db';core.JWT_SECRET=os.environ['STUDIO_JWT_SECRET']
    worker.ROOT=tmp_path
    core.init_db()
    with TestClient(core.app) as client:
        owner=core.sign_token('director','owner',int(time.time())+1800)
        editor=core.sign_token('compañera','editor',int(time.time())+1800)
        yield client,worker,{'Authorization':'Bearer '+owner},{'Authorization':'Bearer '+editor},tmp_path

def synthetic(path,duration=2):
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','lavfi','-i',f'testsrc2=size=360x640:rate=25:duration={duration}',
        '-f','lavfi','-i',f'sine=frequency=430:sample_rate=48000:duration={duration}',
        '-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac',str(path)],check=True,timeout=25)

def upload(client, auth,video):
    data=Path(video).read_bytes(); sha=hashlib.sha256(data).hexdigest()
    r=client.post('/v3/uploads',json={'filename':Path(video).name,'size_bytes':len(data),'sha256':sha},headers=auth)
    assert r.status_code==200,r.text
    uid=r.json()['id'];n=r.json()['total_chunks'];chunk=r.json()['chunk_size']
    for i in range(n):
        part=data[i*chunk:(i+1)*chunk]
        r=client.put(f'/v3/uploads/{uid}/chunks/{i}',content=part,headers=auth)
        assert r.status_code==200,r.text
    r=client.post(f'/v3/uploads/{uid}/finalize',headers=auth)
    assert r.status_code==200,r.text
    return uid

def test_security_upload_and_approval(env):
    client,worker,owner,editor,tmp=env
    video=tmp/'prueba.mp4';synthetic(video)
    assert client.get('/v3/renders').status_code==401
    uid=upload(client,editor,video)
    assert client.get(f'/v3/uploads/{uid}',headers=owner).status_code==200
    r=client.post(f'/v3/uploads/{uid}/renders',headers=editor,json={'mode':'automatic'})
    assert r.status_code==200,r.text
    rid=r.json()['id']
    duplicate=client.post(f'/v3/uploads/{uid}/renders',headers=editor,json={'mode':'automatic'})
    assert duplicate.json()['id']==rid and duplicate.json()['reused'] is True
    assert worker.process_next() is True
    status=client.get(f'/v3/renders/{rid}',headers=editor).json()
    assert status['status']=='needs_approval',status
    assert status['qc']['decode_ok'] and status['qc']['original_has_audio']
    assert status['qc']['width']==1080 and status['qc']['height']==1920
    assert client.get(status['preview_path'],headers=editor).status_code==200
    assert client.get(status['preview_path']).status_code==401
    assert client.post(f'/v3/renders/{rid}/approve',headers=editor,json={'sha256':status['sha256'],'confirm':True}).status_code==403
    assert client.post(f'/v3/renders/{rid}/approve',headers=owner,json={'sha256':'0'*64,'confirm':True}).status_code==409
    good=client.post(f'/v3/renders/{rid}/approve',headers=owner,json={'sha256':status['sha256'],'confirm':True})
    assert good.status_code==200,good.text
    assert client.get(f'/v3/renders/{rid}',headers=owner).json()['status']=='approved'
    assert worker.process_next() is False

def test_isolation_and_validation(env):
    client,worker,owner,editor,tmp=env
    video=tmp/'prueba.mp4';synthetic(video,1.5)
    uid=upload(client,owner,video)
    assert client.get(f'/v3/uploads/{uid}',headers=editor).status_code==404
    assert client.post(f'/v3/uploads/{uid}/renders',headers=editor,json={'mode':'automatic'}).status_code==404
    assert client.post(f'/v3/uploads/{uid}/renders',headers=owner,json={'mode':'creative','segments':[{'in':0.0,'out':8.0}]}).status_code==422
    valid=client.post(f'/v3/uploads/{uid}/renders',headers=owner,json={'mode':'creative','segments':[{'in':0.0,'out':1.0}], 'captions':[{'start':0.1,'end':0.9,'text':'Hola Maresme'}]})
    assert valid.status_code==200
    assert worker.process_next()
    status=client.get('/v3/renders/'+valid.json()['id'],headers=owner).json()
    assert status['status']=='needs_approval',status
    assert status['qc']['generative_effects']=='disabled'
    assert status['qc']['embedded_caption_count']==1
