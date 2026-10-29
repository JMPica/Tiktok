"""Visión semántica OPCIONAL con un modelo local vía Ollama (sin nube, sin coste).

Activación: BLAU_VISION_MODEL (p. ej. ``qwen2.5vl:7b`` o ``llava:7b`` instalado con `ollama pull`).
Describe un fotograma por plano: qué pasa, si hay personas, emoción aparente y si podría salir un cliente
o un menor (sin identificar a nadie). Si no está configurado o falla, se devuelve None/un error explícito y
el director sigue con señales de imagen y sonido, diciéndolo.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from pathlib import Path

from creative_engine.media import run, tonemap_filter

PROMPT = ('Eres asistente de edición de vídeo de un centro de estética. Describe SOLO lo visible en este fotograma, '
          'sin identificar a nadie ni inventar. Responde JSON con claves: "descripcion" (máx 20 palabras, castellano), '
          '"accion" (verbo principal o ""), "personas" (número), "emocion" ("neutral","alegria","sorpresa","concentracion","otra"), '
          '"calidad" (1-5 encuadre/luz), "posible_cliente" (true si parece una clienta en tratamiento), "posible_menor" (true/false).')
MAX_SHOTS = 12


def _frame_jpeg(video: Path, t: float, meta: dict, dest: Path) -> bytes:
    vf = f'scale=512:-2,{tonemap_filter(meta)}'.rstrip(',')
    r = run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', str(video), '-frames:v', '1',
             '-vf', vf, '-q:v', '4', str(dest)], timeout=120)
    if r.returncode or not dest.is_file():
        raise RuntimeError('no se pudo extraer fotograma: ' + r.stderr[-200:])
    return dest.read_bytes()


def _ask(url: str, model: str, jpeg: bytes, timeout: int) -> dict:
    body = json.dumps({'model': model, 'prompt': PROMPT, 'images': [base64.b64encode(jpeg).decode()],
                       'format': 'json', 'stream': False, 'options': {'temperature': 0}}).encode()
    req = urllib.request.Request(url.rstrip('/') + '/api/generate', data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(json.loads(r.read())['response'])
    return {'descripcion': str(data.get('descripcion', ''))[:160], 'accion': str(data.get('accion', ''))[:40],
            'personas': int(data.get('personas') or 0), 'emocion': str(data.get('emocion', ''))[:20],
            'calidad': max(1, min(5, int(data.get('calidad') or 3))),
            'posible_cliente': bool(data.get('posible_cliente')), 'posible_menor': bool(data.get('posible_menor'))}


def describe_shots(video: Path, analysis: dict, workdir: Path) -> dict | None:
    model = os.environ.get('BLAU_VISION_MODEL')
    if not model:
        return None
    url = os.environ.get('BLAU_OLLAMA_URL', 'http://127.0.0.1:11434')
    timeout = int(os.environ.get('BLAU_VISION_TIMEOUT', '180'))
    shots = sorted(analysis['visual']['shots'], key=lambda s: s['end'] - s['start'], reverse=True)[:MAX_SHOTS]
    shots.sort(key=lambda s: s['start'])
    out = []
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        for k, sh in enumerate(shots):
            mid = (sh['start'] + sh['end']) / 2
            jpeg = _frame_jpeg(video, mid, analysis['meta'], workdir / f'kf{k}.jpg')
            out.append({'start': sh['start'], 'end': sh['end'], 't': round(mid, 2), **_ask(url, model, jpeg, timeout)})
    except Exception as exc:  # modelo ausente, apagado o respuesta inválida: se informa, no se inventa
        return {'model': model, 'error': f'{type(exc).__name__}: {exc}'[:300], 'shots': out}
    return {'model': model, 'shots': out}


def window_notes(semantic: dict | None, a: float, b: float) -> dict:
    """Resumen de lo visto entre a y b para el director."""
    if not semantic or not semantic.get('shots'):
        return {'available': False}
    hits = [s for s in semantic['shots'] if s['start'] < b and s['end'] > a]
    if not hits:
        return {'available': True, 'seen': []}
    return {'available': True, 'seen': [h['descripcion'] for h in hits if h['descripcion']][:3],
            'people': max(h['personas'] for h in hits), 'quality': min(h['calidad'] for h in hits),
            'emotion': sorted({h['emocion'] for h in hits if h['emocion'] not in ('', 'neutral')}),
            'client': any(h['posible_cliente'] for h in hits), 'minor': any(h['posible_menor'] for h in hits)}
