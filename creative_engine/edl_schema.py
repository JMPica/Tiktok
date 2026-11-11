"""Validación del EDL contra ``edl.schema.json`` antes de renderizar (sin dependencias externas).

Implementa el subconjunto de JSON Schema que usa el fichero: type, enum, required, properties, items,
minimum/maximum, minLength/maxLength, minItems/maxItems y pattern. Además comprueba coherencia temporal.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_TYPES = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'null': type(None)}


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(Path(__file__).with_name('edl.schema.json').read_text(encoding='utf8'))


def _is(value, t: str) -> bool:
    if t == 'number':
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == 'integer':
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _TYPES[t])


def _check(value, sch: dict, path: str, errors: list[str]):
    if len(errors) >= 20:
        return
    if 'enum' in sch and value not in sch['enum']:
        errors.append(f'{path}: valor no permitido ({value!r})')
        return
    if 'type' in sch:
        types = sch['type'] if isinstance(sch['type'], list) else [sch['type']]
        if not any(_is(value, t) for t in types):
            errors.append(f'{path}: se esperaba {"/".join(types)}')
            return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 'minimum' in sch and value < sch['minimum']:
            errors.append(f'{path}: {value} < mínimo {sch["minimum"]}')
        if 'maximum' in sch and value > sch['maximum']:
            errors.append(f'{path}: {value} > máximo {sch["maximum"]}')
    if isinstance(value, str):
        if len(value) < sch.get('minLength', 0) or len(value) > sch.get('maxLength', 10 ** 9):
            errors.append(f'{path}: longitud no permitida')
        if 'pattern' in sch and not re.search(sch['pattern'], value):
            errors.append(f'{path}: formato no válido')
    if isinstance(value, list):
        if len(value) < sch.get('minItems', 0) or len(value) > sch.get('maxItems', 10 ** 9):
            errors.append(f'{path}: número de elementos no permitido ({len(value)})')
        if 'items' in sch:
            for k, item in enumerate(value):
                _check(item, sch['items'], f'{path}[{k}]', errors)
    if isinstance(value, dict):
        for key in sch.get('required', []):
            if key not in value:
                errors.append(f'{path}.{key}: falta')
        for key, sub in sch.get('properties', {}).items():
            if key in value:
                _check(value[key], sub, f'{path}.{key}', errors)


def errors(edl: dict, source_duration: float | None = None) -> list[str]:
    out: list[str] = []
    _check(edl, schema(), 'edl', out)
    if out:
        return out
    for k, s in enumerate(edl['segments']):
        if s['out'] <= s['in']:
            out.append(f'edl.segments[{k}]: out <= in')
        if source_duration is not None and s['out'] > source_duration + 0.05:
            out.append(f'edl.segments[{k}]: fuera del original ({s["out"]:.2f} > {source_duration:.2f})')
    total = sum(s['out'] - s['in'] for s in edl['segments'])
    for name in ('captions', 'overlays'):
        events = edl['captions']['events'] if name == 'captions' else edl.get('overlays') or []
        for k, e in enumerate(events):
            if e['end'] <= e['start'] or e['start'] > total + 0.5:
                out.append(f'edl.{name}[{k}]: tiempos fuera del montaje')
    return out


def assert_valid(edl: dict, source_duration: float | None = None):
    found = errors(edl, source_duration)
    if found:
        raise ValueError('EDL no válido: ' + '; '.join(found[:6]))
