"""Orquestación local: análisis -> transcripción -> director 0..N -> render -> QC -> portada.

La usan el agente (cola Cloudflare) y la CLI. Nunca publica. Cada resultado lleva EDL, QC medido y SHA256.
"""
from __future__ import annotations

import json
import os
import tempfile
import traceback
from pathlib import Path
from typing import Callable

from creative_engine import qc as QC
from creative_engine.analysis import analyze
from creative_engine.director import build_plan
from creative_engine.media import probe
from creative_engine.render import poster, render
from creative_engine.revise import apply, apply_manual
from creative_engine.transcribe import transcribe_local
from creative_engine.vision_llm import describe_shots

Progress = Callable[[str, int, str], None]


def _noop(stage, pct, msg):
    pass


def understand(source: Path, language: str = 'ca', progress: Progress = _noop, transcript: dict | None = None) -> dict:
    progress('analyzing', 5, 'Llegint el vídeo')
    meta = probe(source)
    progress('analyzing', 10, 'Analitzant imatge i so')
    an = analyze(source, meta)
    if os.environ.get('BLAU_VISION_MODEL'):
        progress('analyzing', 20, 'Descrivint els plans amb el model de visió local')
        an['semantic_vision'] = describe_shots(source, an, Path(tempfile.mkdtemp(prefix='blau-vision-')))
    if transcript is None:
        progress('transcribing', 30, 'Transcrivint el diàleg en local')
        try:
            transcript = transcribe_local(source, language)
        except Exception as exc:  # sin modelo/librería: se dice, no se inventa
            transcript = {'segments': [], 'error': str(exc)[:300], 'engine': None}
    return {'meta': meta, 'analysis': an, 'transcript': transcript}


def render_candidate(source: Path, meta: dict, edl: dict, workdir: Path) -> dict:
    out = workdir / f"{edl['id']}-v{edl.get('version', 1)}.mp4"
    info = render(edl, source, meta, out, workdir / ('work-' + edl['id']))
    report = QC.check(out, edl, meta, info)
    jpg = poster(out, out.with_suffix('.jpg'), at=min(0.5, max(0.0, report['duration'] / 3)))
    return {'edl': edl, 'path': out, 'poster': jpg, 'qc': report, 'render': info, 'sha256': QC.sha256(out)}


def produce(source: Path, workdir: Path, style: str = 'auto', language: str = 'ca', options: dict | None = None,
            progress: Progress = _noop, understood: dict | None = None) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    u = understood or understand(source, language, progress)
    progress('directing', 45, 'Buscant les millors històries')
    plan = build_plan(u['transcript'].get('segments', []), u['meta']['duration'], style, language,
                      analysis=u['analysis'], meta=u['meta'], options=options or {})
    if u['transcript'].get('error'):
        plan['transcript_error'] = u['transcript']['error']
    results = []
    n = len(plan['candidates'])
    for k, edl in enumerate(plan['candidates']):
        progress('rendering', 50 + int(40 * k / max(1, n)), f'Muntant proposta {k + 1} de {n}')
        try:
            results.append(render_candidate(source, u['meta'], edl, workdir))
        except Exception as exc:
            results.append({'edl': edl, 'error': f'{type(exc).__name__}: {exc}'[:500], 'trace': traceback.format_exc()[-1500:]})
    progress('qc', 92, 'Control de qualitat fet')
    return {'understood': u, 'plan': plan, 'results': results}


def revise(source: Path, workdir: Path, edl: dict, understood: dict, instruction: str | None = None,
           manual: dict | None = None, progress: Progress = _noop) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    progress('directing', 40, 'Aplicant la correcció')
    if manual:
        new, done = apply_manual(edl, manual, understood['meta']), ['edició manual']
    else:
        new, done = apply(edl, instruction or '', understood['transcript'].get('segments', []), understood['meta'],
                          understood['analysis'])
    progress('rendering', 55, 'Muntant la nova versió')
    return {'result': render_candidate(source, understood['meta'], new, workdir), 'applied': done}


def summary(understood: dict) -> dict:
    """Resumen ligero para la base de datos/UI (sin series temporales completas)."""
    an, tr = understood['analysis'], understood['transcript']
    v, au = an['visual'], an.get('audio') or {}
    return {'meta': understood['meta'],
            'shots': len(v['shots']), 'face_ratio': v.get('face_ratio'), 'face_detector': v.get('face_detector'),
            'blurry_ranges': v['blurry_ranges'][:20], 'dark_ranges': v['dark_ranges'][:20],
            'motion_bursts': v['motion_bursts'][:30],
            'audio': {k: au.get(k) for k in ('has_audio', 'median_db', 'probable_music', 'bpm', 'silences', 'energy_bursts')},
            'transcript': {'engine': tr.get('engine'), 'language': tr.get('language'), 'word_timing': tr.get('word_timing'),
                           'error': tr.get('error'), 'segments': [{'start': s['start'], 'end': s['end'], 'text': s['text']}
                                                                  for s in tr.get('segments', [])]},
            'semantic_vision': an.get('semantic_vision')}


def dump(obj, path: Path):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding='utf8')
