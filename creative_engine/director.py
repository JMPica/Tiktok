"""Director editorial V4: propone 0..N historias SOLO con material existente, con puntuación auditable.

Entradas: transcripción local (con tiempos por palabra), análisis de señal (planos, caras, nitidez, energía)
y, si existe, descripción semántica de un modelo de visión local. Sin señales fiables => ``needs_review``.

Puntuación editorial (no es probabilidad de viralidad): gancho 20, historia 20, autenticidad 20,
utilidad 15, ritmo 15, marca 10, con veto externo (privacidad, claims, legal, calidad técnica).
"""
from __future__ import annotations

import json
import math
import re
import uuid
from pathlib import Path

from creative_engine import analysis as A
from creative_engine.captions import chunk, map_words
from creative_engine.media import output_fps

THRESHOLD = 55
EDL_SCHEMA = 'blau.edl/4'

HOOK = {
    'ca': ('per què', 'com ', 'sabeu', 'saps', 'mai', 'secret', 'error', 'mira', 'compte', 'atenció', 'ningú', 'sempre',
           'el que', 'no et creuràs', 'avui', 'pregunta', 'truc', 'mite'),
    'es': ('por qué', 'cómo', 'sabes', 'sabéis', 'nunca', 'secreto', 'error', 'mira', 'ojo', 'atención', 'nadie', 'siempre',
           'lo que', 'no te vas a creer', 'hoy', 'pregunta', 'truco', 'mito'),
}
PAYOFF = {
    'ca': ('per això', 'resultat', 'al final', 'així que', 'per tant', 'i ja està', 'secret', 'la clau', 'ja ho saps'),
    'es': ('por eso', 'resultado', 'al final', 'así que', 'por tanto', 'y ya está', 'secreto', 'la clave', 'ya lo sabes'),
}
USEFUL = {
    'ca': ('perquè', 'com ', 'consell', 'truc', 'error', 'mite', 'pas', 'primer', 'després', 'important', 'cal', 'recomanem'),
    'es': ('porque', 'cómo', 'consejo', 'truco', 'error', 'mito', 'paso', 'primero', 'después', 'importante', 'hay que', 'recomendamos'),
}
BRAND = ('blau de mar', 'cabina', 'pell', 'piel', 'tractament', 'tratamiento', 'facial', 'massatge', 'masaje', 'centre',
         'centro', 'arenys', 'clienta', 'equip', 'equipo', 'estètica', 'estética')
FILLERS = ('eh', 'ehm', 'em', 'mmm', 'mm', 'ah', 'eee', 'doncs', 'pues', 'bueno', 'vale', 'o sigui', 'o sea')
# Afirmaciones que necesitan verificación legal/técnica antes de publicarse (no se bloquean en silencio).
CLAIMS = re.compile(r'\b(cura|curar|curem|elimina|eliminar|per sempre|para siempre|garantit|garantizado|garantia|garantía|'
                    r'100 ?%|sense dolor|sin dolor|sense efectes|sin efectos|rejoveneix|rejuvenece|anys menys|años menos|'
                    r'definitiu|definitivo|mèdic|médico|metge|tratamiento médico|clínicament|clínicamente|demostrat|demostrado|'
                    r'adelgaza|aprima|cel·lulitis|celulitis|arrugues|arrugas)\b', re.I)
MINORS = re.compile(r'\b(nen|nena|nens|niño|niña|niños|menor|filla|fill|hija|hijo)\b', re.I)


def load_styles() -> dict:
    data = json.loads(Path(__file__).with_name('styles.v4.json').read_text(encoding='utf8'))
    return {s['id']: s for s in data['profiles']}


def clean_phrase(s: str) -> str:
    return ' '.join(str(s).strip().split())


def validate_transcript(rows: list[dict], duration: float) -> list[dict]:
    out = []
    for i, r in enumerate(rows):
        a, b, t = float(r['start']), float(r['end']), clean_phrase(r.get('text', ''))
        if not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= duration + 0.5):
            raise ValueError(f'Transcript segment invalid: {i}')
        if not re.search(r'\w{2,}', t):
            continue  # ruido tipo '#', '...'
        words = [w for w in (r.get('words') or []) if str(w.get('word', '')).strip()]
        if not words:
            words = [{'start': a + (b - a) * k / max(1, len(t.split())), 'end': a + (b - a) * (k + 1) / max(1, len(t.split())),
                      'word': tok, 'probability': None} for k, tok in enumerate(t.split())]
        out.append({'start': a, 'end': min(b, duration), 'text': t, 'words': words,
                    'confidence': r.get('avg_logprob'), 'no_speech_prob': r.get('no_speech_prob')})
    return sorted(out, key=lambda x: x['start'])


# ---------------------------------------------------------------- puntuación
def _has(text: str, keys) -> int:
    t = ' ' + text.lower() + ' '
    return sum(1 for k in keys if k in t)


def _ends_sentence(text: str) -> bool:
    return text.rstrip()[-1:] in '.?!…'


def score_window(rows: list[dict], i: int, j: int, language: str, analysis: dict | None, recipe: dict) -> dict:
    win = rows[i:j + 1]
    a, b = win[0]['start'], win[-1]['end']
    text = ' '.join(r['text'] for r in win)
    first = win[0]['text']
    words = sum(len(r['text'].split()) for r in win)
    speech = sum(r['end'] - r['start'] for r in win)
    lang = language if language in HOOK else 'es'
    notes = []
    # Gancho (20)
    hook = 6
    if first.endswith('?') or _has(first, HOOK[lang]):
        hook += 8
        notes.append('arrenca amb pregunta/ganxo')
    if len(first.split()) <= 14:
        hook += 3
    if first.lower().split()[0].strip(',.') in FILLERS:
        hook -= 5
        notes.append('comença amb una crossa (eh, doncs…)')
    # Historia (20): empieza y acaba en frase completa, tiene desarrollo y remate.
    story = 4
    starts_clean = i == 0 or _ends_sentence(rows[i - 1]['text']) or win[0]['start'] - rows[i - 1]['end'] > 0.8
    ends_clean = _ends_sentence(win[-1]['text'])
    story += 5 if starts_clean else 0
    story += 5 if ends_clean else 0
    if 2 <= len(win) <= 10:
        story += 3
    if _has(win[-1]['text'], PAYOFF[lang]) or win[-1]['text'].endswith('!'):
        story += 3
        notes.append('té remat')
    if not starts_clean:
        notes.append('comença a mitja frase')
    if not ends_clean:
        notes.append('acaba sense tancar la frase')
    # Autenticidad (20): persona en cuadro, habla real, sin música de fondo dominante.
    auth = 8
    face = A.face_stats(analysis, a, b) if analysis else {'ratio': None}
    if face['ratio'] is not None:
        auth += round(8 * face['ratio'])
        if face['ratio'] > 0.5:
            notes.append('persona visible al pla')
    else:
        auth += 4
    audio = (analysis or {}).get('audio') or {}
    if audio.get('probable_music'):
        auth -= 4
        notes.append('possible música de fons (revisar drets)')
    if analysis and A.has_burst(analysis, b - 1.5, b + 1.0):
        auth += 4
        notes.append('reacció/riure probable al final')
    # Utilidad (15)
    useful = min(15, 4 + 3 * _has(text, USEFUL[lang]) + (2 if re.search(r'\d', text) else 0))
    # Ritmo (15)
    dur = b - a
    wps = words / max(speech, 0.1)
    dead = 1 - speech / max(dur, 0.1)
    lo, hi = recipe.get('ideal', [12, 45])
    rhythm = 5 + (5 if 1.8 <= wps <= 3.8 else 2) + (5 if lo <= dur <= hi else 2 if dur <= recipe.get('max_len', 75) else 0)
    rhythm -= 3 if dead > 0.45 and not recipe.get('comedy_pauses') else 0
    # Marca (10): presencia natural, no publicidad.
    brand = min(10, 4 + 2 * _has(text, BRAND))
    # Calidad técnica (veto parcial)
    veto = []
    if analysis:
        q = A.visual_quality(analysis, a, b)
        if q['sharp_rel'] < 0.35:
            veto.append('imatge molt desenfocada')
        if q['dark']:
            veto.append('imatge massa fosca')
    low_conf = [r for r in win if (r.get('no_speech_prob') or 0) > 0.6 or (r.get('confidence') is not None and r['confidence'] < -1.2)]
    if len(low_conf) > len(win) / 2:
        veto.append('transcripció poc fiable: revisar subtítols')
    scores = {'hook': max(0, min(20, hook)), 'story': max(0, min(20, story)), 'authenticity': max(0, min(20, auth)),
              'utility': max(0, min(15, useful)), 'rhythm': max(0, min(15, rhythm)), 'brand': max(0, min(10, brand))}
    total = sum(scores.values())
    if veto:
        total = min(total, THRESHOLD - 1) if any('desenfocada' in v or 'oscura' in v for v in veto) else total - 8
    return {'scores': scores, 'total': int(total), 'notes': notes, 'veto': veto, 'range': [a, b], 'text': text}


# ---------------------------------------------------------------- cortes
def cut_window(rows: list[dict], recipe: dict, duration: float) -> list[dict]:
    """Cortes en límites de palabra; quita pausas largas pero respeta pausas cómicas según receta."""
    max_pause = float(recipe.get('max_pause', 0.55))
    pre, post = 0.08, 0.14
    words = [w for r in rows for w in r['words']]
    # Quita muletillas aisladas al principio.
    while len(words) > 3 and words[0]['word'].lower().strip(',.') in FILLERS:
        words = words[1:]
    cuts = []
    for w in words:
        a, b = max(0.0, w['start'] - pre), min(duration, w['end'] + post)
        if cuts and a - cuts[-1]['out'] <= max_pause:
            cuts[-1]['out'] = max(cuts[-1]['out'], b)
        elif cuts and a < cuts[-1]['out']:
            cuts[-1]['out'] = max(cuts[-1]['out'], b)
        else:
            cuts.append({'in': round(a, 3), 'out': round(b, 3)})
    for c in cuts:
        c['in'], c['out'] = round(c['in'], 3), round(c['out'], 3)
    return [c for c in cuts if c['out'] - c['in'] >= 0.25]


def frame_segments(cuts: list[dict], analysis: dict | None, meta: dict, recipe: dict) -> list[dict]:
    from creative_engine.render import max_zoom
    zmax = max_zoom(meta)
    punch = float(recipe.get('punch_zoom') or 0)
    out = []
    for k, c in enumerate(cuts):
        face = A.face_stats(analysis, c['in'], c['out']) if analysis else {'ratio': None, 'cx': 0.5, 'cy': 0.4}
        z = 1.0 + (punch if k % 2 == 1 else 0.0)
        z = min(z, zmax)
        seg = {'id': f's{k + 1}', 'in': c['in'], 'out': c['out'], 'zoom': round(z, 3),
               'x': face['cx'] if face['ratio'] else 0.5, 'y': min(0.6, max(0.3, face['cy'])) if face['ratio'] else 0.5,
               'push_in': float(recipe.get('push_in') or 0), 'framing': 'face' if face['ratio'] else 'center'}
        out.append(seg)
    return out


# ---------------------------------------------------------------- estilo automático
def resolve_style(style: str, rows: list[dict], analysis: dict | None, duration: float) -> tuple[str, str]:
    if style != 'auto':
        return style, 'estil triat per l’usuària'
    speech = sum(r['end'] - r['start'] for r in rows)
    if speech < 0.15 * duration or not rows:
        return 'asmr', 'gairebé sense diàleg: muntatge sensorial del procés amb so real'
    text = ' '.join(r['text'] for r in rows).lower()
    if any(k in text for k in ('per què', 'por qué', 'consell', 'consejo', 'truc', 'truco', 'mite', 'mito')):
        return 'educativo', 'diàleg explicatiu: format consell/mite'
    if analysis and len((analysis.get('audio') or {}).get('energy_bursts', [])) >= 3:
        return 'tacho_humor', 'reaccions/riures detectats: humor quotidià'
    return 'tacho_humano', 'diàleg a càmera: humà autèntic'


# ---------------------------------------------------------------- plan
def _edl(cand_id, style, styles, language, segs, captions, overlays, meta, score, provenance, risks, requires, explanation):
    recipe = styles[style]['render']
    fps, fps_reason = output_fps(meta)
    total = round(sum(s['out'] - s['in'] for s in segs), 3)
    return {'schema': EDL_SCHEMA, 'id': cand_id, 'version': 1, 'style': style, 'style_label': styles[style]['label'],
            'language': language, 'grade': recipe.get('grade', 'natural'),
            'output': {'width': 1080, 'height': 1920, 'fps': fps, 'fps_reason': fps_reason},
            'source': {'duration': meta['duration'], 'width': meta['width'], 'height': meta['height'],
                       'fps': meta['fps'], 'hdr': meta.get('hdr', False)},
            'segments': segs, 'captions': captions, 'overlays': overlays,
            'audio': {'keep_original': True, 'target_lufs': -16, 'true_peak_max': -1.0, 'music': None,
                      'note': 'sin música añadida: solo audio original o librería con licencia comercial verificada'},
            'loop': bool(recipe.get('loop')), 'duration': total, 'score': score, 'provenance': provenance,
            'risks': risks, 'requires': requires, 'explanation': explanation,
            'automatic_publish': False, 'editorial_review_required': True}


def _requirements(style, styles, text, options) -> tuple[list[str], list[str]]:
    reqs = list(styles[style]['render'].get('requires', []))
    risks = []
    claims = sorted({m.group(0).lower() for m in CLAIMS.finditer(text)})
    if claims:
        risks.append('afirmacions a verificar abans de publicar: ' + ', '.join(claims))
        if 'claims_review' not in reqs:
            reqs.append('claims_review')
    if MINORS.search(text):
        risks.append('possible menció de menors: revisar consentiment')
    reqs.append('team_consent')
    if 'comment_text' in reqs and options.get('comment_text'):
        reqs.remove('comment_text')
    if 'trend_source' in reqs and options.get('trend_source', {}).get('url') and options.get('trend_source', {}).get('date'):
        reqs.remove('trend_source')
    return reqs, risks


def _explain(win, style_reason, scores, notes, language) -> str:
    a, b = win['range']
    parts = [f'Fragment {a:.1f}–{b:.1f}s del bruto.', style_reason.capitalize() + '.']
    if notes:
        parts.append('Per què: ' + '; '.join(notes[:4]) + '.')
    parts.append(f'Puntuació editorial {sum(scores.values())}/100 (no és predicció de viralitat).')
    return ' '.join(parts)


def _overlaps(r1, r2) -> float:
    inter = max(0.0, min(r1[1], r2[1]) - max(r1[0], r2[0]))
    return inter / max(0.1, min(r1[1] - r1[0], r2[1] - r2[0]))


def speech_candidates(rows, style, styles, language, analysis, meta, options, style_reason):
    recipe = styles[style]['render']
    lo, hi = recipe.get('ideal', [12, 45])
    max_len = recipe.get('max_len', 75)
    min_len = max(5.0, lo * 0.35)
    wins = []
    for i in range(len(rows)):
        for j in range(i, len(rows)):
            dur = rows[j]['end'] - rows[i]['start']
            if dur > max_len:
                break
            if j > i and rows[j]['start'] - rows[j - 1]['end'] > 6:
                break  # una pausa muy larga separa historias
            if dur < min_len:
                continue
            w = score_window(rows, i, j, language, analysis, recipe)
            w['i'], w['j'] = i, j
            wins.append(w)
    wins.sort(key=lambda w: (-w['total'], -(w['range'][1] - w['range'][0])))
    picked = []
    limit = int(options.get('max_candidates') or 4)
    for w in wins:
        if w['total'] < THRESHOLD or len(picked) >= limit:
            break
        if any(_overlaps(w['range'], p['range']) > 0.2 for p in picked):
            continue
        picked.append(w)
    return picked, (wins[0] if wins else None)


def visual_candidates(style, styles, analysis, meta, options):
    """Sin diálogo: secuencia de planos nítidos, solo para estilos sensoriales. Nunca recorte ciego."""
    recipe = styles[style]['render']
    if recipe.get('speech') == 'required':
        return [], 'l’estil necessita diàleg i no s’ha detectat veu'
    if not analysis:
        return [], 'sense anàlisi visual'
    shots = []
    for sh in analysis['visual']['shots']:
        a, b = sh['start'], sh['end']
        if b - a < 1.0:
            continue
        q = A.visual_quality(analysis, a, b)
        if q['dark'] or q['sharp_rel'] < 0.6:
            continue
        lo_s, hi_s = 2.0, 4.5
        mid = (a + b) / 2
        length = min(hi_s, b - a)
        shots.append({'in': round(max(a, mid - length / 2), 3), 'out': round(min(b, mid + length / 2), 3),
                      'q': q['sharp_rel'], 'motion': q['motion']})
    if len(shots) < 2:
        # Un único plano largo: se acepta solo si es nítido y dura lo suficiente (p. ej. ASMR continuo).
        long = [s for s in shots if s['out'] - s['in'] >= 4]
        if not long:
            return [], 'no hi ha prou plans nítids per a una peça sense diàleg'
    shots.sort(key=lambda s: s['in'])
    best = sorted(shots, key=lambda s: -s['q'])[:8]
    best.sort(key=lambda s: s['in'])
    total = sum(s['out'] - s['in'] for s in best)
    if total < 6:
        return [], f'només {total:.1f}s de material visual aprofitable'
    return [{'cuts': [{'in': s['in'], 'out': s['out']} for s in best], 'total': total}], ''


def build_plan(transcript, duration, style='auto', language='ca', analysis=None, meta=None, options=None):
    """Plan editorial 0..N. Compatible con la firma V4 inicial (transcript, duration, style, language)."""
    styles = load_styles()
    if style not in styles:
        raise ValueError('Unknown style: ' + style)
    if language not in ('ca', 'es'):
        raise ValueError('Unsupported language')
    options = options or {}
    meta = meta or (analysis or {}).get('meta') or {'duration': duration, 'width': 1080, 'height': 1920, 'fps': '30/1'}
    rows = validate_transcript(transcript, duration)
    chosen, style_reason = resolve_style(style, rows, analysis, duration)
    recipe = styles[chosen]['render']
    base = {'style_requested': style, 'style': chosen, 'style_reason': style_reason, 'automatic_publish': False,
            'editorial_review_required': True, 'caption_review_required': True, 'claims_checked': False,
            'selection': 'multimodal_signals+speech' if analysis else 'speech_only',
            'semantic_vision': (analysis or {}).get('semantic_vision') or 'no disponible: només senyals d’imatge i so'}
    candidates = []
    if rows and recipe.get('speech') != 'none':
        picked, best = speech_candidates(rows, chosen, styles, language, analysis, meta, options, style_reason)
        for k, w in enumerate(picked):
            win_rows = rows[w['i']:w['j'] + 1]
            cuts = cut_window(win_rows, recipe, duration)
            if not cuts:
                continue
            segs = frame_segments(cuts, analysis, meta, recipe)
            words = map_words(cuts, [x for r in win_rows for x in r['words']])
            mode = recipe.get('captions', 'phrase')
            face_low = analysis and A.face_stats(analysis, *w['range'])['cy'] > 0.62
            captions = {'mode': mode, 'size': 'l' if mode == 'words' else 'm',
                        'position': 'upper' if face_low else 'lower', 'events': chunk(words)}
            total = sum(c['out'] - c['in'] for c in cuts)
            overlays = []
            if options.get('comment_text') and chosen == 'respuesta_comentario':
                overlays.append({'kind': 'comment', 'start': 0.0, 'end': min(3.5, total), 'text': options['comment_text'][:120]})
            reqs, risks = _requirements(chosen, styles, w['text'], options)
            risks += w['veto']
            cid = uuid.uuid4().hex[:12]
            hook_text = win_rows[0]['text']
            score = {**w['scores'], 'total': w['total'], 'meaning': 'puntuació editorial, no probabilitat de viralitat'}
            prov = {'transcript_rows': [w['i'], w['j']], 'source_range': [round(x, 3) for x in w['range']],
                    'text': w['text'][:1200], 'notes': w['notes']}
            edl = _edl(cid, chosen, styles, language, segs, captions, overlays, meta, score, prov, risks, reqs,
                       _explain(w, style_reason, w['scores'], w['notes'], language))
            edl['hook_overlay_suggestion'] = hook_text[:74]
            edl['title'] = f"{k + 1}. {hook_text[:48]}"
            candidates.append(edl)
        if not candidates:
            why = 'no hi ha cap història parlada amb prou qualitat editorial'
            if best:
                why += f" (millor fragment {best['range'][0]:.1f}–{best['range'][1]:.1f}s: {best['total']}/100"
                why += (': ' + '; '.join(best['notes'] + best['veto'])) if best['notes'] or best['veto'] else ''
                why += ')'
            return {**base, 'status': 'needs_review', 'reason': why.capitalize(), 'candidates': []}
    else:
        vis, why = visual_candidates(chosen, styles, analysis, meta, options)
        if not vis:
            reason = ('Sense transcripció vàlida: no es talla cap tram arbitrari (sin transcripción válida)' if not analysis else
                      f'No es pot muntar sense inventar: {why}. Prova un estil sensorial (ASMR/Premium) o grava una nova presa.')
            return {**base, 'status': 'needs_review', 'reason': reason, 'candidates': []}
        for v in vis:
            segs = frame_segments(v['cuts'], analysis, meta, recipe)
            reqs, risks = _requirements(chosen, styles, '', options)
            if (analysis.get('audio') or {}).get('probable_music'):
                risks.append('l’àudio original sembla contenir música: verificar drets')
            q = {'hook': 10, 'story': 8, 'authenticity': 14, 'utility': 6, 'rhythm': 11, 'brand': 6}
            score = {**q, 'total': sum(q.values()), 'meaning': 'puntuació editorial, no probabilitat de viralitat'}
            prov = {'shots': v['cuts'], 'notes': ['plans més nítids en ordre cronològic', 'so original']}
            edl = _edl(uuid.uuid4().hex[:12], chosen, styles, language, segs, {'mode': 'none', 'events': []}, [],
                       meta, score, prov, risks, reqs,
                       f"Peça sense diàleg amb {len(segs)} plans nítids ({v['total']:.1f}s) i so real. {style_reason.capitalize()}.")
            edl['title'] = '1. Procés / sensorial'
            candidates.append(edl)
    return {**base, 'status': 'drafts', 'candidates': candidates}
