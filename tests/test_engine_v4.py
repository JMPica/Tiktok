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


def test_output_fps_rules():
    assert output_fps({'fps': '25/1', 'vfr': False})[0] == '25/1'
    assert output_fps({'fps': '30000/1001', 'vfr': False})[0] == '30000/1001'
    fps, why = output_fps({'fps': '2397/80', 'vfr': True})  # iPhone VFR ~29.96
    assert fps == '30000/1001' and 'VFR' in why
    assert output_fps({'fps': '120/1', 'vfr': False})[0] == '60/1'


def test_caption_lines_fit_safe_width():
    from creative_engine.captions import caption_report, chunk
    words = [{'start': i * 0.3, 'end': i * 0.3 + 0.25, 'word': w} for i, w in
             enumerate('Després escalfem les tovalloles perquè el client estigui còmode i relaxat des del primer minut'.split())]
    for size in ('m', 'l'):
        events = chunk(words, size)
        assert all(ev['text'].count('\n') <= 1 for ev in events)
        rep = caption_report({'mode': 'phrase', 'size': size, 'position': 'lower', 'events': events})
        assert not [i for i in rep['issues'] if 'ancha' in i], rep['issues']


def _fake_ollama(reply: dict):
    """Servidor HTTP local que responde como Ollama /api/generate (solo para probar el cliente)."""
    import http.server
    import json as _json
    import threading

    seen = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = _json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            seen.append(body)
            out = _json.dumps({'response': _json.dumps(reply)}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


def test_semantic_vision_feeds_director_and_flags_client(tmp_path, monkeypatch):
    from creative_engine.vision_llm import describe_shots
    srv, seen = _fake_ollama({'descripcion': 'Esteticista prepara la cabina', 'accion': 'preparar', 'personas': 1,
                              'emocion': 'alegria', 'calidad': 4, 'posible_cliente': True, 'posible_menor': False})
    monkeypatch.setenv('BLAU_VISION_MODEL', 'fake-vl')
    monkeypatch.setenv('BLAU_OLLAMA_URL', f'http://127.0.0.1:{srv.server_address[1]}')
    src = make(tmp_path / 'in.mp4', 16, '30')
    an = analyze(src)
    an['semantic_vision'] = describe_shots(src, an, tmp_path / 'kf')
    assert seen and seen[0]['model'] == 'fake-vl' and seen[0]['images'], 'debe enviar un fotograma real'
    assert an['semantic_vision']['shots'][0]['descripcion'].startswith('Esteticista')
    rows = [{'start': 1.0, 'end': 4.5, 'text': 'Sabeu per què la cabina sempre està calenta?'},
            {'start': 4.8, 'end': 8.5, 'text': 'Perquè el confort és el primer pas del tractament.'},
            {'start': 8.8, 'end': 12.0, 'text': 'I per això ho preparem tot abans, és la clau!'}]
    p = build_plan(rows, an['meta']['duration'], 'tacho_humano', 'ca', analysis=an, meta=an['meta'])
    c = p['candidates'][0]
    assert any('es veu' in n for n in c['provenance']['notes'])
    assert any('clienta' in r for r in c['risks'])
    assert 'fake-vl' in p['semantic_vision']
    srv.shutdown()


def test_semantic_vision_unavailable_is_explicit(tmp_path, monkeypatch):
    from creative_engine.vision_llm import describe_shots
    monkeypatch.setenv('BLAU_VISION_MODEL', 'missing')
    monkeypatch.setenv('BLAU_OLLAMA_URL', 'http://127.0.0.1:9')  # nadie escucha
    monkeypatch.setenv('BLAU_VISION_TIMEOUT', '3')
    src = make(tmp_path / 'in.mp4', 3)
    an = analyze(src)
    sem = describe_shots(src, an, tmp_path / 'kf')
    assert sem['error'] and sem['model'] == 'missing'


def test_dark_footage_is_vetoed(tmp_path):
    src = tmp_path / 'dark.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=720x1280:rate=30:duration=14',
                    '-f', 'lavfi', '-i', 'sine=frequency=330:beep_factor=4:sample_rate=48000:duration=14',
                    '-vf', 'eq=brightness=-0.9', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                    str(src)], check=True)
    an = analyze(src)
    rows = [{'start': 1.0, 'end': 4.5, 'text': 'Sabeu per què la cabina sempre està calenta?'},
            {'start': 4.8, 'end': 8.5, 'text': 'Perquè el confort és el primer pas del tractament.'},
            {'start': 8.8, 'end': 12.0, 'text': 'I per això ho preparem tot abans, és la clau!'}]
    p = build_plan(rows, an['meta']['duration'], 'tacho_humano', 'ca', analysis=an, meta=an['meta'])
    assert p['status'] == 'needs_review' and 'fosca' in p['reason']


def test_hdr_tonemap_keeps_brightness_close_to_reference(tmp_path):
    """El HLG se fabrica desde un patrón SDR conocido: la salida no debe oscurecerse (antes: -48 % de brillo)."""
    import numpy as np
    src = make(tmp_path / 'hdr.mov', 2, '30', size='1080x1920', hdr=True)
    meta = probe(src)
    out = tmp_path / 'sdr.mp4'
    render(edl([{'in': 0.2, 'out': 1.5}]), src, meta, out, tmp_path / 'w')

    def mean_rgb(path, extra=''):
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '0.5', '-i', str(path), '-frames:v', '1', '-vf',
                              f'{extra}scale=108:192,format=rgb24', '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.uint8).astype(float).mean()
    ref = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=1080x1920:rate=30:duration=1', '-frames:v', '1',
                          '-vf', 'scale=108:192,format=rgb24', '-f', 'rawvideo', '-'], capture_output=True, check=True).stdout
    ref_mean = np.frombuffer(ref, np.uint8).astype(float).mean()
    assert abs(mean_rgb(out) - ref_mean) / ref_mean < 0.15
