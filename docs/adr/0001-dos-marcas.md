# ADR 0001 — Dos marcas sobre el mismo estudio (11-11-2026)

## Qué cambia
El estudio de Blau de Mar pasa a servir también a Top House. Cada subida, trabajo y versión lleva una columna
`brand`; los objetos nuevos de R2 se guardan bajo `brands/<marca>/`; la ficha de cada marca vive en
`creative_engine/brands.v1.json` (`brand_style_v1`) y la leen tanto el motor Python como el Worker.

## Por qué
El briefing pide dos identidades con activos, presets y reglas separados, sin reconstruir. El Worker, la cola,
el agente y el render ya funcionaban; duplicar el despliegue habría duplicado mantenimiento y coste de atención.

## Alternativas descartadas
- **Dos Workers + dos buckets**: aislamiento más fuerte, pero doble despliegue, doble Access y doble editor.
  Sigue siendo posible más adelante: las claves R2 ya van prefijadas por marca.
- **Marca como «estilo»**: no separa permisos ni listas; un miembro de un equipo vería vídeos del otro.

## Permisos
- `OWNER_EMAIL`: ve y aprueba las dos marcas.
- `TEAM_EMAILS`: quién entra. `BRAND_MEMBERS` (secreto, JSON): qué marca ve cada correo, p. ej.
  `{"top_house":"agente@ejemplo.cat","blau_de_mar":"equipo@ejemplo.cat"}`.
- Quien no aparece en `BRAND_MEMBERS` solo ve Blau de Mar: es el comportamiento que ya tenía el equipo actual.

## Estados: correspondencia con el briefing
| Briefing | Estudio |
|---|---|
| uploaded | upload `uploaded` |
| analyzed / storyboard_ready / approved_for_render / rendering / quality_check | job `processing`, campo `stage` |
| ready_for_review | variant `needs_approval` (o `needs_review` si el QC falla) |
| approved | variant `approved` (ligada al SHA256) |
| exported | descarga del MP4; no hay estado propio |
| failed / cancelled | job `failed`; variant `rejected` |
No se renombra nada para no invalidar los datos existentes. `approved_for_render` no existe: hoy se renderiza
sin aprobación previa del guion (pendiente, Fase 2).

## Riesgos
- Worker nuevo sobre D1 sin migrar ⇒ error en todas las consultas con `brand`.
- Editor antiguo (rama anterior en GitHub Actions) con Worker nuevo ⇒ los vídeos de Top House se rechazan
  al subir la versión (estilo de otra marca). Los de Blau siguen funcionando.
- Aspecto de marca provisional: puede publicarse con colores no oficiales si nadie lo revisa. La interfaz lo avisa.

## Despliegue (NO ejecutado; requiere tu permiso)
```bash
cd cloudflare
npx wrangler d1 export blau-tiktok-v3 --remote --output=backup-antes-0003.sql
npx wrangler d1 execute blau-tiktok-v3 --remote --file=migrations/0003_brands.sql
npx wrangler secret put BRAND_MEMBERS
npx wrangler deploy
```
Además, `GITHUB_REF` en `wrangler.jsonc` debe apuntar a la rama que contenga este cambio para que el editor
al núvol use el motor nuevo.

## Rollback
Volver a desplegar el Worker anterior. La columna `brand` y los objetos bajo `brands/` no molestan al código
antiguo (lee las claves desde D1). No hay que revertir la migración.
