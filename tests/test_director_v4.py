import pytest
from creative_engine.director import build_plan,load_styles

def test_every_style_has_unique_id():
 s=load_styles();assert len(s)>=15 and len(s)==len(set(s))

def test_no_transcript_is_not_blind_18_second_cut():
 p=build_plan([],80,'auto','es');assert p['status']=='needs_review' and p['candidates']==[]

def test_valid_speech_candidate_not_first_18_seconds():
 utterances=[{'start':25.0,'end':30.0,'text':'¿Sabes por qué el cuidado de la piel cambia con los años?'},
             {'start':30.3,'end':35.0,'text':'Hoy lo explicamos de manera sencilla con un ejemplo real.'}]
 p=build_plan(utterances,85,'tacho_humano','es');assert p['status']=='drafts'
 c=p['candidates'][0];assert c['segments'][0]['in']>24 and c['duration']>8
 assert c['claims_checked'] is False and p['automatic_publish'] is False
 assert c['captions'][0]['text']==utterances[0]['text']

def test_invalid_timecode():
 with pytest.raises(ValueError):build_plan([{'start':21,'end':81,'text':'hola'}],30)

def test_no_poor_speech_forced_into_video():
 p=build_plan([{'start':0,'end':5,'text':'eh'}],25);assert p['status']=='needs_review'

def test_unlicensed_style_not_accepted():
 with pytest.raises(ValueError):build_plan([],60,style='clone_influencer')
