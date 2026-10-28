"""Motor V4 con FFmpeg real: render, QC medido, fps, HDR, mudo, director 0..N y correcciones."""
import subprocess
from pathlib import Path

import pytest

from creative_engine import qc as QC
from creative_engine.analysis import analyze
from creative_engine.director import CLAIMS, build_plan
from creative_engine.media import output_fps, probe
from creative_engine.pipeline import render_candidate
from creative_engine.render import crop_geometry, render
from creative_engine.revise import NotUnderstood, apply, parse


def make(path: Path, duration=6.0, rate='25', size='720x1280', audio=True, hdr=False, extra=None):
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=size={size}:rate={rate}:duration={duration}']
    if audio:
        cmd += ['-f', 'lavfi', '-i', f'sine=frequency=330:beep_factor=4:sample_rate=48000:duration={duration}']
    vf = []
    if hdr:
        vf = ['-vf', 'zscale=tin=bt709:pin=bt709:min=bt709:rin=tv:t=arib-std-b67:p=bt2020:m=bt2020nc:r=tv,format=yuv420p10le',
              '-color_trc', 'arib-std-b67', '-color_primaries', 'bt2020', '-colorspace', 'bt2020nc']
    cmd += vf + ['-c:v', 'libx265' if hdr else 'libx264', '-preset', 'ultrafast']
    if not hdr:
        cmd += ['-pix_fmt', 'yuv420p']
    cmd += (['-c:a', 'aac'] if audio else []) + (extra or []) + [str(path)]
    subprocess.run(cmd, check=True, timeout=120)
    return path


STORY_A = [{'start': 3.0, 'end': 6.0, 'text': 'Sabeu per què escalfem les tovalloles abans de cada tractament?'},
           {'start': 6.4, 'end': 10.0, 'text': 'Perquè el client estigui còmode i relaxat des del primer minut.'},
           {'start': 10.3, 'end': 13.5, 'text': 'I per això la cabina sempre fa olor de cafè, és el secret!'}]
STORY_B = [{'start': 30.0, 'end': 33.0, 'text': 'Mai us he explicat l’error més gran del meu primer dia?'},
           {'start': 33.4, 'end': 37.0, 'text': 'Vaig obrir la porta de la cabina equivocada amb tota la confiança.'},
           {'start': 37.3, 'end': 40.5, 'text': 'Al final vam riure tant que ara és la nostra broma de l’equip!'}]


def edl(segments, captions=None):
    return {'id': 't', 'segments': segments, 'grade': 'natural',
            'captions': {'mode': 'phrase', 'events': captions or []}}


def test_director_proposes_several_distinct_stories():
    p = build_plan(STORY_A + STORY_B, 60, 'tacho_humano', 'ca')
    assert p['status'] == 'drafts' and len(p['candidates']) == 2
    r1, r2 = (c['provenance']['source_range'] for c in p['candidates'])
    assert r1[1] <= r2[0] or r2[1] <= r1[0], 'propuestas solapadas'
    assert all(c['segments'][0]['in'] >= 2.9 for c in p['candidates'])


def test_claims_are_flagged_not_hidden():
    rows = [{'start': 1, 'end': 5, 'text': 'Aquest tractament elimina les arrugues per sempre, garantit al 100%!'},
            {'start': 5.3, 'end': 9, 'text': 'Sabeu per què? Perquè és el secret de la cabina.'}]
    p = build_plan(rows, 20, 'educativo', 'ca')
    assert CLAIMS.search(rows[0]['text'])
    c = p['candidates'][0]
    assert 'claims_review' in c['requires'] and any('afirmacions' in r for r in c['risks'])


def test_revision_parser_and_apply():
    assert parse('Fes-lo més curt i sense subtítols') == [{'op': 'shorter'}, {'op': 'captions', 'mode': 'none'}]
    assert parse('más divertido por favor')[0] == {'op': 'style', 'style': 'tacho_humor'}
    assert parse('canvia "cafe" per "cafè"')[0]['op'] == 'replace_text'
    with pytest.raises(NotUnderstood):
        parse('fes màgia')
    p = build_plan(STORY_A, 20, 'tacho_humano', 'ca')
    base = p['candidates'][0]
    meta = {'duration': 20, 'width': 1080, 'height': 1920, 'fps': '30/1'}
    new, done = apply(base, 'més curt', STORY_A, meta, None)
    assert new['version'] == 2 and new['duration'] < base['duration'] and new['parent_id'] == base['id']
    fixed, _ = apply(base, 'canvia "tovalloles" per "tovalloles calentes"', STORY_A, meta, None)
    assert any('calentes' in e['text'] and e['type'] == 'edited' for e in fixed['captions']['events'])


def test_crop_geometry_landscape_and_zoom_limits():
    meta4k = {'width': 3840, 'height': 2160}
    cw, ch, x0, y0 = crop_geometry(meta4k, 1.0, 0.8)
    assert (cw, ch) == (1214, 2160) and x0 > 1920
    small = {'width': 720, 'height': 1280}
    assert crop_geometry(small, 1.5)[0] == 720  # zoom anulado en baja resolución


def test_render_keeps_25fps_measures_loudness_and_peak(tmp_path):
    src = make(tmp_path / 'in.mp4', 6, '25')
    meta = probe(src)
    assert output_fps(meta)[0] == '25/1'
    caps = [{'start': 0.2, 'end': 1.5, 'text': 'Hola Maresme', 'words': [], 'type': 'edited'}]
    out = tmp_path / 'out.mp4'
    info = render(edl([{'in': 0.5, 'out': 2.0}, {'in': 3.0, 'out': 4.6}], caps), src, meta, out, tmp_path / 'w')
    rep = QC.check(out, edl([], caps), meta, info)
    assert rep['status'] == 'pass', rep['checks']
    m = rep['measured']
    assert m['fps'] == '25/1' and (m['width'], m['height']) == (1080, 1920)
    assert abs(m['integrated_lufs'] + 16) <= 2 and m['true_peak_dbtp'] <= -0.95
    assert abs(m['duration'] - 3.1) < 0.2


def test_hdr_hlg_is_tonemapped_to_bt709(tmp_path):
    src = make(tmp_path / 'hdr.mov', 3, '30', hdr=True)
    meta = probe(src)
    assert meta['hdr'] and meta['color_transfer'] == 'arib-std-b67'
    out = tmp_path / 'sdr.mp4'
    info = render(edl([{'in': 0.2, 'out': 2.2}]), src, meta, out, tmp_path / 'w')
    assert info['tonemapped']
    o = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=color_transfer,pix_fmt',
                        '-of', 'csv=p=0', str(out)], capture_output=True, text=True).stdout
    assert 'bt709' in o and 'yuv420p' in o


def test_silent_source_never_passes_qc(tmp_path):
    src = make(tmp_path / 'mute.mp4', 4, '30', audio=False)
    meta = probe(src)
    out = tmp_path / 'o.mp4'
    info = render(edl([{'in': 0.5, 'out': 3.0}]), src, meta, out, tmp_path / 'w')
    rep = QC.check(out, edl([]), meta, info)
    assert rep['status'] == 'fail' and any(c['check'] == 'audio' and c['status'] == 'fail' for c in rep['checks'])


def test_out_of_range_segment_rejected(tmp_path):
    src = make(tmp_path / 'in.mp4', 3)
    with pytest.raises(ValueError):
        render(edl([{'in': 2.0, 'out': 9.0}]), src, probe(src), tmp_path / 'o.mp4', tmp_path / 'w')


def test_visual_only_without_signal_goes_to_review(tmp_path):
    src = make(tmp_path / 'in.mp4', 4)
    an = analyze(src)
    p = build_plan([], 4, 'tacho_humano', 'ca', analysis=an, meta=an['meta'])
    assert p['status'] == 'needs_review' and p['candidates'] == []


def test_pipeline_candidate_has_hash_poster_and_qc(tmp_path):
    src = make(tmp_path / 'in.mp4', 16, '30')
    an = analyze(src)
    rows = [{'start': 1.0, 'end': 4.5, 'text': 'Sabeu per què la cabina sempre està calenta?'},
            {'start': 4.8, 'end': 8.5, 'text': 'Perquè el confort és el primer pas del tractament.'},
            {'start': 8.8, 'end': 12.0, 'text': 'I per això ho preparem tot abans, és la clau!'}]
    p = build_plan(rows, an['meta']['duration'], 'auto', 'ca', analysis=an, meta=an['meta'])
    assert p['status'] == 'drafts'
    res = render_candidate(src, an['meta'], p['candidates'][0], tmp_path)
    assert len(res['sha256']) == 64 and res['poster'].is_file() and res['qc']['status'] == 'pass'
    assert res['sha256'] == QC.sha256(res['path'])
