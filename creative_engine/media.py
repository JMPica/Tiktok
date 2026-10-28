"""Lectura técnica del bruto: ffprobe robusto (rotación, VFR, HDR, audio) y decisiones de formato.

Todo local, sin red. Las decisiones (fps de salida, tonemap) se devuelven con su motivo para que
queden registradas en el EDL y en el informe de QC.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

SUPPORTED_CODECS = ('h264', 'hevc', 'mpeg4', 'vp9', 'av1', 'prores', 'mjpeg')
STANDARD_FPS = (Fraction(24000, 1001), Fraction(24), Fraction(25), Fraction(30000, 1001),
                Fraction(30), Fraction(50), Fraction(60000, 1001), Fraction(60))
HDR_TRANSFERS = ('arib-std-b67', 'smpte2084')


class MediaError(ValueError):
    """El archivo no es un vídeo reproducible o soportado."""


def require_tools():
    missing = [t for t in ('ffmpeg', 'ffprobe') if not shutil.which(t)]
    if missing:
        raise MediaError('Falta ' + ' y '.join(missing) + ' en el PATH')


def _fraction(value: str | None) -> Fraction | None:
    try:
        f = Fraction(str(value))
    except (ValueError, ZeroDivisionError, TypeError):
        return None
    return f if f > 0 else None


def run(cmd: list, timeout: int = 900, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout,
                          cwd=str(cwd) if cwd else None, encoding='utf-8', errors='replace')


def probe(path: Path) -> dict:
    """Metadatos normalizados. width/height son de VISUALIZACIÓN (rotación aplicada)."""
    require_tools()
    r = run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path], timeout=60)
    if r.returncode:
        raise MediaError('ffprobe no puede leer el archivo: ' + r.stderr.strip()[:200])
    try:
        info = json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError('ffprobe devolvió datos ilegibles') from exc
    streams = info.get('streams', [])
    vids = [s for s in streams if s.get('codec_type') == 'video' and s.get('disposition', {}).get('attached_pic') != 1]
    if not vids:
        raise MediaError('El archivo no contiene pista de vídeo')
    v = vids[0]
    if v.get('codec_name') not in SUPPORTED_CODECS:
        raise MediaError(f"Códec de vídeo no soportado: {v.get('codec_name')}")
    try:
        duration = float(info['format'].get('duration') or v.get('duration'))
    except (TypeError, ValueError, KeyError) as exc:
        raise MediaError('Duración desconocida') from exc
    if not 0.5 <= duration <= 4 * 3600:
        raise MediaError(f'Duración fuera de rango: {duration:.2f}s')
    coded_w, coded_h = int(v['width']), int(v['height'])
    rotation = 0
    for sd in v.get('side_data_list') or []:
        if 'rotation' in sd:
            rotation = int(float(sd['rotation']))
    if 'rotate' in (v.get('tags') or {}):
        rotation = int(float(v['tags']['rotate']))
    w, h = (coded_h, coded_w) if abs(rotation) % 180 == 90 else (coded_w, coded_h)
    avg = _fraction(v.get('avg_frame_rate'))
    real = _fraction(v.get('r_frame_rate'))
    fps = avg or real or Fraction(30)
    # VFR: el iPhone graba con fps variable; si avg y r difieren más de un 1 % lo tratamos como VFR.
    vfr = bool(avg and real and abs(float(avg) - float(real)) / float(real) > 0.01)
    audio = [s for s in streams if s.get('codec_type') == 'audio']
    a = audio[0] if audio else {}
    transfer = v.get('color_transfer') or ''
    dovi = any('dovi' in str(sd.get('side_data_type', '')).lower() or 'dolby' in str(sd.get('side_data_type', '')).lower()
               for sd in v.get('side_data_list') or [])
    return {
        'duration': duration, 'width': w, 'height': h, 'coded_width': coded_w, 'coded_height': coded_h,
        'rotation': rotation, 'fps': f'{fps.numerator}/{fps.denominator}', 'fps_float': round(float(fps), 3),
        'r_frame_rate': v.get('r_frame_rate'), 'vfr': vfr,
        'hdr': transfer in HDR_TRANSFERS, 'color_transfer': transfer,
        'color_primaries': v.get('color_primaries') or '', 'color_space': v.get('color_space') or '',
        'dolby_vision': dovi, 'pix_fmt': v.get('pix_fmt') or '', 'codec': v.get('codec_name'),
        'audio': bool(audio), 'audio_codec': a.get('codec_name'), 'audio_channels': int(a.get('channels') or 0),
        'audio_rate': int(a.get('sample_rate') or 0), 'size_bytes': int(info['format'].get('size') or 0),
    }


def output_fps(meta: dict) -> tuple[str, str]:
    """fps de salida y motivo. Nunca sube 25->30: conserva la cadencia del bruto."""
    src = _fraction(meta.get('fps')) or Fraction(30)
    if meta.get('vfr'):
        best = min(STANDARD_FPS, key=lambda f: abs(float(f) - float(src)))
        reason = f'fuente VFR (media {float(src):.3f}); normalizado a la cadencia estándar más cercana'
    else:
        best = min(STANDARD_FPS, key=lambda f: abs(float(f) - float(src)))
        reason = 'fps nativo del bruto'
        if abs(float(best) - float(src)) > 0.05:
            best, reason = src, 'fps nativo no estándar conservado'
    if best > 60:
        # 120/240 fps (cámara lenta del iPhone): se entrega a 60 o 30 conservando la división exacta.
        best = Fraction(60) if float(best) % 60 == 0 else Fraction(30)
        reason = f'fuente de alta velocidad ({float(src):.0f} fps) entregada a {best} fps'
    return f'{best.numerator}/{best.denominator}', reason


def tonemap_filter(meta: dict) -> str:
    """Cadena HDR (HLG/PQ, también Dolby Vision 8.4 compatible HLG) -> SDR BT.709. '' si SDR."""
    if not meta.get('hdr'):
        return ''
    npl = 203 if meta.get('color_transfer') == 'arib-std-b67' else 100
    tin = meta.get('color_transfer')
    return (f'zscale=tin={tin}:pin=bt2020:min=bt2020nc:t=linear:npl={npl},format=gbrpf32le,'
            'zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,')


def ffmpeg_has_filters(*names: str) -> list[str]:
    out = run(['ffmpeg', '-hide_banner', '-filters'], timeout=30).stdout
    have = {line.split()[1] for line in out.splitlines() if len(line.split()) > 2}
    return [n for n in names if n not in have]
