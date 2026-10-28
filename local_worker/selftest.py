"""Autoprueba del ordenador editor (Windows/macOS/Linux). No usa Cloudflare ni gasta nada.

  python -m local_worker.selftest [--online]

Comprueba FFmpeg (libass, zscale, tonemap, loudnorm), monta un clip sintético con el motor V4,
mide el QC (1080x1920, -16 LUFS, pico <= -1 dBTP) y verifica que hay motor de transcripción.
--online además consulta /api/health del Worker configurado en local_worker/.env.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from creative_engine import qc as QC  # noqa: E402
from creative_engine.media import ffmpeg_has_filters, probe, require_tools  # noqa: E402
from creative_engine.render import render  # noqa: E402


def main() -> int:
    ok = True

    def line(good, text):
        nonlocal ok
        ok &= bool(good)
        print(('OK   ' if good else 'FALLA') + ' ' + text, flush=True)

    require_tools()
    missing = ffmpeg_has_filters('ass', 'zscale', 'tonemap', 'loudnorm', 'ebur128')
    line(not missing, 'FFmpeg con filtros necesarios' + (f' (faltan: {", ".join(missing)} -> instala la build FULL)' if missing else ''))
    with tempfile.TemporaryDirectory(prefix='blau-selftest-') as d:
        d = Path(d)
        src = d / 'in.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=720x1280:rate=30:duration=5',
                        '-f', 'lavfi', '-i', 'sine=frequency=330:beep_factor=4:sample_rate=48000:duration=5',
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(src)], check=True)
        meta = probe(src)
        edl = {'segments': [{'in': 0.5, 'out': 2.0}, {'in': 2.5, 'out': 4.5}], 'grade': 'natural',
               'captions': {'mode': 'phrase', 'events': [{'start': 0.2, 'end': 1.4, 'text': 'Prova Blau de Mar', 'words': [], 'type': 'edited'}]}}
        out = d / 'out.mp4'
        info = render(edl, src, meta, out, d / 'w')
        rep = QC.check(out, edl, meta, info)
        m = rep['measured']
        line(rep['status'] == 'pass', f"render V4 1080x1920 · {m['integrated_lufs']} LUFS · pico {m['true_peak_dbtp']} dBTP")
    engine = os.environ.get('BLAU_ASR_ENGINE', 'faster-whisper')
    mod = 'sherpa_onnx' if engine.startswith('sherpa') else 'faster_whisper'
    line(importlib.util.find_spec(mod) is not None, f'motor de transcripción {engine} instalado')
    line(importlib.util.find_spec('cv2') is not None, 'detector de caras OpenCV instalado (sin identificación)')
    if '--online' in sys.argv:
        import requests
        base = os.environ.get('STUDIO_PUBLIC_URL', '').rstrip('/')
        try:
            r = requests.get(base + '/api/health', timeout=15, headers={'CF-Access-Client-Id': os.environ.get('CF_ACCESS_CLIENT_ID', ''),
                                                                         'CF-Access-Client-Secret': os.environ.get('CF_ACCESS_CLIENT_SECRET', '')})
            line(r.ok and r.json().get('status') == 'ok', f'Worker accesible: {base} ({r.status_code})')
        except Exception as exc:
            line(False, f'Worker no accesible: {exc}')
    print('\nAUTOPRUEBA ' + ('SUPERADA' if ok else 'CON FALLOS') + '. No equivale a prueba desde iPhone ni con tu Cloudflare.')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
