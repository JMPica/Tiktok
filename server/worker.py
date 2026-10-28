"""Crash-recoverable SQLite queue worker and cost-free FFmpeg render pipeline."""
from __future__ import annotations
import hashlib,json,os,subprocess,time,traceback
from pathlib import Path
from server.core import ROOT,connect,init_db,probe,hash_file


def ffmpeg_render(source:Path,target:Path, metadata:dict, segments:list[dict]|None, captions:list[dict]|None=None):
    """Render determinista heredado V3 -> motor V4 (creative_engine.render). Sin recorte ciego.

    V4: ``segments=None`` ya NO produce los primeros 18 s; es un error explícito.
    """
    if segments is None:
        raise ValueError('V4: sin segmentos no se monta nada (prohibido el recorte fijo de 18 s)')
    if not segments:raise ValueError('An empty edit plan is not renderable')
    from creative_engine.media import probe as v4probe
    from creative_engine.render import render
    meta=v4probe(source)
    events=[{'start':float(c['start']),'end':float(c['end']),'text':str(c['text']),'words':[],'type':'edited'} for c in (captions or [])]
    edl={'segments':[{'id':f's{i}','in':float(x['in']),'out':float(x['out'])} for i,x in enumerate(segments)],
         'captions':{'mode':'phrase' if events else 'none','events':events},'grade':'natural'}
    work=target.parent/(target.stem+'-work')
    try:return render(edl,source,meta,target,work)
    finally:
        import shutil;shutil.rmtree(work,ignore_errors=True)


def _ass_time(sec):
    h=int(sec//3600);m=int(sec//60%60);ss=sec%60
    return f'{h}:{m:02d}:{ss:05.2f}'

def apply_captions(video:Path,captions:list[dict]):
    """Burn supplied, human-reviewed timestamps; preserve the original preview/source hash contract."""
    if not captions:return
    ass=video.with_suffix('.ass')
    head="""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Captions,Arial,66,&H00FFFFFF,&H00FFFFFF,&H00202020,&H80202020,-1,0,0,0,100,100,0,0,1,4,0,2,80,80,310,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines=[head]
    for cap in captions:
        text=str(cap['text']).replace('\\','').replace('{','(').replace('}',')').replace('\n',r'\N').replace('\r','')
        lines.append(f"Dialogue: 0,{_ass_time(float(cap['start']))},{_ass_time(float(cap['end']))},Captions,,0,0,0,,{text}\n")
    ass.write_text(''.join(lines),encoding='utf-8')
    target=video.with_name(video.stem+'-captions.mp4')
    subprocess.run(['ffmpeg','-hide_banner','-nostdin','-loglevel','error','-y','-i',str(video),
                    '-vf',f'ass={str(ass)}','-c:v','libx264','-preset','veryfast','-crf','22',
                    '-c:a','copy','-movflags','+faststart',str(target)],check=True,capture_output=True,text=True,timeout=600)
    target.replace(video);ass.unlink(missing_ok=True)


def process_next():
    init_db()
    with connect() as d:
        d.execute('BEGIN IMMEDIATE')
        r=d.execute("SELECT * FROM renders WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if not r:return False
        d.execute('UPDATE renders SET status=?,updated=? WHERE id=?',('processing',int(time.time()),r['id']))
    rid=r['id'];target=ROOT/'renders'/f'{rid}.mp4'
    try:
        with connect() as d:u=d.execute('SELECT * FROM uploads WHERE id=?',(r['upload_id'],)).fetchone()
        meta=json.loads(u['metadata']);plan=json.loads(r['plan'])
        if not plan.get('segments'):
            # V4: el servidor local V3 no decide cortes. La selección editorial la hace creative_engine (agente).
            with connect() as d:d.execute('UPDATE renders SET status=?,error=?,updated=? WHERE id=?',
                ('needs_review','V4: sin plan de montaje no se recorta nada; usa el agente V4 o indica segmentos',int(time.time()),rid))
            return True
        ffmpeg_render(Path(u['path']),target,meta,plan.get('segments'),plan.get('captions') or [])
        rendered=probe(target)
        if rendered['width']!=1080 or rendered['height']!=1920:raise ValueError('Invalid render resolution')
        if rendered['duration']<0.3 or not rendered['audio']:raise ValueError('Invalid render audio/duration')
        check=subprocess.run(['ffmpeg','-v','error','-i',str(target),'-f','null','-'],capture_output=True,text=True,timeout=180)
        if check.returncode or check.stderr.strip():raise ValueError('Decode QA failed: '+check.stderr[:200])
        digest=hash_file(target)
        qc={'decode_ok':True,'width':rendered['width'],'height':rendered['height'],
            'duration':rendered['duration'],'audio_present':True,'original_has_audio':meta['audio'],
            'frame_rate':rendered['fps'],'source_segments':plan.get('segments'),
            'generative_effects':'disabled','claims_review':'human_required',
            'editorial_review':'pending','caption_review':'pending','embedded_caption_count':len(plan.get('captions') or [])}
        with connect() as d:d.execute('UPDATE renders SET status=?,path=?,sha256=?,qc=?,updated=? WHERE id=?',
                                     ('needs_approval',str(target),digest,json.dumps(qc),int(time.time()),rid))
    except Exception as e:
        with connect() as d:d.execute('UPDATE renders SET status=?,error=?,updated=? WHERE id=?',
                                     ('failed',str(e)[:1500],int(time.time()),rid))
    return True


def recover_stuck(max_age_seconds=1800):
    with connect() as d:d.execute('UPDATE renders SET status=?,error=NULL WHERE status=? AND updated<?',('queued','processing',int(time.time())-max_age_seconds))

if __name__=='__main__':
    init_db(); recover_stuck()
    while True:
        if not process_next():time.sleep(2)
