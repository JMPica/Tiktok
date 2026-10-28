#!/usr/bin/env python3
"""
analyze_video.py - Análisis del vídeo bruto ANTES de decidir cortes.

Uso:
  python3 analyze_video.py BRUTO.mov [--out carpeta]
      -> hojas de contacto a 1 fps con tiempo, ráfagas de movimiento (con su pico),
         momentos quietos, silencios y probabilidad de música en el audio. Resumen en resumen.json.
  python3 analyze_video.py BRUTO.mov --strip T DUR [--out carpeta]
      -> tira de fotogramas a 5 fps desde T durante DUR segundos, con tiempo exacto en cada uno.
         Úsala para fijar el "in", el "out" y el "impact" exactos de cada segmento.

Un modelo no ve el vídeo como una persona: ve fotogramas sueltos. Por eso hay que
mirar las hojas y las tiras, no adivinar ni cortar en segundos redondos.
"""
import argparse, json, os, re, subprocess, sys
import numpy as np


def sh(cmd, out=False):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
        raise SystemExit("ERROR: ffmpeg/ffprobe falló")
    return r.stdout if out else r.stderr


def probe(src):
    j = json.loads(sh(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", src], out=True))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    n, d = (v.get("avg_frame_rate") or v["r_frame_rate"]).split("/")
    trc = v.get("color_transfer", "")
    return {"W": int(v["width"]), "H": int(v["height"]), "fps": float(n) / float(d) if float(d) else 0,
            "trc": trc, "hdr": trc in ("arib-std-b67", "smpte2084"),
            "audio": any(s["codec_type"] == "audio" for s in j["streams"]),
            "duration": float(j["format"]["duration"])}


def tm(info):
    if not info["hdr"]:
        return "format=yuv420p"
    return ("zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
            "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def runs(mask, t, min_len):
    out, start = [], None
    for i, m in enumerate(np.append(mask, False)):
        if m and start is None:
            start = i
        elif not m and start is not None:
            if t[i - 1] - t[start] >= min_len:
                out.append((start, i - 1))
            start = None
    return out


def strip(src, info, t0, dur, outdir):
    path = os.path.join(outdir, f"tira_{t0:.2f}.jpg")
    n = max(1, int(round(dur * 5)))
    cols = min(n, 6)
    rows = int(np.ceil(n / cols))
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", src, "-vf",
        f"fps=5,scale=240:-2,{tm(info)},drawtext=text='%{{pts\\:flt\\:{t0:.3f}}}':x=6:y=6:fontsize=20:"
        f"fontcolor=yellow:box=1:boxcolor=black@0.7,tile={cols}x{rows}", "-frames:v", "1", path])
    print(path)


def full(src, info, outdir):
    D = info["duration"]
    sheets = []
    for k, s0 in enumerate(np.arange(0, D, 20.0)):
        p = os.path.join(outdir, f"hoja_{int(s0):03d}s.jpg")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{s0:.2f}", "-t", "20", "-i", src, "-vf",
            f"fps=1,scale=300:-2,{tm(info)},drawtext=text='%{{eif\\:t+{s0:.0f}\\:d}}s':x=6:y=6:fontsize=26:"
            "fontcolor=yellow:box=1:boxcolor=black@0.7,tile=5x4", "-frames:v", "1", p])
        sheets.append(p)

    # movimiento a 10 fps (diferencia entre fotogramas)
    mfile = os.path.join(outdir, "movimiento.txt")
    sh(["ffmpeg", "-v", "error", "-i", src, "-vf",
        f"fps=10,scale=96:-2,format=gray,tblend=all_mode=difference,signalstats,"
        f"metadata=print:key=lavfi.signalstats.YAVG:file={mfile}", "-f", "null", "-"])
    t, m = [], []
    for line in open(mfile):
        a = re.search(r"pts_time:([\d.]+)", line)
        if a:
            t.append(float(a.group(1)))
        b = re.search(r"YAVG=([\d.]+)", line)
        if b:
            m.append(float(b.group(1)))
    t, m = np.array(t[:len(m)]), np.array(m[:len(t)])
    ms = np.convolve(m, np.ones(3) / 3, mode="same") if len(m) > 3 else m
    lo, hi = np.percentile(ms, 40), np.percentile(ms, 95)
    thr = lo + 0.35 * (hi - lo)
    bursts = []
    for a, b in runs(ms > thr, t, 0.3):
        k = a + int(np.argmax(ms[a:b + 1]))
        bursts.append({"inicio": round(t[a], 2), "fin": round(t[b], 2), "pico_mov": round(t[k], 2),
                       "intensidad": round(float(ms[k]), 2)})
    still = [{"inicio": round(t[a], 2), "fin": round(t[b], 2)}
             for a, b in runs(ms < np.percentile(ms, 15), t, 0.5)]

    audio = {"tiene_audio": info["audio"]}
    if info["audio"]:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-map", "0:a:0", "-ac", "1", "-ar", "16000",
                              "-f", "f32le", "-"], capture_output=True).stdout
        x = np.frombuffer(raw, dtype=np.float32)
        hop = 4000  # 0.25 s
        if len(x) > hop * 4:
            fr = x[:len(x) // hop * hop].reshape(-1, hop)
            rms = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
            ta = np.arange(len(rms)) * 0.25
            sil = [{"inicio": round(ta[a], 2), "fin": round(ta[b] + 0.25, 2)} for a, b in runs(rms < -45, ta, 0.4)]
            # ritmo regular en el audio -> probablemente música (derechos de autor)
            win, h = 1024, 256
            S = np.array([np.abs(np.fft.rfft(x[i:i + win] * np.hanning(win))) for i in range(0, len(x) - win, h)])
            flux = np.maximum(0, np.diff(np.log1p(S), axis=0)).sum(1)
            flux = (flux - flux.mean()) / (flux.std() + 1e-9)
            ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
            ac /= ac[0] + 1e-9
            lags = np.arange(len(ac)) * h / 16000
            sel = (lags > 0.3) & (lags < 1.5)
            score = float(ac[sel].max()) if sel.any() else 0.0
            bpm = float(60 / lags[sel][np.argmax(ac[sel])]) if sel.any() else 0.0
            audio.update({"rms_medio_dB": round(float(np.median(rms)), 1), "silencios": sil,
                          "ritmo_regular": round(score, 2), "bpm_estimado": round(bpm),
                          "probable_musica": score > 0.25})
    res = {"bruto": src, "resolucion": f"{info['W']}x{info['H']}", "fps": round(info["fps"], 3),
           "hdr": info["hdr"], "transferencia": info["trc"], "duracion_s": round(info["duration"], 2),
           "hojas_de_contacto": sheets, "rafagas_de_movimiento": bursts, "momentos_quietos": still,
           "audio": audio,
           "nota": "Los picos de movimiento son candidatos. Confirma cada 'in', 'out' e 'impact' con --strip."}
    json.dump(res, open(os.path.join(outdir, "resumen.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default=None)
    ap.add_argument("--strip", nargs=2, type=float, metavar=("T", "DUR"))
    a = ap.parse_args()
    outdir = a.out or os.path.splitext(os.path.basename(a.video))[0] + "_analisis"
    os.makedirs(outdir, exist_ok=True)
    info = probe(a.video)
    if a.strip:
        strip(a.video, info, a.strip[0], a.strip[1], outdir)
    else:
        full(a.video, info, outdir)


if __name__ == "__main__":
    main()
