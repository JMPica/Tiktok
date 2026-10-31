import pytest
from creative_engine.director import build_plan, load_styles


def test_every_style_has_unique_id_and_render_recipe():
    s = load_styles()
    assert len(s) == 18 and len(s) == len(set(s))
    assert all('render' in p and p['automated_state'] == 'render_recipe' for p in s.values())


def test_no_transcript_is_not_blind_18_second_cut():
    p = build_plan([], 80, 'auto', 'es')
    assert p['status'] == 'needs_review' and p['candidates'] == []


def test_valid_speech_candidate_not_first_18_seconds():
    utterances = [{'start': 25.0, 'end': 30.0, 'text': '¿Sabes por qué el cuidado de la piel cambia con los años?'},
                  {'start': 30.3, 'end': 35.0, 'text': 'Hoy lo explicamos de manera sencilla con un ejemplo real.'}]
    p = build_plan(utterances, 85, 'tacho_humano', 'es')
    assert p['status'] == 'drafts'
    c = p['candidates'][0]
    assert c['segments'][0]['in'] > 24 and c['duration'] > 8
    assert p['claims_checked'] is False and p['automatic_publish'] is False and c['automatic_publish'] is False
    assert c['captions']['events'][0]['text'].replace('\n', ' ').startswith('¿Sabes por qué')
    assert c['score']['total'] >= 55 and 'viralitat' in c['score']['meaning']


def test_invalid_timecode():
    with pytest.raises(ValueError):
        build_plan([{'start': 21, 'end': 81, 'text': 'hola'}], 30)


def test_no_poor_speech_forced_into_video():
    p = build_plan([{'start': 0, 'end': 5, 'text': 'eh'}], 25)
    assert p['status'] == 'needs_review'


def test_unlicensed_style_not_accepted():
    with pytest.raises(ValueError):
        build_plan([], 60, style='clone_influencer')


RETAKE = [{'start': 2.0, 'end': 4.0, 'text': 'Sabeu per què escalfem les'},
          {'start': 4.6, 'end': 8.5, 'text': 'Sabeu per què escalfem les tovalloles abans de cada tractament?'},
          {'start': 8.8, 'end': 12.5, 'text': 'Perquè el client estigui còmode i relaxat des del primer minut.'},
          {'start': 12.8, 'end': 16.0, 'text': 'I per això la cabina fa olor de cafè, és el secret!'}]


def test_retake_keeps_last_complete_take():
    from creative_engine.director import drop_retakes, validate_transcript
    kept, dropped = drop_retakes(validate_transcript(RETAKE, 20))
    assert [r['start'] for r in dropped] == [2.0] and kept[0]['start'] == 4.6
    p = build_plan(RETAKE, 20, 'tacho_humano', 'ca')
    c = p['candidates'][0]
    assert all(s['in'] >= 4.4 for s in c['segments']), 'la presa tallada no pot sortir al muntatge'
    assert p['retakes_removed'][0]['start'] == 2.0 and 'repetida' in c['explanation']


def test_full_repeat_is_kept_as_gag_in_humor_styles():
    from creative_engine.director import drop_retakes, validate_transcript
    rows = validate_transcript([{'start': 1, 'end': 3, 'text': 'Una més i marxo.'},
                                {'start': 4, 'end': 6, 'text': 'Una més i marxo.'}], 10)
    assert len(drop_retakes(rows, keep_full_repeats=True)[0]) == 2
    assert len(drop_retakes(rows, keep_full_repeats=False)[0]) == 1


def test_revision_uses_same_rows_after_retakes():
    from creative_engine.revise import apply
    p = build_plan(RETAKE, 20, 'tacho_humano', 'ca')
    meta = {'duration': 20, 'width': 1080, 'height': 1920, 'fps': '30/1'}
    new, _ = apply(p['candidates'][0], 'treu el final', RETAKE, meta, None)
    assert all(s['in'] >= 4.4 for s in new['segments']) and new['duration'] < p['candidates'][0]['duration']
