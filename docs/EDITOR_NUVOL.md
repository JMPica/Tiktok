# Editor al núvol (GitHub Actions) — editar sense cap ordinador encès

Quan algú puja un vídeo o demana un canvi, el Worker avisa GitHub. GitHub engega un ordinador temporal
(Ubuntu, 2 nuclis), executa el mateix motor (`local_worker.agent --drain`), puja les propostes i s'apaga.
El Mac/PC continua sent opcional: si està encès, també agafa feina de la mateixa cua.

- **Cost:** 0 €. Repositori privat: 2.000 minuts/mes gratuïts. Un minut de vídeo 4K ≈ 5–8 min d'editor (estimat;
  es mesurarà amb els primers vídeos reals).
- **Privacitat:** el vídeo es processa uns minuts en servidors de GitHub (Microsoft) i s'esborra en acabar.
  Els registres no mostren noms de fitxer ni transcripcions.
- **Seguretat:** cap clau d'agent compartida. El Worker accepta el runner només amb un token OIDC signat per GitHub
  per a `JMPica/Tiktok` i el flux `editor.yml`, i a més cal passar Cloudflare Access amb un Service Token.
- **Cua:** si un avís es perd, el Worker torna a avisar cada 20 minuts mentre hi hagi feina de les últimes 24 h.

## Passos (una sola vegada)
1. **Repositori privat** — github.com/JMPica/Tiktok → *Settings* → *General* → *Danger Zone* → *Change visibility* → *Private*.
2. **Service Token d'Access** — one.dash.cloudflare.com → *Access* → *Service credentials* → *Service Tokens* →
   *Create Service Token* («Editor núvol», *Non-expiring*). Copia *Client ID* i *Client Secret*.
3. **Secrets a GitHub** — al repositori: *Settings* → *Secrets and variables* → *Actions* → *New repository secret*:
   `CF_ACCESS_CLIENT_ID` i `CF_ACCESS_CLIENT_SECRET` amb els valors del pas 2.
4. **Token per engegar l'editor** — github.com/settings/personal-access-tokens/new (*Fine-grained*):
   *Repository access* → *Only select repositories* → `JMPica/Tiktok`; *Permissions* → **Actions: Read and write**;
   caducitat 1 any → *Generate token* i copia'l.
5. **Desa'l al Worker** — dash.cloudflare.com → *Workers & Pages* → `blau-tiktok-v3` → *Settings* →
   *Variables and Secrets* → *Add* → tipus **Secret**, nom `GITHUB_DISPATCH_TOKEN`, valor el token del pas 4.

Cap d'aquests valors s'ha d'enganxar al xat.

## Comprovar
Puja un vídeo curt des de l'iPhone. A github.com/JMPica/Tiktok/actions ha d'aparèixer una execució «editor» en
menys d'un minut, i en uns minuts les propostes a la web. Opcions: variables de repositori `BLAU_WHISPER_MODEL`
(`small` per defecte, `medium` = millor català i més lent) i `BLAU_X264_PRESET` (`faster` per defecte).
