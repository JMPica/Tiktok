# Motion Creator — investigación y diseño (sin implementar) · 11-11-2026

Estado: **solo diseño**. No se ha escrito código de Motion Creator, no se ha instalado nada de terceros y no se ha
comprado ningún producto. La implementación queda bloqueada hasta que el editor de vídeo real pase sus pruebas (§7).

## 1. Qué se ha podido investigar y qué no

| Fuente pedida | Resultado | Confianza |
|---|---|---|
| `https://blackdark.club/es/tienda/blackdark-reels` | **No accesible.** `blackdark.club` no está entre los dominios permitidos de esta sesión (el proxy rechaza la conexión). | `not_verified` |
| `https://www.instagram.com/blackdarketing/` | **No accesible.** `www.instagram.com` tampoco está permitido. | `not_verified` |
| Búsqueda web sobre «Blackdark Reels» | Solo aparece la portada `blackdark.club/es`: se presenta como archivo de IA y marketing con prompts, herramientas y guías, parte libre y parte reservada a un «Club», y lista una skill llamada «Disección de reels virales». Ningún resultado describe el producto «Blackdark Reels». | `reported` (resumen del buscador, no lectura directa) |

Consecuencia: **no he visto los 11 estilos, ni su flujo guion-storyboard-montaje-QA, ni sus recursos de subtítulos y
sonido, ni su análisis de estilos de referencia.** No describo nada de ello: sería inventarlo. Tampoco sé su precio, su
licencia de uso ni de qué herramientas depende. Lo que sigue se apoya en lo que tú has enumerado en el encargo (que
existen esas cuatro áreas) y en lo que sí he podido leer de primera mano (licencias, §2).

Para completar esta parte hace falta una de dos cosas: permitir `blackdark.club` y `www.instagram.com` en la red de la
sesión, o pasarme capturas o el texto de la ficha del producto. La comparación de §3 tiene una columna vacía reservada.

## 2. Licencias verificadas (leídas hoy en el repositorio de cada proyecto)

| Herramienta | Licencia | Lo que implica aquí |
|---|---|---|
| **Remotion** | Licencia propia, no es código abierto. Gratis para: una persona, una **organización con ánimo de lucro de hasta 3 empleados**, entidades sin ánimo de lucro, y quien lo esté evaluando sin uso comercial. El resto necesita **Company License**. Prohíbe vender o relicenciar derivados de Remotion. El fichero avisa de que la licencia cambiará ligeramente en Remotion 5.0. | Depende del **número de empleados de la entidad que lo use**. Blau de Mar y Top House Real Estate S.L. son entidades distintas y no conozco su plantilla. Si cualquiera de las dos (o la que opere el estudio) supera 3 empleados, hace falta licencia de pago. Los precios que da la búsqueda no coinciden entre fuentes (desde unos 100 $/mes según varias), así que no los doy por buenos. |
| **HyperFrames** (HeyGen) | **Apache-2.0**. Escribe HTML/CSS y lo renderiza a vídeo; requiere Node ≥ 22 (y, según las reseñas, Chrome sin interfaz + FFmpeg). | Uso comercial libre sin umbral de empleados. Hay que conservar los avisos de licencia. La licencia cubre el código, **no** la música o efectos que se obtengan con sus módulos: cada audio tiene la suya. |
| **reels-montage** | **MIT** | Es una guía de método para un asistente, no un motor. Reutilizable como referencia. |
| FFmpeg, libass, Poppins (ya en uso) | LGPL/GPL según compilación · ISC · OFL 1.1 | Sin cambios; ver `docs/LICENCIAS.md`. |
| Producto «Blackdark Reels» | **Desconocida** | No se usa ni se copia nada suyo. Si se compra, hay que leer su licencia antes de reutilizar plantillas, tipografías, sonidos o prompts dentro de un producto para dos empresas. |

Fuentes: `raw.githubusercontent.com/remotion-dev/remotion/main/LICENSE.md`, `…/heygen-com/hyperframes/main/LICENSE` y
`README.md`, `…/itpartypattaya/reels-montage/main/LICENSE`, consultados el 11-11-2026.

## 3. Qué existe ya y qué merece la pena incorporar

Las filas son las áreas que nombras en el encargo. La columna de Blackdark queda sin rellenar a propósito.

| Área | En Content Studio hoy | Blackdark Reels | ¿Merece la pena incorporar? |
|---|---|---|---|
| Catálogo de estilos | 24 recetas de render para **vídeo grabado** (18 genéricas + 3 por marca). Ninguna es de gráficos animados. | no verificado (dices que son 11) | **Sí**, pero como formatos de Motion Creator (§5), no como más recetas del editor real. |
| Guion | Encargo por vídeo (tema, público, objetivo, duración, cierre). No genera guiones. | no verificado | **Sí**: en Motion Creator el guion *es* el contenido; hay que escribirlo y aprobarlo antes de renderizar. |
| Storyboard | Guion por momentos derivado del EDL, visible **después** del render. | no verificado | **Sí, como paso previo**: en motion no hay metraje que descubrir, así que aprobar el storyboard antes es barato y evita renders inútiles. |
| Montaje | FFmpeg en una codificación, cortes por frase, reencuadre, HDR→SDR. | no verificado | Ya existe para vídeo real. Para motion hace falta otro motor (§6). |
| QA | QC medido (resolución, códecs, duración, sonoridad, pico, negros, subtítulos, primeros 2 s) + aprobación ligada al hash. | no verificado | **Reutilizar entero** y añadir comprobaciones de texto (§5.4). |
| Subtítulos | Palabra a palabra o por frase, zonas seguras, una fuente con licencia (Poppins), acento por marca, exportación `.srt`. Sin animaciones de entrada ni estilos alternativos. | no verificado | **Sí, con moderación**: 2–3 estilos de subtítulo por marca y resaltado de palabra clave. Depende del brand kit. |
| Sonido | Solo audio original, normalizado. **Sin música ni efectos.** | no verificado | **Sí, con condición**: solo una biblioteca cuya licencia comercial esté verificada pista a pista. Hasta entonces, nada. |
| Análisis de estilos de referencia | Ficha `references.v1.json` con 6 enlaces **sin verificar**. No mide nada. | no verificado | **Sí, la parte medible**: sobre vídeos aportados legítimamente, medir duración, cortes por minuto, sonoridad, proporción de voz, y si hay texto en los 2 primeros segundos. El motor de análisis ya calcula casi todo eso para el bruto propio. Sin descargar reels de terceros. |

## 4. Dos módulos, una base común

```text
CONTENT STUDIO
├── Compartido
│   ├── Perfiles de marca (brands.v1.json): vocabulario, límites, aspecto, sonoridad, requisitos de aprobación
│   ├── Cola de trabajos, agente de render, almacenamiento por marca (brands/<marca>/…)
│   ├── QC medido del MP4 final
│   └── Versiones, aprobación ligada al SHA256, auditoría, permisos por marca
├── Real Video Editor  (existe)      entrada: grabación → análisis → director → EDL → FFmpeg
└── Motion Creator     (este diseño) entrada: guion + datos → storyboard aprobado → escenas → render
```

Separación estricta:
- **Tipo de trabajo distinto** (`motion`, frente a `produce` y `revise`) y **carpeta propia** (`motion_engine/`). El
  director, el EDL y el render actuales no se tocan.
- **Documento propio**: `motion.spec/1` (lista de escenas con texto, datos, duración y transición), validado por
  esquema igual que el EDL. Una pieza de motion nunca finge ser un EDL de metraje.
- **Misma salida**: MP4 1080×1920 H.264/AAC en la tabla de versiones de siempre, de modo que revisión, descarga,
  aprobación y borrado funcionan sin código nuevo.
- **Pestaña propia en la web** («Crear gráfic»), para que el equipo no confunda «editar lo que he grabado» con
  «crear una pieza desde un texto».

## 5. Formatos propuestos (hipótesis hasta validarlos contigo)

### 5.1 Blau de Mar — explicativos elegantes
| Formato | Qué es | Dato que exige |
|---|---|---|
| `blau_steps` | 3–5 pasos de un ritual o cuidado, una idea por tarjeta, fondo neutro y un detalle fotográfico propio | texto revisado por personal cualificado |
| `blau_faq` | Pregunta frecuente real y respuesta en 2–3 tarjetas | la pregunta ha de ser real |
| `blau_treatment` | Ficha de un servicio: qué es, para quién, cuánto dura la sesión | sin promesas de resultado; `claims_review` siempre |
| `blau_myth` | «Mite / realitat» en dos tiempos | fuente de la afirmación |
| `blau_gift` | Tarjeta regalo o experiencia (Navidad) | **solo ofertas aprobadas**: campo obligatorio con la referencia de la oferta |

Tono: pocos elementos, tipografía grande, movimiento lento (entradas por opacidad y desplazamiento corto), sin
destellos ni contadores. Nada que parezca generado por IA ni que retoque piel.

### 5.2 Top House — gráficos inmobiliarios
| Formato | Qué es | Dato que exige |
|---|---|---|
| `top_property_card` | Ficha del inmueble sobre fotos propias: precio, superficie, habitaciones, zona | `property_permission` + cada cifra con su origen |
| `top_compare` | «Què pots comprar al Maresme per X €»: 2–3 inmuebles reales comparados | permiso y precio contrastado de cada uno |
| `top_process` | Línea de tiempo: pasos para vender o valorar | ninguno sensible |
| `top_market_stat` | Un dato de mercado grande con contexto | **fuente y fecha obligatorias**, visibles en pantalla |
| `top_owner_tip` | Consejo para propietarios en 3 tarjetas con cierre de valoración | `claims_review` |

Nunca: direcciones identificables, planos o vistas generados, datos de operaciones privadas. Si una imagen es
generada, rótulo visible obligatorio.

### 5.3 Qué se comparte del perfil de marca
Hay que **ampliar `brands.v1.json`** con paleta completa, tipografías con licencia, logotipo y márgenes. Hoy solo hay
un color de acento provisional por marca: sin brand kit real, Motion Creator saldría con identidad inventada. Es el
primer requisito, antes que cualquier motor.

### 5.4 Controles de calidad añadidos para motion
Además del QC actual: tamaño mínimo de letra, contraste texto/fondo, tiempo de lectura por tarjeta (que dé tiempo a
leerla), texto dentro de zonas seguras, toda cifra con fuente y fecha, y aviso si la pieza no tiene audio (permitido,
pero decidido a conciencia). La aprobación reutiliza la lista existente y añade «he comprobado todas las cifras».

## 6. Motor de render: opciones

| Opción | A favor | En contra | Licencia |
|---|---|---|---|
| **A. FFmpeg + libass + imágenes** (lo ya instalado) | Cero dependencias nuevas; mismo editor al núvol | Animación limitada; maquetar es laborioso | ya cubierta |
| **B. HyperFrames** | HTML/CSS: maquetación y tipografía de calidad; pensado para automatizar | Añade Node 22 y Chrome sin interfaz al editor; renders más lentos; hay que probarlo en GitHub Actions | Apache-2.0 |
| **C. Remotion** | Ecosistema grande, muchas plantillas | Licencia según plantilla de la empresa; React; mismo coste técnico que B | propia; de pago por encima de 3 empleados |

Recomendación: **B**, con una prueba acotada antes de decidir (un formato por marca, medir tiempo de render y
aspecto). **C solo** si confirmas que la entidad que lo usará tiene 3 empleados o menos, o si decides pagar la
licencia. **A** como alternativa si no quieres añadir Chrome al editor: suficiente para tarjetas sobrias, que es
justo el tono de las dos marcas.

## 7. Condiciones para empezar a implementar

1. Los tres clips reales (`BLAU_01`, `BLAU_02`, `TOP_01`) pasan las pruebas de aceptación del editor de vídeo real.
2. Brand kit de ambas marcas confirmado (colores, tipografías con licencia, logotipos).
3. Tu autorización expresa para instalar el motor elegido en §6.
4. Para Remotion, además: número de empleados de la entidad usuaria.

Orden cuando se cumplan: esquema `motion.spec/1` y validador → un formato por marca (`blau_steps`,
`top_property_card`) → QC de texto → pestaña web → resto de formatos según uso real.

## 8. Lo que no se hará
- Copiar plantillas, tipografías, sonidos, textos o estilos reconocibles de Blackdark ni de ningún otro creador.
- Comprar el paquete o instalar su código sin tu autorización y sin leer su licencia.
- Generar voces, avatares o imágenes de inmuebles sin consentimiento y sin rotularlo.
- Añadir música sin licencia comercial verificada.
