"""Uso local sin Cloudflare (desarrollo o pruebas de calidad):

  python -m creative_engine.cli VIDEO.mov [--style auto] [--language ca] [--transcript t.json] [--render] [--out carpeta]

Genera ``edit_plan.json`` con 0..N propuestas y, con --render, los MP4 + portada + informe QC.
El original no se modifica. Nada se publica.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from creative_engine import pipeline as P
from creative_engine.director import build_plan, load_styles


def main():
    p = argparse.ArgumentParser()
    p.add_argument('video')
    p.add_argument('--style', default='auto', choices=sorted(load_styles()))
    p.add_argument('--language', default='ca', choices=['ca', 'es'])
    p.add_argument('--transcript', help='JSON con segmentos ya transcritos (opcional)')
    p.add_argument('--render', action='store_true')
    p.add_argument('--out', help='carpeta de salida (por defecto junto al vídeo)')
    args = p.parse_args()
    source = Path(args.video).resolve()
    out = Path(args.out).resolve() if args.out else source.parent / (source.stem + '_v4')
    out.mkdir(parents=True, exist_ok=True)
    tr = None
    if args.transcript:
        data = json.loads(Path(args.transcript).read_text(encoding='utf8'))
        tr = data if isinstance(data, dict) else {'segments': data}
    u = P.understand(source, args.language, lambda s, pct, m: print(f'[{pct:3d}%] {m}', flush=True), transcript=tr)
    P.dump(P.summary(u), out / 'analysis_summary.json')
    if not args.render:
        plan = build_plan(u['transcript'].get('segments', []), u['meta']['duration'], args.style, args.language,
                          analysis=u['analysis'], meta=u['meta'])
        P.dump(plan, out / 'edit_plan.json')
        print(f'PLAN: {out / "edit_plan.json"} -> {plan["status"]} ({len(plan["candidates"])} propostes)')
        return 0 if plan['status'] == 'drafts' else 2
    res = P.produce(source, out, args.style, args.language, understood=u,
                    progress=lambda s, pct, m: print(f'[{pct:3d}%] {m}', flush=True))
    P.dump(res['plan'], out / 'edit_plan.json')
    if res['plan']['status'] != 'drafts':
        print('CAP PROPOSTA:', res['plan'].get('reason'))
        return 2
    for r in res['results']:
        if 'error' in r:
            print('ERROR', r['edl']['id'], r['error'], file=sys.stderr)
            continue
        P.dump({'qc': r['qc'], 'render': r['render'], 'sha256': r['sha256'], 'edl': r['edl']}, r['path'].with_suffix('.qc.json'))
        print(f"{r['qc']['status'].upper():4} {r['path']}  sha256={r['sha256'][:16]}…  {r['edl']['explanation']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
