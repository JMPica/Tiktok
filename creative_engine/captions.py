"""Subtítulos ca/es desde la transcripción: palabras mapeadas al tiempo de salida, troceado legible y ASS.

Los textos salen del audio (``auto_unverified``) y siempre se pueden corregir antes de aprobar.
Zonas seguras TikTok 1080x1920: nada por encima de y=220 ni por debajo de y=1290, margen derecho 150 px.
"""
from __future__ import annotations

FONT = 'Poppins ExtraBold'
FONT_SEMI = 'Poppins SemiBold'
SAFE_TOP, SAFE_BOTTOM, SAFE_LEFT, SAFE_RIGHT = 220, 1290, 90, 930
MAX_LINE_CHARS = 17
CHAR_WIDTH = 0.62  # ancho medio de un carácter de Poppins ExtraBold respecto al cuerpo
MAX_EVENT_SECONDS = 3.2
SIZES = {'m': 72, 'l': 84}
POSITIONS = {'lower': (540, 1240, 2), 'upper': (540, 360, 8), 'middle': (540, 980, 5)}


def map_words(cuts: list[dict], words: list[dict]) -> list[dict]:
    """Palabras del bruto -> tiempo del montaje. Solo entran las que caen dentro de un corte."""
    out, offset = [], 0.0
    for cut in cuts:
        a, b = float(cut['in']), float(cut['out'])
        for w in words:
            mid = (w['start'] + w['end']) / 2
            if a <= mid < b:
                s = offset + max(0.0, w['start'] - a)
                e = offset + min(b - a, w['end'] - a)
                if e > s:
                    out.append({'start': round(s, 3), 'end': round(e, 3), 'word': w['word'].strip(),
                                'source_start': w['start']})
        offset += b - a
    return out


def _wrap(text: str, limit: int = MAX_LINE_CHARS) -> str:
    if len(text) <= limit:
        return text
    words = text.split()
    best, best_cost = text, 10 ** 9
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        cost = max(len(a), len(b))
        if cost < best_cost:
            best, best_cost = a + '\n' + b, cost
    return best


def line_limit(size: str = 'm') -> int:
    """Caracteres por línea que caben en la zona segura con ese tamaño de letra."""
    return int((SAFE_RIGHT - SAFE_LEFT) / (SIZES.get(size, SIZES['m']) * CHAR_WIDTH))


def chunk(words: list[dict], size: str = 'm', gap: float = 0.35) -> list[dict]:
    """Agrupa palabras en eventos de <=2 líneas, cortando en pausas y puntuación."""
    limit = line_limit(size)
    max_chars = limit * 2
    events, cur = [], []

    def flush():
        if cur:
            text = ' '.join(w['word'] for w in cur)
            events.append({'start': cur[0]['start'], 'end': cur[-1]['end'], 'text': _wrap(text, limit),
                           'words': [dict(w) for w in cur], 'type': 'transcript_auto_unverified'})
            cur.clear()

    for w in words:
        if cur:
            candidate = ' '.join(x['word'] for x in cur) + ' ' + w['word']
            too_wide = max(len(line) for line in _wrap(candidate, limit).split('\n')) > limit
            if (w['start'] - cur[-1]['end'] > gap or len(candidate) > max_chars or too_wide
                    or w['end'] - cur[0]['start'] > MAX_EVENT_SECONDS or cur[-1]['word'][-1:] in '.?!'):
                flush()
        cur.append(w)
    flush()
    # Duración mínima legible: alarga hasta el siguiente evento sin solaparse.
    for i, e in enumerate(events):
        limit = events[i + 1]['start'] if i + 1 < len(events) else e['end'] + 0.6
        e['end'] = round(min(max(e['end'], e['start'] + 0.7), limit), 3)
    return events


def _ass_time(sec: float) -> str:
    cs = int(round(max(0.0, sec) * 100))
    return f'{cs // 360000}:{(cs // 6000) % 60:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}'


def _clean(text: str) -> str:
    return (str(text).replace('\\', '').replace('{', '(').replace('}', ')').replace('\r', '')
            .replace('\n', r'\N'))


def _bgr(hexrgb: str) -> str:
    h = hexrgb.lstrip('#')
    return f'&H00{h[4:6]}{h[2:4]}{h[0:2]}'.upper()


def build_ass(captions: dict, overlays: list[dict] | None = None, accent: str = '#7FE3D6') -> str:
    """captions = {'mode': words|phrase|none, 'size': m|l, 'position': lower|upper|middle, 'events': [...]}"""
    mode = captions.get('mode', 'phrase')
    size = SIZES.get(captions.get('size', 'm'), 72)
    x, y, an = POSITIONS.get(captions.get('position', 'lower'), POSITIONS['lower'])
    acc = _bgr(accent)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: cap,{FONT},{size},&H00FFFFFF,&H00FFFFFF,&H00151515,&H96000000,0,0,0,0,100,100,0,0,1,6,2,{an},{SAFE_LEFT},{1080 - SAFE_RIGHT},0,1
Style: hook,{FONT},84,&H00FFFFFF,&H00FFFFFF,&H00151515,&H96000000,0,0,0,0,100,100,0,0,1,7,3,8,{SAFE_LEFT},{1080 - SAFE_RIGHT},0,1
Style: bubble,{FONT_SEMI},50,&H00202020,&H00202020,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,3,16,0,8,{SAFE_LEFT},{1080 - SAFE_RIGHT},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    if mode != 'none':
        for ev in captions.get('events', []):
            text = ev['text']
            words = ev.get('words') or []
            edited = ev.get('type') == 'edited' or ' '.join(w['word'] for w in words).replace('\n', ' ') != text.replace('\n', ' ')
            if mode == 'words' and words and not edited:
                # Un evento por palabra: frase completa con la palabra hablada resaltada.
                for k, w in enumerate(words):
                    end = words[k + 1]['start'] if k + 1 < len(words) else ev['end']
                    parts = []
                    for j, ww in enumerate(words):
                        token = _clean(ww['word'])
                        parts.append(f'{{\\c{acc}}}{token}{{\\c&H00FFFFFF&}}' if j == k else token)
                    body = _wrap(' '.join(ww['word'] for ww in words), line_limit(captions.get('size', 'm')))
                    # Reconstruye saltos de línea del texto envuelto sobre las piezas coloreadas.
                    first_line = len(body.split('\n')[0].split()) if '\n' in body else None
                    if first_line:
                        parts.insert(first_line, r'\N')
                    joined = ' '.join(parts).replace(r' \N ', r'\N')
                    lines.append(f'Dialogue: 0,{_ass_time(max(w["start"], ev["start"]))},{_ass_time(max(end, w["start"] + 0.05))},'
                                 f'cap,,0,0,0,,{{\\pos({x},{y})}}{joined}')
            else:
                lines.append(f'Dialogue: 0,{_ass_time(ev["start"])},{_ass_time(ev["end"])},cap,,0,0,0,,'
                             f'{{\\pos({x},{y})}}{_clean(_wrap(text.replace(chr(10), " "), line_limit(captions.get('size', 'm'))))}')
    for ov in overlays or []:
        style = 'bubble' if ov.get('kind') == 'comment' else 'hook'
        oy = 300 if captions.get('position', 'lower') != 'upper' else 1100
        lines.append(f'Dialogue: 1,{_ass_time(ov["start"])},{_ass_time(ov["end"])},{style},,0,0,0,,'
                     f'{{\\an8\\pos(540,{oy})}}{_clean(_wrap(ov["text"], 22))}')
    return head + '\n'.join(lines) + '\n'


def caption_report(captions: dict, overlays: list[dict] | None = None) -> dict:
    size = SIZES.get(captions.get('size', 'm'), 72)
    issues = []
    for ev in captions.get('events', []) if captions.get('mode') != 'none' else []:
        for line in str(ev['text']).split('\n'):
            width = len(line) * size * CHAR_WIDTH
            if width > SAFE_RIGHT - SAFE_LEFT:
                issues.append(f'línea demasiado ancha ({len(line)} car.): «{line[:30]}»')
        if ev['end'] - ev['start'] < 0.5:
            issues.append(f'subtítulo de {ev["end"] - ev["start"]:.2f}s: no da tiempo a leerlo')
        if str(ev['text']).count('\n') > 1:
            issues.append('subtítulo con más de 2 líneas')
    x, y, an = POSITIONS.get(captions.get('position', 'lower'), POSITIONS['lower'])
    top = y - (2 * size * 1.2 if an == 2 else 0)
    if top < SAFE_TOP or y > SAFE_BOTTOM:
        issues.append('subtítulos fuera de la zona segura')
    return {'mode': captions.get('mode'), 'events': len(captions.get('events', [])),
            'overlays': len(overlays or []), 'issues': issues,
            'verified_by_human': all(ev.get('type') == 'edited' for ev in captions.get('events', [])) and bool(captions.get('events'))}
