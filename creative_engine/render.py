"""Render determinista EDL v4 -> MP4 1080x1920 H.264/AAC en una sola codificación.

- Cada segmento se lee con seek preciso (-ss/-t por entrada) y se sincroniza a número exacto de fotogramas.
- Reencuadre 9:16 centrado en el sujeto (caras detectadas) con zoom limitado por resolución.
- HDR (HLG/PQ/Dolby Vision 8.4) -> SDR BT.709 con zscale+tonemap.
- Audio original, microfundidos de 15 ms en cada corte (sin clics) y loudnorm en dos pasadas a -16 LUFS / -1.5 dBTP.
- Subtítulos/rótulos ASS con fuentes OFL incluidas.
Sin efectos generativos, sin música añadida.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from fractions import Fraction
from pathlib import Path

from creative_engine.captions import build_ass
from creative_engine.media import MediaError, output_fps, run, tonemap_filter

OUT_W, OUT_H = 1080, 1920
FONTS = Path(__file__).resolve().parents[1] / 'assets' / 'fonts'
GRADES = {
    'natural': 'eq=contrast=1.03:saturation=1.05',
    'punchy': "eq=contrast=1.07:saturation=1.12:gamma=0.98,unsharp=5:5:0.35:5:5:0",
    'premium': 'eq=contrast=1.02:saturation=0.95:gamma=1.01,colorbalance=rs=0.015:bs=-0.015:rh=0.01:bh=-0.01',
    'none': '',
}
MAX_OUTPUT_SECONDS = 180


def max_zoom(meta: dict) -> float:
    short = min(meta['width'], meta['height'])
    return 1.5 if short >= 2160 else 1.1 if short >= 1080 else 1.0


def crop_geometry(meta: dict, zoom: float = 1.0, fx: float = 0.5, fy: float = 0.5) -> tuple[int, int, int, int]:
    """Recorte 9:16 en píxeles de visualización. fx/fy = centro deseado (0..1)."""
    w, h = meta['width'], meta['height']
    if w / h > 9 / 16:
        bw, bh = h * 9 / 16, h
    else:
        bw, bh = w, w * 16 / 9
    zoom = max(1.0, min(float(zoom), max_zoom(meta)))
    cw, ch = int(bw / zoom) // 2 * 2, int(bh / zoom) // 2 * 2
    x0 = int(round(fx * w - cw / 2))
    y0 = int(round(fy * h - ch / 2))
    x0 = max(0, min(x0, w - cw)) // 2 * 2
    y0 = max(0, min(y0, h - ch)) // 2 * 2
    return cw, ch, x0, y0


def validate_edl(edl: dict, meta: dict) -> list[dict]:
    segs = edl.get('segments') or []
    if not segs:
        raise ValueError('EDL sin segmentos: no hay nada que montar')
    if len(segs) > 120:
        raise ValueError('Demasiados segmentos')
    total = 0.0
    for s in segs:
        a, b = float(s['in']), float(s['out'])
        if not (0 <= a < b <= meta['duration'] + 0.05) or b - a < 0.12:
            raise ValueError(f'Segmento fuera del bruto: {a:.2f}-{b:.2f} (duración {meta["duration"]:.2f})')
        total += b - a
    if total > MAX_OUTPUT_SECONDS:
        raise ValueError(f'Montaje demasiado largo ({total:.1f}s)')
    return segs


def _segment_filters(i: int, seg: dict, meta: dict, fps: Fraction, grade: str, n_frames: int) -> tuple[str, str]:
    d = n_frames / fps
    cw, ch, x0, y0 = crop_geometry(meta, seg.get('zoom', 1.0), seg.get('x', 0.5), seg.get('y', 0.5))
    v = [f'crop={cw}:{ch}:{x0}:{y0}', f'scale={OUT_W}:{OUT_H}:flags=lanczos']
    tm = tonemap_filter(meta)
    if tm:
        # Tonemap tras reducir a 1080x1920: mismo resultado visual, ~4x menos trabajo con brutos 4K.
        v.append(tm.rstrip(','))
    push = float(seg.get('push_in') or 0)
    if push > 0:
        expr = f'(1+{push:.4f}*t/{float(d):.4f})'
        v.append(f"scale=w='trunc({OUT_W}*{expr}/2)*2':h='trunc({OUT_H}*{expr}/2)*2':eval=frame:flags=bicubic")
        v.append(f'crop={OUT_W}:{OUT_H}')
    if GRADES.get(grade):
        v.append(GRADES[grade])
    v += ['setpts=PTS-STARTPTS', f'fps={fps}', 'tpad=stop_mode=clone:stop=-1', f'trim=end_frame={n_frames}', 'setsar=1', 'format=yuv420p']
    fade = min(0.015, float(d) / 4)
    if meta.get('audio'):
        a = f'[{i}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS,'
    else:
        a = 'anullsrc=r=48000:cl=stereo,aformat=sample_fmts=fltp,'
    a += (f'apad,atrim=end={float(d):.6f},afade=t=in:d={fade:.3f},'
          f'afade=t=out:st={max(0.0, float(d) - fade):.6f}:d={fade:.3f}')
    return f'[{i}:v:0]' + ','.join(v) + f'[v{i}]', a + f'[a{i}]'


def _build(edl: dict, source: Path, meta: dict, fps: Fraction, audio_only: bool = False):
    segs = validate_edl(edl, meta)
    inputs, graph, frames = [], [], []
    for i, s in enumerate(segs):
        a, b = float(s['in']), float(s['out'])
        n = max(1, int(round((b - a) * fps)))
        frames.append(n)
        inputs += ['-ss', f'{a:.4f}', '-t', f'{n / fps + 0.25:.4f}', '-i', str(source)]
        vf, af = _segment_filters(i, s, meta, fps, edl.get('grade', 'natural'), n)
        if not audio_only:
            graph.append(vf)
        graph.append(af)
    k = len(segs)
    if audio_only:
        graph.append(''.join(f'[a{i}]' for i in range(k)) + f'concat=n={k}:v=0:a=1[ac]')
    else:
        graph.append(''.join(f'[v{i}][a{i}]' for i in range(k)) + f'concat=n={k}:v=1:a=1[vc][ac]')
    return inputs, graph, sum(frames) / fps


def _measure_loudness(edl, source, meta, fps, cwd) -> dict | None:
    if not meta.get('audio'):
        return None
    inputs, graph, _ = _build(edl, source, meta, fps, audio_only=True)
    graph.append('[ac]loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json[ao]')
    r = run(['ffmpeg', '-hide_banner', '-nostdin', '-nostats', *inputs, '-filter_complex', ';'.join(graph),
             '-map', '[ao]', '-f', 'null', '-'], cwd=cwd, timeout=1800)
    if r.returncode:
        raise MediaError('Medición de sonoridad fallida: ' + r.stderr[-400:])
    m = re.search(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr, re.S)
    if not m:
        return None
    data = json.loads(m.group(0))
    if data.get('input_i') in ('-inf', None) or float(data['input_i']) < -60:
        return None
    return data


def render(edl: dict, source: Path, meta: dict, target: Path, workdir: Path) -> dict:
    """Renderiza el EDL. Devuelve info técnica (fps, duración esperada, sonoridad medida en entrada)."""
    workdir.mkdir(parents=True, exist_ok=True)
    fps_str, fps_reason = output_fps(meta)
    if (edl.get('output') or {}).get('fps'):
        fps_str, fps_reason = edl['output']['fps'], (edl['output'].get('fps_reason') or fps_reason)
    fps = Fraction(fps_str)
    ass = build_ass(edl.get('captions') or {'mode': 'none', 'events': []}, edl.get('overlays'),
                    (edl.get('brand') or {}).get('accent', '#7FE3D6'))
    (workdir / 'subs.ass').write_text(ass, encoding='utf-8')
    fonts = workdir / 'fonts'
    if FONTS.is_dir() and not fonts.exists():
        shutil.copytree(FONTS, fonts)
    loud = _measure_loudness(edl, source, meta, fps, workdir)
    inputs, graph, expected = _build(edl, source, meta, fps)
    # Rutas relativas (cwd=workdir): evita el escapado de rutas de Windows dentro del filtro.
    graph.append('[vc]ass=subs.ass:fontsdir=fonts[vo]')
    if loud:
        graph.append(f"[ac]loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={loud['input_i']}:measured_TP={loud['input_tp']}:"
                     f"measured_LRA={loud['input_lra']}:measured_thresh={loud['input_thresh']}:offset={loud['target_offset']}:"
                     'linear=true,aresample=48000[ao]')
    else:
        graph.append('[ac]anull[ao]')
    tmp = workdir / ('render-' + target.name)
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', *inputs, '-filter_complex', ';'.join(graph),
           '-map', '[vo]', '-map', '[ao]', '-r', str(fps),
           '-c:v', 'libx264', '-preset', os.environ.get('BLAU_X264_PRESET', 'medium'), '-crf', '18',
           '-profile:v', 'high', '-pix_fmt', 'yuv420p',
           '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv',
           '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
           '-movflags', '+faststart', '-max_muxing_queue_size', '4096', str(tmp)]
    r = run(cmd, cwd=workdir, timeout=7200)
    if r.returncode:
        raise MediaError('FFmpeg no pudo renderizar: ' + r.stderr[-600:])
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp.replace(target)
    return {'fps': fps_str, 'fps_reason': fps_reason, 'expected_duration': round(float(expected), 3),
            'loudness_input': loud, 'tonemapped': bool(meta.get('hdr')),
            'filters': 'single_pass_concat', 'encoder': 'libx264 crf18'}


def poster(video: Path, target: Path, at: float = 0.4) -> Path:
    r = run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-y', '-ss', f'{at:.3f}', '-i', str(video),
             '-frames:v', '1', '-q:v', '3', str(target)], timeout=120)
    if r.returncode or not target.is_file():
        raise MediaError('No se pudo extraer la portada: ' + r.stderr[-200:])
    return target
