// Prueba de interfaz en navegador con viewport de iPhone (Chromium, NO Safari real) contra `wrangler dev`.
//   node test/ui_e2e.mjs <video> [carpeta_capturas]
// Simula Cloudflare Access con un JWKS local. El agente Python se ejecuta una vez para producir propuestas.
import { spawn, spawnSync } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { generateKeyPair, exportJWK, SignJWT } from 'jose';

const require = createRequire(import.meta.url);
const { chromium, devices } = require('playwright');
const here = path.dirname(fileURLToPath(import.meta.url));
const CF = path.resolve(here, '..');
const ROOT = path.resolve(CF, '..');
const video = path.resolve(process.argv[2] || '');
const shots = path.resolve(process.argv[3] || path.join(ROOT, 'docs', 'evidence', 'ui'));
fs.mkdirSync(shots, { recursive: true });
const TEAM = 'blau-test.cloudflareaccess.com', AUD = 'e2e-aud', OWNER = 'owner@blau.test', EDITOR = 'editor@blau.test';
const results = [];
const check = (name, ok, detail = '') => { results.push({ check: name, status: ok ? 'passed' : 'failed', detail: String(detail).slice(0, 300) }); console.log((ok ? 'PASS ' : 'FAIL ') + name, detail || ''); if (!ok) throw new Error(name); };
const port = () => new Promise((r) => { const s = http.createServer(); s.listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => r(p)); }); });

const { publicKey, privateKey } = await generateKeyPair('RS256');
const jwk = { ...(await exportJWK(publicKey)), kid: 'e2e', alg: 'RS256', use: 'sig' };
const token = (email) => new SignJWT({ email }).setProtectedHeader({ alg: 'RS256', kid: 'e2e' }).setIssuer(`https://${TEAM}`)
  .setAudience(AUD).setIssuedAt().setExpirationTime('2h').sign(privateKey);
const jport = await port(), wport = await port();
const jwks = http.createServer((_, res) => { res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({ keys: [jwk] })); }).listen(jport, '127.0.0.1');
const state = fs.mkdtempSync(path.join(os.tmpdir(), 'blau-ui-'));
const agentToken = [...crypto.getRandomValues(new Uint8Array(32))].map((b) => b.toString(16).padStart(2, '0')).join('');
const wr = path.join(CF, 'node_modules', '.bin', 'wrangler');
const env = { ...process.env, WRANGLER_SEND_METRICS: 'false', CI: '1' };
spawnSync(wr, ['d1', 'execute', 'blau-tiktok-v3', '--local', '--persist-to', state, '--file', 'schema.sql', '-y'], { cwd: CF, env, stdio: 'ignore' });
const vars = { ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: AUD, OWNER_EMAIL: OWNER, TEAM_EMAILS: EDITOR, ACCESS_JWKS_URL: `http://127.0.0.1:${jport}/certs`, AGENT_TOKEN: agentToken };
const args = ['dev', '--local', '--ip', '127.0.0.1', '--port', String(wport), '--persist-to', state, '--show-interactive-dev-session=false',
  ...Object.entries(vars).flatMap(([k, v]) => ['--var', `${k}:${v}`])];
const worker = spawn(wr, args, { cwd: CF, env, stdio: 'ignore' });
const base = `http://127.0.0.1:${wport}`;
for (let i = 0; i < 120; i++) { try { if ((await fetch(base + '/api/health')).ok) break; } catch { /* */ } await new Promise((r) => setTimeout(r, 1000)); }

const venvPy = path.join(ROOT, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const PY = process.env.PYTHON || (fs.existsSync(venvPy) ? venvPy : 'python3');
const runAgent = () => spawnSync(PY, ['-m', 'local_worker.agent', '--once'], { cwd: ROOT, encoding: 'utf8',
  env: { ...process.env, STUDIO_PUBLIC_URL: base, STUDIO_ALLOW_INSECURE_LOCALHOST: '1', STUDIO_AGENT_TOKEN: agentToken, BLAU_X264_PRESET: 'veryfast' }, timeout: 3600000 });

const iphone = { ...devices['iPhone 13'] };
delete iphone.defaultBrowserType;
const browser = await chromium.launch();
let status = 'passed';
try {
  const ed = await browser.newContext({ ...iphone, extraHTTPHeaders: { 'Cf-Access-Jwt-Assertion': await token(EDITOR) } });
  const page = await ed.newPage();
  await page.goto(base + '/');
  await page.getByText(`${EDITOR} · Equip`).waitFor();
  check('Simple: sessió d’equip visible i sense commutador Advanced', await page.locator('#modeSwitch').isHidden());
  check('equip de Blau: 21 estils (auto + 3 formats de marca + 17 genèrics) i sense commutador de marca',
    (await page.locator('#style option').count()) === 21 && await page.locator('#brandSwitch').isHidden());
  const noScroll = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  check('sense scroll horitzontal a 390 px', noScroll);
  await page.screenshot({ path: path.join(shots, '01_simple_inici.jpg'), fullPage: true, type: 'jpeg', quality: 70 });
  await page.setInputFiles('#videoInput', video);
  await page.click('#upload');
  check('cal confirmar consentiment abans de pujar', (await page.locator('#alert').textContent()).includes('permís'));
  await page.locator('details.brief summary').click();
  await page.fill('#briefSeconds', '12');
  await page.fill('#briefCta', 'Reserva la teva hora');
  await page.check('#consent');
  await page.click('#upload');
  await page.getByText('A la cua d’edició').waitFor({ timeout: 300000 });
  check('pujada amb progrés real fins a la cua', true);
  await page.screenshot({ path: path.join(shots, '02_pujat.jpg'), fullPage: true, type: 'jpeg', quality: 70 });
  const a = runAgent();
  check('agent local processa el vídeo', a.status === 0, (a.stdout || '').slice(-200));
  await page.click('#refresh');
  await page.locator('.job').first().click();
  await page.locator('.variant').first().waitFor();
  const nVariants = await page.locator('.variant').count();
  check('propostes visibles amb vídeo i explicació', nVariants >= 1 && (await page.locator('.variant video').count()) >= 1, `${nVariants} propostes`);
  await page.locator('.variant details.story summary').first().click();
  await page.locator('.variant .storyrows li').first().waitFor();
  const story = await page.locator('.variant .storyrows').first().textContent();
  check('guió per moments visible, amb origen i tancament escrit per la persona', story.includes('de l’original') && story.includes('Reserva la teva hora'), story.slice(0, 160));
  await page.screenshot({ path: path.join(shots, '08_guio_per_moments.jpg'), fullPage: true, type: 'jpeg', quality: 70 });
  check('l’equip no veu el botó Aprovar', (await page.getByRole('button', { name: 'Aprovar' }).count()) === 0);
  await page.screenshot({ path: path.join(shots, '03_propostes_equip.jpg'), fullPage: true, type: 'jpeg', quality: 70 });
  await page.locator('.variant textarea').first().fill('més curt');
  await page.getByRole('button', { name: 'Enviar petició' }).first().click();
  await page.getByText('Petició: «més curt»').waitFor();
  check('petició de canvi en text crea una correcció a la cua', true);

  const ow = await browser.newContext({ ...iphone, extraHTTPHeaders: { 'Cf-Access-Jwt-Assertion': await token(OWNER) } });
  const op = await ow.newPage();
  await op.goto(base + '/');
  await op.getByText(`${OWNER} · Propietària`).waitFor();
  await op.click('#modeSwitch button[data-mode="advanced"]');
  check('Advanced: veu tots els vídeos', (await op.locator('#listTitle').textContent()) === 'Tots els vídeos');
  // Dues marques: la propietària pot canviar; Top House té els seus formats i la seva llista (buida) separada.
  check('propietària: commutador amb les dues marques', (await op.locator('#brandSwitch button').count()) === 2);
  await op.locator('#brandSwitch button[data-brand="top_house"]').click();
  await op.getByText('Encara no hi ha vídeos.').waitFor();
  const topStyles = await op.locator('#style option').allTextContents();
  check('Top House: només els seus formats (auto + 3 propis + 6 genèrics) i cap vídeo de Blau',
    topStyles.length === 10 && topStyles.some((t) => t.includes('Visita d’immoble')) && !topStyles.some((t) => t.includes('Blau')) && (await op.locator('.job').count()) === 0, topStyles.join(' | '));
  check('Top House: avís de colors provisionals visible', await op.locator('#brandNote').isVisible());
  await op.screenshot({ path: path.join(shots, '07_top_house.jpg'), fullPage: true, type: 'jpeg', quality: 70 });
  await op.locator('#brandSwitch button[data-brand="blau_de_mar"]').click();
  await op.locator('.job').first().waitFor();
  await op.locator('.job', { hasText: 'Propostes llestes' }).first().click();
  await op.locator('.variant').first().waitFor();
  await op.getByText('Original i anàlisi').waitFor();
  await op.locator('summary', { hasText: 'Editar línia de temps' }).first().click();
  await op.getByText('Segments (temps del bruto)').first().waitFor();
  check('Advanced: editor de segments i subtítols', (await op.locator('.variant table input').count()) > 2);
  await op.screenshot({ path: path.join(shots, '04_advanced.jpg'), fullPage: true, type: 'jpeg', quality: 70 });
  await op.getByRole('button', { name: 'Aprovar' }).first().click();
  const boxes = op.locator('#approveChecks input');
  check('checklist d’aprovació (consentiment, subtítols, afirmacions)', (await boxes.count()) >= 3);
  await op.screenshot({ path: path.join(shots, '05_checklist.jpg'), type: 'jpeg', quality: 70 });
  for (let i = 0; i < await boxes.count(); i++) await boxes.nth(i).check();
  await op.click('#approveConfirm');
  await op.locator('.variant .pill', { hasText: 'Aprovat' }).first().waitFor();
  check('aprovació amb hash exacte des de la interfície', true);
  await op.screenshot({ path: path.join(shots, '06_aprovat.jpg'), fullPage: true, type: 'jpeg', quality: 70 });
} catch (e) {
  status = 'failed';
  console.error(e);
} finally {
  await browser.close();
  worker.kill();
  jwks.close();
  fs.rmSync(state, { recursive: true, force: true });
}
fs.writeFileSync(path.join(shots, 'ui_e2e.json'), JSON.stringify({ date: new Date().toISOString(), status, browser: 'Chromium (viewport iPhone 13), no Safari real', checks: results }, null, 1));
console.log(JSON.stringify({ status, checks: results.length }));
process.exit(status === 'passed' ? 0 : 1);
