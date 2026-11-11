"""Dos marcas, un motor: presets, vocabulario, riesgos, aspecto y EDL validado por esquema."""
import copy
import subprocess

import pytest

from creative_engine import brands as B
from creative_engine import edl_schema
from creative_engine.analysis import analyze
from creative_engine.captions import build_ass
from creative_engine.director import build_plan, load_styles
from creative_engine.pipeline import render_candidate
from creative_engine.revise import apply
from tests.test_engine_v4 import STORY_A, make

OWNER = [{'start': 2.0, 'end': 6.0, 'text': 'Saps per què alguns pisos porten mesos als portals sense vendre’s?'},
         {'start': 6.4, 'end': 10.5, 'text': 'Perquè el preu de sortida no surt d’una valoració real del barri.'},
         {'start': 10.8, 'end': 14.5, 'text': 'Per això el primer pas sempre és una bona valoració, és la clau!'}]


def test_each_brand_has_three_own_presets():
    styles = load_styles()
    for bid in B.brand_ids():
        b = B.get(bid)
        assert len(b['presets']) == 3
        assert all(styles[p]['brand'] == bid for p in b['presets'])
        assert set(b['auto_map'].values()) <= set(b['presets'])
        assert b['visual']['status'] in ('provisional', 'verified')


def test_brand_presets_do_not_cross():
    with pytest.raises(ValueError):
        build_plan(OWNER, 20, 'blau_expert', 'ca', brand='top_house')
    with pytest.raises(ValueError):
        build_plan(STORY_A, 20, 'top_property', 'ca', brand='blau_de_mar')
    with pytest.raises(ValueError):
        build_plan(STORY_A, 20, 'tacho_humor', 'ca', brand='top_house')  # estilo genérico no habilitado para Top House
    with pytest.raises(ValueError):
        build_plan(STORY_A, 20, 'auto', 'ca', brand='otra_marca')


def test_auto_picks_a_preset_of_the_brand_and_edl_carries_brand():
    top = build_plan(OWNER, 20, 'auto', 'ca', brand='top_house')
    blau = build_plan(STORY_A, 20, 'auto', 'ca', brand='blau_de_mar')
    assert top['status'] == blau['status'] == 'drafts'
    assert top['style'] == 'top_owner_expert' and blau['style'] in B.get('blau_de_mar')['presets']
    t, b = top['candidates'][0], blau['candidates'][0]
    assert t['brand']['id'] == 'top_house' and b['brand']['id'] == 'blau_de_mar'
    assert t['brand']['accent'] != b['brand']['accent'] and t['grade'] != b['grade']
    assert 'property_permission' in t['requires'] and 'property_permission' not in b['requires']
    assert edl_schema.errors(t, 20) == [] and edl_schema.errors(b, 20) == []


def test_default_brand_is_backwards_compatible():
    p = build_plan(STORY_A, 20, 'tacho_humano', 'ca')
    assert p['brand'] == 'blau_de_mar' and p['candidates'][0]['brand']['id'] == 'blau_de_mar'


def test_top_house_flags_prices_and_addresses():
    rows = [{'start': 1.0, 'end': 5.0, 'text': 'Saps què pots comprar al Maresme per 350.000 euros?'},
            {'start': 5.3, 'end': 9.5, 'text': 'Aquest pis del carrer Ample té 90 metres i terrassa amb vistes.'},
            {'start': 9.8, 'end': 13.0, 'text': 'Per això te l’ensenyem avui, és una oportunitat!'}]
    c = build_plan(rows, 20, 'top_local_story', 'ca', brand='top_house')['candidates'][0]
    joined = ' '.join(c['risks'])
    assert 'afirmacions a verificar' in joined and 'euros' in joined
    assert 'adreça' in joined
    assert {'claims_review', 'property_permission', 'team_consent'} <= set(c['requires'])


def test_blau_flags_unapproved_promotions():
    rows = [{'start': 1.0, 'end': 5.0, 'text': 'Sabeu que aquesta setmana tenim un descompte especial al facial?'},
            {'start': 5.3, 'end': 9.5, 'text': 'Perquè volem que proveu la cabina nova amb tota la calma.'},
            {'start': 9.8, 'end': 13.0, 'text': 'Per això us esperem a Arenys, és la clau!'}]
    c = build_plan(rows, 20, 'blau_human', 'ca', brand='blau_de_mar')['candidates'][0]
    assert any('promoció' in r for r in c['risks']) and 'claims_review' in c['requires']


def test_revision_keeps_style_inside_the_brand():
    c = build_plan(OWNER, 20, 'top_owner_expert', 'ca', brand='top_house')['candidates'][0]
    new, done = apply(c, 'més divertit', OWNER, {'duration': 20, 'width': 1080, 'height': 1920, 'fps': '30/1'}, None)
    assert load_styles()[new['style']].get('brand') == 'top_house' and new['brand']['id'] == 'top_house'
    assert new['version'] == 2


def test_caption_font_and_size_follow_brand():
    caps = {'mode': 'phrase', 'events': [{'start': 0, 'end': 1, 'text': 'Hola Maresme'}]}
    top = build_ass(caps, None, '#E8D9B5', 'Poppins SemiBold', 64)
    assert 'Style: cap,Poppins SemiBold,64,' in top
    assert 'Style: cap,Poppins ExtraBold,72,' in build_ass(caps)
    assert 'Style: cap,Poppins ExtraBold,' in build_ass(caps, None, '#E8D9B5', 'Fuente Sin Licencia')


def test_schema_rejects_broken_edl():
    good = build_plan(STORY_A, 20, 'blau_human', 'ca')['candidates'][0]
    assert edl_schema.errors(good, 20) == []
    for mutate, needle in [
        (lambda e: e.update(automatic_publish=True), 'automatic_publish'),
        (lambda e: e['output'].update(width=1920), 'output.width'),
        (lambda e: e['segments'][0].update({'in': 9.0, 'out': 4.0}), 'out <= in'),
        (lambda e: e['segments'][0].update(out=99.0), 'fuera del original'),
        (lambda e: e.pop('segments'), 'segments'),
        (lambda e: e['captions'].update(mode='karaoke'), 'captions.mode'),
        (lambda e: e['brand'].update(accent='azul'), 'brand.accent'),
    ]:
        bad = copy.deepcopy(good)
        mutate(bad)
        found = edl_schema.errors(bad, 20)
        assert found and any(needle in f for f in found), (needle, found)
    with pytest.raises(ValueError):
        edl_schema.assert_valid({'schema': 'blau.edl/4'})


def test_two_brands_render_distinguishable_outputs(tmp_path):
    """Mismo bruto, dos marcas: dos MP4 válidos con EDL, grade y subtítulos distintos (render FFmpeg real)."""
    src = make(tmp_path / 'in.mp4', 16, '30')
    an = analyze(src)
    outs = {}
    for bid, rows, style in (('blau_de_mar', STORY_A, 'blau_expert'), ('top_house', OWNER, 'top_owner_expert')):
        plan = build_plan(rows, an['meta']['duration'], style, 'ca', analysis=an, meta=an['meta'], brand=bid)
        assert plan['status'] == 'drafts', plan.get('reason')
        outs[bid] = render_candidate(src, an['meta'], plan['candidates'][0], tmp_path / bid)
    for bid, r in outs.items():
        assert r['qc']['status'] == 'pass', r['qc']
        assert r['path'].stat().st_size > 20000 and r['edl']['brand']['id'] == bid
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,codec_name',
                                '-of', 'csv=p=0', str(r['path'])], capture_output=True, text=True, check=True).stdout.strip()
        assert probe == 'h264,1080,1920'
    assert outs['blau_de_mar']['sha256'] != outs['top_house']['sha256']


def test_invalid_edl_is_never_rendered(tmp_path):
    src = make(tmp_path / 'in.mp4', 6, '30')
    an = analyze(src)
    with pytest.raises(ValueError, match='EDL no válido'):
        render_candidate(src, an['meta'], {'id': 'x', 'segments': [{'in': 0, 'out': 2}]}, tmp_path / 'w')


# ------------------------------------------------------------ encargo por vídeo, guion y sonoridad (guía de referencia)
LONG = OWNER + [{'start': 15.0, 'end': 19.0, 'text': 'I després cal preparar bé la casa abans de fer les fotos.'},
                {'start': 19.3, 'end': 23.5, 'text': 'Per això sempre fem una visita prèvia amb el propietari, és la clau!'}]


def test_brief_max_seconds_and_cta_are_respected():
    free = build_plan(LONG, 30, 'top_owner_expert', 'ca', brand='top_house')['candidates'][0]
    p = build_plan(LONG, 30, 'top_owner_expert', 'ca', brand='top_house',
                   options={'brief': {'max_seconds': 14, 'cta': 'Demana una valoració', 'topic': 'pisos que no es venen', 'goal': 'leads'}})
    c = p['candidates'][0]
    assert free['duration'] > 14 >= c['duration']
    cta = [o for o in c['overlays'] if o.get('kind') == 'cta']
    assert cta and cta[0]['text'] == 'Demana una valoració' and abs(cta[0]['end'] - c['duration']) < 0.01
    assert c['brief']['goal'] == 'leads' and p['brief']['max_seconds'] == 14
    assert edl_schema.errors(c, 30) == []


def test_brief_ignores_garbage_and_never_invents_cta():
    c = build_plan(OWNER, 20, 'top_owner_expert', 'ca', brand='top_house',
                   options={'brief': {'max_seconds': 'molt', 'goal': 'viral', 'cta': '  '}})['candidates'][0]
    assert c['brief'] == {} and not [o for o in c['overlays'] if o.get('kind') == 'cta']


def test_revision_to_a_duration_keeps_whole_sentences_and_moves_cta():
    meta = {'duration': 30, 'width': 1080, 'height': 1920, 'fps': '30/1'}
    c = build_plan(LONG, 30, 'top_owner_expert', 'ca', brand='top_house', options={'brief': {'cta': 'Escriu-nos'}})['candidates'][0]
    new, done = apply(c, 'Fes una versió de 13 s', LONG, meta, None)
    assert new['duration'] <= 13.5 < c['duration'] and any('màxim 13' in d for d in done)
    assert new['captions']['events'][-1]['text'].rstrip().endswith(('?', '.', '!'))
    cta = [o for o in new['overlays'] if o.get('kind') == 'cta'][0]
    assert abs(cta['end'] - new['duration']) < 0.01
    short, _ = apply(c, 'Fes una versió de 6 s', LONG, meta, None)
    assert short['provenance']['transcript_rows'][0] == short['provenance']['transcript_rows'][1]  # queda una frase entera
    from creative_engine.revise import NotUnderstood
    slow = [{'start': 1.0, 'end': 9.5, 'text': 'Saps per què alguns pisos porten molts mesos als portals sense vendre’s mai?'}] + LONG[1:]
    slow[1] = {**slow[1], 'start': 9.8, 'end': 13.0}
    slow[2] = {**slow[2], 'start': 13.2, 'end': 14.8}
    c2 = build_plan(slow, 30, 'top_owner_expert', 'ca', brand='top_house')['candidates'][0]
    with pytest.raises(NotUnderstood):
        apply(c2, 'Fes una versió de 6 s', slow, meta, None)  # la primera frase ya dura más: se dice, no se corta


def test_storyboard_traces_every_moment_to_the_source():
    from creative_engine import storyboard
    c = build_plan(OWNER, 20, 'top_owner_expert', 'ca', brand='top_house', options={'brief': {'cta': 'Escriu-nos'}})['candidates'][0]
    rows = storyboard.build(c)
    assert len(rows) == len(c['segments']) and rows[0]['start'] == 0
    assert abs(rows[-1]['end'] - c['duration']) < 0.02
    assert all(r['source_out'] > r['source_in'] for r in rows) and any('valoració' in r['says'] for r in rows)
    assert 'Escriu-nos' in rows[-1]['on_screen'] and '| Original |' in storyboard.as_markdown(c)


def test_loudness_target_follows_the_edl_and_first_two_seconds_are_checked(tmp_path):
    src = make(tmp_path / 'in.mp4', 16, '30')
    an = analyze(src)
    edl = build_plan(STORY_A, an['meta']['duration'], 'blau_expert', 'ca', analysis=an, meta=an['meta'])['candidates'][0]
    assert edl['audio']['target_lufs'] == -16
    edl['audio']['target_lufs'] = -14
    r = render_candidate(src, an['meta'], edl, tmp_path / 'w')
    checks = {c['check']: c for c in r['qc']['checks']}
    assert abs(r['qc']['measured']['integrated_lufs'] + 14) <= 1.0 and 'objetivo -14' in checks['sonoridad']['detail']
    assert checks['primeros 2 s sin sonido']['status'] == 'pass' and r['edl']['storyboard']
    edl2 = copy.deepcopy(edl)
    edl2['id'], edl2['captions'] = 'sense-text', {'mode': 'none', 'events': []}
    r2 = render_candidate(src, an['meta'], edl2, tmp_path / 'w2')
    assert {c['check']: c for c in r2['qc']['checks']}['primeros 2 s sin sonido']['status'] == 'warn'
    assert r2['qc']['status'] == 'pass'  # aviso, no bloqueo: un vídeo sensorial sin texto es legítimo
