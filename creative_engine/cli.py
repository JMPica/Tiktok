"""Run: python -m creative_engine.cli <video.mov> [--style tacho_humano] [--transcript segments.json]
Only generates an edit_plan and optionally renders draft when reviewable. Original untouched.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from creative_engine.director import build_plan,load_styles
from creative_engine.transcribe import transcribe_local
from server.core import probe
from server.worker import ffmpeg_render,apply_captions

def main():
 p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('--style',default='auto',choices=sorted(load_styles()));
 p.add_argument('--language',default='ca',choices=['ca','es']);p.add_argument('--transcript');p.add_argument('--render',action='store_true')
 args=p.parse_args();source=Path(args.video).resolve();meta=probe(source)
 if args.transcript:
    data=json.loads(Path(args.transcript).read_text(encoding='utf8'));transcript=data['segments'] if isinstance(data,dict) else data
 else:
    try:transcript=transcribe_local(source,args.language)['segments']
    except Exception as e:
       print('Transcripción no disponible: '+str(e),file=sys.stderr);transcript=[]
 plan=build_plan(transcript,meta['duration'],args.style,args.language)
 target=source.parent/(source.stem+'.v4-edit-plan.json');target.write_text(json.dumps(plan,indent=2,ensure_ascii=False),encoding='utf8')
 print(f'PLAN: {target} -> {plan["status"]}')
 if plan['status']!='drafts':return 2
 if args.render:
    first=plan['candidates'][0];rendered=source.parent/(source.stem+'.v4-preview.mp4')
    ffmpeg_render(source,rendered,meta,first['segments']);apply_captions(rendered,first['captions'])
    print('BORRADOR PREVIEW pendiente revisión humana:',rendered)
 return 0
if __name__=='__main__':raise SystemExit(main())
