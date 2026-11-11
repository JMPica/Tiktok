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
