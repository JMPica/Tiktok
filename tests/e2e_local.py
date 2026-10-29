"""E2E local completo: Worker real (wrangler dev / workerd) + D1/R2 locales + agente Python + FFmpeg.

Simula Cloudflare Access con un emisor JWKS local (solo aceptado por el Worker si apunta a 127.0.0.1).
No toca tu cuenta Cloudflare ni sube nada fuera de este ordenador.

  python tests/e2e_local.py --video MI_VIDEO.mov [--language ca] [--evidence docs/evidence/e2e.json]

Requiere: node + `npm install` en cloudflare/, FFmpeg, y motor de transcripción configurado
(faster-whisper por defecto, o BLAU_ASR_ENGINE=sherpa + BLAU_SHERPA_MODEL_DIR).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

ROOT = Path(__file__).resolve().parents[1]
CF = ROOT / 'cloudflare'
TEAM, AUD = 'blau-test.cloudflareaccess.com', 'e2e-aud'
OWNER, EDITOR, OUTSIDER = 'owner@blau.test', 'editor@blau.test', 'intrus@example.com'
PART = 8 * 1024 * 1024
LOG = []


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode()


class Issuer:
    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pub = self.key.public_key().public_numbers()
        n = pub.n.to_bytes((pub.n.bit_length() + 7) // 8, 'big')
        self.jwks = {'keys': [{'kty': 'RSA', 'kid': 'e2e', 'alg': 'RS256', 'use': 'sig', 'n': b64u(n), 'e': b64u(pub.e.to_bytes(3, 'big'))}]}

    def token(self, email, aud=AUD, exp_in=3600, iss=f'https://{TEAM}'):
        head = b64u(json.dumps({'alg': 'RS256', 'kid': 'e2e', 'typ': 'JWT'}).encode())
        body = b64u(json.dumps({'email': email, 'aud': [aud], 'iss': iss, 'iat': int(time.time()), 'exp': int(time.time()) + exp_in,
                                'sub': hashlib.sha1(email.encode()).hexdigest()}).encode())
        sig = self.key.sign(f'{head}.{body}'.encode(), padding.PKCS1v15(), hashes.SHA256())
        return f'{head}.{body}.{b64u(sig)}'

    def serve(self, port):
        jwks = json.dumps(self.jwks).encode()

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(jwks)

            def log_message(self, *a):
                pass
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', port), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def check(name, cond, detail=''):
    LOG.append({'check': name, 'status': 'passed' if cond else 'failed', 'detail': str(detail)[:400]})
    print(('PASS ' if cond else 'FAIL ') + name + (f' · {detail}' if detail else ''), flush=True)
    if not cond:
        raise AssertionError(name + ': ' + str(detail))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', required=True)
    ap.add_argument('--language', default='ca')
    ap.add_argument('--style', default='auto')
    ap.add_argument('--evidence')
    ap.add_argument('--keep', action='store_true')
    args = ap.parse_args()
    video = Path(args.video).resolve()
    tmp = Path(tempfile.mkdtemp(prefix='blau-e2e-'))
    issuer = Issuer()
    jport, wport = free_port(), free_port()
    issuer.serve(jport)
    agent_token = secrets.token_hex(32)
    wr = str(CF / 'node_modules' / '.bin' / 'wrangler')
    env = {**os.environ, 'WRANGLER_SEND_METRICS': 'false', 'CI': '1'}
    subprocess.run([wr, 'd1', 'execute', 'blau-tiktok-v3', '--local', '--persist-to', str(tmp / 'state'), '--file', 'schema.sql', '-y'],
                   cwd=CF, env=env, check=True, capture_output=True, timeout=180)
    variables = {'ACCESS_TEAM_DOMAIN': TEAM, 'ACCESS_AUD': AUD, 'OWNER_EMAIL': OWNER, 'TEAM_EMAILS': EDITOR,
                 'ACCESS_JWKS_URL': f'http://127.0.0.1:{jport}/certs', 'AGENT_TOKEN': agent_token,
                 'LEASE_SECONDS': '20'}
    cmd = [wr, 'dev', '--local', '--ip', '127.0.0.1', '--port', str(wport), '--persist-to', str(tmp / 'state'), '--show-interactive-dev-session=false', '--test-scheduled']
    for k, v in variables.items():
        cmd += ['--var', f'{k}:{v}']
    wlog = (tmp / 'wrangler.log').open('w')
    proc = subprocess.Popen(cmd, cwd=CF, env=env, stdout=wlog, stderr=subprocess.STDOUT)
    base = f'http://127.0.0.1:{wport}'
    started = time.time()
    try:
        for _ in range(120):
            try:
                if requests.get(base + '/api/health', timeout=2).ok:
                    break
            except requests.RequestException:
                time.sleep(1)
        else:
            raise SystemExit('wrangler dev no arrancó; mira ' + str(tmp / 'wrangler.log'))
        run_flow(base, issuer, agent_token, video, args, tmp)
        status = 'passed'
    except Exception as exc:
        status = 'failed'
        LOG.append({'check': 'excepción', 'status': 'failed', 'detail': repr(exc)[:500]})
        print('E2E FALLÓ:', exc, flush=True)
        print((tmp / 'wrangler.log').read_text()[-3000:])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
    evidence = {'date': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'status': status, 'seconds': round(time.time() - started, 1),
                'platform': sys.platform, 'runtime': 'wrangler dev (workerd) + D1/R2 locales + agente Python local',
                'input': {'file': video.name, 'bytes': video.stat().st_size}, 'checks': LOG,
                'not_covered': ['Cloudflare Access real en tu cuenta', 'Safari iPhone físico', 'R2/D1 remotos']}
    if args.evidence:
        Path(args.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence).write_text(json.dumps(evidence, ensure_ascii=False, indent=1), encoding='utf8')
    if not args.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps({'status': status, 'checks': len(LOG)}, ensure_ascii=False))
    return 0 if status == 'passed' else 1


def run_flow(base, issuer, agent_token, video, args, tmp):
    def s(email):
        x = requests.Session()
        x.headers['Cf-Access-Jwt-Assertion'] = issuer.token(email)
        return x
    owner, editor = s(OWNER), s(EDITOR)

    def agent_once(label):
        env = {**os.environ, 'STUDIO_PUBLIC_URL': base, 'STUDIO_ALLOW_INSECURE_LOCALHOST': '1', 'STUDIO_AGENT_TOKEN': agent_token,
               'BLAU_DEFAULT_LANGUAGE': args.language, 'BLAU_X264_PRESET': os.environ.get('BLAU_X264_PRESET', 'veryfast'),
               'STUDIO_POLL_SECONDS': '5', 'PYTHONPATH': str(ROOT)}
        t = time.time()
        r = subprocess.run([sys.executable, '-m', 'local_worker.agent', '--once'], cwd=ROOT, env=env, capture_output=True, text=True, timeout=3600)
        (tmp / f'agent-{label}.log').write_text(r.stdout + r.stderr)
        print(r.stdout[-1500:], r.stderr[-800:], flush=True)
        return r.returncode, time.time() - t

    # --- acceso
    check('T01 sin sesión Access => 401', requests.get(base + '/api/me').status_code == 401)
    check('T01 correo fuera del equipo => 403', s(OUTSIDER).get(base + '/api/me').status_code == 403)
    bad = requests.get(base + '/api/me', headers={'Cf-Access-Jwt-Assertion': issuer.token(OWNER, aud='otra-app')})
    check('T01 token de otra aplicación (aud) => 401', bad.status_code == 401)
    exp = requests.get(base + '/api/me', headers={'Cf-Access-Jwt-Assertion': issuer.token(OWNER, exp_in=-60)})
    check('T01 token caducado => 401', exp.status_code == 401)
    check('T02 roles owner/editor', owner.get(base + '/api/me').json()['role'] == 'owner' and editor.get(base + '/api/me').json()['role'] == 'editor')
    check('agente sin token => 401', requests.post(base + '/api/agent/claim').status_code == 401)
    check('estáticos servidos', requests.get(base + '/').status_code == 200 and 'TikTok Studio' in requests.get(base + '/').text)
    cross = editor.post(base + '/api/uploads', json={'filename': 'x.mp4', 'size_bytes': 5000}, headers={'Origin': 'https://evil.example'})
    check('CSRF: mutación desde otro origen => 403', cross.status_code == 403)

    # --- subida por partes con corte y reanudación
    fake = editor.post(base + '/api/uploads', json={'filename': 'falso.mp4', 'size_bytes': 4096}).json()
    r = editor.put(f"{base}/api/uploads/{fake['id']}/parts/1", data=b'<html>' + b'0' * 4090)
    check('magic bytes: no-vídeo rechazado', r.status_code == 415, r.text)
    data = video.read_bytes()
    start = editor.post(base + '/api/uploads', json={'filename': video.name, 'size_bytes': len(data), 'consent_team': True}).json()
    uid, total = start['id'], start['total_parts']
    check('subida multipart con varias partes', total >= 2, f'{total} partes de 8 MiB')
    order = [n for n in range(1, total + 1) if n != 2] if total > 2 else [1]
    for n in order:
        r = editor.put(f'{base}/api/uploads/{uid}/parts/{n}', data=data[(n - 1) * PART:n * PART])
        assert r.ok, r.text
    st = editor.get(f'{base}/api/uploads/{uid}').json()
    check('T04 reanudar: el servidor recuerda las partes subidas', sorted(st['uploaded_parts']) == order, st['uploaded_parts'])
    check('finalizar con partes pendientes => 422', editor.post(f'{base}/api/uploads/{uid}/finalize').status_code == 422)
    for n in range(1, total + 1):
        if n not in order:
            assert editor.put(f'{base}/api/uploads/{uid}/parts/{n}', data=data[(n - 1) * PART:n * PART]).ok
    check('finalizar subida', editor.post(f'{base}/api/uploads/{uid}/finalize').json()['status'] == 'uploaded')
    check('aislamiento: otra persona no ve la subida', s('otra@blau.test').get(f'{base}/api/uploads/{uid}').status_code in (403, 404))
    job = editor.post(f'{base}/api/uploads/{uid}/jobs', json={'style': args.style, 'language': args.language}).json()
    dup = editor.post(f'{base}/api/uploads/{uid}/jobs', json={'style': args.style, 'language': args.language}).json()
    check('T19 doble envío no duplica el trabajo', dup.get('reused') and dup['id'] == job['id'])
    check('T05 sin ordenador encendido el trabajo queda en cola', editor.get(f"{base}/api/jobs/{job['id']}").json()['status'] == 'queued')

    # --- agente: análisis + director + render + QC + subida
    code, secs = agent_once('produce')
    j = editor.get(f"{base}/api/jobs/{job['id']}").json()
    check('agente procesa y termina', code == 0 and j['status'] in ('done', 'needs_review'), f"{j['status']} en {secs:.0f}s · {j.get('error')}")
    if j['status'] != 'done':
        check('T08 sin historia => 0 clips con motivo', bool(j.get('error')), j.get('error'))
        return
    vs = j['variants']
    check('T09 0..N propuestas por mérito', len(vs) >= 1, f'{len(vs)} propuestas: ' + '; '.join(v['title'] for v in vs))
    v = vs[0]
    check('QC medido aprobado', v['qc']['status'] == 'pass', v['qc']['checks'])
    det = owner.get(f"{base}/api/variants/{v['id']}").json()
    m = det['qc_full']['measured']
    check('T12 1080x1920 H.264/AAC fps nativo', (m['width'], m['height'], m['codec'], m['audio_codec']) == (1080, 1920, 'h264', 'aac'), m['fps'])
    check('T13 -16 LUFS ±2 y pico ≤ -1 dBTP', abs(m['integrated_lufs'] + 16) <= 2 and m['true_peak_dbtp'] <= -0.95,
          f"{m['integrated_lufs']} LUFS / {m['true_peak_dbtp']} dBTP")
    check('EDL con timecodes del bruto y procedencia', det['edl']['segments'][0]['in'] >= 0 and 'provenance' in det['edl'], det['edl']['segments'][:2])
    check('T08 nunca los primeros 18 s a ciegas', not (det['edl']['segments'][0]['in'] == 0 and abs(det['edl']['duration'] - 18) < 0.5))

    # --- preview con Range (Safari iOS) y descarga
    full = editor.get(f"{base}/api/variants/{v['id']}/download")
    sha = hashlib.sha256(full.content).hexdigest()
    check('T18 descarga = sha256 informado', sha == v['sha256'] and 'attachment' in full.headers.get('Content-Disposition', ''))
    rr = editor.get(f"{base}/api/variants/{v['id']}/preview", headers={'Range': 'bytes=0-1'})
    check('preview Range 206 (Safari iOS)', rr.status_code == 206 and len(rr.content) == 2 and rr.headers['Content-Range'].endswith('/' + str(len(full.content))))
    hd = editor.head(f"{base}/api/variants/{v['id']}/preview")
    check('HEAD de preview con Accept-Ranges', hd.status_code == 200 and hd.headers.get('Accept-Ranges') == 'bytes')
    srt = editor.get(f"{base}/api/variants/{v['id']}/subtitles.srt")
    check('subtítulos .srt para CapCut', srt.ok and ' --> ' in srt.text and srt.text.startswith('1\n'), srt.text[:60])
    check('portada JPEG', editor.get(f"{base}/api/variants/{v['id']}/poster").content[:2] == b'\xff\xd8')
    check('sin sesión no hay vídeo', requests.get(f"{base}/api/variants/{v['id']}/preview").status_code == 401)

    # --- aprobación ligada al hash
    check('T17 editora no puede aprobar', editor.post(f"{base}/api/variants/{v['id']}/approve", json={'sha256': v['sha256'], 'confirm': True}).status_code == 403)
    check('T17 hash distinto => 409', owner.post(f"{base}/api/variants/{v['id']}/approve", json={'sha256': '0' * 64, 'confirm': True}).status_code == 409)
    r = owner.post(f"{base}/api/variants/{v['id']}/approve", json={'sha256': v['sha256'], 'confirm': True, 'checklist': {}})
    check('T15 sin checklist de consentimiento/claims => 422', r.status_code == 422, r.text)
    checklist = {k: True for k in ['team_consent', 'client_consent', 'captions_reviewed', *v['requires']]}
    r = owner.post(f"{base}/api/variants/{v['id']}/approve", json={'sha256': v['sha256'], 'confirm': True, 'checklist': checklist})
    check('T17 propietaria aprueba hash exacto, sin publicar', r.ok and r.json()['published'] is False, r.text)

    # --- corrección en lenguaje natural => versión nueva con hash nuevo
    rv = editor.post(f"{base}/api/variants/{v['id']}/revise", json={'instruction': 'Fes-lo més curt i amb subtítols a dalt'}).json()
    code, secs = agent_once('revise')
    jr = editor.get(f"{base}/api/jobs/{rv['id']}").json()
    ok = jr['status'] == 'done' and jr['variants'] and jr['variants'][0]['sha256'] != v['sha256']
    check('T16 corrección de texto => versión nueva con hash nuevo', ok, f"{jr['status']} {jr.get('error')} en {secs:.0f}s")
    nv = jr['variants'][0]
    check('versión enlazada a la anterior', nv['version'] == v['version'] + 1 and nv['parent_variant_id'] == v['id'])

    # --- edición Advanced de subtítulos (propietaria)
    det2 = owner.get(f"{base}/api/variants/{nv['id']}").json()
    caps = [{'start': c['start'], 'end': c['end'], 'text': c['text'].replace('\n', ' ')} for c in det2['edl']['captions']['events']]
    if caps:
        caps[0]['text'] = 'Text corregit a mà'
    check('editora no puede usar el editor Advanced', editor.post(f"{base}/api/variants/{nv['id']}/edit", json={'captions': caps}).status_code == 403)
    ed = owner.post(f"{base}/api/variants/{nv['id']}/edit", json={'captions': caps, 'caption_mode': 'phrase'}).json()
    code, secs = agent_once('edit')
    je = owner.get(f"{base}/api/jobs/{ed['id']}").json()
    ev = je['variants'][0] if je['variants'] else None
    det3 = owner.get(f"{base}/api/variants/{ev['id']}").json() if ev else {}
    check('T06 subtítulo corregido a mano entra en la nueva versión', bool(ev) and det3['edl']['captions']['events'][0]['text'] == 'Text corregit a mà',
          je.get('error'))

    # --- T05: el ordenador se apaga a mitad de un vídeo
    crash = editor.post(f'{base}/api/uploads/{uid}/jobs', json={'style': 'tacho_humor', 'language': args.language}).json()
    ghost = requests.post(base + '/api/agent/claim', headers={'Authorization': f'Bearer {agent_token}'}).json()['job']
    check('T05 agente fantasma reserva el trabajo', ghost and ghost['id'] == crash['id'] and
          editor.get(f"{base}/api/jobs/{crash['id']}").json()['status'] == 'processing')
    time.sleep(23)  # reserva caducada: el PC "apagado" no ha enviado latido
    code, secs = agent_once('recover')
    jc = editor.get(f"{base}/api/jobs/{crash['id']}").json()
    check('T05 al volver, otro agente recupera y termina el trabajo', jc['status'] in ('done', 'needs_review'), f"{jc['status']} en {secs:.0f}s")
    late = requests.post(f"{base}/api/agent/jobs/{crash['id']}/complete", json={},
                         headers={'Authorization': f'Bearer {agent_token}', 'X-Agent-Id': ghost['agent_id']})
    check('T05 el agente antiguo ya no puede escribir resultados', late.status_code in (404, 409), late.status_code)

    # --- auditoría, cron y borrado RGPD
    sch = requests.get(base + '/__scheduled?cron=17+3+*+*+*')
    check('cron de mantenimiento se ejecuta', sch.ok, sch.status_code)
    time.sleep(1)
    acts = {a['action'] for a in owner.get(f'{base}/api/audit').json()['items']}
    check('mantenimiento registrado en auditoría', 'maintenance' in acts)
    check('auditoría registra subida/aprobación/correcciones', {'upload_completed', 'variant_approved', 'variant_revision_requested'} <= acts)
    check('editora no ve auditoría', editor.get(f'{base}/api/audit').status_code == 403)
    an = editor.get(f'{base}/api/uploads/{uid}/analysis').json()
    check('análisis y transcripción visibles (Advanced)', 'transcript' in an and an['meta']['duration'] > 0, an.get('transcript', {}).get('engine'))
    k = owner.delete(f'{base}/api/uploads/{uid}?keep_renders=1')
    check('liberar R2: borrar solo el original conserva las versiones', k.ok and owner.get(f"{base}/api/variants/{v['id']}/preview", headers={'Range': 'bytes=0-1'}).status_code == 206)
    check('sin original no se piden versiones nuevas', editor.post(f"{base}/api/variants/{v['id']}/revise", json={'instruction': 'més curt'}).status_code == 409)
    d = owner.delete(f'{base}/api/uploads/{uid}')
    check('T23 borrado RGPD del original y versiones', d.ok and d.json()['deleted'], d.text)
    check('tras borrar, la preview ya no existe', owner.get(f"{base}/api/variants/{v['id']}/preview").status_code == 404)
    check('tras borrar, el trabajo ya no existe', owner.get(f"{base}/api/jobs/{job['id']}").status_code == 404)


if __name__ == '__main__':
    raise SystemExit(main())
