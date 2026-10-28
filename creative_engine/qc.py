"""Control de calidad MEDIDO sobre el MP4 final (no supuesto).

Fallos bloquean la aprobación (el vídeo queda en ``needs_review``). Avisos se muestran a la revisora.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from creative_engine.captions import caption_report
from creative_engine.media import probe, run


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def loudness(path: Path) -> dict:
    r = run(['ffmpeg', '-hide_banner', '-nostdin', '-nostats', '-i', str(path), '-vn', '-af', 'ebur128=peak=true',
             '-f', 'null', '-'], timeout=1800)
    summary = r.stderr.split('Summary:')[-1]

    def grab(pattern):
        m = re.search(pattern, summary)
        if not m:
            return None
        return float('-inf') if m.group(1) == '-inf' else float(m.group(1))
    return {'integrated_lufs': grab(r'I:\s+(-?[\d.]+|-inf) LUFS'), 'lra_lu': grab(r'LRA:\s+(-?[\d.]+) LU'),
            'true_peak_dbtp': grab(r'Peak:\s+(-?[\d.]+|-inf) dBFS')}


def decode_errors(path: Path) -> str:
    r = run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-i', str(path), '-f', 'null', '-'], timeout=1800)
    return (r.stderr.strip() or ('exit %d' % r.returncode if r.returncode else ''))[:400]


def black_ratio(path: Path, duration: float) -> float:
    r = run(['ffmpeg', '-hide_banner', '-nostdin', '-i', str(path), '-an', '-vf', 'blackdetect=d=0.2:pix_th=0.08',
             '-f', 'null', '-'], timeout=1800)
    total = sum(float(x) for x in re.findall(r'black_duration:([\d.]+)', r.stderr))
    return round(total / duration, 3) if duration > 0 else 0.0


def check(video: Path, edl: dict, source_meta: dict, render_info: dict) -> dict:
    checks = []

    def add(name, status, detail):
        checks.append({'check': name, 'status': status, 'detail': detail})

    m = probe(video)
    add('resolución', 'pass' if (m['width'], m['height']) == (1080, 1920) else 'fail', f"{m['width']}x{m['height']}")
    add('códec', 'pass' if m['codec'] == 'h264' and m['audio_codec'] == 'aac' else 'fail', f"{m['codec']}/{m['audio_codec']}")
    errs = decode_errors(video)
    add('decodificación completa', 'fail' if errs else 'pass', errs or 'sin errores')
    exp = render_info.get('expected_duration') or 0
    add('duración', 'pass' if abs(m['duration'] - exp) <= 0.3 else 'fail', f"{m['duration']:.2f}s (esperado {exp:.2f}s)")
    add('fps', 'pass' if m['fps'] == render_info.get('fps') or abs(m['fps_float'] - float(eval_fraction(render_info.get('fps')))) < 0.02 else 'fail',
        f"{m['fps']} · {render_info.get('fps_reason')}")
    loud = loudness(video) if m['audio'] else {'integrated_lufs': None, 'true_peak_dbtp': None, 'lra_lu': None}
    il, tp = loud['integrated_lufs'], loud['true_peak_dbtp']
    if not m['audio']:
        add('audio', 'fail', 'sin pista de audio')
    elif il is None or il == float('-inf') or il < -50:
        add('audio', 'fail', 'export mudo: el audio está en silencio' + ('' if source_meta.get('audio') else ' (el bruto no tiene audio)'))
    else:
        add('audio', 'pass', 'audio presente')
        add('sonoridad', 'pass' if abs(il + 16) <= 2 else 'warn' if abs(il + 16) <= 4 else 'fail', f'{il:.1f} LUFS (objetivo -16)')
        add('pico real', 'pass' if tp is not None and tp <= -0.95 else 'fail', f'{tp:.2f} dBTP (máximo -1)')
    br = black_ratio(video, m['duration'])
    add('negros', 'pass' if br < 0.05 else 'warn', f'{br * 100:.1f}% del metraje en negro')
    if source_meta.get('hdr'):
        add('HDR->SDR', 'pass' if render_info.get('tonemapped') else 'fail', f"{source_meta.get('color_transfer')} -> bt709")
    if min(source_meta['width'], source_meta['height']) < 1080:
        add('resolución de origen', 'warn', f"bruto {source_meta['width']}x{source_meta['height']}: se ha ampliado, se verá blando")
    cap = caption_report(edl.get('captions') or {}, edl.get('overlays'))
    add('subtítulos', 'warn' if cap['issues'] else 'pass', '; '.join(cap['issues'][:4]) or f"{cap['events']} subtítulos · pendientes de revisión humana")
    status = 'fail' if any(c['status'] == 'fail' for c in checks) else 'pass'
    return {'status': status, 'checks': checks, 'measured': {**m, **loud, 'black_ratio': br},
            'captions': cap, 'decode_ok': not errs, 'audio_present': bool(m['audio'] and il not in (None, float('-inf')) and il >= -50),
            'width': m['width'], 'height': m['height'], 'duration': m['duration'], 'fps': m['fps'],
            'editorial_review': 'human_required', 'generative_effects': 'disabled'}


def eval_fraction(value) -> float:
    try:
        a, _, b = str(value).partition('/')
        return float(a) / float(b or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0
