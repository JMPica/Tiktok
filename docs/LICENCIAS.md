# Licencias y dependencias — 11-11-2026

Las licencias indicadas son las que conozco de cada proyecto; **confírmalas en el repositorio de cada uno antes de
un uso comercial distinto del actual** (no he podido abrir sus páginas desde esta sesión, salvo PyPI/npm/GitHub).

## En uso
| Componente | Para qué | Licencia | Nota |
|---|---|---|---|
| FFmpeg / ffprobe | corte, render, medición | LGPL 2.1+ o GPL según compilación | se usa como programa externo; x264 es GPL. No se redistribuye |
| faster-whisper + CTranslate2 | transcripción local (por defecto) | MIT | modelos Whisper: MIT. No probado en esta sesión |
| sherpa-onnx | transcripción local alternativa (ONNX) | Apache-2.0 | usado en las pruebas de hoy; VAD Silero: MIT |
| OpenCV (opencv-python-headless) | análisis de imagen, caras sin identificación | Apache-2.0 | |
| NumPy | cálculo | BSD-3-Clause | |
| requests | cliente HTTP del agente | Apache-2.0 | |
| jose | verificación de JWT en el Worker | MIT | |
| Wrangler / workerd | desarrollo y despliegue | MIT / Apache-2.0 | solo desarrollo |
| Playwright, pytest, cryptography | pruebas | Apache-2.0 / MIT / Apache-2.0 o BSD | solo desarrollo |
| Poppins (assets/fonts) | subtítulos | SIL OFL 1.1 | `assets/fonts/OFL.txt` incluido |
| espeak-ng | voz de los fixtures de prueba | GPL-3.0 | solo en pruebas; no forma parte del producto |

## Evaluadas, NO integradas
| Herramienta | Decisión | Motivo |
|---|---|---|
| HyperFrames (HeyGen) | pendiente de prueba práctica | Apache-2.0 según la evaluación previa; necesita Chrome sin interfaz en el editor: más tiempo de render |
| Remotion | no integrar por ahora | licencia de empresa para equipos a partir de cierto tamaño; verificar condiciones vigentes |
| reels-montage | solo como referencia de método | pensado para Claude Code en un PC, no para una cola sin operador |
| rembg (u2net_human_seg) | no integrar por ahora | coste de cálculo alto en CPU; aporta poco a los formatos actuales |
| yt-dlp | no integrar | descargar Reels/Shorts de terceros choca con las condiciones de las plataformas; las referencias se analizan con material aportado legítimamente |

## Servicios y coste
Cloudflare Workers + D1 + R2 + Access en plan gratuito y GitHub Actions: 0 €/mes previsto con el volumen actual
(límites: 10 GB en R2, minutos gratuitos de Actions). Ningún servicio de pago ni API de IA externa se ha llamado.
Coste de cálculo medido hoy: 36–67 s por vídeo de ~45 s a 1080p (2 propuestas), 4 núcleos sin GPU.
