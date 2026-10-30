// Blau de Mar TikTok Studio V4 · interfície iPhone (Simple per a l'equip, Advanced per a la propietària).
// Tot text que ve de l'usuari o del servidor s'insereix amb textContent (sense HTML injectat).
const $ = (id) => document.getElementById(id);
const PART = 8 * 1024 * 1024;
const STATUS = {
  queued: ['En cua · l’editor arrencarà en breu', ''], processing: ['Editant', ''],
  done: ['Propostes llestes', 'ok'], needs_review: ['Cal revisar el material', 'warn'], failed: ['Error', 'bad'],
  needs_approval: ['Per aprovar', ''], approved: ['Aprovat', 'ok'], rejected: ['Descartat', 'bad'], uploading: ['Pujant', ''],
};
const STAGES = { claimed: 'Preparant', downloading: 'Descarregant', analyzing: 'Analitzant imatge i so', transcribing: 'Transcrivint',
  saving_analysis: 'Desant anàlisi', directing: 'Triant històries', rendering: 'Muntant', qc: 'Control de qualitat', uploading: 'Pujant resultats' };
const CHECKS = {
  team_consent: 'Les persones de l’equip que surten hi estan d’acord',
  client_consent: 'No surt cap client identificable, o tinc el seu consentiment per escrit',
  captions_reviewed: 'He revisat els subtítols i diuen exactament el que se sent',
  claims_review: 'Les afirmacions sobre tractaments són certes i verificables (sense promeses mèdiques)',
  licensed_music: 'Si hi ha música, té llicència comercial per a TikTok',
  before_after_evidence: 'L’abans/després és real, comparable i sense retocs',
  trend_source: 'La tendència té font i data i encara és vigent',
  comment_text: 'El comentari respost és real i autoritzat',
};
let me = null, config = null, mode = 'simple', currentJob = null, timer = null;

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class') n.className = v; else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else if (k === 'text') n.textContent = v; else n.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) n.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return n;
}
function show(msg) { $('alert').hidden = !msg; $('alert').textContent = msg || ''; if (msg) $('alert').scrollIntoView({ behavior: 'smooth', block: 'center' }); }
async function api(path, opts = {}) {
  const r = await fetch('/api' + path, { credentials: 'same-origin', cache: 'no-store', ...opts });
  if (!r.ok) {
    let e; try { e = await r.json(); } catch { /* */ }
    if (r.status === 401) throw new Error('La sessió ha caducat. Recarrega la pàgina per tornar a entrar.');
    throw new Error(e?.error || `Error ${r.status}`);
  }
  return r;
}
const getJSON = async (p) => (await api(p)).json();
const send = async (p, data = {}, method = 'POST') => (await api(p, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })).json();
const fmtTime = (ms) => new Date(ms).toLocaleString('ca-ES', { dateStyle: 'short', timeStyle: 'short' });
const pill = (status) => { const [t, c] = STATUS[status] || [status, '']; return el('span', { class: 'pill ' + c, text: t }); };

// ------------------------------------------------------------------ arrencada
async function boot() {
  try {
    [me, config] = await Promise.all([getJSON('/me'), getJSON('/config')]);
    $('user').textContent = `${me.email} · ${me.role === 'owner' ? 'Propietària' : 'Equip'}`;
    for (const s of config.styles) if (s.id !== 'auto') $('style').append(el('option', { value: s.id, text: s.label }));
    if (me.role === 'owner') {
      $('modeSwitch').hidden = false;
      try { mode = localStorage.getItem('blau-mode') || 'simple'; } catch { /* */ }
      setMode(mode);
    }
    onStyle();
    await refresh();
  } catch (e) { show('No s’ha pogut iniciar: ' + e.message); }
}
function setMode(m) {
  mode = me?.role === 'owner' ? m : 'simple';
  for (const b of document.querySelectorAll('#modeSwitch button')) b.classList.toggle('on', b.dataset.mode === mode);
  $('auditPanel').hidden = mode !== 'advanced';
  $('listTitle').textContent = mode === 'advanced' ? 'Tots els vídeos' : 'Els meus vídeos';
  try { localStorage.setItem('blau-mode', mode); } catch { /* */ }
  if (currentJob) openJob(currentJob.id);
}
function onStyle() {
  const s = config?.styles.find((x) => x.id === $('style').value);
  $('styleHelp').textContent = s ? s.intent : '';
  $('commentField').hidden = $('style').value !== 'respuesta_comentario';
  $('trendFields').hidden = $('style').value !== 'trend_adaptation';
}

// ------------------------------------------------------------------ pujada reprenible, diversos fitxers
const storeKey = (f) => `blau-up:${f.name}:${f.size}:${f.lastModified}`;
function loadSaved(f) { try { return JSON.parse(localStorage.getItem(storeKey(f)) || 'null'); } catch { return null; } }
function save(f, v) { try { v ? localStorage.setItem(storeKey(f), JSON.stringify(v)) : localStorage.removeItem(storeKey(f)); } catch { /* */ } }

async function uploadAll() {
  const files = [...($('videoInput').files || [])];
  if (!files.length) return show('Tria almenys un vídeo.');
  if (!$('consent').checked) return show('Confirma que les persones que surten han donat permís.');
  show('');
  $('upload').disabled = true;
  const opts = { style: $('style').value, language: $('language').value, comment_text: $('commentText').value || undefined,
    trend_source: $('trendUrl').value ? { url: $('trendUrl').value, date: $('trendDate').value } : undefined };
  try {
    for (const f of files) await uploadOne(f, opts);
    $('videoInput').value = '';
    await refresh();
  } finally { $('upload').disabled = false; }
}
async function uploadOne(f, opts) {
  const bar = el('progress', { max: 100, value: 0 });
  const label = el('div', { class: 'small muted', text: 'Preparant…' });
  const pause = el('button', { class: 'secondary small-btn', type: 'button', text: 'Pausa' });
  let paused = false;
  pause.onclick = () => { paused = !paused; pause.textContent = paused ? 'Continuar' : 'Pausa'; };
  const item = el('div', { class: 'qitem' }, el('div', { class: 'row between' }, el('strong', { text: f.name }), pause), bar, label);
  $('queue').prepend(item);
  try {
    let s = loadSaved(f);
    if (s) {
      try { const x = await getJSON('/uploads/' + s.id); s.parts = x.uploaded_parts; s.status = x.status; }
      catch { s = null; }
    }
    if (!s) {
      const x = await send('/uploads', { filename: f.name, size_bytes: f.size, consent_team: true });
      s = { id: x.id, parts: [], status: 'uploading' };
      save(f, s);
    }
    const total = Math.ceil(f.size / PART);
    let done = s.status === 'uploaded' ? total : s.parts.length;
    const t0 = performance.now(); let sent = 0;
    for (let n = 1; n <= total && s.status === 'uploading'; n++) {
      if (s.parts.includes(n)) continue;
      while (paused) await new Promise((r) => setTimeout(r, 400));
      const chunk = f.slice((n - 1) * PART, Math.min(n * PART, f.size));
      let err = null;
      for (let attempt = 0; attempt < 5; attempt++) {
        try { await api(`/uploads/${s.id}/parts/${n}`, { method: 'PUT', headers: { 'Content-Type': 'application/octet-stream' }, body: chunk }); err = null; break; }
        catch (e) { err = e; if (/no sembla un vídeo|Massa|Mida/.test(e.message)) break; label.textContent = `Reintentant part ${n} (${attempt + 1})…`; await new Promise((r) => setTimeout(r, 1000 * 2 ** attempt)); }
      }
      if (err) throw err;
      s.parts.push(n); save(f, s); done++; sent += chunk.size;
      const pct = Math.round((100 * done) / total);
      const mbps = sent / 1e6 / ((performance.now() - t0) / 1000);
      bar.value = pct; label.textContent = `Pujant ${pct}% · ${mbps.toFixed(1)} MB/s`;
    }
    if (s.status !== 'uploaded') await send(`/uploads/${s.id}/finalize`);
    bar.value = 100;
    const job = await send(`/uploads/${s.id}/jobs`, { mode: 'automatic', ...opts });
    save(f, null);
    pause.remove();
    label.textContent = job.reused ? 'Ja estava a la cua.' : 'Pujat. A la cua d’edició.';
  } catch (e) {
    label.textContent = 'Error: ' + e.message + ' · torna a triar el fitxer per continuar';
    item.classList.add('bad');
  }
}

// ------------------------------------------------------------------ llista de treballs
async function refresh() {
  if (!me) return;
  try {
    const d = await getJSON('/jobs');
    const box = $('jobs'); box.replaceChildren();
    if (!d.items.length) box.append(el('p', { class: 'muted', text: 'Encara no hi ha vídeos.' }));
    const mine = mode === 'advanced' ? d.items : d.items.filter((j) => j.owner === me.email || me.role !== 'owner');
    for (const j of mine) {
      const stage = j.status === 'processing' ? `${STAGES[j.stage] || 'Editant'} · ${j.progress}%` : '';
      const card = el('button', { class: 'job', type: 'button', onclick: () => openJob(j.id) },
        el('div', { class: 'row between' }, el('strong', { text: j.filename || 'Vídeo' }), pill(j.status)),
        el('div', { class: 'small muted', text: `${j.kind === 'revise' ? 'Correcció · ' : ''}${j.style_label} · ${fmtTime(j.created_at)}${mode === 'advanced' ? ' · ' + j.owner : ''}` }),
        j.status === 'processing' ? el('progress', { max: 100, value: j.progress }) : null,
        stage ? el('div', { class: 'small muted', text: stage + (j.message ? ' · ' + j.message : '') }) : null,
        j.status === 'needs_review' || j.status === 'failed' ? el('div', { class: 'small', text: j.error || '' }) : null,
        j.variants.length ? el('div', { class: 'thumbs' }, j.variants.map((v) => v.has_poster
          ? el('img', { src: `/api/variants/${v.id}/poster`, alt: v.title || 'proposta', loading: 'lazy' })
          : el('span', { class: 'pill', text: (STATUS[v.status] || [v.status])[0] }))) : null);
      box.append(card);
    }
    const active = d.items.some((j) => ['queued', 'processing'].includes(j.status));
    clearTimeout(timer); timer = setTimeout(refresh, active ? 6000 : 30000);
    if (currentJob && d.items.some((j) => j.id === currentJob.id && j.updated_at !== currentJob.updated_at)) openJob(currentJob.id, false);
  } catch (e) { show(e.message); }
}

// ------------------------------------------------------------------ detall i propostes
async function openJob(id, scroll = true) {
  try {
    const j = await getJSON('/jobs/' + id);
    currentJob = j;
    $('detail').hidden = false;
    $('detailTitle').textContent = j.filename || 'Propostes';
    const st = $('detailStatus'); st.replaceChildren(pill(j.status));
    if (j.status === 'processing') st.append(' ', `${STAGES[j.stage] || ''} ${j.progress}%`);
    if (j.instruction) st.append(el('div', { class: 'small', text: 'Petició: «' + j.instruction + '»' }));
    if (j.error) st.append(el('div', { text: j.error }));
    if (j.summary?.style_reason) st.append(el('div', { class: 'small', text: 'Estil: ' + j.summary.style_reason }));
    if (j.summary?.transcript_error) st.append(el('div', { class: 'small', text: 'Transcripció no disponible: ' + j.summary.transcript_error }));
    if (['needs_review', 'failed'].includes(j.status)) st.append(retryBox(j));
    const box = $('variants'); box.replaceChildren();
    if (j.status === 'done' && !j.variants.length) box.append(el('p', { class: 'muted', text: 'No hi ha propostes.' }));
    for (const v of j.variants) box.append(variantCard(v));
    const adv = $('advancedUpload');
    adv.hidden = mode !== 'advanced';
    if (mode === 'advanced') renderUploadAdvanced(j);
    if (scroll) $('detail').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) { show(e.message); }
}
function retryBox(j) {
  const sel = el('select', {}, config.styles.map((s) => el('option', { value: s.id, text: s.label, selected: s.id === j.style })));
  return el('div', { class: 'actions' },
    el('button', { class: 'secondary', type: 'button', text: 'Reintentar', onclick: async () => { try { await send(`/jobs/${j.id}/retry`); refresh(); openJob(j.id); } catch (e) { show(e.message); } } }),
    sel,
    el('button', { type: 'button', text: 'Provar aquest estil', onclick: async () => {
      try { await send(`/uploads/${j.upload_id}/jobs`, { style: sel.value, language: j.language }); refresh(); show(''); } catch (e) { show(e.message); } } }));
}
function variantCard(v) {
  const card = el('article', { class: 'variant' });
  card.append(el('div', { class: 'row between' }, el('strong', { text: `${v.title || 'Proposta'} · v${v.version}` }), pill(v.status)));
  card.append(el('div', { class: 'small muted', text: `${v.style_label} · ${v.duration ? v.duration.toFixed(1) + ' s' : ''} · puntuació editorial ${v.score_total ?? '–'}/100 (no és predicció de viralitat)` }));
  if (v.has_preview) {
    card.append(el('video', { controls: true, playsinline: true, preload: 'metadata', src: `/api/variants/${v.id}/preview`,
      poster: v.has_poster ? `/api/variants/${v.id}/poster` : null }));
  }
  if (v.explanation) card.append(el('p', { class: 'small', text: v.explanation }));
  if (v.risks.length) card.append(el('ul', { class: 'risks' }, v.risks.map((r) => el('li', { text: r }))));
  if (v.qc) {
    card.append(el('details', {}, el('summary', { text: `Control de qualitat: ${v.qc.status === 'pass' ? 'correcte' : 'cal revisar'}` }),
      el('ul', { class: 'qc' }, v.qc.checks.map((c) => el('li', { class: c.status, text: `${c.status === 'pass' ? '✓' : c.status === 'warn' ? '!' : '✗'} ${c.check}: ${c.detail}` })))));
  }
  if (v.approved_at) card.append(el('div', { class: 'small', text: `Aprovat per ${v.approved_by} · ${fmtTime(v.approved_at)} · sha256 ${v.sha256.slice(0, 12)}…` }));
  const actions = el('div', { class: 'actions' });
  if (v.has_preview) actions.append(el('button', { class: 'secondary', type: 'button', text: 'Descarregar MP4', onclick: () => window.location.assign(`/api/variants/${v.id}/download`) }));
  if (v.has_preview) actions.append(el('button', { class: 'secondary', type: 'button', text: 'Subtítols .srt (CapCut)', onclick: () => window.location.assign(`/api/variants/${v.id}/subtitles.srt`) }));
  if (v.status === 'needs_approval' && me.role === 'owner') actions.append(el('button', { type: 'button', text: 'Aprovar', onclick: () => approve(v) }));
  if (['needs_approval', 'needs_review'].includes(v.status)) actions.append(el('button', { class: 'danger', type: 'button', text: 'Descartar', onclick: () => rejectV(v) }));
  card.append(actions);
  if (v.status !== 'uploading') {
    const ta = el('textarea', { placeholder: 'Demana un canvi: «més curt», «més divertit», «sense subtítols», canvia "text" per "text correcte"…', maxlength: 500 });
    card.append(el('div', { class: 'adv' }, el('label', { class: 'field', text: 'Demanar una nova versió' }), ta,
      el('div', { class: 'actions' }, el('button', { type: 'button', text: 'Enviar petició', onclick: async () => {
        try { const r = await send(`/variants/${v.id}/revise`, { instruction: ta.value }); ta.value = ''; await refresh(); openJob(r.id); }
        catch (e) { show(e.message); } } }))));
  }
  if (mode === 'advanced') card.append(advancedEditor(v));
  return card;
}
async function rejectV(v) {
  const reason = prompt('Motiu (opcional):') ?? null;
  if (reason === null) return;
  try { await send(`/variants/${v.id}/reject`, { reason }); openJob(v.job_id, false); refresh(); } catch (e) { show(e.message); }
}
function approve(v) {
  const dlg = $('approveDialog');
  $('approveHash').textContent = v.sha256;
  const req = [...new Set(['team_consent', 'client_consent', 'captions_reviewed', ...v.requires])];
  const box = $('approveChecks'); box.replaceChildren();
  for (const k of req) box.append(el('label', { class: 'check' }, el('input', { type: 'checkbox', name: k, required: true }), CHECKS[k] || k));
  dlg.returnValue = '';
  dlg.onclose = async () => {
    if (dlg.returnValue !== 'ok') return;
    const checklist = Object.fromEntries([...box.querySelectorAll('input')].map((i) => [i.name, i.checked]));
    try { await send(`/variants/${v.id}/approve`, { sha256: v.sha256, confirm: true, checklist }); openJob(v.job_id, false); refresh(); }
    catch (e) { show(e.message); }
  };
  dlg.showModal();
}

// ------------------------------------------------------------------ Advanced (propietària)
function advancedEditor(v) {
  const wrap = el('details', { class: 'adv' }, el('summary', { text: 'Editar línia de temps i subtítols (Advanced)' }));
  wrap.addEventListener('toggle', async () => {
    if (!wrap.open || wrap.dataset.loaded) return;
    wrap.dataset.loaded = '1';
    try {
      const d = await getJSON('/variants/' + v.id);
      const edl = d.edl || { segments: [], captions: { events: [] } };
      const segT = el('table', {}, el('tr', {}, el('th', { text: '#' }), el('th', { text: 'Entrada (s)' }), el('th', { text: 'Sortida (s)' }), el('th', {})));
      const addSeg = (s) => {
        const tr = el('tr', {}, el('td', { text: String(segT.rows.length) }),
          el('td', {}, el('input', { type: 'number', step: '0.01', value: s.in })), el('td', {}, el('input', { type: 'number', step: '0.01', value: s.out })),
          el('td', {}, el('button', { class: 'secondary small-btn', type: 'button', text: '✕', onclick: () => tr.remove() })));
        segT.append(tr);
      };
      edl.segments.forEach(addSeg);
      const capT = el('table', {}, el('tr', {}, el('th', { text: 'Inici' }), el('th', { text: 'Fi' }), el('th', { text: 'Text' })));
      for (const c of edl.captions?.events || []) {
        capT.append(el('tr', {}, el('td', {}, el('input', { type: 'number', step: '0.01', value: c.start })),
          el('td', {}, el('input', { type: 'number', step: '0.01', value: c.end })),
          el('td', {}, el('input', { value: String(c.text).replace(/\n/g, ' '), maxlength: 140 }))));
      }
      const capMode = el('select', {}, ['phrase', 'words', 'none'].map((m) => el('option', { value: m, text: { phrase: 'Frases', words: 'Paraula a paraula', none: 'Sense subtítols' }[m], selected: edl.captions?.mode === m })));
      wrap.append(
        el('p', { class: 'small muted', text: `EDL ${edl.schema || ''} · font ${edl.source?.width}x${edl.source?.height} ${edl.source?.fps} fps${edl.source?.hdr ? ' HDR' : ''} · sortida ${edl.output?.fps} (${edl.output?.fps_reason || ''})` }),
        el('h3', { text: 'Segments (temps del bruto)' }), segT,
        el('button', { class: 'secondary small-btn', type: 'button', text: '+ segment', onclick: () => addSeg({ in: 0, out: 1 }) }),
        el('h3', { text: 'Subtítols (temps del muntatge)' }), el('label', { class: 'field', text: 'Mode' }, capMode), capT,
        el('div', { class: 'actions' }, el('button', { type: 'button', text: 'Generar versió nova', onclick: async () => {
          const segments = [...segT.rows].slice(1).map((r) => ({ in: Number(r.cells[1].firstChild.value), out: Number(r.cells[2].firstChild.value) }));
          const captions = [...capT.rows].slice(1).map((r) => ({ start: Number(r.cells[0].firstChild.value), end: Number(r.cells[1].firstChild.value), text: r.cells[2].firstChild.value }));
          try { const r = await send(`/variants/${v.id}/edit`, { segments, captions, caption_mode: capMode.value }); await refresh(); openJob(r.id); }
          catch (e) { show(e.message); } } })),
        d.qc_full ? el('details', {}, el('summary', { text: 'Mesures tècniques' }), el('pre', { class: 'small', text: JSON.stringify(d.qc_full.measured, null, 1) })) : null);
    } catch (e) { wrap.append(el('p', { class: 'alert', text: e.message })); }
  });
  return wrap;
}
async function renderUploadAdvanced(j) {
  const box = $('advancedUpload'); box.replaceChildren(el('h3', { text: 'Original i anàlisi' }));
  try {
    const a = await getJSON(`/uploads/${j.upload_id}/analysis`);
    if (a.available === false) box.append(el('p', { class: 'small muted', text: 'Encara no hi ha anàlisi.' }));
    else {
      const m = a.meta || {};
      box.append(el('p', { class: 'small', text: `${m.width}x${m.height} · ${m.fps} fps${m.vfr ? ' (VFR)' : ''}${m.hdr ? ' · HDR ' + m.color_transfer : ''} · ${m.duration?.toFixed(1)} s · ${a.shots} plans · cares en ${a.face_ratio == null ? '–' : Math.round(a.face_ratio * 100) + '%'} dels instants · música probable: ${a.audio?.probable_music ? 'sí' : 'no'}` }));
      box.append(el('p', { class: 'small muted', text: 'Visió semàntica: ' + (a.semantic_vision || 'no disponible') }));
      const tr = a.transcript || {};
      box.append(el('details', {}, el('summary', { text: `Transcripció (${tr.engine || 'sense motor'}${tr.word_timing === 'estimated' ? ', temps de paraula estimats' : ''})` }),
        el('table', {}, (tr.segments || []).map((s) => el('tr', {}, el('td', { text: `${s.start.toFixed(1)}–${s.end.toFixed(1)}` }), el('td', { text: s.text }))))));
    }
  } catch (e) { box.append(el('p', { class: 'small', text: e.message })); }
  box.append(el('div', { class: 'actions' }, el('button', { class: 'secondary', type: 'button', text: 'Esborrar només l’original (allibera espai)', onclick: async () => {
    if (!confirm('S’esborrarà l’original i l’anàlisi. Les versions es conserven, però no se’n podran fer de noves. Continuar?')) return;
    try { await api('/uploads/' + j.upload_id + '?keep_renders=1', { method: 'DELETE' }); openJob(j.id, false); }
    catch (e) { show(e.message); } } })));
  box.append(el('div', { class: 'actions' }, el('button', { class: 'danger', type: 'button', text: 'Esborrar original i totes les versions (RGPD)', onclick: async () => {
    if (!confirm('S’esborraran per sempre l’original, l’anàlisi i totes les versions d’aquest vídeo. Continuar?')) return;
    try { await api('/uploads/' + j.upload_id, { method: 'DELETE' }); $('detail').hidden = true; currentJob = null; refresh(); }
    catch (e) { show(e.message); } } })));
}
async function loadAudit() {
  try {
    const d = await getJSON('/audit');
    $('audit').replaceChildren(...d.items.map((a) => el('div', { text: `${fmtTime(a.at)} · ${a.actor} · ${a.action} · ${a.target || ''}` })));
  } catch (e) { show(e.message); }
}

$('upload').onclick = uploadAll;
$('refresh').onclick = refresh;
$('style').onchange = onStyle;
$('closeDetail').onclick = () => { $('detail').hidden = true; currentJob = null; };
$('loadAudit').onclick = loadAudit;
for (const b of document.querySelectorAll('#modeSwitch button')) b.onclick = () => setMode(b.dataset.mode);
boot();
