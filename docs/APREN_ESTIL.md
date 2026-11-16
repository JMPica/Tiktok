# «Aprèn l'estil» (V4.2.0)

Crea un estil nou a partir de **2–8 vídeos de referència acabats** (preferiblement vostres). El programa **mesura** el
ritme i el converteix en un estil editable que després es tria a l'app com qualsevol altre.

## Què mesura (i què no)
| Mesura (senyal real, en local) | Com s'usa |
|---|---|
| Durada de cada vídeo | durada ideal i màxima de les peces |
| Talls per 10 s i durada mitjana del pla | durada objectiu dels plans; zoom alterns suau si el ritme és ràpid (≥5 talls/10 s) |
| Pauses (silencis) més llargues | pausa màxima que es conserva al muntatge |
| Parlat o no (silencis, àudio) | si l'estil exigeix diàleg o és opcional |
| Música probable | s'avisa; **mai es copia** (només àudio original) |
| Entrevista (opcions): subtítols paraula/frase/cap, color natural/punchy/premium | es copien tal qual |

**No** mesura ni copia: humor, guió, veu, cares, frases, música, identitat de ningú. No es desa transcripció ni fotogrames:
la fitxa (`learned_styles/learned_<nom>.json`) només té números + l'explicació de cada decisió, i es pot editar a mà.
Un estil après **no pot treure** requisits d'aprovació (consentiment, claims) ni publica res sol.

## Com usar-ho
1. A l'**ordinador editor** (el de `01_INSTALAR`/`01_PREPARAR`), posa 3–6 vídeos a la carpeta `estil_referencies/`.
2. Windows: doble clic a `07_APRENDRE_ESTIL_WINDOWS.cmd`. Mac: `macos/07_APRENDRE_ESTIL_MAC.command`. Escriu el nom.
3. L'script crea la fitxa i, si l'ordinador ja està configurat (`02_CONFIGURAR`), la **registra al servei**: només els números.
4. A l'app apareix a la llista d'estils amb «(après)». Advanced → «Estils apresos» permet esborrar-lo.
Línia d'ordres equivalent: `python -m creative_engine.style_learn A.mp4 B.mp4 C.mp4 --name "Humor de cabina" [--captions words|phrase|none] [--grade natural|punchy|premium|none]` i `python -m local_worker.agent --sync-styles`.

## L'editor al núvol (GitHub Actions)
No veu el teu ordenador: rep la fitxa del servei amb cada treball, la valida i la fa servir. Els vídeos de referència **no** es pugen.

## Estat honest
`implemented` · `tested_unit` (mesura real amb FFmpeg sobre vídeos amb talls coneguts, derivació, validació, integració al director) ·
`tested_e2e_local` (registre per l'agent, validació 422, config, permisos, treball amb estil après fins a l'agent). **No** provat:
amb vídeos de referència reals vostres, ni la qualitat creativa del resultat, ni UI a l'iPhone, ni `deployed` (cal aplicar `cloudflare/migrations/0003_learned_styles.sql` a la D1 remota i redesplegar).
Limitació: els talls es detecten per canvi d'histograma; plans molt semblants poden no comptar-se (subestima el ritme).
