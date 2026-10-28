"""Transcripción local ca/es, sin servicios externos.

Motores (BLAU_ASR_ENGINE):
- ``faster-whisper`` (por defecto): tiempos por palabra del propio modelo. Descarga el modelo la primera vez
  desde Hugging Face salvo que BLAU_WHISPER_MODEL_DIR apunte a una copia local.
- ``sherpa-onnx``: Whisper exportado a ONNX + VAD Silero (BLAU_SHERPA_MODEL_DIR). Tiempos de frase por VAD y
  tiempos de palabra ESTIMADOS por longitud (se marca ``word_timing='estimated'``).

Sin transcripción no se inventa nada: el director pasa a ``needs_review`` o a selección visual explícita.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np

SR = 16000


def extract_audio(video: Path) -> np.ndarray:
    """Audio mono 16 kHz float32. Array vacío si el vídeo no tiene audio."""
    proc = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-v', 'error', '-i', str(video), '-map', '0:a:0?',
                           '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, timeout=1800)
    if proc.returncode:
        raise RuntimeError('No se ha podido extraer el audio: ' + proc.stderr.decode('utf8', 'replace')[-300:])
    return np.frombuffer(proc.stdout, dtype=np.float32)


def _estimate_words(text: str, start: float, end: float) -> list[dict]:
    tokens = text.split()
    if not tokens:
        return []
    weights = [max(1, len(t.strip('.,;:!?¡¿"«»'))) + 1 for t in tokens]
    span, total, cursor, out = end - start, sum(weights), start, []
    for tok, w in zip(tokens, weights):
        dur = span * w / total
        out.append({'start': round(cursor, 3), 'end': round(cursor + dur, 3), 'word': tok, 'probability': None})
        cursor += dur
    return out


def _faster_whisper(video: Path, language: str | None, model: str) -> dict:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError('Falta faster-whisper: instala requirements-ai-local.txt') from exc
    model_dir = os.environ.get('BLAU_WHISPER_MODEL_DIR')
    name = model_dir if model_dir and Path(model_dir).is_dir() else os.environ.get('BLAU_WHISPER_MODEL', model)
    engine = WhisperModel(name, device=os.environ.get('BLAU_WHISPER_DEVICE', 'cpu'),
                          compute_type=os.environ.get('BLAU_WHISPER_COMPUTE', 'int8'))
    audio = extract_audio(video)
    if audio.size < SR // 2:
        return {'segments': [], 'language': language, 'engine': 'faster-whisper', 'word_timing': 'model'}
    segments, info = engine.transcribe(audio, language=language, beam_size=5, word_timestamps=True,
                                       vad_filter=True, condition_on_previous_text=False)
    rows = []
    for s in segments:
        text = s.text.strip()
        if not text:
            continue
        rows.append({'start': round(s.start, 3), 'end': round(s.end, 3), 'text': text,
                     'avg_logprob': round(s.avg_logprob, 3), 'no_speech_prob': round(s.no_speech_prob, 3),
                     'words': [{'start': round(w.start, 3), 'end': round(w.end, 3), 'word': w.word.strip(),
                                'probability': round(w.probability, 3)} for w in (s.words or []) if w.word.strip()]})
    return {'segments': rows, 'language': info.language, 'language_probability': round(info.language_probability, 3),
            'engine': 'faster-whisper:' + str(name), 'word_timing': 'model'}


def _sherpa(video: Path, language: str | None) -> dict:
    try:
        import sherpa_onnx
    except ImportError as exc:
        raise RuntimeError('Falta sherpa-onnx (pip install sherpa-onnx)') from exc
    d = Path(os.environ.get('BLAU_SHERPA_MODEL_DIR', ''))
    enc = sorted(d.glob('*encoder*.onnx'))
    dec = sorted(d.glob('*decoder*.onnx'))
    tok = sorted(d.glob('*tokens.txt'))
    vad_model = Path(os.environ.get('BLAU_SHERPA_VAD', str(d / 'silero_vad.onnx')))
    if not (enc and dec and tok and vad_model.is_file()):
        raise RuntimeError('BLAU_SHERPA_MODEL_DIR debe contener encoder/decoder/tokens de Whisper y silero_vad.onnx')
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(encoder=str(enc[0]), decoder=str(dec[0]), tokens=str(tok[0]),
                                                     language=language or '', task='transcribe',
                                                     num_threads=max(1, (os.cpu_count() or 2) - 1))
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = str(vad_model)
    cfg.silero_vad.min_silence_duration = 0.35
    cfg.silero_vad.min_speech_duration = 0.25
    cfg.silero_vad.max_speech_duration = 20
    cfg.sample_rate = SR
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=600)
    audio = extract_audio(video)
    rows = []
    window = cfg.silero_vad.window_size

    def drain():
        while not vad.empty():
            seg = vad.front
            start = seg.start / SR
            samples = np.asarray(seg.samples, dtype=np.float32)
            end = start + len(samples) / SR
            stream = rec.create_stream()
            stream.accept_waveform(SR, samples)
            rec.decode_stream(stream)
            text = stream.result.text.strip()
            if text:
                rows.append({'start': round(start, 3), 'end': round(end, 3), 'text': text,
                             'words': _estimate_words(text, start, end)})
            vad.pop()

    for i in range(0, len(audio), window):
        vad.accept_waveform(audio[i:i + window])
        drain()
    vad.flush()
    drain()
    return {'segments': rows, 'language': language, 'engine': 'sherpa-onnx:whisper', 'word_timing': 'estimated'}


def transcribe_local(video: Path, language: str | None = 'ca', model: str = 'small') -> dict:
    """Transcribe en local. ``language`` 'ca', 'es' o None/'auto' para detección."""
    lang = None if language in (None, '', 'auto') else language
    engine = os.environ.get('BLAU_ASR_ENGINE', 'faster-whisper').lower()
    result = _sherpa(Path(video), lang) if engine.startswith('sherpa') else _faster_whisper(Path(video), lang, model)
    result['human_verified'] = False
    return result
