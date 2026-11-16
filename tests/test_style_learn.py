"""«Aprèn l'estil»: medidas reales con FFmpeg, derivación auditable, validación y uso en el director."""
import json
import subprocess
from pathlib import Path

import pytest

from creative_engine import style_learn as SL
from creative_engine.director import build_plan, load_styles, register_learned, _REGISTERED
from tests.test_engine_v4 import STORY_A, make


def cuts_video(path: Path, seg=2.0, n=5):
    """Vídeo con cortes duros cada ``seg`` segundos (colores distintos) y audio con tono."""
    colors = ['red', 'green', 'blue', 'yellow', 'white', 'purple', 'orange']
    ins, flt = [], []
    for k in range(n):
        ins += ['-f', 'lavfi', '-i', f'color=c={colors[k % 7]}:s=360x640:r=25:d={seg}']
    ins += ['-f', 'lavfi', '-i', f'sine=frequency=300:sample_rate=48000:duration={seg * n}']
    cat = ''.join(f'[{k}:v]' for k in range(n)) + f'concat=n={n}:v=1:a=0[v]'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', cat, '-map', '[v]', '-map', f'{n}:a',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(path)], check=True, timeout=120)
    return path


@pytest.fixture(scope='module')
def refs(tmp_path_factory):
    d = tmp_path_factory.mktemp('refs')
    return [cuts_video(d / 'a.mp4', 1.2, 7), cuts_video(d / 'b.mp4', 1.2, 10), cuts_video(d / 'c.mp4', 1.2, 12)]


def test_measure_detects_real_cut_rhythm(refs):
    m = SL.measure(refs[0])
    assert 8 <= m['duration'] <= 9 and 4 <= m['shots'] <= 8
    assert 1.0 <= m['median_shot_s'] <= 2.2, m
    assert m['has_audio'] and 'shot_lengths' in m


def test_derive_is_auditable_and_bounded(refs):
    ms = [SL.measure(r) for r in refs]
    prof = SL.derive(ms, 'Ritme ràpid', captions='words', grade='punchy')
    assert prof['id'] == 'learned_ritme_rapid' and prof['learned']['copies_content'] is False
    r = prof['render']
    assert r['punch_zoom'] == 0.08                       # >= 5 cortes/10 s => zoom alterno suave
    assert 8 <= r['ideal'][0] < r['ideal'][1] <= r['max_len'] <= 90
    assert prof['target_shot_seconds']['max'] > prof['target_shot_seconds']['min']
    assert prof['learned']['explanation'] and 'transcript' not in json.dumps(prof)
    assert SL.validate(json.loads(json.dumps(prof)))['id'] == prof['id']


def test_needs_between_2_and_8_references():
    with pytest.raises(ValueError):
        SL.derive([{'duration': 20, 'shot_lengths': [2], 'cuts_per_10s': 3, 'has_audio': True,
                    'pause_s_p90': None, 'silence_ratio': 0.1, 'probable_music': False}], 'x')


@pytest.mark.parametrize('field,value', [('max_pause', 5), ('punch_zoom', 0.9), ('captions', 'rainbow'), ('grade', 'neon')])
def test_validate_rejects_out_of_range(refs, field, value):
    prof = SL.derive([SL.measure(r) for r in refs[:2]], 'Prova')
    prof['render'][field] = value
    with pytest.raises(ValueError):
        SL.validate(prof)


def test_learned_style_cannot_remove_approval_requirements(refs):
    prof = SL.derive([SL.measure(r) for r in refs[:2]], 'Sense requisits')
    prof['render']['requires'] = []
    p = SL.validate(prof)
    assert p['render']['requires'] == []
    reg = {**prof}
    register_learned(reg)
    try:
        plan = build_plan(STORY_A, 20, reg['id'], 'ca')
        assert plan['candidates'] and 'team_consent' in plan['candidates'][0]['requires']  # el consentimiento sigue exigido
        assert plan['candidates'][0]['style'] == reg['id'] and plan['candidates'][0]['automatic_publish'] is False
    finally:
        _REGISTERED.clear()


def test_save_and_load_from_folder_and_builtin_not_overridden(refs, tmp_path, monkeypatch):
    prof = SL.derive([SL.measure(r) for r in refs[:2]], 'Disc')
    path = SL.save(prof, tmp_path)
    (tmp_path / 'learned_trencat.json').write_text('{no json')
    monkeypatch.setenv('BLAU_STYLES_DIR', str(tmp_path))
    st = load_styles()
    assert prof['id'] in st and 'tacho_humano' in st and len(st) >= 19
    assert path.name == prof['id'] + '.json'
