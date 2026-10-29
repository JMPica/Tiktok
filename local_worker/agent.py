"""Agente local V4: Windows/macOS/Linux, sin Docker, sin puertos entrantes, sin IA de pago.

Consulta la cola de Cloudflare por HTTPS saliente, descarga el original privado a una carpeta temporal,
lo analiza y monta en ESTE ordenador (creative_engine) y sube 0..N propuestas con EDL, QC y SHA256.
Si el ordenador se apaga, el trabajo vuelve a la cola cuando caduca su reserva (30 min sin latido).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creative_engine import pipeline as P  # noqa: E402
from creative_engine.media import require_tools  # noqa: E402
from creative_engine.revise import NotUnderstood  # noqa: E402

PART = 8 * 1024 * 1024
VERSION = '4.0.0'


class KeepAwake:
    """Evita que el ordenador se suspenda MIENTRAS edita (no cuando está esperando)."""

    def __enter__(self):
        self.proc = None
        try:
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # CONTINUOUS | SYSTEM_REQUIRED
            elif sys.platform == 'darwin' and shutil.which('caffeinate'):
                import subprocess
                self.proc = subprocess.Popen(['caffeinate', '-i', '-w', str(os.getpid())])
        except Exception:
            pass
        return self

    def __exit__(self, *exc):
        try:
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            elif self.proc:
                self.proc.terminate()
        except Exception:
            pass


class JobGone(Exception):
    """El trabajo se ha borrado/reasignado en el servidor: se abandona sin reportar."""


class Agent:
    def __init__(self, env=os.environ):
        self.base = env.get('STUDIO_PUBLIC_URL', '').rstrip('/')
        insecure_ok = env.get('STUDIO_ALLOW_INSECURE_LOCALHOST') == '1' and self.base.startswith(('http://127.0.0.1', 'http://localhost'))
        token = env.get('STUDIO_AGENT_TOKEN', '')
        cid, secret = env.get('CF_ACCESS_CLIENT_ID', ''), env.get('CF_ACCESS_CLIENT_SECRET', '')
        if not (self.base.startswith('https://') or insecure_ok) or not token or (not insecure_ok and not (cid and secret)):
            raise SystemExit('Falten STUDIO_PUBLIC_URL (https), STUDIO_AGENT_TOKEN o el Service Token de Cloudflare Access.')
        self.poll = max(5 if insecure_ok else 10, int(env.get('STUDIO_POLL_SECONDS', '30')))
        self.language = env.get('BLAU_DEFAULT_LANGUAGE', 'ca')
        self.workroot = Path(env.get('BLAU_WORK_DIR') or tempfile.gettempdir())
        self.s = requests.Session()
        self.s.headers.update({'Authorization': f'Bearer {token}', 'User-Agent': f'blau-agent/{VERSION}'})
        if cid and secret:
            self.s.headers.update({'CF-Access-Client-Id': cid, 'CF-Access-Client-Secret': secret})
        self.job = None
        self.stage = ('claimed', 1, '')
        self._beat_stop = threading.Event()

    # ------------------------------------------------------------ HTTP
    def api(self, method, path, retries=4, **kw):
        timeout = kw.pop('timeout', 120)
        headers = kw.pop('headers', {})
        if self.job:
            headers['X-Agent-Id'] = self.job['agent_id']
        for attempt in range(retries):
            try:
                r = self.s.request(method, self.base + path, timeout=timeout, headers=headers, **kw)
            except requests.RequestException:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
                continue
            if r.status_code in (404, 409) and self.job and '/api/agent/' in path and 'claim' not in path:
                raise JobGone(r.text[:200])
            if r.status_code >= 500 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r
        raise RuntimeError('unreachable')

    def progress(self, stage, pct, message=''):
        self.stage = (stage, pct, message)
        print(f'  [{pct:3d}%] {message or stage}', flush=True)
        try:
            self.api('POST', f"/api/agent/jobs/{self.job['id']}/progress", json={'stage': stage, 'progress': pct, 'message': message}, retries=2)
        except JobGone:
            raise
        except Exception as exc:  # el progreso no debe tumbar el render
            print('  (no s’ha pogut enviar el progrés:', exc, ')', flush=True)

    def _heartbeat(self):
        lease = max(30.0, (self.job.get('lease_until', 0) / 1000) - time.time())
        while not self._beat_stop.wait(max(5.0, min(240.0, lease / 3))):
            try:
                st, pct, msg = self.stage
                self.api('POST', f"/api/agent/jobs/{self.job['id']}/progress", json={'stage': st, 'progress': pct, 'message': msg}, retries=1)
            except Exception:
                pass

    def download(self, dest: Path):
        """Descarga reanudable (Range) del original privado."""
        url = f"/api/agent/jobs/{self.job['id']}/source"
        expected = self.job.get('size_bytes')
        for attempt in range(6):
            have = dest.stat().st_size if dest.exists() else 0
            if expected and have >= expected:
                return
            headers = {'Range': f'bytes={have}-'} if have else {}
            try:
                with self.api('GET', url, stream=True, timeout=300, headers=headers) as r, dest.open('ab' if have and r.status_code == 206 else 'wb') as out:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        out.write(chunk)
                if not expected or dest.stat().st_size == expected:
                    return
            except (requests.RequestException, OSError) as exc:
                print('  descàrrega interrompuda, reintentant:', exc, flush=True)
                time.sleep(2 ** attempt)
        raise RuntimeError('No s’ha pogut descarregar l’original sencer')

    # ------------------------------------------------------------ subida de una variante
    def upload_variant(self, result: dict, idx: int):
        edl, path = result['edl'], Path(result['path'])
        size = path.stat().st_size
        meta = {'idx': idx, 'version': edl.get('version', 1), 'title': edl.get('title') or f'Proposta {idx + 1}',
                'style': edl['style'], 'edl': edl, 'size_bytes': size, 'explanation': edl.get('explanation', ''),
                'score_total': (edl.get('score') or {}).get('total'), 'risks': edl.get('risks', []), 'requires': edl.get('requires', [])}
        v = self.api('POST', f"/api/agent/jobs/{self.job['id']}/variants", json=meta).json()
        vid = v['variant_id']
        with path.open('rb') as f:
            n = 0
            while data := f.read(PART):
                n += 1
                self.api('PUT', f'/api/agent/variants/{vid}/parts/{n}', data=data, timeout=600,
                         headers={'Content-Type': 'application/octet-stream'})
        if result.get('poster') and Path(result['poster']).is_file():
            self.api('PUT', f'/api/agent/variants/{vid}/poster', data=Path(result['poster']).read_bytes(),
                     headers={'Content-Type': 'image/jpeg'})
        qc = dict(result['qc'])
        qc['render'] = {k: result['render'].get(k) for k in ('fps', 'fps_reason', 'expected_duration', 'tonemapped', 'encoder')}
        out = self.api('POST', f'/api/agent/variants/{vid}/finish', json={'sha256': result['sha256'], 'qc': qc}).json()
        print(f"  → proposta {idx + 1} pujada ({size / 1e6:.1f} MB) · {out['status']}", flush=True)
        return vid

    # ------------------------------------------------------------ trabajo
    def understood_from_server(self):
        if not self.job.get('analysis_available'):
            return None
        try:
            data = self.api('GET', f"/api/agent/jobs/{self.job['id']}/analysis", timeout=300, retries=2).json()
            return data if {'meta', 'analysis', 'transcript'} <= set(data) else None
        except JobGone:
            return None

    def process(self, job: dict):
        self.job = job
        self._beat_stop.clear()
        beat = threading.Thread(target=self._heartbeat, daemon=True)
        beat.start()
        work = Path(tempfile.mkdtemp(prefix='blau-v4-', dir=self.workroot))
        try:
            name = Path(job.get('filename') or 'original.mp4').suffix.lower() or '.mp4'
            src = work / ('original' + name)
            self.progress('downloading', 2, 'Descarregant l’original privat')
            self.download(src)
            lang = job.get('language') or self.language
            if job['kind'] == 'revise':
                self.run_revision(src, work, lang)
            else:
                self.run_production(src, work, lang)
        finally:
            self._beat_stop.set()
            shutil.rmtree(work, ignore_errors=True)  # el original no se queda en el PC
            self.job = None

    def run_production(self, src, work, lang):
        job = self.job
        u = self.understood_from_server() or P.understand(src, lang, self.progress)
        if not job.get('analysis_available'):
            self.progress('saving_analysis', 40, 'Desant l’anàlisi per a futures correccions')
            self.api('PUT', f"/api/agent/jobs/{job['id']}/analysis", json={'full': u, 'summary': P.summary(u)}, timeout=300)
        res = P.produce(src, work, job.get('style') or 'auto', lang, job.get('options') or {}, self.progress, understood=u)
        plan, results = res['plan'], res['results']
        ok = [r for r in results if 'error' not in r]
        skip = int(job.get('variants_done') or 0)
        for k, r in enumerate(ok):
            if k < skip:
                continue
            self.progress('uploading', 93 + int(6 * k / max(1, len(ok))), f'Pujant proposta {k + 1} de {len(ok)}')
            self.upload_variant(r, k)
        errors = [r['error'] for r in results if 'error' in r]
        reason = plan.get('reason') if plan['status'] != 'drafts' else ('; '.join(errors) if not ok and errors else '')
        self.api('POST', f"/api/agent/jobs/{job['id']}/complete", json={'reason': reason, 'summary': {
            'style': plan.get('style'), 'style_reason': plan.get('style_reason'), 'selection': plan.get('selection'),
            'semantic_vision': plan.get('semantic_vision'), 'transcript_error': plan.get('transcript_error'),
            'candidates': len(plan['candidates']), 'render_errors': errors[:5]}})

    def run_revision(self, src, work, lang):
        job = self.job
        parent = job.get('parent') or {}
        if not parent.get('edl'):
            raise RuntimeError('La versió original no té EDL')
        u = self.understood_from_server() or P.understand(src, lang, self.progress)
        try:
            out = P.revise(src, work, parent['edl'], u, instruction=job.get('instruction'), manual=job.get('manual_edits'),
                           progress=self.progress)
        except (NotUnderstood, ValueError) as exc:
            self.api('POST', f"/api/agent/jobs/{job['id']}/complete", json={'reason': str(exc)[:500]})
            return
        self.progress('uploading', 94, 'Pujant la nova versió')
        self.upload_variant(out['result'], parent.get('idx', 0))
        self.api('POST', f"/api/agent/jobs/{job['id']}/complete", json={'summary': {'applied': out['applied']}})

    def loop(self, once=False):
        require_tools()
        print(f'Blau de Mar · agent V{VERSION} · sense ports d’entrada · IA de pagament desactivada', flush=True)
        while True:
            try:
                job = self.api('POST', '/api/agent/claim', json={}).json().get('job')
            except KeyboardInterrupt:
                return
            except Exception as exc:
                print('Connexió amb el servei:', exc, flush=True)
                if once:
                    raise
                time.sleep(min(self.poll * 2, 120))
                continue
            if not job:
                if once:
                    return
                time.sleep(self.poll)
                continue
            print(f"[{job['id'][:8]}] {job['kind']} · {job.get('filename')} · estil {job.get('style')}", flush=True)
            try:
                with KeepAwake():
                    self.process(job)
                print(f"[{job['id'][:8]}] acabat", flush=True)
            except JobGone as exc:
                print(f"[{job['id'][:8]}] el treball ja no existeix al servidor ({exc}); s’abandona", flush=True)
            except Exception as exc:
                print(f"[{job['id'][:8]}] error: {exc!r}", flush=True)
                try:
                    self.job = job
                    self.api('POST', f"/api/agent/jobs/{job['id']}/fail", json={'error': f'{type(exc).__name__}: {exc}'[:500]}, retries=2)
                except Exception as rep:
                    print('No s’ha pogut informar de l’error:', rep, flush=True)
                finally:
                    self.job = None
            if once:
                return


def main():
    Agent().loop(once='--once' in sys.argv)


if __name__ == '__main__':
    main()
