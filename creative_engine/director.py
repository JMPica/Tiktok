"""Director editorial V4 de contingencia: heurístico y auditable.
No equivale a un LLM multimodal. Nunca finge haber comprendido imágenes o tonos de voz.
Al no existir señales fiables, devuelve NEEDS_REVIEW en vez de recortar 18s.
"""
from __future__ import annotations
import re, json, math
from pathlib import Path

KEYWORDS={
 'ca': ('per què','com','realment','mai','secret','error','això','així','què passa','resultat','mira'),
 'es': ('por qué','cómo','realmente','nunca','secreto','error','esto','así','qué pasa','resultado','mira'),
}

def load_styles():
    return {s['id']:s for s in json.loads((Path(__file__).with_name('styles.v4.json')).read_text(encoding='utf8'))['profiles']}

def clean_phrase(s):
    return ' '.join(str(s).strip().split())

def validate_transcript(rows, duration):
    out=[]
    for i,r in enumerate(rows):
        a=float(r['start']);b=float(r['end']);t=clean_phrase(r.get('text',''))
        if not (math.isfinite(a) and math.isfinite(b) and 0<=a<b<=duration+0.5):
            raise ValueError(f'Transcript segment invalid: {i}')
        if t:out.append({'start':a,'end':b,'text':t})
    return sorted(out,key=lambda x:x['start'])

def quality(segment, language='ca'):
    """Heuristic rank NOT predicted virality. A hook is an editorial hypothesis."""
    t=segment['text'].lower().strip(); words=t.split()
    score=0
    if any(x in t for x in KEYWORDS.get(language,KEYWORDS['es'])):score+=2
    if t.endswith(('?','!')):score+=1
    if len(words)>=4:score+=1
    if len(words)>35:score-=2
    if t.startswith(('eh','eee','mmm','bueno','vale','doncs','pues')):score-=1
    return score

def build_plan(transcript, duration, style='auto', language='ca'):
    """Return plan with source timecodes and local subtitle alignment or needs_review.
    This is explicitly a narrow speech-first baseline; Claude must replace with multimodal ranking.
    """
    if style not in load_styles():raise ValueError('Unknown style: '+style)
    if language not in ('ca','es'):raise ValueError('Unsupported language')
    rows=validate_transcript(transcript,duration)
    if not rows:
        return {'status':'needs_review','reason':'Sin transcripción válida; no seleccionar tiempo arbitrario',
                'style':style,'candidates':[],'claims_checked':False}
    # Group speech at natural pauses, never cut in the middle of a phrase.
    groups=[];cur=[]
    for row in rows:
        if cur and (row['start']-cur[-1]['end']>2 or row['end']-cur[0]['start']>42):
            groups.append(cur);cur=[]
        cur.append(row)
    if cur:groups.append(cur)
    candidates=[]
    for group in groups:
        # One coherent story; do not force N videos or arbitrary 18 seconds.
        # May include multiple utterances with discontinuities <=2s.
        start=max(0,group[0]['start']-0.18);end=min(duration,group[-1]['end']+0.20)
        if not 4<=end-start<=45:continue
        viable=[(quality(s,language),s) for s in group]
        best=max(viable,key=lambda x:x[0]); hook=best[1]
        if best[0]<1:continue
        # Allow minimal jump cuts of long pauses but preserve the sequence.
        cuts=[];cursor=0
        for r in group:
            a=max(0,r['start']-0.09);b=min(duration,r['end']+0.12)
            if cuts and a<cuts[-1]['out']:a=cuts[-1]['out']
            if b-a>=0.3:cuts.append({'in':round(a,3),'out':round(b,3)})
        if not cuts:continue
        # Hook can be editorial text; never fabricate a direct quote.
        t=hook['text']; hook_overlay=t[:74] if len(t)<=74 else t[:71].rstrip()+'...'
        captions=[];timeline=0.0
        for cut,r in zip(cuts,group):
            length=cut['out']-cut['in']
            captions.append({'start':round(timeline,3),'end':round(timeline+length,3),'text':r['text'],
                             'source_start':r['start'],'type':'transcript_auto_unverified'})
            timeline+=length
        candidates.append({'style':style,'language':language,'segments':cuts,'captions':captions,
            'hook_overlay_suggestion':hook_overlay,'reason':'Secuencia hablada coherente con inicio candidato; requiere revisión editorial',
            'score_heuristic':best[0],'duration':round(timeline,2),'source_range':[start,end],
            'claims_checked':False,'creative_quality_verified':False})
    candidates.sort(key=lambda c:(-c['score_heuristic'],-c['duration']))
    if not candidates:
        return {'status':'needs_review','reason':'No hay historia hablada con señales suficientes para montaje',
                'style':style,'candidates':[],'claims_checked':False}
    return {'status':'drafts','style':style,'candidates':candidates[:3],
            'selection':'speech_heuristic_not_multimodal','automatic_publish':False,
            'editorial_review_required':True,'caption_review_required':True}
