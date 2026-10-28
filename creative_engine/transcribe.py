"""Opt-in offline transcription. Local Whisper model download can happen on first use.
No transcript means NEEDS_REVIEW. Never invent speech or silently crop source.
"""
from __future__ import annotations
import json,os,subprocess,tempfile
from pathlib import Path

def transcribe_local(video:Path,language='ca',model='small'):
    try:from faster_whisper import WhisperModel
    except ImportError:raise RuntimeError('Instala requirements-ai-local.txt: falta faster-whisper')
    model_dir=os.environ.get('BLAU_WHISPER_MODEL_DIR') or None
    if model_dir and Path(model_dir).is_dir():name=model_dir
    else:name=model
    kwargs={'compute_type':os.environ.get('BLAU_WHISPER_COMPUTE','int8'),'device':os.environ.get('BLAU_WHISPER_DEVICE','cpu')}
    engine=WhisperModel(name,**kwargs)
    with tempfile.TemporaryDirectory(prefix='blau_audio_') as d:
        wav=Path(d)/'audio.wav'
        proc=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(video),
                             '-vn','-ac','1','-ar','16000',str(wav)],capture_output=True,text=True,timeout=600)
        if proc.returncode:raise RuntimeError('No se ha podido extraer audio: '+proc.stderr[-300:])
        segments,info=engine.transcribe(str(wav),language=language,beam_size=5,word_timestamps=True,vad_filter=True)
        rows=[{'start':round(s.start,3),'end':round(s.end,3),'text':s.text.strip(),
               'words':[{'start':round(w.start,3),'end':round(w.end,3),'word':w.word} for w in (s.words or [])]}
              for s in segments if s.text.strip()]
    return {'segments':rows,'language':info.language,'engine':'faster-whisper','human_verified':False}
