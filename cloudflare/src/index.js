/** Blau de Mar TikTok Studio V4 · Cloudflare Workers Free + D1 + R2 privado + Access.
 *
 * - Toda ruta de usuario exige JWT de Cloudflare Access verificado (firma, aud, iss, exp) + allowlist opcional.
 * - El agente local usa HTTPS saliente con Service Token de Access + AGENT_TOKEN propio.
 * - Un trabajo produce 0..N variantes; cada variante tiene EDL, QC medido, SHA256, portada y aprobación propia.
 * - El vídeo nunca se procesa en el Worker. Nada se publica: la aprobación solo marca el hash exacto.
 */
import { createRemoteJWKSet, jwtVerify } from 'jose';
import styleData from '../../creative_engine/styles.v4.json' with { type: 'json' };

const VERSION = '4.0.0';
const PART = 8 * 1024 * 1024;
const MAX_NAME = 180;
const LEASE_MS = 30 * 60 * 1000;
const MAX_ATTEMPTS = 3;
const STYLES = new Map(styleData.profiles.map((s) => [s.id, s]));
const APPROVAL_ITEMS = ['team_consent', 'client_consent', 'claims_review', 'licensed_music', 'before_after_evidence',
  'trend_source', 'comment_text', 'captions_reviewed'];
const jwksCache = new Map();

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
const fail = (status, message) => { throw new HttpError(status, message); };
const json = (obj, status = 200) => Response.json(obj, { status, headers: { 'Cache-Control': 'no-store' } });
const now = () => Date.now();
const randomId = () => crypto.randomUUID().replaceAll('-', '');
const parse = (s, fallback = null) => { try { return s ? JSON.parse(s) : fallback; } catch { return fallback; } };
function filename(n) { return String(n ?? '').split(/[\\/]/).pop().replace(/[^\w .()À-ÿ-]/g, '_').slice(0, MAX_NAME); }
async function bodyJSON(req, max = 256 * 1024) {
  const text = await req.text();
  if (text.length > max) fail(413, 'Petició massa gran');
  try { return text ? JSON.parse(text) : {}; } catch { fail(400, 'JSON requerit'); }
}
function timingSafeEqual(a, b) {
  const x = new TextEncoder().encode(String(a)), y = new TextEncoder().encode(String(b));
  if (x.length !== y.length) return false;
  let r = 0; for (let i = 0; i < x.length; i++) r |= x[i] ^ y[i];
  return r === 0;
}
async function audit(env, actor, action, target, detail) {
  await env.DB.prepare('INSERT INTO audit(at,actor,action,target,detail) VALUES(?,?,?,?,?)')
    .bind(now(), actor, action, target ?? null, detail ? JSON.stringify(detail).slice(0, 2000) : null).run();
}

// ------------------------------------------------------------------ identidad
const emails = (v) => String(v || '').toLowerCase().split(/[,\s]+/).map((x) => x.trim()).filter(Boolean);
function jwksFor(env, team) {
  // ACCESS_JWKS_URL solo se acepta apuntando a localhost (pruebas E2E con `wrangler dev`); en producción se ignora.
  const local = String(env.ACCESS_JWKS_URL || '');
  const url = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?\//.test(local) ? local : `https://${team}/cdn-cgi/access/certs`;
  let jwks = jwksCache.get(url);
  if (!jwks) { jwks = createRemoteJWKSet(new URL(url)); jwksCache.set(url, jwks); }
  return jwks;
}
async function who(req, env) {
  if (!env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD || String(env.ACCESS_AUD).startsWith('REPLACE_')) fail(503, 'Cloudflare Access no configurat');
  const token = req.headers.get('Cf-Access-Jwt-Assertion');
  if (!token) fail(401, 'Inicia sessió amb Cloudflare Access');
  const team = env.ACCESS_TEAM_DOMAIN.replace(/^https?:\/\//, '').replace(/\/$/, '');
  let payload;
  try {
    ({ payload } = await jwtVerify(token, jwksFor(env, team), { audience: env.ACCESS_AUD, issuer: `https://${team}` }));
  } catch { fail(401, 'Sessió no vàlida o caducada. Torna a entrar.'); }
  const email = String(payload.email ?? '').toLowerCase().trim();
  if (!email || !email.includes('@')) fail(403, 'Sense correu verificat');
  const owners = emails(env.OWNER_EMAIL);
  const team_ = emails(env.TEAM_EMAILS);
  const role = owners.includes(email) ? 'owner' : 'editor';
  // Defensa en profundidad: si hi ha llista d'equip, ningú fora d'ella entra encara que Access ho permeti.
  if (role !== 'owner' && team_.length && !team_.includes(email)) fail(403, 'Aquest correu no forma part de l’equip');
  return { email, role };
}
function requireOwnerRole(user) { if (user.role !== 'owner') fail(403, 'Només la propietària pot fer això'); }
function assertCanSee(row, user) { if (!row || (user.role !== 'owner' && row.owner !== user.email)) fail(404, 'No trobat'); }
function requireAgent(req, env) {
  const s = req.headers.get('Authorization') ?? '';
  if (!env.AGENT_TOKEN || String(env.AGENT_TOKEN).length < 32 || !s.startsWith('Bearer ') || !timingSafeEqual(s.slice(7), env.AGENT_TOKEN))
    fail(401, 'Agent no autoritzat');
}

// ------------------------------------------------------------------ R2 privado con Range (Safari iOS lo exige)
async function serveObject(req, env, key, { type = 'video/mp4', download = null } = {}) {
  const head = await env.BUCKET.head(key);
  if (!head) fail(404, 'Fitxer no disponible');
  const size = head.size;
  const headers = new Headers({ 'Content-Type': head.httpMetadata?.contentType || type, 'Cache-Control': 'private, no-store',
    'Accept-Ranges': 'bytes', 'X-Content-Type-Options': 'nosniff' });
  if (download) headers.set('Content-Disposition', `attachment; filename="${download}"`);
  const range = req.headers.get('Range');
  const m = range && /^bytes=(\d*)-(\d*)$/.exec(range.trim());
  if (m && (m[1] || m[2])) {
    let start, end;
    if (m[1] === '') { const n = Math.min(Number(m[2]), size); start = size - n; end = size - 1; }
    else { start = Number(m[1]); end = m[2] ? Math.min(Number(m[2]), size - 1) : size - 1; }
    if (!(start >= 0 && start <= end && start < size)) {
      headers.set('Content-Range', `bytes */${size}`);
      return new Response(null, { status: 416, headers });
    }
    headers.set('Content-Range', `bytes ${start}-${end}/${size}`);
    headers.set('Content-Length', String(end - start + 1));
    if (req.method === 'HEAD') return new Response(null, { status: 206, headers });
    const obj = await env.BUCKET.get(key, { range: { offset: start, length: end - start + 1 } });
    return new Response(obj.body, { status: 206, headers });
  }
  headers.set('Content-Length', String(size));
  if (req.method === 'HEAD') return new Response(null, { status: 200, headers });
  const obj = await env.BUCKET.get(key);
  return new Response(obj.body, { status: 200, headers });
}
const looksLikeVideo = (buf) => {
  // MP4/MOV: caja ISO BMFF al inicio (ftyp, o átomos QuickTime antiguos).
  const tag = new TextDecoder().decode(new Uint8Array(buf.slice(4, 8)));
  return ['ftyp', 'wide', 'moov', 'mdat', 'free', 'skip', 'pnot'].includes(tag);
};

// ------------------------------------------------------------------ subidas
const getUpload = (env, id) => env.DB.prepare('SELECT * FROM uploads WHERE id=?').bind(id).first();
const getJob = (env, id) => env.DB.prepare('SELECT * FROM jobs WHERE id=?').bind(id).first();
const getVariant = (env, id) => env.DB.prepare('SELECT * FROM variants WHERE id=?').bind(id).first();

async function beginUpload(req, env, user) {
  const b = await bodyJSON(req);
  const name = filename(b.filename);
  const size = Number(b.size_bytes);
  const max = Number(env.MAX_UPLOAD_BYTES || 4294967296);
  if (!name || !/\.(mp4|mov|m4v)$/i.test(name)) fail(422, 'Només vídeos MP4/MOV');
  if (!Number.isSafeInteger(size) || size < 1024 || size > max) fail(413, `Mida no permesa (màxim ${Math.round(max / 1073741824)} GB)`);
  const limit = Number(env.UPLOADS_PER_HOUR || 40);
  const recent = await env.DB.prepare('SELECT COUNT(*) AS n FROM uploads WHERE owner=? AND created_at>?').bind(user.email, now() - 3600000).first();
  if (recent.n >= limit) fail(429, 'Massa pujades en una hora. Espera una mica.');
  const id = randomId();
  const key = `originals/${id}/${name}`;
  const multi = await env.BUCKET.createMultipartUpload(key, { httpMetadata: { contentType: /\.mov$/i.test(name) ? 'video/quicktime' : 'video/mp4' } });
  await env.DB.prepare('INSERT INTO uploads (id,owner,filename,size_bytes,r2_key,multipart_id,status,created_at,consent_team) VALUES (?,?,?,?,?,?,?,?,?)')
    .bind(id, user.email, name, size, key, multi.uploadId, 'uploading', now(), b.consent_team ? 1 : 0).run();
  await audit(env, user.email, 'upload_started', id, { size });
  return json({ id, chunk_size: PART, total_parts: Math.ceil(size / PART) });
}
async function uploadPart(req, env, user, id, partNo) {
  const row = await getUpload(env, id); assertCanSee(row, user);
  if (row.status !== 'uploading') fail(409, 'Pujada ja finalitzada');
  const count = Math.ceil(row.size_bytes / PART);
  if (!Number.isInteger(partNo) || partNo < 1 || partNo > count) fail(400, 'Part no vàlida');
  const expected = Math.min(PART, row.size_bytes - (partNo - 1) * PART);
  const declared = req.headers.get('Content-Length');
  if (declared && Number(declared) !== expected) fail(422, 'Mida de part incorrecta');
  const chunk = await req.arrayBuffer();
  if (chunk.byteLength !== expected) fail(422, 'Part incompleta');
  if (partNo === 1 && !looksLikeVideo(chunk)) fail(415, 'El fitxer no sembla un vídeo MP4/MOV real');
  const uploaded = await env.BUCKET.resumeMultipartUpload(row.r2_key, row.multipart_id).uploadPart(partNo, chunk);
  await env.DB.prepare('INSERT INTO upload_parts(upload_id,part_no,etag,size_bytes) VALUES(?,?,?,?) ON CONFLICT(upload_id,part_no) DO UPDATE SET etag=excluded.etag,size_bytes=excluded.size_bytes')
    .bind(id, partNo, uploaded.etag, expected).run();
  return json({ part_no: partNo, ok: true });
}
async function finalizeUpload(env, user, id) {
  const row = await getUpload(env, id); assertCanSee(row, user);
  if (row.status === 'uploaded') return json({ id, status: 'uploaded' });
  if (row.status !== 'uploading') fail(409, 'Estat no vàlid');
  const { results } = await env.DB.prepare('SELECT part_no,etag,size_bytes FROM upload_parts WHERE upload_id=? ORDER BY part_no').bind(id).all();
  if (results.length !== Math.ceil(row.size_bytes / PART) || results.reduce((a, b) => a + b.size_bytes, 0) !== row.size_bytes)
    fail(422, 'Falten parts del vídeo');
  await env.BUCKET.resumeMultipartUpload(row.r2_key, row.multipart_id).complete(results.map((p) => ({ partNumber: p.part_no, etag: p.etag })));
  await env.DB.prepare("UPDATE uploads SET status='uploaded',completed_at=? WHERE id=? AND status='uploading'").bind(now(), id).run();
  await env.DB.prepare('DELETE FROM upload_parts WHERE upload_id=?').bind(id).run();
  await audit(env, user.email, 'upload_completed', id);
  return json({ id, status: 'uploaded' });
}
function jobOptions(b) {
  const o = {};
  if (b.comment_text) o.comment_text = String(b.comment_text).slice(0, 200);
  if (b.trend_source?.url) o.trend_source = { url: String(b.trend_source.url).slice(0, 400), date: String(b.trend_source.date || '').slice(0, 20) };
  const n = Number(b.max_candidates || 4);
  o.max_candidates = Number.isInteger(n) && n >= 1 && n <= 8 ? n : 4;
  return o;
}
async function createJob(req, env, user, uid) {
  const row = await getUpload(env, uid); assertCanSee(row, user);
  if (row.status !== 'uploaded') fail(409, 'Acaba primer la pujada');
  const b = await bodyJSON(req);
  const mode = b.mode || 'automatic';
  if (!['automatic', 'real', 'creative'].includes(mode)) fail(422, 'Mode no vàlid');
  const style = b.style || 'auto';
  if (!STYLES.has(style)) fail(422, 'Estil no vàlid');
  const language = b.language || 'ca';
  if (!['ca', 'es'].includes(language)) fail(422, 'Idioma no vàlid');
  const dup = await env.DB.prepare("SELECT id,status FROM jobs WHERE upload_id=? AND kind='produce' AND style=? AND language=? AND status IN ('queued','processing')")
    .bind(uid, style, language).first();
  if (dup) return json({ id: dup.id, status: dup.status, reused: true });
  const id = randomId();
  await env.DB.prepare('INSERT INTO jobs(id,upload_id,owner,mode,style,language,options,kind,status,stage,progress,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)')
    .bind(id, uid, row.owner, mode, style, language, JSON.stringify(jobOptions(b)), 'produce', 'queued', 'queued', 0, now(), now()).run();
  await audit(env, user.email, 'job_created', id, { style, language });
  return json({ id, status: 'queued' }, 201);
}

// ------------------------------------------------------------------ trabajos y variantes (usuaria)
function publicVariant(v, full = false) {
  const out = { id: v.id, job_id: v.job_id, upload_id: v.upload_id, idx: v.idx, version: v.version, parent_variant_id: v.parent_variant_id,
    title: v.title, style: v.style, style_label: STYLES.get(v.style)?.label_ca || v.style, status: v.status, sha256: v.sha256,
    explanation: v.explanation, score_total: v.score_total, risks: parse(v.risks, []), requires: parse(v.requires, []),
    duration: v.duration, has_preview: !!v.r2_key && ['needs_approval', 'needs_review', 'approved', 'rejected'].includes(v.status),
    has_poster: !!v.poster_key, approved_at: v.approved_at, approved_by: v.approved_by, review_note: v.review_note,
    created_at: v.created_at };
  const qc = parse(v.qc, null);
  out.qc = qc ? { status: qc.status, checks: qc.checks, captions: qc.captions } : null;
  if (full) { out.qc_full = qc; out.approval_checklist = parse(v.approval_checklist, null); }
  return out;
}
function publicJob(j, upload) {
  return { id: j.id, upload_id: j.upload_id, filename: upload?.filename, owner: j.owner, kind: j.kind, status: j.status,
    style: j.style, style_label: STYLES.get(j.style)?.label_ca || j.style, language: j.language, stage: j.stage, progress: j.progress,
    message: j.message, error: j.error, instruction: j.instruction, parent_variant_id: j.parent_variant_id,
    created_at: j.created_at, updated_at: j.updated_at, finished_at: j.finished_at, summary: parse(j.summary, null) };
}
async function listJobs(env, user) {
  const base = `SELECT j.*, u.filename FROM jobs j JOIN uploads u ON u.id=j.upload_id`;
  const q = user.role === 'owner' ? env.DB.prepare(`${base} ORDER BY j.created_at DESC LIMIT 100`)
    : env.DB.prepare(`${base} WHERE j.owner=? ORDER BY j.created_at DESC LIMIT 100`).bind(user.email);
  const { results } = await q.all();
  const ids = results.map((j) => j.id);
  const variants = new Map();
  if (ids.length) {
    const marks = ids.map(() => '?').join(',');
    const { results: vs } = await env.DB.prepare(`SELECT id,job_id,status,title,score_total,poster_key FROM variants WHERE job_id IN (${marks}) ORDER BY idx`).bind(...ids).all();
    for (const v of vs) { if (!variants.has(v.job_id)) variants.set(v.job_id, []); variants.get(v.job_id).push({ id: v.id, status: v.status, title: v.title, score_total: v.score_total, has_poster: !!v.poster_key }); }
  }
  return json({ items: results.map((j) => ({ ...publicJob(j, j), variants: variants.get(j.id) || [] })) });
}
async function jobDetail(env, user, id) {
  const j = await getJob(env, id); assertCanSee(j, user);
  const u = await getUpload(env, j.upload_id);
  const { results } = await env.DB.prepare('SELECT * FROM variants WHERE job_id=? ORDER BY idx').bind(id).all();
  return json({ ...publicJob(j, u), variants: results.map((v) => publicVariant(v)) });
}
async function retryJob(env, user, id) {
  const j = await getJob(env, id); assertCanSee(j, user);
  if (!['failed', 'needs_review'].includes(j.status)) fail(409, 'Només es poden reintentar treballs fallits o en revisió');
  await env.DB.prepare("UPDATE jobs SET status='queued',stage='queued',progress=0,error=NULL,message=NULL,attempts=0,lease_until=NULL,updated_at=? WHERE id=?").bind(now(), id).run();
  await audit(env, user.email, 'job_retry', id);
  return json({ id, status: 'queued' });
}
async function variantDetail(env, user, id) {
  const v = await getVariant(env, id); assertCanSee(v, user);
  const edlObj = v.edl_key ? await env.BUCKET.get(v.edl_key) : null;
  return json({ ...publicVariant(v, true), edl: edlObj ? await edlObj.json() : null });
}
function srtTime(t) {
  const ms = Math.max(0, Math.round(Number(t) * 1000));
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return `${p(Math.floor(ms / 3600000))}:${p(Math.floor(ms / 60000) % 60)}:${p(Math.floor(ms / 1000) % 60)},${p(ms % 1000, 3)}`;
}
async function variantSrt(env, user, id) {
  // Subtítols del muntatge en SRT: per acabar a CapCut/Premiere sense tornar a transcriure.
  const v = await getVariant(env, id); assertCanSee(v, user);
  const edlObj = v.edl_key ? await env.BUCKET.get(v.edl_key) : null;
  if (!edlObj) fail(404, 'Sense EDL');
  const edl = await edlObj.json();
  const events = edl.captions?.events || [];
  const body = events.map((e, i) => `${i + 1}\n${srtTime(e.start)} --> ${srtTime(e.end)}\n${String(e.text).replace(/\r/g, '')}\n`).join('\n');
  return new Response(body, { headers: { 'Content-Type': 'application/x-subrip; charset=utf-8', 'Cache-Control': 'private, no-store',
    'Content-Disposition': `attachment; filename="blau-${id.slice(0, 8)}-v${v.version}.srt"` } });
}
async function approve(req, env, user, id) {
  requireOwnerRole(user);
  const v = await getVariant(env, id); assertCanSee(v, user);
  if (v.status !== 'needs_approval') fail(409, 'Aquesta versió no espera aprovació');
  const b = await bodyJSON(req);
  if (b.confirm !== true || !timingSafeEqual(String(b.sha256 || ''), v.sha256 || '')) fail(409, 'Confirma el hash exacte del fitxer que has revisat');
  const required = new Set([...parse(v.requires, []), 'team_consent', 'client_consent', 'captions_reviewed']);
  const checklist = b.checklist || {};
  const missing = [...required].filter((k) => APPROVAL_ITEMS.includes(k) && checklist[k] !== true);
  if (missing.length) fail(422, 'Falta confirmar: ' + missing.join(', '));
  const r = await env.DB.prepare("UPDATE variants SET status='approved',approved_by=?,approved_sha256=?,approved_at=?,approval_checklist=?,updated_at=? WHERE id=? AND status='needs_approval' AND sha256=?")
    .bind(user.email, v.sha256, now(), JSON.stringify(checklist), now(), id, v.sha256).run();
  if (!r.meta?.changes) fail(409, 'La versió ha canviat; torna-la a revisar');
  await audit(env, user.email, 'variant_approved', id, { sha256: v.sha256, checklist });
  return json({ status: 'approved', sha256: v.sha256, published: false });
}
async function reject(req, env, user, id) {
  const v = await getVariant(env, id); assertCanSee(v, user);
  if (!['needs_approval', 'needs_review'].includes(v.status)) fail(409, 'Aquesta versió no està pendent');
  const b = await bodyJSON(req);
  await env.DB.prepare("UPDATE variants SET status='rejected',reviewed_by=?,review_note=?,updated_at=? WHERE id=?")
    .bind(user.email, String(b.reason || '').slice(0, 300) || null, now(), id).run();
  await audit(env, user.email, 'variant_rejected', id, { reason: b.reason });
  return json({ status: 'rejected' });
}
async function revise(req, env, user, id, manual) {
  const v = await getVariant(env, id); assertCanSee(v, user);
  if (manual) requireOwnerRole(user);
  if (!v.edl_key) fail(409, 'Aquesta versió no té EDL editable');
  const up = await getUpload(env, v.upload_id);
  if (up?.status !== 'uploaded') fail(409, 'L’original ja s’ha esborrat: no es poden fer versions noves');
  const b = await bodyJSON(req, 512 * 1024);
  let instruction = null, edits = null;
  if (manual) {
    edits = {};
    if (Array.isArray(b.segments)) edits.segments = b.segments.slice(0, 120).map((s) => ({ in: Number(s.in), out: Number(s.out) }));
    if (Array.isArray(b.captions)) edits.captions = b.captions.slice(0, 300).map((c) => ({ start: Number(c.start), end: Number(c.end), text: String(c.text || '').slice(0, 140) }));
    if (['none', 'phrase', 'words'].includes(b.caption_mode)) edits.caption_mode = b.caption_mode;
    if (!Object.keys(edits).length) fail(422, 'Cap canvi');
  } else {
    instruction = String(b.instruction || '').trim().slice(0, 500);
    if (instruction.length < 3) fail(422, 'Escriu què vols canviar');
  }
  const j = await getJob(env, v.job_id);
  const jid = randomId();
  await env.DB.prepare('INSERT INTO jobs(id,upload_id,owner,mode,style,language,options,kind,status,stage,progress,parent_variant_id,instruction,manual_edits,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)')
    .bind(jid, v.upload_id, v.owner, j?.mode || 'automatic', v.style, j?.language || 'ca', j?.options || null, 'revise', 'queued', 'queued', 0, id,
      instruction, edits ? JSON.stringify(edits) : null, now(), now()).run();
  await audit(env, user.email, manual ? 'variant_edited' : 'variant_revision_requested', id, { job: jid, instruction });
  return json({ id: jid, status: 'queued' }, 201);
}
async function deleteObjects(env, keys) {
  const list = keys.filter(Boolean);
  for (let i = 0; i < list.length; i += 900) await env.BUCKET.delete(list.slice(i, i + 900));
}
async function deleteOriginalOnly(env, user, u) {
  // Allibera espai R2 (la quota gratuïta és de 10 GB): esborra l'original i l'anàlisi, conserva les versions.
  if (u.status !== 'uploaded') fail(409, 'L’original no està disponible');
  await deleteObjects(env, [u.r2_key, u.analysis_key, u.analysis_key && u.analysis_key.replace(/\.json$/, '.summary.json')]);
  await env.DB.prepare("UPDATE uploads SET status='original_deleted',analysis_key=NULL WHERE id=?").bind(u.id).run();
  await audit(env, user.email, 'original_deleted', u.id);
  return json({ deleted: true, kept_renders: true });
}
async function deleteUpload(env, user, id, keepRenders = false) {
  const u = await getUpload(env, id); assertCanSee(u, user);
  if (keepRenders) return deleteOriginalOnly(env, user, u);
  const { results: vs } = await env.DB.prepare('SELECT id,r2_key,poster_key,edl_key,output_multipart_id,status FROM variants WHERE upload_id=?').bind(id).all();
  for (const v of vs) if (v.status === 'uploading' && v.output_multipart_id && v.r2_key) {
    try { await env.BUCKET.resumeMultipartUpload(v.r2_key, v.output_multipart_id).abort(); } catch { /* ja tancat */ }
  }
  if (u.status === 'uploading') { try { await env.BUCKET.resumeMultipartUpload(u.r2_key, u.multipart_id).abort(); } catch { /* ja tancat */ } }
  await deleteObjects(env, [u.r2_key, u.analysis_key, u.analysis_key && u.analysis_key.replace(/\.json$/, '.summary.json'),
    ...vs.flatMap((v) => [v.r2_key, v.poster_key, v.edl_key])]);
  const { results: js } = await env.DB.prepare('SELECT id,r2_key FROM jobs WHERE upload_id=?').bind(id).all();
  await deleteObjects(env, js.map((j) => j.r2_key));
  await env.DB.batch([
    env.DB.prepare('DELETE FROM variant_parts WHERE variant_id IN (SELECT id FROM variants WHERE upload_id=?)').bind(id),
    env.DB.prepare('DELETE FROM variants WHERE upload_id=?').bind(id),
    env.DB.prepare('DELETE FROM job_output_parts WHERE job_id IN (SELECT id FROM jobs WHERE upload_id=?)').bind(id),
    env.DB.prepare('DELETE FROM jobs WHERE upload_id=?').bind(id),
    env.DB.prepare('DELETE FROM upload_parts WHERE upload_id=?').bind(id),
    env.DB.prepare('DELETE FROM uploads WHERE id=?').bind(id),
  ]);
  await audit(env, user.email, 'upload_deleted_gdpr', id, { variants: vs.length, jobs: js.length });
  return json({ deleted: true, variants: vs.length, jobs: js.length });
}
async function uploadAnalysis(env, user, id) {
  const u = await getUpload(env, id); assertCanSee(u, user);
  if (!u.analysis_key) return json({ available: false });
  const obj = await env.BUCKET.get(u.analysis_key.replace(/\.json$/, '.summary.json'));
  return obj ? new Response(obj.body, { headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } }) : json({ available: false });
}

// ------------------------------------------------------------------ agente local
async function claim(env) {
  const t = now();
  await env.DB.prepare("UPDATE jobs SET status='failed',error='L’ordinador editor s’ha aturat massa vegades amb aquest vídeo',stage='failed',updated_at=? WHERE status='processing' AND lease_until<? AND attempts>=?")
    .bind(t, t, MAX_ATTEMPTS).run();
  const agentId = randomId();
  const j = await env.DB.prepare("UPDATE jobs SET status='processing',stage='claimed',progress=1,message='L’ordinador editor ha agafat el vídeo',lease_until=?,agent_id=?,attempts=attempts+1,updated_at=? WHERE id=(SELECT id FROM jobs WHERE status='queued' OR (status='processing' AND lease_until<?) ORDER BY created_at LIMIT 1) RETURNING *")
    .bind(t + LEASE_MS, agentId, t, t).first();
  if (!j) return json({ job: null });
  // Restos de un intento anterior interrumpido: se descartan para no duplicar variantes.
  const { results: stale } = await env.DB.prepare("SELECT id,r2_key,output_multipart_id,poster_key,edl_key FROM variants WHERE job_id=? AND status='uploading'").bind(j.id).all();
  for (const v of stale) {
    if (v.output_multipart_id) { try { await env.BUCKET.resumeMultipartUpload(v.r2_key, v.output_multipart_id).abort(); } catch { /* */ } }
    await deleteObjects(env, [v.poster_key, v.edl_key]);
    await env.DB.batch([env.DB.prepare('DELETE FROM variant_parts WHERE variant_id=?').bind(v.id), env.DB.prepare('DELETE FROM variants WHERE id=?').bind(v.id)]);
  }
  const u = await getUpload(env, j.upload_id);
  let parent = null;
  if (j.parent_variant_id) {
    const pv = await getVariant(env, j.parent_variant_id);
    const edlObj = pv?.edl_key ? await env.BUCKET.get(pv.edl_key) : null;
    parent = pv ? { id: pv.id, version: pv.version, idx: pv.idx, edl: edlObj ? await edlObj.json() : null } : null;
  }
  const { results: done } = await env.DB.prepare("SELECT COUNT(*) AS n FROM variants WHERE job_id=? AND status!='uploading'").bind(j.id).all();
  return json({ job: { id: j.id, kind: j.kind, upload_id: j.upload_id, filename: u?.filename, size_bytes: u?.size_bytes, mode: j.mode,
    style: j.style || 'auto', language: j.language || 'ca', options: parse(j.options, {}), instruction: j.instruction,
    manual_edits: parse(j.manual_edits, null), parent, analysis_available: !!u?.analysis_key, lease_until: t + LEASE_MS,
    agent_id: agentId, attempt: j.attempts, variants_done: done[0]?.n || 0 } });
}
async function agentJob(req, env, id) {
  const j = await getJob(env, id);
  if (!j || j.status !== 'processing') fail(404, 'El treball ja no està en procés');
  const agent = req.headers.get('X-Agent-Id');
  if (agent && j.agent_id && agent !== j.agent_id) fail(409, 'Un altre agent té aquest treball');
  return j;
}
async function progress(req, env, id) {
  await agentJob(req, env, id);
  const b = await bodyJSON(req);
  const stage = String(b.stage || 'processing').slice(0, 30);
  const pct = Math.max(0, Math.min(99, Math.round(Number(b.progress) || 0)));
  await env.DB.prepare("UPDATE jobs SET stage=?,progress=?,message=?,lease_until=?,updated_at=? WHERE id=? AND status='processing'")
    .bind(stage, pct, String(b.message || '').slice(0, 200), now() + LEASE_MS, now(), id).run();
  return json({ ok: true, lease_until: now() + LEASE_MS });
}
async function agentSource(req, env, id) {
  const j = await agentJob(req, env, id);
  const u = await getUpload(env, j.upload_id);
  if (!u || u.status !== 'uploaded') fail(404, 'Original no disponible');
  return serveObject(req, env, u.r2_key, { type: 'application/octet-stream' });
}
async function putAnalysis(req, env, id) {
  const j = await agentJob(req, env, id);
  const b = await bodyJSON(req, 40 * 1024 * 1024);
  if (!b.full || !b.summary) fail(422, 'Falten dades d’anàlisi');
  const key = `analysis/${j.upload_id}.json`;
  await env.BUCKET.put(key, JSON.stringify(b.full), { httpMetadata: { contentType: 'application/json' } });
  await env.BUCKET.put(key.replace(/\.json$/, '.summary.json'), JSON.stringify(b.summary), { httpMetadata: { contentType: 'application/json' } });
  await env.DB.prepare('UPDATE uploads SET analysis_key=? WHERE id=?').bind(key, j.upload_id).run();
  return json({ ok: true });
}
async function getAnalysis(req, env, id) {
  const j = await agentJob(req, env, id);
  const u = await getUpload(env, j.upload_id);
  const obj = u?.analysis_key ? await env.BUCKET.get(u.analysis_key) : null;
  if (!obj) fail(404, 'Sense anàlisi desada');
  return new Response(obj.body, { headers: { 'Content-Type': 'application/json' } });
}
async function startVariant(req, env, id) {
  const j = await agentJob(req, env, id);
  const b = await bodyJSON(req, 8 * 1024 * 1024);
  const size = Number(b.size_bytes);
  if (!Number.isSafeInteger(size) || size < 1 || size > 2 * 1024 * 1024 * 1024) fail(422, 'Mida de vídeo no vàlida');
  if (!b.edl || !Array.isArray(b.edl.segments)) fail(422, 'EDL requerit');
  if (b.style && !STYLES.has(b.style)) fail(422, 'Estil no vàlid');
  const vid = randomId();
  const key = `renders/${j.upload_id}/${vid}.mp4`;
  const edlKey = `edl/${j.upload_id}/${vid}.json`;
  await env.BUCKET.put(edlKey, JSON.stringify(b.edl), { httpMetadata: { contentType: 'application/json' } });
  const mpu = await env.BUCKET.createMultipartUpload(key, { httpMetadata: { contentType: 'video/mp4' } });
  let idx = Number(b.idx) || 0, version = Number(b.version) || 1, parentId = null;
  if (j.parent_variant_id) {
    const pv = await getVariant(env, j.parent_variant_id);
    if (pv) { idx = pv.idx; version = (pv.version || 1) + 1; parentId = pv.id; }
  }
  await env.DB.prepare('INSERT INTO variants(id,job_id,upload_id,owner,idx,version,parent_variant_id,title,style,status,r2_key,edl_key,output_multipart_id,size_bytes,explanation,score_total,risks,requires,duration,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)')
    .bind(vid, id, j.upload_id, j.owner, idx, version, parentId, String(b.title || '').slice(0, 120), b.style || j.style, 'uploading', key, edlKey, mpu.uploadId, size,
      String(b.explanation || '').slice(0, 1500), Number.isFinite(b.score_total) ? Math.round(b.score_total) : null,
      JSON.stringify((b.risks || []).slice(0, 20)), JSON.stringify((b.requires || []).filter((x) => APPROVAL_ITEMS.includes(x))),
      Number(b.edl.duration) || null, now(), now()).run();
  return json({ variant_id: vid, chunk_size: PART }, 201);
}
async function agentVariant(req, env, vid) {
  const v = await getVariant(env, vid);
  if (!v || v.status !== 'uploading') fail(404, 'Variant no en pujada');
  await agentJob(req, env, v.job_id);
  return v;
}
async function variantPart(req, env, vid, partNo) {
  const v = await agentVariant(req, env, vid);
  const count = Math.ceil(v.size_bytes / PART);
  if (!Number.isInteger(partNo) || partNo < 1 || partNo > count) fail(422, 'Número de part no vàlid');
  const expected = Math.min(PART, v.size_bytes - (partNo - 1) * PART);
  const chunk = await req.arrayBuffer();
  if (chunk.byteLength !== expected) fail(422, 'Mida de part incorrecta');
  const part = await env.BUCKET.resumeMultipartUpload(v.r2_key, v.output_multipart_id).uploadPart(partNo, chunk);
  await env.DB.prepare('INSERT INTO variant_parts(variant_id,part_no,etag,size_bytes) VALUES(?,?,?,?) ON CONFLICT(variant_id,part_no) DO UPDATE SET etag=excluded.etag,size_bytes=excluded.size_bytes')
    .bind(vid, partNo, part.etag, chunk.byteLength).run();
  return json({ part_no: partNo });
}
async function variantPoster(req, env, vid) {
  const v = await agentVariant(req, env, vid);
  const buf = await req.arrayBuffer();
  const b = new Uint8Array(buf);
  if (buf.byteLength < 100 || buf.byteLength > 3 * 1024 * 1024 || b[0] !== 0xff || b[1] !== 0xd8) fail(422, 'Portada JPEG no vàlida');
  const key = `posters/${v.upload_id}/${vid}.jpg`;
  await env.BUCKET.put(key, buf, { httpMetadata: { contentType: 'image/jpeg' } });
  await env.DB.prepare('UPDATE variants SET poster_key=?,updated_at=? WHERE id=?').bind(key, now(), vid).run();
  return json({ ok: true });
}
async function finishVariant(req, env, vid) {
  const v = await agentVariant(req, env, vid);
  const b = await bodyJSON(req, 512 * 1024);
  if (!/^[0-9a-f]{64}$/.test(String(b.sha256 || ''))) fail(422, 'sha256 requerit');
  if (!b.qc || !['pass', 'fail'].includes(b.qc.status)) fail(422, 'Informe QC requerit');
  const { results } = await env.DB.prepare('SELECT part_no,etag,size_bytes FROM variant_parts WHERE variant_id=? ORDER BY part_no').bind(vid).all();
  const count = Math.ceil(v.size_bytes / PART);
  if (results.length !== count || results.some((p, i) => p.part_no !== i + 1) || results.reduce((a, p) => a + p.size_bytes, 0) !== v.size_bytes)
    fail(422, 'Falten parts del vídeo');
  await env.BUCKET.resumeMultipartUpload(v.r2_key, v.output_multipart_id).complete(results.map((p) => ({ partNumber: p.part_no, etag: p.etag })));
  const ok = b.qc.status === 'pass' && b.qc.decode_ok === true && b.qc.audio_present === true;
  await env.DB.prepare('UPDATE variants SET status=?,sha256=?,qc=?,output_multipart_id=NULL,updated_at=? WHERE id=?')
    .bind(ok ? 'needs_approval' : 'needs_review', b.sha256, JSON.stringify(b.qc).slice(0, 60000), now(), vid).run();
  await env.DB.prepare('DELETE FROM variant_parts WHERE variant_id=?').bind(vid).run();
  return json({ status: ok ? 'needs_approval' : 'needs_review' });
}
async function completeJob(req, env, id) {
  const j = await agentJob(req, env, id);
  const b = await bodyJSON(req, 512 * 1024);
  const { results } = await env.DB.prepare("SELECT status FROM variants WHERE job_id=? AND status!='uploading'").bind(id).all();
  const status = results.length ? 'done' : 'needs_review';
  const reason = String(b.reason || (results.length ? '' : 'Cap proposta: el material no té prou història')).slice(0, 600) || null;
  await env.DB.prepare("UPDATE jobs SET status=?,stage=?,progress=100,message=?,error=?,summary=?,finished_at=?,lease_until=NULL,updated_at=? WHERE id=? AND status='processing'")
    .bind(status, status, results.length ? `${results.length} proposta(es) per revisar` : null, status === 'needs_review' ? reason : null,
      b.summary ? JSON.stringify(b.summary).slice(0, 20000) : null, now(), now(), id).run();
  await audit(env, 'agent', 'job_' + status, id, { variants: results.length, kind: j.kind });
  return json({ status });
}
async function failJob(req, env, id) {
  await agentJob(req, env, id);
  const b = await bodyJSON(req);
  await env.DB.prepare("UPDATE jobs SET status='failed',stage='failed',error=?,lease_until=NULL,updated_at=? WHERE id=? AND status='processing'")
    .bind(String(b.error || 'Error desconegut').slice(0, 600), now(), id).run();
  await audit(env, 'agent', 'job_failed', id, { error: String(b.error || '').slice(0, 200) });
  return json({ status: 'failed' });
}

// ------------------------------------------------------------------ router
async function agentRouter(req, env, p, m) {
  requireAgent(req, env);
  if (m === 'POST' && p === '/api/agent/claim') return claim(env);
  let x = p.match(/^\/api\/agent\/jobs\/([0-9a-f]{32})\/(progress|source|analysis|variants|complete|fail)$/);
  if (x) {
    const [, id, action] = x;
    if (m === 'POST' && action === 'progress') return progress(req, env, id);
    if (m === 'GET' && action === 'source') return agentSource(req, env, id);
    if (m === 'PUT' && action === 'analysis') return putAnalysis(req, env, id);
    if (m === 'GET' && action === 'analysis') return getAnalysis(req, env, id);
    if (m === 'POST' && action === 'variants') return startVariant(req, env, id);
    if (m === 'POST' && action === 'complete') return completeJob(req, env, id);
    if (m === 'POST' && action === 'fail') return failJob(req, env, id);
  }
  x = p.match(/^\/api\/agent\/variants\/([0-9a-f]{32})\/(parts\/(\d+)|poster|finish)$/);
  if (x) {
    if (m === 'PUT' && x[3]) return variantPart(req, env, x[1], Number(x[3]));
    if (m === 'PUT' && x[2] === 'poster') return variantPoster(req, env, x[1]);
    if (m === 'POST' && x[2] === 'finish') return finishVariant(req, env, x[1]);
  }
  fail(404, 'Ruta d’agent desconeguda');
}

async function router(req, env) {
  const u = new URL(req.url), p = u.pathname, m = req.method;
  if (p === '/api/health') return json({ status: 'ok', version: VERSION, paid_ai: false, autopublish: false });
  if (p.startsWith('/api/agent/')) return agentRouter(req, env, p, m);
  const user = await who(req, env);
  // Evita peticions creuades amb la cookie d'Access.
  if (!['GET', 'HEAD', 'OPTIONS'].includes(m)) {
    const origin = req.headers.get('Origin');
    if (origin && origin !== u.origin) fail(403, 'Petició d’un altre origen denegada');
  }
  if (m === 'GET' && p === '/api/me') return json(user);
  if (m === 'GET' && p === '/api/config') return json({ version: VERSION, part_size: PART, max_upload_bytes: Number(env.MAX_UPLOAD_BYTES || 4294967296),
    styles: [...STYLES.values()].map((s) => ({ id: s.id, label: s.label_ca || s.label, intent: s.intent_ca || s.intent, requires: s.render?.requires || [] })) });
  if (m === 'GET' && p === '/api/audit') {
    requireOwnerRole(user);
    const { results } = await env.DB.prepare('SELECT * FROM audit ORDER BY id DESC LIMIT 300').all();
    return json({ items: results });
  }
  if (m === 'POST' && p === '/api/uploads') return beginUpload(req, env, user);
  let x = p.match(/^\/api\/uploads\/([0-9a-f]{32})(?:\/(parts\/(\d+)|finalize|render|jobs|analysis))?$/);
  if (x) {
    const id = x[1], action = x[2];
    if (m === 'GET' && !action) {
      const row = await getUpload(env, id); assertCanSee(row, user);
      const { results } = await env.DB.prepare('SELECT part_no FROM upload_parts WHERE upload_id=?').bind(id).all();
      return json({ id, status: row.status, filename: row.filename, uploaded_parts: results.map((r) => r.part_no), size_bytes: row.size_bytes });
    }
    if (m === 'DELETE' && !action) return deleteUpload(env, user, id, u.searchParams.get('keep_renders') === '1');
    if (m === 'PUT' && action?.startsWith('parts/')) return uploadPart(req, env, user, id, Number(x[3]));
    if (m === 'POST' && action === 'finalize') return finalizeUpload(env, user, id);
    if (m === 'POST' && (action === 'render' || action === 'jobs')) return createJob(req, env, user, id);
    if (m === 'GET' && action === 'analysis') return uploadAnalysis(env, user, id);
  }
  if (m === 'GET' && p === '/api/jobs') return listJobs(env, user);
  x = p.match(/^\/api\/jobs\/([0-9a-f]{32})(?:\/(retry))?$/);
  if (x) {
    if (m === 'GET' && !x[2]) return jobDetail(env, user, x[1]);
    if (m === 'POST' && x[2] === 'retry') return retryJob(env, user, x[1]);
  }
  x = p.match(/^\/api\/variants\/([0-9a-f]{32})(?:\/(preview|download|poster|approve|reject|revise|edit|subtitles\.srt))?$/);
  if (x) {
    const id = x[1], action = x[2];
    if (m === 'GET' && !action) return variantDetail(env, user, id);
    if (m === 'GET' && action === 'subtitles.srt') return variantSrt(env, user, id);
    if (['GET', 'HEAD'].includes(m) && ['preview', 'download', 'poster'].includes(action)) {
      const v = await getVariant(env, id); assertCanSee(v, user);
      if (action === 'poster') { if (!v.poster_key) fail(404, 'Sense portada'); return serveObject(req, env, v.poster_key, { type: 'image/jpeg' }); }
      if (!v.r2_key || v.status === 'uploading') fail(404, 'Vista prèvia no disponible');
      return serveObject(req, env, v.r2_key, { download: action === 'download' ? `blau-${id.slice(0, 8)}-v${v.version}.mp4` : null });
    }
    if (m === 'POST' && action === 'approve') return approve(req, env, user, id);
    if (m === 'POST' && action === 'reject') return reject(req, env, user, id);
    if (m === 'POST' && action === 'revise') return revise(req, env, user, id, false);
    if (m === 'POST' && action === 'edit') return revise(req, env, user, id, true);
  }
  fail(404, 'No trobat');
}

// ------------------------------------------------------------------ mantenimiento (Cron Trigger)
export async function maintenance(env) {
  const t = now();
  const report = { aborted_uploads: 0, aborted_variants: 0, failed_jobs: 0 };
  const { results: ups } = await env.DB.prepare("SELECT id,r2_key,multipart_id FROM uploads WHERE status='uploading' AND created_at<?").bind(t - 48 * 3600000).all();
  for (const u of ups) {
    try { await env.BUCKET.resumeMultipartUpload(u.r2_key, u.multipart_id).abort(); } catch { /* */ }
    await env.DB.batch([env.DB.prepare('DELETE FROM upload_parts WHERE upload_id=?').bind(u.id), env.DB.prepare("DELETE FROM uploads WHERE id=? AND status='uploading'").bind(u.id)]);
    report.aborted_uploads++;
  }
  const { results: vs } = await env.DB.prepare("SELECT id,r2_key,output_multipart_id,edl_key,poster_key FROM variants WHERE status='uploading' AND updated_at<?").bind(t - 6 * 3600000).all();
  for (const v of vs) {
    try { await env.BUCKET.resumeMultipartUpload(v.r2_key, v.output_multipart_id).abort(); } catch { /* */ }
    await deleteObjects(env, [v.edl_key, v.poster_key]);
    await env.DB.batch([env.DB.prepare('DELETE FROM variant_parts WHERE variant_id=?').bind(v.id), env.DB.prepare('DELETE FROM variants WHERE id=?').bind(v.id)]);
    report.aborted_variants++;
  }
  const r = await env.DB.prepare("UPDATE jobs SET status='failed',stage='failed',error='L’ordinador editor no ha pogut acabar aquest vídeo',updated_at=? WHERE status='processing' AND lease_until<? AND attempts>=?")
    .bind(t, t, MAX_ATTEMPTS).run();
  report.failed_jobs = r.meta?.changes || 0;
  const days = Number(env.REJECTED_RETENTION_DAYS || 0);
  if (days > 0) {
    const { results: old } = await env.DB.prepare("SELECT id,r2_key,poster_key,edl_key FROM variants WHERE status='rejected' AND updated_at<?").bind(t - days * 86400000).all();
    await deleteObjects(env, old.flatMap((v) => [v.r2_key, v.poster_key, v.edl_key]));
    for (const v of old) await env.DB.prepare("UPDATE variants SET status='purged',r2_key=NULL,poster_key=NULL,edl_key=NULL,updated_at=? WHERE id=?").bind(t, v.id).run();
    report.purged_rejected = old.length;
  }
  await audit(env, 'cron', 'maintenance', null, report);
  return report;
}

export default {
  async fetch(req, env) {
    try {
      const { pathname } = new URL(req.url);
      if (pathname.startsWith('/api/')) return await router(req, env);
      // Los estáticos quedan protegidos por la aplicación de Cloudflare Access sobre todo el hostname.
      return await env.ASSETS.fetch(req);
    } catch (e) {
      if (e instanceof HttpError) return json({ error: e.message }, e.status);
      console.error('worker_error', e?.stack || String(e));
      return json({ error: 'Error del servidor' }, 500);
    }
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(maintenance(env));
  },
};
