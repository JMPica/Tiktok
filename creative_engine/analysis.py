"""Análisis local del bruto: lo que realmente ocurre en imagen y sonido, sin nube.

Una pasada de decodificación a baja resolución (``ANALYSIS_FPS``) mide por instante:
movimiento, brillo, nitidez, cambios de plano y caras (detección, NUNCA identificación).
El audio mide energía por 100 ms, silencios, ráfagas (risas/reacciones probables) y ritmo regular
(música probable -> riesgo de derechos).

Limitación honesta: son señales, no comprensión semántica. La comprensión de acciones/emoción
requiere un modelo de visión local opcional (``vision_llm``); si no está, se indica en ``semantic_vision``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from creative_engine.media import probe, tonemap_filter
from creative_engine.transcribe import SR, extract_audio

ANALYSIS_FPS = 4.0
ANALYSIS_W = 320
AUDIO_HOP = 0.1


def _frames(video: Path, meta: dict, fps: float = ANALYSIS_FPS, width: int = ANALYSIS_W):
    h = int(round(width * meta['height'] / meta['width'] / 2) * 2)
    vf = f'{tonemap_filter(meta)}fps={fps},scale={width}:{h}:flags=area,format=gray'
    proc = subprocess.Popen(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-i', str(video), '-an', '-vf', vf,
                             '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    size = width * h
    i = 0
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield i / fps, np.frombuffer(buf, dtype=np.uint8).reshape(h, width)
            i += 1
    finally:
        proc.stdout.close()
        proc.wait(timeout=60)


def _face_detector():
    try:
        import cv2
    except ImportError:
        return None
    path = Path(cv2.data.haarcascades) / 'haarcascade_frontalface_default.xml'
    det = cv2.CascadeClassifier(str(path))
    return None if det.empty() else det


def _runs(mask, t, min_len, step):
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        elif not m and start is not None:
            if t[i - 1] - t[start] + step >= min_len:
                out.append((round(float(t[start]), 2), round(float(t[i - 1] + step), 2)))
            start = None
    return out


def visual_analysis(video: Path, meta: dict) -> dict:
    det = _face_detector()
    t, motion, bright, sharp, cut_score, faces = [], [], [], [], [], []
    prev, prev_hist = None, None
    for ts, f in _frames(video, meta):
        x = f.astype(np.float32)
        t.append(ts)
        bright.append(float(x.mean()))
        lap = x[1:-1, 1:-1] * 4 - x[:-2, 1:-1] - x[2:, 1:-1] - x[1:-1, :-2] - x[1:-1, 2:]
        sharp.append(float(lap.var()))
        motion.append(float(np.abs(x - prev).mean()) if prev is not None else 0.0)
        hist = np.histogram(f, bins=32, range=(0, 256))[0].astype(np.float32)
        hist /= hist.sum() + 1e-9
        cut_score.append(float(0.5 * np.abs(hist - prev_hist).sum()) if prev_hist is not None else 0.0)
        prev, prev_hist = x, hist
        if det is not None and len(t) % 2 == 1:  # caras a 2 fps
            found = det.detectMultiScale(f, scaleFactor=1.15, minNeighbors=5, minSize=(24, 24))
            fh, fw = f.shape
            faces.append({'t': round(ts, 2), 'boxes': [[round(a / fw, 3), round(b / fh, 3), round(c / fw, 3), round(d / fh, 3)]
                                                       for a, b, c, d in (found if len(found) else [])]})
    if not t:
        raise ValueError('No se pudieron decodificar fotogramas del vídeo')
    t = np.array(t)
    motion, bright, sharp, cut_score = map(np.array, (motion, bright, sharp, cut_score))
    step = 1 / ANALYSIS_FPS
    # Cortes de plano: salto de histograma alto y aislado respecto a su entorno.
    shots, start = [], 0.0
    thr = max(0.35, float(np.percentile(cut_score, 98)) if len(cut_score) > 20 else 0.35)
    for i in np.where(cut_score >= thr)[0]:
        if t[i] - start >= 0.5:
            shots.append({'start': round(start, 2), 'end': round(float(t[i]), 2)})
            start = float(t[i])
    shots.append({'start': round(start, 2), 'end': round(meta['duration'], 2)})
    ms = np.convolve(motion, np.ones(3) / 3, mode='same') if len(motion) > 3 else motion
    hi = float(np.percentile(ms, 90)) if len(ms) else 0
    lo = float(np.percentile(ms, 40)) if len(ms) else 0
    bursts = [{'start': a, 'end': b} for a, b in _runs(ms > lo + 0.5 * (hi - lo) + 0.5, t, 0.4, step)] if hi > 1 else []
    blur_thr = max(15.0, float(np.median(sharp)) * 0.25)
    blurry = _runs(sharp < blur_thr, t, 0.75, step)
    dark = _runs(bright < 18, t, 0.5, step)
    face_ratio = (sum(1 for f in faces if f['boxes']) / len(faces)) if faces else None
    return {
        'fps': ANALYSIS_FPS, 't': [round(float(x), 2) for x in t],
        'motion': [round(float(x), 2) for x in ms], 'brightness': [round(float(x), 1) for x in bright],
        'sharpness': [round(float(x), 1) for x in sharp],
        'shots': shots, 'motion_bursts': bursts,
        'blurry_ranges': [{'start': a, 'end': b} for a, b in blurry],
        'dark_ranges': [{'start': a, 'end': b} for a, b in dark],
        'faces': faces, 'face_detector': 'opencv-haar' if det is not None else None,
        'face_ratio': None if face_ratio is None else round(face_ratio, 3),
    }


def audio_analysis(video: Path, meta: dict) -> dict:
    if not meta.get('audio'):
        return {'has_audio': False}
    x = extract_audio(video)
    hop = int(SR * AUDIO_HOP)
    if len(x) < hop * 5:
        return {'has_audio': True, 'too_short': True, 'rms_db': []}
    fr = x[:len(x) // hop * hop].reshape(-1, hop)
    rms = 20 * np.log10(np.sqrt((fr.astype(np.float64) ** 2).mean(1)) + 1e-9)
    ta = np.arange(len(rms)) * AUDIO_HOP
    floor = float(np.percentile(rms, 10))
    silence_thr = max(-55.0, min(floor + 8, -32.0))
    silences = _runs(rms < silence_thr, ta, 0.35, AUDIO_HOP)
    # Ráfagas: subidas bruscas de energía respecto a la media móvil de 2 s (risas, reacciones, golpes).
    k = int(2 / AUDIO_HOP)
    base = np.convolve(rms, np.ones(k) / k, mode='same')
    bursts = _runs(rms > base + 9, ta, 0.2, AUDIO_HOP)
    music = {'probable_music': False, 'regularity': 0.0, 'bpm': 0}
    win, h = 1024, 512
    if len(x) > SR * 4:
        seg = x[: SR * 120]
        frames = np.lib.stride_tricks.sliding_window_view(seg, win)[::h] * np.hanning(win)
        spec = np.abs(np.fft.rfft(frames, axis=1))
        flux = np.maximum(0, np.diff(np.log1p(spec), axis=0)).sum(1)
        flux = (flux - flux.mean()) / (flux.std() + 1e-9)
        ac = np.correlate(flux, flux, 'full')[len(flux) - 1:]
        ac /= ac[0] + 1e-9
        lags = np.arange(len(ac)) * h / SR
        sel = (lags > 0.3) & (lags < 1.5)
        if sel.any():
            score = float(ac[sel].max())
            music = {'probable_music': score > 0.3, 'regularity': round(score, 3),
                     'bpm': int(round(60 / lags[sel][np.argmax(ac[sel])]))}
    return {'has_audio': True, 'hop': AUDIO_HOP, 'rms_db': [round(float(v), 1) for v in rms],
            'median_db': round(float(np.median(rms)), 1), 'silence_threshold_db': round(silence_thr, 1),
            'silences': [{'start': a, 'end': b} for a, b in silences],
            'energy_bursts': [{'start': a, 'end': b} for a, b in bursts], **music}


def analyze(video: Path, meta: dict | None = None) -> dict:
    meta = meta or probe(video)
    return {'schema': 'blau.analysis/4', 'meta': meta, 'visual': visual_analysis(video, meta),
            'audio': audio_analysis(video, meta), 'semantic_vision': None}


# ---------------------------------------------------------------- consultas usadas por el director
def _window(series_t, values, a, b):
    t = np.asarray(series_t)
    v = np.asarray(values)
    if not len(t):
        return v[:0]
    m = (t >= a) & (t < b)
    return v[m]


def face_stats(analysis: dict, a: float, b: float) -> dict:
    faces = [f for f in analysis['visual']['faces'] if a <= f['t'] < b]
    with_face = [f for f in faces if f['boxes']]
    if not faces:
        return {'ratio': None, 'cx': 0.5, 'cy': 0.4}
    centers = []
    for f in with_face:
        x, y, w, h = max(f['boxes'], key=lambda bb: bb[2] * bb[3])
        centers.append((x + w / 2, y + h / 2))
    if not centers:
        return {'ratio': 0.0, 'cx': 0.5, 'cy': 0.4}
    c = np.median(np.array(centers), axis=0)
    return {'ratio': round(len(with_face) / len(faces), 3), 'cx': round(float(c[0]), 3), 'cy': round(float(c[1]), 3)}


def visual_quality(analysis: dict, a: float, b: float) -> dict:
    v = analysis['visual']
    sharp = _window(v['t'], v['sharpness'], a, b)
    bright = _window(v['t'], v['brightness'], a, b)
    motion = _window(v['t'], v['motion'], a, b)
    all_sharp = np.asarray(v['sharpness']) if v['sharpness'] else np.array([1.0])
    rel = float(np.median(sharp) / (np.median(all_sharp) + 1e-9)) if len(sharp) else 0.0
    return {'sharp_rel': round(rel, 3), 'brightness': round(float(np.median(bright)), 1) if len(bright) else 0.0,
            'motion': round(float(np.median(motion)), 2) if len(motion) else 0.0,
            'dark': bool(len(bright) and np.median(bright) < 18)}


def audio_energy(analysis: dict, a: float, b: float) -> float | None:
    au = analysis.get('audio') or {}
    if not au.get('rms_db'):
        return None
    i, j = int(a / au['hop']), max(int(a / au['hop']) + 1, int(b / au['hop']))
    seg = au['rms_db'][i:j]
    return round(float(np.mean(seg)), 1) if seg else None


def has_burst(analysis: dict, a: float, b: float) -> bool:
    return any(x['start'] < b and x['end'] > a for x in (analysis.get('audio') or {}).get('energy_bursts', []))
