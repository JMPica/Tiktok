# Desplegar en tu Cloudflare (Workers Free + D1 + R2 + Access)

Todo esto se hace **una vez** desde un ordenador con Node 20+. Nada aquí activa pagos; R2 sí puede cobrar
si superas su cuota gratuita (ver «Costes»). Si un paso pide tarjeta o un plan de pago, **para**.

## 1. Recursos
```bash
cd cloudflare
npm install
npx wrangler login
npx wrangler d1 create blau-tiktok-v3          # copia el database_id a wrangler.jsonc
npx wrangler r2 bucket create blau-tiktok-private
```
El bucket queda privado: **no** actives `r2.dev` ni dominio público. El Worker accede por binding interno.

## 2. Base de datos
- **Base nueva:** `npx wrangler d1 execute blau-tiktok-v3 --remote --file=schema.sql`
- **Ya tenías V3 desplegada:** copia de seguridad y migración:
  ```bash
  npx wrangler d1 export blau-tiktok-v3 --remote --output=backup-v3.sql
  npx wrangler d1 execute blau-tiktok-v3 --remote --file=migrations/0001_add_style.sql   # solo si no la aplicaste
  npx wrangler d1 execute blau-tiktok-v3 --remote --file=migrations/0002_v4.sql
  ```

## 3. Secreto del agente
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"   # cópialo solo al siguiente comando y a local_worker/.env
npx wrangler secret put AGENT_TOKEN
```

## 4. Cloudflare Access (obligatorio antes de subir vídeos reales)
1. Despliega una vez para que exista el hostname: `npx wrangler deploy` → `https://blau-tiktok-v3.<tu-subdominio>.workers.dev`.
2. Zero Trust → Access → Applications → **Add application → Self-hosted**. Dominio: ese hostname completo, sin ruta
   (protege web **y** API). (También puedes activar Access desde Workers → tu Worker → Settings → Domains & Routes → workers.dev.)
3. Política **«Equip»**: Action *Allow* · Include *Emails*: los correos exactos del equipo y el tuyo.
4. Política **«Ordinador editor»**: Action *Service Auth* · Include *Service Token* → crea uno en Access → Service credentials →
   Service Tokens. Guarda *Client ID* y *Client Secret* (solo se muestran una vez) para `local_worker/.env`.
5. Copia el **Application Audience (AUD) Tag** de la aplicación y tu **team domain** (`<equipo>.cloudflareaccess.com`).

## 5. Variables y despliegue final
En `wrangler.jsonc` → `vars`:
- `ACCESS_TEAM_DOMAIN`, `ACCESS_AUD`: del paso 4.
- `OWNER_EMAIL`: tu correo (rol propietaria/Advanced; admite varios separados por coma).
- `TEAM_EMAILS`: correos del equipo (doble barrera: aunque Access deje pasar a alguien, el Worker lo rechaza si no está).
- `REJECTED_RETENTION_DAYS`: 0 = nunca borrar automáticamente. Los originales **nunca** se borran solos.

`npx wrangler deploy`. El cron diario (`17 3 * * *`) limpia subidas abandonadas y trabajos atascados.

## 6. Verificación (5 minutos, desde el iPhone)
1. Ventana privada → la URL pide login de Access. Un correo no autorizado **no** entra.
2. Con tu correo: arriba pone «Propietària» y aparece el selector Simple/Advanced. Con el de una compañera: «Equip».
3. `https://…/api/health` (con sesión) devuelve `{"status":"ok","version":"4.0.0"}`.
4. Configura el ordenador (`docs/GUIA_WINDOWS_MAC.md`), sube un vídeo propio consentido, espera las propuestas,
   reprodúcelas en Safari, aprueba una y descárgala.

## Costes (plan Free, consultar precios vigentes antes de activar R2)
- Workers Free: 100.000 peticiones/día. Un vídeo de 1 GB son ~130 peticiones de subida; el agente consulta cada 45 s (~1.900/día).
- D1 Free: muy por encima del uso de este estudio.
- **R2: 10 GB-mes gratis.** Un minuto de 4K HDR del iPhone ocupa ~350–450 MB: con 10 GB caben ~25 min de originales.
  Tras aprobar, usa en Advanced **«Esborrar només l’original»** (conserva las versiones) o el borrado RGPD completo.
  Revisa el uso en el panel de R2 cada semana. https://developers.cloudflare.com/r2/pricing/
