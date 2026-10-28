"""Correcciones en lenguaje natural (ca/es) sobre un EDL existente -> EDL nuevo (versión +1).

Reglas deterministas y auditables. Si la petición no se entiende, se dice exactamente qué se puede pedir.
Opcional: modelo local vía Ollama (BLAU_OLLAMA_MODEL) para traducir frases libres a las mismas operaciones.
"""
from __future__ import annotations

import copy
import json
import os
import re
import urllib.request

from creative_engine.captions import chunk, map_words
from creative_engine.director import cut_window, frame_segments, load_styles, validate_transcript

HELP = ('Puc entendre: «més curt», «més llarg», «més divertit», «més ràpid/lent», «sense subtítols», '
        '«subtítols a dalt/més grans», «treu el principi/final», «comença al segon 12», «estil premium/educatiu/…», '
        '«canvia "text antic" per "text nou"». En castellà també.')

STYLE_WORDS = {
    'premium': 'premium', 'luxe': 'premium', 'lujo': 'premium', 'educatiu': 'educativo', 'educativo': 'educativo',
    'asmr': 'asmr', 'cinemàtic': 'cinematic', 'cinematico': 'cinematic', 'cinemático': 'cinematic', 'pov': 'pov',
    'bucle': 'loop', 'loop': 'loop', 'vlog': 'microvlog', 'backstage': 'backstage', 'bastidors': 'backstage',
    'dinàmic': 'fast_cuts', 'dinámico': 'fast_cuts', 'fast': 'fast_cuts', 'revelació': 'reveal', 'revelación': 'reveal',
    'humà': 'tacho_humano', 'humano': 'tacho_humano', 'talking': 'clean_talking', 'servei': 'service_conversion',
    'servicio': 'service_conversion', 'reserva': 'service_conversion',
}


class NotUnderstood(ValueError):
    pass


def parse(instruction: str) -> list[dict]:
    t = ' ' + instruction.lower().strip() + ' '
    ops = []
    for old, new in re.findall(r'["«“]([^"»”]+)["»”]\s*(?:per|por|->|→|a)\s*["«“]([^"»”]+)["»”]', instruction):
        ops.append({'op': 'replace_text', 'old': old, 'new': new})
    if re.search(r'm[eé]s curt|más corto|mas corto|acorta|escurça|redueix|reduce|más breve', t):
        ops.append({'op': 'shorter'})
    if re.search(r'm[eé]s llarg|más largo|mas largo|allarga|alarga', t):
        ops.append({'op': 'longer'})
    if re.search(r'divertit|divertido|gracios|graciós|humor|riure|reír', t):
        ops.append({'op': 'style', 'style': 'tacho_humor'})
    if re.search(r'm[eé]s r[àa]pid|más rápido|mas rapido|més ritme|más ritmo|dinàmic|dinámico', t) and not any(o['op'] == 'style' for o in ops):
        ops.append({'op': 'pace', 'factor': 0.5})
    if re.search(r'm[eé]s lent|más lento|mas lento|més calma|más calma|pausat|pausado', t):
        ops.append({'op': 'pace', 'factor': 1.8})
    if re.search(r'sense subt[íi]tols|sin subt[íi]tulos|treu (els )?subt|quita (los )?subt', t):
        ops.append({'op': 'captions', 'mode': 'none'})
    elif re.search(r'subt[íi]t\w* (a )?(dalt|arriba)', t):
        ops.append({'op': 'captions', 'position': 'upper'})
    elif re.search(r'subt[íi]t\w* (a )?(baix|abajo)', t):
        ops.append({'op': 'captions', 'position': 'lower'})
    if re.search(r'subt[íi]t\w* m[aé]s grans|subt[íi]t\w* más grandes|lletra més gran|letra más grande', t):
        ops.append({'op': 'captions', 'size': 'l'})
    if re.search(r'paraula a paraula|palabra a palabra|karaoke', t):
        ops.append({'op': 'captions', 'mode': 'words'})
    if re.search(r'(treu|quita|elimina)\w* (el )?(principi|inici|inicio|començament|comienzo)', t):
        ops.append({'op': 'drop_first'})
    if re.search(r'(treu|quita|elimina)\w* (el )?(final|últim|último)', t):
        ops.append({'op': 'drop_last'})
    m = re.search(r'(comen[çc]a|empieza|inicia)\w*\s+(al|en el|a|en)?\s*(segon|segundo|minut|minuto)?\s*(\d+)(?:[:.,](\d+))?', t)
    if m:
        sec = int(m.group(4)) * 60 + int(m.group(5)) if m.group(5) and ':' in t[m.start():m.end()] else float(m.group(4))
        ops.append({'op': 'start_at', 'seconds': float(sec)})
    for word, style in STYLE_WORDS.items():
        if re.search(r'\b' + re.escape(word) + r'\b', t) and not any(o['op'] == 'style' for o in ops):
            ops.append({'op': 'style', 'style': style})
    if not ops:
        ops = _ollama(instruction)
    if not ops:
        raise NotUnderstood('No he entès la petició. ' + HELP)
    return ops


def _ollama(instruction: str) -> list[dict]:
    model = os.environ.get('BLAU_OLLAMA_MODEL')
    if not model:
        return []
    prompt = ('Convierte la petición de edición en JSON {"ops":[...]} usando SOLO estas operaciones: '
              '{"op":"shorter"},{"op":"longer"},{"op":"style","style":ID},{"op":"pace","factor":0.5|1.8},'
              '{"op":"captions","mode":"none|words|phrase","position":"upper|lower","size":"m|l"},'
              '{"op":"drop_first"},{"op":"drop_last"},{"op":"start_at","seconds":N},'
              '{"op":"replace_text","old":"...","new":"..."}. IDs de estilo: ' + ', '.join(load_styles()) +
              '. Si no encaja, {"ops":[]}. Petición: ' + instruction)
    body = json.dumps({'model': model, 'prompt': prompt, 'format': 'json', 'stream': False}).encode()
    try:
        req = urllib.request.Request(os.environ.get('BLAU_OLLAMA_URL', 'http://127.0.0.1:11434') + '/api/generate',
                                     data=body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=120) as r:
            ops = json.loads(json.loads(r.read())['response']).get('ops', [])
    except (OSError, ValueError, KeyError):
        return []
    allowed = {'shorter', 'longer', 'style', 'pace', 'captions', 'drop_first', 'drop_last', 'start_at', 'replace_text'}
    styles = load_styles()
    return [o for o in ops if isinstance(o, dict) and o.get('op') in allowed and (o['op'] != 'style' or o.get('style') in styles)]


def _recut(edl, rows, i, j, style, meta, analysis, pace=1.0):
    styles = load_styles()
    recipe = dict(styles[style]['render'])
    recipe['max_pause'] = recipe.get('max_pause', 0.55) * pace
    win = rows[i:j + 1]
    cuts = cut_window(win, recipe, meta['duration'])
    edl['segments'] = frame_segments(cuts, analysis, meta, recipe)
    old = edl.get('captions') or {}
    edl['captions'] = {'mode': old.get('mode', recipe.get('captions')), 'size': old.get('size', 'm'),
                       'position': old.get('position', 'lower'),
                       'events': chunk(map_words(cuts, [w for r in win for w in r['words']]))}
    edl['provenance']['transcript_rows'] = [i, j]
    edl['provenance']['source_range'] = [win[0]['start'], win[-1]['end']]


def apply(edl: dict, instruction: str, transcript: list[dict] | None, meta: dict, analysis: dict | None) -> tuple[dict, list[str]]:
    ops = parse(instruction)
    new = copy.deepcopy(edl)
    new['version'] = int(edl.get('version', 1)) + 1
    new['parent_id'] = edl.get('id')
    styles = load_styles()
    rows = validate_transcript(transcript or [], meta['duration']) if transcript else []
    rng = (edl.get('provenance') or {}).get('transcript_rows')
    i, j = (rng if rng and rows else (None, None))
    style, pace, done = new['style'], 1.0, []
    for op in ops:
        kind = op['op']
        if kind == 'style':
            style = op['style']
            new['style'], new['style_label'] = style, styles[style]['label']
            new['grade'] = styles[style]['render'].get('grade', 'natural')
            new['loop'] = bool(styles[style]['render'].get('loop'))
            if new.get('captions', {}).get('mode') != 'none':
                new.setdefault('captions', {})['mode'] = styles[style]['render'].get('captions', 'phrase')
            done.append(f'estil → {styles[style]["label"]}')
        elif kind == 'pace':
            pace *= float(op.get('factor', 1))
            done.append('ritme més ràpid' if op['factor'] < 1 else 'ritme més pausat')
        elif kind == 'shorter':
            if i is not None and j > i:
                j = max(i, j - max(1, (j - i + 1) // 4))
            elif len(new['segments']) > 1:
                keep = max(1, int(len(new['segments']) * 0.75))
                new['segments'] = new['segments'][:keep]
            else:
                raise NotUnderstood('Ja és el mínim fragment amb sentit; no es pot escurçar sense tallar frases.')
            done.append('més curt')
        elif kind == 'longer':
            if i is None or j >= len(rows) - 1:
                raise NotUnderstood('No hi ha més material parlat després d’aquest fragment.')
            j += 1
            done.append('més llarg (frase següent)')
        elif kind == 'drop_first':
            if i is not None and j > i:
                i += 1
            elif len(new['segments']) > 1:
                new['segments'] = new['segments'][1:]
            done.append('sense el principi')
        elif kind == 'drop_last':
            if i is not None and j > i:
                j -= 1
            elif len(new['segments']) > 1:
                new['segments'] = new['segments'][:-1]
            done.append('sense el final')
        elif kind == 'start_at':
            if i is None:
                raise NotUnderstood('Aquest muntatge no té transcripció per recol·locar l’inici.')
            k = next((n for n, r in enumerate(rows) if r['end'] > op['seconds']), None)
            if k is None:
                raise NotUnderstood('Aquest segon és posterior al final del vídeo.')
            span = j - i
            i, j = k, min(len(rows) - 1, k + span)
            done.append(f'comença al segon {op["seconds"]:.0f}')
        elif kind == 'captions':
            cap = new.setdefault('captions', {'events': []})
            for key in ('mode', 'position', 'size'):
                if op.get(key):
                    cap[key] = op[key]
            done.append('subtítols: ' + ', '.join(f'{k}={op[k]}' for k in ('mode', 'position', 'size') if op.get(k)))
    if i is not None and (any(o['op'] in ('shorter', 'longer', 'drop_first', 'drop_last', 'start_at', 'pace', 'style') for o in ops)):
        _recut(new, rows, i, j, style, meta, analysis, pace)
    for op in ops:
        if op['op'] == 'replace_text':
            hits = 0
            for ev in new.get('captions', {}).get('events', []):
                if op['old'].lower() in ev['text'].lower():
                    ev['text'] = re.sub(re.escape(op['old']), op['new'], ev['text'], flags=re.I)
                    ev['type'] = 'edited'
                    hits += 1
            if not hits:
                raise NotUnderstood(f'No trobo «{op["old"]}» als subtítols.')
            done.append(f'subtítol corregit: «{op["old"]}» → «{op["new"]}»')
    new['duration'] = round(sum(s['out'] - s['in'] for s in new['segments']), 3)
    new['revision'] = {'instruction': instruction[:500], 'applied': done}
    new['explanation'] = (edl.get('explanation', '') + f' · Versió {new["version"]}: ' + '; '.join(done)).strip()
    return new, done


def apply_manual(edl: dict, edits: dict, meta: dict) -> dict:
    """Edición Advanced (sin JSON a mano en la UI): segmentos y textos editados en tabla."""
    new = copy.deepcopy(edl)
    new['version'] = int(edl.get('version', 1)) + 1
    new['parent_id'] = edl.get('id')
    if 'segments' in edits:
        segs = []
        for k, s in enumerate(edits['segments']):
            a, b = float(s['in']), float(s['out'])
            if not (0 <= a < b <= meta['duration'] + 0.05):
                raise ValueError(f'Segment {k + 1} fora del bruto')
            base = new['segments'][k] if k < len(new['segments']) else {'zoom': 1.0, 'x': 0.5, 'y': 0.5, 'push_in': 0}
            segs.append({**base, 'id': f's{k + 1}', 'in': round(a, 3), 'out': round(b, 3)})
        if not segs:
            raise ValueError('Cal com a mínim un segment')
        new['segments'] = segs
    if 'captions' in edits:
        events = []
        for ev in edits['captions']:
            s, e, txt = float(ev['start']), float(ev['end']), str(ev['text']).strip()[:140]
            if e <= s or not txt:
                continue
            events.append({'start': s, 'end': e, 'text': txt, 'words': [], 'type': 'edited'})
        new.setdefault('captions', {'mode': 'phrase'})['events'] = events
        if new['captions'].get('mode') == 'words':
            new['captions']['mode'] = 'phrase'
    if 'caption_mode' in edits:
        new.setdefault('captions', {})['mode'] = edits['caption_mode']
    new['duration'] = round(sum(s['out'] - s['in'] for s in new['segments']), 3)
    new['revision'] = {'instruction': 'edició manual (Advanced)', 'applied': list(edits)}
    return new
