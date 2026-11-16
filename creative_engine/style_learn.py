"""«Aprèn l'estil»: mide vídeos de referencia propios y deriva una ficha de estilo editable.

Qué hace: mide con señales reales (ritmo de planos, duración, pausas, sonoridad, presencia de cara, música probable)
3–6 vídeos de referencia y convierte esas medidas en un perfil de render (mismas claves que ``styles.v4.json``).
Qué NO hace: no copia vídeos, frases, voces ni identidades; no guarda transcripción ni fotogramas; no sube nada.
Solo se guardan números agregados + la entrevista (subtítulos, color) que la persona responde.

Uso:
  python -m creative_engine.style_learn REF1.mp4 REF2.mp4 REF3.mp4 --name "El nostre ritme" [--captions words]
Los perfiles se guardan en ``learned_styles/<id>.json`` (carpeta configurable con BLAU_STYLES_DIR).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import unicodedata
from pathlib import Path

from creative_engine import analysis as A
from creative_engine.media import probe

SCHEMA = 'blau.learned_style/1'
MIN_REFS, MAX_REFS = 2, 8
GRADES = ('natural', 'punchy', 'premium', 'none')  # mismas claves que render.GRADES
CAPTIONS = ('words', 'phrase', 'none')


def styles_dir() -> Path:
    return Path(os.environ.get('BLAU_STYLES_DIR') or Path(__file__).resolve().parent.parent / 'learned_styles')


def slug(name: str) -> str:
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_')[:32] or 'estil'
    return 'learned_' + s


def _pct(vals: list[float], q: float) -> float:
    s = sorted(vals)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def measure(video: Path, analysis: dict | None = None) -> dict:
    """Medidas de UN vídeo de referencia (sin transcripción: solo señal de imagen y sonido)."""
    meta = probe(video)
    an = analysis or A.analyze(video, meta)
    dur = float(meta['duration'])
    shots = [s['end'] - s['start'] for s in an['visual']['shots'] if s['end'] - s['start'] > 0.2]
    au = an.get('audio') or {}
    pauses = [s['end'] - s['start'] for s in au.get('silences', [])]
    silent = sum(pauses)
    return {
        'duration': round(dur, 2),
        'shots': len(shots),
        'cuts_per_10s': round(10 * max(0, len(shots) - 1) / dur, 2) if dur else 0,
        'median_shot_s': round(statistics.median(shots), 2) if shots else None,
        'shot_lengths': [round(x, 2) for x in shots],
        'face_ratio': an['visual'].get('face_ratio'),
        'has_audio': bool(au.get('has_audio')),
        'pause_count': len(pauses), 'pause_s_median': round(statistics.median(pauses), 2) if pauses else None,
        'pause_s_p90': round(_pct(pauses, 0.9), 2) if pauses else None,
        'silence_ratio': round(silent / dur, 3) if dur else None,
        'median_db': au.get('median_db'), 'probable_music': bool(au.get('probable_music')),
        'energy_bursts': len(au.get('energy_bursts', [])),
        'fps': meta.get('fps'),
    }


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def derive(measures: list[dict], name: str, captions: str = 'words', grade: str = 'natural',
           speech: str | None = None, notes: str = '', style_id: str | None = None) -> dict:
    """Ficha de estilo (perfil de render) a partir de las medidas. Reglas simples y auditables."""
    if not MIN_REFS <= len(measures) <= MAX_REFS:
        raise ValueError(f'Calen entre {MIN_REFS} i {MAX_REFS} vídeos de referència (n’hi ha {len(measures)})')
    if captions not in CAPTIONS or grade not in GRADES:
        raise ValueError('captions/grade no vàlids')
    durs = [m['duration'] for m in measures]
    shots = [x for m in measures for x in m['shot_lengths']]
    cuts = statistics.median(m['cuts_per_10s'] for m in measures)
    med_shot = statistics.median(shots) if shots else 2.5
    pauses = [m['pause_s_p90'] for m in measures if m['pause_s_p90'] is not None]
    with_audio = [m for m in measures if m['has_audio']]
    talk = [m for m in with_audio if (m['silence_ratio'] or 0) < 0.5]
    inferred_speech = 'required' if with_audio and len(talk) == len(measures) else 'optional'
    explain = []
    lo_s = round(_clip(_pct(shots, 0.25), 0.8, 6), 1) if shots else 1.4
    hi_s = round(_clip(max(_pct(shots, 0.75), lo_s + 0.6), 1.5, 9), 1) if shots else 4.0
    explain.append(f'planos: mediana {med_shot:.1f}s, {cuts:.1f} cortes cada 10 s → plano objetivo {lo_s}–{hi_s}s')
    ideal_lo = int(_clip(round(_pct(durs, 0.25)), 8, 60))
    ideal_hi = int(_clip(round(max(_pct(durs, 0.75), ideal_lo + 6)), 14, 75))
    max_len = int(_clip(round(max(durs) * 1.15), ideal_hi, 90))
    explain.append(f'duración: {min(durs):.0f}–{max(durs):.0f}s en las referencias → ideal {ideal_lo}–{ideal_hi}s, máximo {max_len}s')
    # Pausa máxima que se conserva: si las referencias casi no tienen pausas largas, el montaje es apretado.
    max_pause = round(_clip(statistics.median(pauses) if pauses else 0.5, 0.25, 0.9), 2)
    explain.append(f'pausas: las más largas de las referencias rondan {max_pause}s → se conservan hasta ese valor')
    punch = 0.08 if cuts >= 5 else 0.0
    push = 0.05 if med_shot >= 3.5 and cuts < 3 else 0.0
    if punch:
        explain.append('ritmo rápido (≥5 cortes/10 s): zoom alterno suave entre planos')
    if any(m['probable_music'] for m in measures):
        explain.append('alguna referencia lleva música: este estilo NO la copia; solo se usa el audio original')
    recipe = {'speech': speech or inferred_speech, 'ideal': [ideal_lo, ideal_hi], 'max_len': max_len,
              'max_pause': max_pause, 'grade': grade, 'captions': captions, 'push_in': push, 'punch_zoom': punch,
              'loop': False, 'requires': []}
    sid = style_id or slug(name)
    return {
        'schema': SCHEMA, 'id': sid, 'label': name, 'label_ca': name,
        'intent': 'Estilo aprendido de vídeos de referencia propios (ritmo, duración y pausas)',
        'intent_ca': f'Estil après de {len(measures)} vídeos de referència (ritme, durada i pauses); editable',
        'look': grade, 'target_shot_seconds': {'min': lo_s, 'max': hi_s}, 'story_arc': 'auto',
        'automated_state': 'learned_from_references', 'render': recipe,
        'learned': {'references': len(measures), 'explanation': explain, 'notes': notes[:500],
                    'measures': [{k: v for k, v in m.items() if k != 'shot_lengths'} for m in measures],
                    'copies_content': False,
                    'caveat': 'Mide ritmo y estructura, no humor, estética ni identidad. Revisar a mano antes de confiar.'},
    }


def validate(profile: dict) -> dict:
    """Valida un perfil (también el que llega del servidor). Devuelve el perfil o lanza ValueError."""
    if profile.get('schema') != SCHEMA or not re.fullmatch(r'learned_[a-z0-9_]{1,32}', str(profile.get('id', ''))):
        raise ValueError('perfil d’estil no vàlid')
    r = profile.get('render') or {}
    if r.get('speech') not in ('required', 'optional', 'none') or r.get('captions') not in CAPTIONS or r.get('grade') not in GRADES:
        raise ValueError('receta no vàlida')
    for k in ('max_pause', 'push_in', 'punch_zoom', 'max_len'):
        float(r[k])
    lo, hi = r['ideal']
    if not (0 < lo < hi <= r['max_len'] <= 120 and 0 <= r['push_in'] <= 0.2 and 0 <= r['punch_zoom'] <= 0.2
            and 0.1 <= r['max_pause'] <= 1.5):
        raise ValueError('valors fora de rang')
    r['requires'] = []  # un estil aprendido no puede quitar requisitos de aprobación
    return profile


def save(profile: dict, folder: Path | None = None) -> Path:
    validate(profile)
    d = folder or styles_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{profile['id']}.json"
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=1), encoding='utf8')
    return path


def load_learned(folder: Path | None = None) -> dict:
    d = folder or styles_dir()
    out = {}
    for f in sorted(d.glob('learned_*.json')) if d.is_dir() else []:
        try:
            p = validate(json.loads(f.read_text(encoding='utf8')))
            out[p['id']] = p
        except Exception as exc:  # una ficha rota no tumba el estudio
            print(f'AVÍS: ficha d’estil ignorada {f.name}: {exc}', file=sys.stderr)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('videos', nargs='+', help='2–8 vídeos de referencia PROPIOS (o amb permís)')
    p.add_argument('--name', required=True, help='nom de l’estil, p. ex. "Humor de cabina"')
    p.add_argument('--captions', choices=CAPTIONS, default='words')
    p.add_argument('--grade', choices=GRADES, default='natural')
    p.add_argument('--speech', choices=('required', 'optional', 'none'), help='per defecte s’infereix de les referències')
    p.add_argument('--notes', default='')
    p.add_argument('--out', help='carpeta de fitxes (per defecte learned_styles/)')
    a = p.parse_args(argv)
    ms = []
    for v in a.videos:
        path = Path(v)
        if not path.is_file():
            sys.exit(f'No existeix: {v}')
        print(f'Mesurant {path.name}…', flush=True)
        ms.append(measure(path))
    prof = derive(ms, a.name, a.captions, a.grade, a.speech, a.notes)
    out = save(prof, Path(a.out) if a.out else None)
    print(f'\nEstil «{a.name}» desat a {out}  (id: {prof["id"]})')
    for line in prof['learned']['explanation']:
        print(' ·', line)
    print('Pots editar el JSON a mà. Fes servir l’id amb --style o tria’l a l’app (cal registrar-lo: vegeu agent --sync-styles).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
