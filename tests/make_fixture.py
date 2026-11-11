"""Genera un vídeo de PRUEBA (fixture) con voz sintética para el harness: NO es material de cliente.

  python tests/make_fixture.py blau salida.mp4      # guion tipo Blau de Mar (ca), con una toma repetida
  python tests/make_fixture.py top salida.mp4       # guion tipo Top House (ca)

Imagen: patrón de test de FFmpeg (1080x1920, 30 fps). Voz: espeak-ng en catalán. Sirve para comprobar que el
pipeline corta, subtitula, renderiza y descarga de verdad; no dice nada sobre calidad editorial con metraje real.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

SCRIPTS = {
    'blau': [
        (2.0, 'Sabeu per què escalfem les tovalloles abans de cada tractament?'),
        (1.2, 'Perquè el client... perquè la'),  # falsa sortida: s'ha de descartar
        (1.0, 'Perquè la persona estigui còmoda i relaxada des del primer minut.'),
        (0.7, 'I per això la cabina sempre fa olor de cafè, és el secret!'),
        (7.0, 'Mai us he explicat l\'error més gran del meu primer dia?'),
        (0.6, 'Vaig obrir la porta de la cabina equivocada amb tota la confiança.'),
        (0.6, 'Al final vam riure tant que ara és la nostra broma de l\'equip!'),
    ],
    'top': [
        (2.0, 'Saps per què alguns pisos porten mesos als portals sense vendre\'s?'),
        (0.8, 'Perquè el preu de sortida no surt d\'una valoració real del barri.'),
        (0.7, 'I perquè les fotos no expliquen com es viu a la casa.'),
        (0.7, 'Per això el primer pas sempre és una bona valoració, és la clau!'),
        (7.0, 'Saps que vius al Maresme quan baixes a la platja abans d\'anar a treballar?'),
        (0.6, 'Quan el mercat del dissabte és el pla del cap de setmana.'),
        (0.6, 'Al final, viure aquí és tenir el mar a cinc minuts, i per això ens agrada tant!'),
    ],
}


def build(kind: str, out: Path):
    tmp = Path(tempfile.mkdtemp(prefix='fixture-'))
    frames, rate = [], 22050
    for k, (gap, text) in enumerate(SCRIPTS[kind]):
        wav = tmp / f'{k}.wav'
        subprocess.run(['espeak-ng', '-v', 'ca', '-s', '150', '-w', str(wav), text], check=True)
        with wave.open(str(wav)) as w:
            rate = w.getframerate()
            frames.append(b'\0\0' * int(gap * rate) + w.readframes(w.getnframes()))
    frames.append(b'\0\0' * int(2.0 * rate))
    voice = tmp / 'voice.wav'
    with wave.open(str(voice), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b''.join(frames))
    dur = sum(len(f) for f in frames) / 2 / rate
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=size=1080x1920:rate=30:duration={dur:.2f}',
                    '-i', str(voice), '-c:v', 'libx264', '-preset', 'veryfast', '-b:v', '3500k', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-shortest', '-movflags', '+faststart', str(out)], check=True)
    print(f'{out} · {dur:.1f}s · {out.stat().st_size / 1e6:.1f} MB · fixture sintético (no es material de cliente)')


if __name__ == '__main__':
    build(sys.argv[1], Path(sys.argv[2]).resolve())
