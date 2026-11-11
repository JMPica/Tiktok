"""Guion de montaje por momentos (método de la guía «Deja de editar tus reels»), derivado del EDL.

Cada fila: segundo del montaje, de qué segundos del original sale, qué se dice, qué texto se ve y qué efecto lleva.
No añade información: solo hace legible el EDL para revisarlo antes de aprobar.
"""
from __future__ import annotations


def build(edl: dict) -> list[dict]:
    rows, offset = [], 0.0
    caps = (edl.get('captions') or {})
    events = caps.get('events') or []
    shown = caps.get('mode', 'none') != 'none'
    overlays = edl.get('overlays') or []
    for k, s in enumerate(edl.get('segments') or []):
        a, b = offset, offset + (float(s['out']) - float(s['in']))
        said = ' '.join(str(e['text']).replace('\n', ' ') for e in events if a <= (e['start'] + e['end']) / 2 < b)
        texts = [str(o['text']) for o in overlays if o['start'] < b and o['end'] > a]
        effects = []
        if k:
            effects.append('tall net')
        if float(s.get('zoom') or 1) > 1:
            effects.append(f"zoom x{float(s['zoom']):.2f}")
        if float(s.get('push_in') or 0) > 0:
            effects.append('apropament lent')
        if s.get('framing') == 'face':
            effects.append('reenquadrat a la cara')
        rows.append({'n': k + 1, 'start': round(a, 2), 'end': round(b, 2),
                     'source_in': round(float(s['in']), 2), 'source_out': round(float(s['out']), 2),
                     'says': said, 'subtitles': shown and bool(said), 'on_screen': texts,
                     'effect': ', '.join(effects) or 'cap', 'tool': 'FFmpeg'})
        offset = b
    return rows


def as_markdown(edl: dict) -> str:
    brand = (edl.get('brand') or {}).get('name', '')
    out = [f"# Guió per moments · {edl.get('title') or edl.get('id')} · v{edl.get('version', 1)}", '',
           f"Marca: {brand} · Estil: {edl.get('style_label') or edl.get('style')} · Durada: {edl.get('duration')} s", '',
           '| # | Muntatge | Original | Es diu | Text en pantalla | Efecte |', '|---|---|---|---|---|---|']
    for r in build(edl):
        out.append(f"| {r['n']} | {r['start']:.1f}–{r['end']:.1f} s | {r['source_in']:.1f}–{r['source_out']:.1f} s | "
                   f"{r['says'] or '—'} | {'; '.join(r['on_screen']) or '—'} | {r['effect']} |")
    return '\n'.join(out) + '\n'
