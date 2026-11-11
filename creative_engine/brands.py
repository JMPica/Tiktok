"""Perfiles de marca (brand_style_v1): un motor, dos identidades con reglas, presets y riesgos propios.

La ficha vive en ``brands.v1.json`` (versionada, la comparte el Worker). Aquí solo se lee y se consulta.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(Path(__file__).with_name('brands.v1.json').read_text(encoding='utf8'))


def default_brand() -> str:
    return _data()['default_brand']


def brand_ids() -> list[str]:
    return [b['id'] for b in _data()['brands']]


def get(brand: str | None) -> dict:
    wanted = brand or default_brand()
    for b in _data()['brands']:
        if b['id'] == wanted:
            return b
    raise ValueError('Unknown brand: ' + str(brand))


def style_allowed(brand: dict, style: dict) -> bool:
    """Un preset de marca solo sirve a su marca; los estilos genéricos, según ``legacy_styles``."""
    if style.get('brand'):
        return style['brand'] == brand['id']
    legacy = brand.get('legacy_styles', 'all')
    return legacy == 'all' or style['id'] in legacy


def allowed_styles(brand: dict, styles: dict) -> list[str]:
    return [sid for sid, s in styles.items() if style_allowed(brand, s)]


def claims_regex(brand: dict) -> re.Pattern:
    return re.compile(r'(?<!\w)(' + brand['claims_pattern'] + r')(?!\w)', re.I)


def sensitive_hits(brand: dict, text: str) -> list[dict]:
    return [s for s in brand.get('sensitive', []) if re.search(r'(?<!\w)(' + s['pattern'] + r')(?!\w)', text, re.I)]


def edl_brand(brand: dict) -> dict:
    """Bloque de marca que viaja dentro del EDL (reproducible sin consultar la ficha)."""
    v = brand['visual']
    return {'id': brand['id'], 'name': brand['name'], 'style_schema': _data()['schema'], 'style_version': _data()['version'],
            'accent': v['accent'], 'caption_font': v.get('caption_font'), 'caption_size': v.get('caption_size'),
            'visual_status': v.get('status', 'provisional')}


def target_lufs(brand: dict) -> float:
    return float((brand.get('audio') or {}).get('target_lufs', -16))
