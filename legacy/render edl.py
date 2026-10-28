#!/usr/bin/env python3
"""
render_edl.py - Monta un TikTok (1080x1920) a partir de una EDL en JSON.

Uso:
    python3 render_edl.py edl.json

Los segmentos ya renderizados se reutilizan si no cambian sus parámetros, así que
cambiar solo los textos o el sonido vuelve a montar en segundos.

Requisitos: ffmpeg >= 5 con zscale (libzimg), libass y minterpolate; Python 3 con numpy y scipy.

Esquema de la EDL (todos los tiempos en segundos del vídeo ORIGINAL salvo en captions/sfx):
{
  "source": "ruta/al/bruto.mov",
  "output": "salida.mp4",
  "workdir": "carpeta_de_trabajo",          # opcional (por defecto: <output>_work)
  "fps": null,                              # opcional; por defecto = fps del bruto (nunca 25->30)
  "grade": "punchy" | "natural" | "none",
  "loop": true,                             # genera imagen de control del empalme final->inicio
  "brand": {"font": "Inter Display Black", "fonts_dir": null, "accent": "#96FF28",
            "punch_text": "#000000"},
  "audio": {"keep_original": false, "original_gain_db": 0, "sfx": true,
            "sfx_gain_db": 0, "target_lufs": -16},
  "segments": [
    {"id": "hook", "in": 25.75, "out": 26.70, "speed": 0.5, "slowmo": true,
     "zoom": 1.2, "x": 1.0, "y": "bottom",           # x: 0..1 o "center"; y: "top"|"center"|"bottom"|0..1
     "impact": 26.47,                                 # instante del pico (tiempo original) -> zoom + golpe
     "pushin": false, "silent_cut": false, "keep_audio": false}
  ],
  "captions": [
    {"start": 0, "end": "@rep2", "text": "Una més i marxo.", "style": "cap", "y": 330}
  ],
  "sfx_extra": [{"t": "@close+0.2", "type": "pop", "gain": 0.4}]
}
Referencias de tiempo en captions/sfx (tiempo del vídeo FINAL):
  número | "@id" (inicio del segmento) | "@id.end" | "@total" | con desplazamiento: "@id+0.3"
Estilos de texto: "hook" (grande), "cap" (normal), "punch" (caja de color de marca), "sub" (pequeño).
"""
import hashlib, json, os, re, subprocess, sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48000
CANVAS = (2160, 3840)          # lienzo interno para zooms suaves
OUT_W, OUT_H = 1080, 1920
SAFE_Y = (220, 1250)           # zona vertical segura para textos (UI de TikTok)
MAX_CHARS_LINE = 20

GRADES = {
    "punchy": "eq=contrast=1.07:saturation=1.14:gamma=0.98,"
              "curves=all='0/0 0.25/0.22 0.5/0.5 0.78/0.81 1/1',unsharp=5:5:0.45:5:5:0",
    "natural": "eq=contrast=1.03:saturation=1.05,unsharp=5:5:0.3:5:5:0",
    "none": "null",
}
WARN = []


def sh(cmd, out=False):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(" ".join(map(str, cmd))[:800] + "\n" + r.stderr[-2500:] + "\n")
        raise SystemExit(f"ERROR: comando falló (código {r.returncode})")
    return r.stdout if out else r.stderr


def check_ffmpeg():
    f = sh(["ffmpeg", "-hide_banner", "-filters"], out=True)
    missing = [x for x in ("zscale", "ass", "minterpolate", "zoompan", "tonemap") if f" {x} " not in f]
    return missing


def probe(src):
    j = json.loads(sh(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", src], out=True))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    W, H = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    if "rotate" in (v.get("tags") or {}):
        rot = int(v["tags"]["rotate"])
    if abs(rot) % 180 == 90:
        W, H = H, W
    fps = 0.0
    for key in ("avg_frame_rate", "r_frame_rate"):
        n, d = (v.get(key) or "0/0").split("/")
        if float(d) > 0 and float(n) > 0:
            fps = float(n) / float(d)
            break
    trc = v.get("color_transfer", "")
    return {"W": W, "H": H, "fps": fps, "trc": trc, "hdr": trc in ("arib-std-b67", "smpte2084"),
            "has_audio": any(s["codec_type"] == "audio" for s in j["streams"]),
            "duration": float(j["format"]["duration"])}


def tonemap_chain(info):
    if not info["hdr"]:
        return "format=yuv420p"
    npl = 203 if info["trc"] == "arib-std-b67" else 100
    return (f"zscale=t=linear:npl={npl},format=gbrpf32le,zscale=p=bt709,"
            "tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def geometry(seg, info):
    W, H = info["W"], info["H"]
    if W / H > 9 / 16:
        bw, bh = H * 9 / 16, H
    else:
        bw, bh = W, W * 16 / 9
    z = float(seg.get("zoom", 1.0))
    cw, ch = int(bw / z) // 2 * 2, int(bh / z) // 2 * 2
    x, y = seg.get("x", "center"), seg.get("y", "center")
    fx = 0.5 if x == "center" else float(x)
    fy = {"top": 0.0, "center": 0.5, "bottom": 1.0}.get(y)
    fy = float(y) if fy is None else fy
    x0 = max(0, min(int(round((W - cw) * fx)), W - cw)) // 2 * 2
    y0 = max(0, min(int(round((H - ch) * fy)), H - ch)) // 2 * 2
    if cw < OUT_W * 0.95:
        WARN.append(f"segmento {seg['id']}: recorte de {cw}px de ancho (<1080) -> se verá blando; "
                    + ("baja el zoom" if z > 1.0 else "el bruto es horizontal o de baja resolución: pide grabar en vertical 4K"))
    return cw, ch, x0, y0


def count_frames(path):
    o = sh(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
            "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", path], out=True)
    return int(o.strip())


def is_slow(seg):
    return bool(seg.get("slowmo", float(seg.get("speed", 1.0)) < 0.75))


def render_segment(seg, info, ctx):
    a, b, sp = float(seg["in"]), float(seg["out"]), float(seg.get("speed", 1.0))
    if not (0 <= a < b <= info["duration"] + 0.05):
        raise SystemExit(f"ERROR: segmento {seg['id']} fuera de rango ({a}-{b}, duración {info['duration']:.2f})")
    fps, slow = ctx["fps"], is_slow(seg)
    n = int(round((b - a) / sp * fps))
    cw, ch, x0, y0 = geometry(seg, info)
    chain = [f"crop={cw}:{ch}:{x0}:{y0}", tonemap_chain(info),
             f"scale={CANVAS[0]}:{CANVAS[1]}:flags=lanczos", f"setpts=(PTS-STARTPTS)/{sp}"]
    if slow:
        zfps = info["fps"] * sp
    else:
        zfps = fps
        chain.append(f"fps={fps}")
    z = "1"
    if seg.get("impact") is not None:
        imp = float(seg["impact"])
        kf = (imp - a) * info["fps"] if slow else (imp - a) / sp * fps
        z = f"1+{float(seg.get('pulse', 0.055))}*exp(-pow((on-{kf:.2f})/3.2\\,2))"
    if seg.get("pushin"):
        z = f"1+{float(seg.get('pushin_amount', 0.07))}*on/{max(n, 1)}"
    chain.append(f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={OUT_W}x{OUT_H}:fps={zfps:g}")
    if slow:
        chain.append(f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
    chain += [GRADES[ctx["grade"]], "setsar=1"]

    out = os.path.join(ctx["work"], f"seg_{seg['id']}.mp4")
    key = hashlib.sha1(json.dumps([seg, ctx["src"], os.path.getmtime(ctx["src"]), fps, ctx["grade"]],
                                  sort_keys=True).encode()).hexdigest()
    if os.path.exists(out) and os.path.exists(out + ".key") and open(out + ".key").read() == key:
        return out, count_frames(out)
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a + 0.1:.3f}", "-i", ctx["src"],
        "-map", "0:v:0", "-an", "-vf", ",".join(chain), "-frames:v", n,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", "-r", fps,
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", out])
    open(out + ".key", "w").write(key)
    got = count_frames(out)
    if got != n:
        WARN.append(f"segmento {seg['id']}: {got} fotogramas en vez de {n}")
    return out, got


# ---------------------------------------------------------------- tiempos
def make_resolver(starts, ends, total):
    def resolve(v):
        if isinstance(v, (int, float)):
            return float(v)
        m = re.fullmatch(r"@([\w-]+?)(\.end)?([+-][\d.]+)?", str(v).strip())
        if not m:
            raise SystemExit(f"ERROR: referencia de tiempo no válida: {v}")
        name, is_end, off = m.groups()
        if name == "total":
            base = total
        elif name in starts:
            base = ends[name] if is_end else starts[name]
        else:
            raise SystemExit(f"ERROR: segmento desconocido en referencia {v}")
        return max(0.0, min(total, base + (float(off) if off else 0.0)))
    return resolve


# ---------------------------------------------------------------- textos
def ass_color(hexrgb, alpha="00"):
    h = hexrgb.lstrip("#")
    return f"&H{alpha}{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def font_available(name):
    try:
        fams = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True).stdout.lower()
        return name.lower() in fams
    except FileNotFoundError:
        return False


def build_ass(caps, resolve, brand, path):
    font = brand.get("font", "Inter Display Black")
    bold = 0
    if not brand.get("fonts_dir") and not font_available(font):
        WARN.append(f"fuente '{font}' no instalada: uso DejaVu Sans Bold. Sube el .ttf y pon brand.fonts_dir")
        font, bold = "DejaVu Sans", -1
    acc = ass_color(brand.get("accent", "#96FF28"))
    ptxt = ass_color(brand.get("punch_text", "#000000"))
    pop = r"\fscx70\fscy70\t(0,110,\fscx106\fscy106)\t(110,190,\fscx100\fscy100)"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {OUT_W}
PlayResY: {OUT_H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: hook,{font},96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,{bold},0,0,0,100,100,0,0,1,8,5,5,40,40,0,1
Style: cap,{font},86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,{bold},0,0,0,100,100,0,0,1,7,5,5,40,40,0,1
Style: punch,{font},82,{ptxt},{ptxt},{acc},&H00000000,{bold},0,0,0,100,100,1,0,3,18,0,5,40,40,0,1
Style: sub,{font},54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,{bold},0,0,0,100,100,0,0,1,5,3,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def ts(x):
        cs = int(round(x * 100))
        return f"{cs // 360000}:{(cs // 6000) % 60:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}"

    lines = []
    for c in caps:
        st, en = resolve(c["start"]), resolve(c["end"])
        if en <= st:
            WARN.append(f"texto '{c['text']}' con fin <= inicio; se omite")
            continue
        style = c.get("style", "cap")
        y, x = int(c.get("y", 330)), int(c.get("x", 540))
        if not SAFE_Y[0] <= y <= SAFE_Y[1]:
            WARN.append(f"texto '{c['text']}' en y={y}: fuera de la zona segura {SAFE_Y}")
        for part in c["text"].split("\n"):
            if len(part) > MAX_CHARS_LINE:
                WARN.append(f"texto '{part}' tiene {len(part)} caracteres en una línea (máx {MAX_CHARS_LINE})")
        if en - st < 0.8:
            WARN.append(f"texto '{c['text']}' dura {en - st:.2f}s (<0.8s): no da tiempo a leerlo")
        anim = pop if (st > 0 and c.get("anim", "pop") == "pop") else ""
        txt = c["text"].replace("{", "").replace("}", "").replace("\n", "\\N")
        lines.append(f"Dialogue: 1,{ts(st)},{ts(en)},{style},,0,0,0,,{{\\pos({x},{y}){anim}}}{txt}")
    open(path, "w", encoding="utf-8").write(head + "\n".join(lines) + "\n")


# ---------------------------------------------------------------- sonido
rng = np.random.default_rng(11)


def snd_impact(length=0.55):
    t = np.arange(int(SR * length)) / SR
    f = 38 + 52 * np.exp(-t * 22)
    body = np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5) * 2.2) / np.tanh(2.2)
    click = sosfilt(butter(2, 1800, "hp", fs=SR, output="sos"), rng.standard_normal(len(t)) * np.exp(-t * 260))
    thump = sosfilt(butter(2, [120, 900], "bp", fs=SR, output="sos"), rng.standard_normal(len(t))) * np.exp(-t * 40)
    return body + click * 0.35 + thump * 0.6


def snd_whoosh(length=0.42, peak=0.62):
    n = int(SR * length)
    x = np.linspace(0, 1, n)
    noise, out = rng.standard_normal(n), np.zeros(n)
    for s0 in range(0, n, 480):
        p = x[s0]
        fc = 400 + 5200 * np.sin(np.pi * min(p / peak, 1) * 0.5) ** 2 if p < peak else 5600 - 3800 * ((p - peak) / (1 - peak))
        sos = butter(2, [max(fc * 0.55, 60), min(fc * 1.6, 20000)], "bp", fs=SR, output="sos")
        out[s0:s0 + 480] = sosfilt(sos, noise[s0:s0 + 480])
    env = np.where(x < peak, (x / peak) ** 2.2, np.exp(-(x - peak) * 14))
    return out * env * 1.6


def snd_pop(length=0.09):
    t = np.arange(int(SR * length)) / SR
    return np.sin(2 * np.pi * np.cumsum(900 * np.exp(-t * 18) + 260) / SR) * np.exp(-t * 55) * 0.5


SOUNDS = {  # tipo: (generador, ganancia por defecto, adelanto para que el pico caiga en t)
    "impact_big": (lambda: snd_impact(0.7), 1.0, 0.01),
    "impact": (snd_impact, 0.75, 0.01),
    "riser": (lambda: snd_whoosh(1.2, 0.95), 0.45, 0.95 * 1.2),
    "whoosh_big": (lambda: snd_whoosh(0.42, 0.62), 0.55, 0.62 * 0.42),
    "whoosh_small": (lambda: snd_whoosh(0.26, 0.7), 0.28, 0.7 * 0.26),
    "pop": (snd_pop, 0.35, 0.0),
}


def place(buf, sig, t, gain=1.0, pan=0.0):
    i = int(round(t * SR))
    if i < 0:
        sig, i = sig[-i:], 0
    n = min(len(sig), len(buf) - i)
    if n <= 0:
        return
    if sig.ndim == 2:                      # estéreo (audio original): sin panorama
        buf[i:i + n] += sig[:n, :2] * gain
        return
    l, r = np.sqrt(0.5 * (1 - pan)) * 1.414, np.sqrt(0.5 * (1 + pan)) * 1.414
    buf[i:i + n, 0] += sig[:n] * gain * l
    buf[i:i + n, 1] += sig[:n] * gain * r


def build_sfx(segs, starts, caps, resolve, extra, total):
    buf = np.zeros((int(SR * total) + SR, 2))
    cap_starts = [resolve(c["start"]) for c in caps]
    events = []
    for i, s in enumerate(segs):
        st, sp = starts[s["id"]], float(s.get("speed", 1.0))
        if s.get("impact") is not None:
            ti = st + (float(s["impact"]) - float(s["in"])) / sp
            events += [("riser", ti), ("impact_big", ti)] if is_slow(s) else [("impact", ti)]
        if i > 0 and not s.get("silent_cut"):
            beat = any(abs(c - st) < 0.06 for c in cap_starts)
            events.append(("whoosh_big" if beat else "whoosh_small", st))
    for c in caps:
        t = resolve(c["start"])
        if t > 0 and c.get("sfx", True):
            events.append(("pop", t))
    for e in extra or []:
        events.append((e["type"], resolve(e["t"]), e.get("gain")))
    for ev in events:
        kind, t = ev[0], ev[1]
        gen, g, lead = SOUNDS[kind]
        gain = ev[2] if len(ev) > 2 and ev[2] is not None else g
        pan = -0.2 if kind == "whoosh_big" else (0.25 if kind == "whoosh_small" else 0.0)
        place(buf, gen(), t - lead, gain, pan)
    return buf[:int(SR * total)]


def atempo_chain(sp):
    parts = []
    while sp > 2.0:
        parts.append("atempo=2.0"); sp /= 2.0
    while sp < 0.5:
        parts.append("atempo=0.5"); sp /= 0.5
    parts.append(f"atempo={sp:.5f}")
    return ",".join(parts)


def build_original_audio(segs, starts, nfr, ctx, info, total):
    buf = np.zeros((int(SR * total) + SR, 2))
    if not info["has_audio"]:
        WARN.append("el bruto no tiene audio")
        return buf[:int(SR * total)]
    fade = int(0.01 * SR)
    for s in segs:
        if is_slow(s) and not s.get("keep_audio"):
            continue
        a, b, sp = float(s["in"]), float(s["out"]), float(s.get("speed", 1.0))
        tmp = os.path.join(ctx["work"], f"aud_{s['id']}.wav")
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", ctx["src"],
            "-map", "0:a:0", "-af", atempo_chain(sp) + ",aresample=48000", "-ac", "2", tmp])
        _, x = wavfile.read(tmp)
        x = x.astype(np.float64) / (32768.0 if x.dtype == np.int16 else 1.0)
        n = min(len(x), int(nfr[s["id"]] / ctx["fps"] * SR))
        x = x[:n].copy()
        if n > 2 * fade:
            x[:fade] *= np.linspace(0, 1, fade)[:, None]
            x[-fade:] *= np.linspace(1, 0, fade)[:, None]
        place(buf, x, starts[s["id"]], 1.0)
    return buf[:int(SR * total)]


def loudness(path):
    err = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", err)
    p = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", err)
    to_f = lambda s: float("-inf") if s == "-inf" else float(s)
    return (to_f(i[-1]) if i else float("-inf")), (to_f(p[-1]) if p else float("-inf"))


# ---------------------------------------------------------------- control de calidad
def qc(out, ctx, info, loop):
    o = probe(out)
    frames = count_frames(out)
    err = sh(["ffmpeg", "-hide_banner", "-i", out, "-vf", "mpdecimate", "-an", "-f", "null", "-"])
    kept = re.findall(r"frame=\s*(\d+)", err)
    dup = 1 - int(kept[-1]) / frames if kept and frames else 0.0
    I, TP = loudness(out)
    sheet = out.rsplit(".", 1)[0] + "_hoja.jpg"
    sh(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf", "fps=2,scale=216:384,tile=8x4", "-frames:v", "1", sheet])
    rep = {"archivo": out, "duracion_s": round(o["duration"], 2), "resolucion": f"{o['W']}x{o['H']}",
           "fps_salida": round(o["fps"], 3), "fps_bruto": round(info["fps"], 3), "fotogramas": frames,
           "fotogramas_casi_repetidos_pct": round(dup * 100, 1), "loudness_LUFS": I, "true_peak_dBFS": TP,
           "hoja_de_contactos": sheet}
    if loop:
        seam = out.rsplit(".", 1)[0] + "_empalme.png"
        sh(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.08", "-i", out, "-i", out, "-filter_complex",
            "[0:v]trim=end_frame=1,scale=360:640[a];[1:v]trim=end_frame=1,scale=360:640[b];[a][b]hstack",
            "-frames:v", "1", seam])
        rep["empalme_final_inicio"] = seam
    if abs(o["fps"] - round(info["fps"])) > 0.5:
        WARN.append(f"fps de salida {o['fps']:.2f} distinto del bruto {info['fps']:.2f}")
    if dup > 0.12:
        WARN.append(f"{dup * 100:.0f}% de fotogramas casi repetidos: revisa conversión de fps o planos estáticos largos")
    if I != float("-inf") and not -18 <= I <= -13:
        WARN.append(f"volumen integrado {I} LUFS fuera de -18..-13")
    if TP > -1.0:
        WARN.append(f"pico real {TP} dBFS (> -1.0)")
    if o["duration"] > 60:
        WARN.append("dura más de 60 s")
    rep["avisos"] = WARN
    return rep


# ---------------------------------------------------------------- principal
def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    edl_path = sys.argv[1]
    edl = json.load(open(edl_path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(edl_path))
    src = edl["source"] if os.path.isabs(edl["source"]) else os.path.join(base, edl["source"])
    out = edl.get("output", "tiktok.mp4")
    out = out if os.path.isabs(out) else os.path.join(base, out)
    work = edl.get("workdir") or out.rsplit(".", 1)[0] + "_work"
    work = work if os.path.isabs(work) else os.path.join(base, work)
    os.makedirs(work, exist_ok=True)

    missing = check_ffmpeg()
    info = probe(src)
    if missing:
        if "zscale" in missing and info["hdr"]:
            raise SystemExit("ERROR: el bruto es HDR y este ffmpeg no tiene zscale: no puedo convertirlo bien a SDR.")
        if "ass" in missing:
            raise SystemExit("ERROR: este ffmpeg no tiene libass (filtro 'ass'): no puedo poner textos.")
        WARN.append(f"filtros ausentes: {missing}")
    fps = edl.get("fps") or int(round(info["fps"]))
    ctx = {"src": src, "work": work, "fps": fps, "grade": edl.get("grade", "punchy")}
    print(f"bruto: {info['W']}x{info['H']} {info['fps']:.3f} fps, HDR={info['hdr']} ({info['trc']}), "
          f"{info['duration']:.2f}s -> salida {OUT_W}x{OUT_H} a {fps} fps", flush=True)

    segs = edl["segments"]
    ids = [s["id"] for s in segs]
    if len(set(ids)) != len(ids) or "total" in ids:
        raise SystemExit("ERROR: ids de segmento repetidos o 'total' usado como id")
    starts, ends, nfr, files, t = {}, {}, {}, [], 0
    for s in segs:
        path, n = render_segment(s, info, ctx)
        starts[s["id"]], nfr[s["id"]] = t / fps, n
        t += n
        ends[s["id"]] = t / fps
        files.append(path)
        print(f"  {s['id']:<10} {starts[s['id']]:6.2f}s -> {ends[s['id']]:6.2f}s ({n} fot.)", flush=True)
    total = t / fps
    resolve = make_resolver(starts, ends, total)

    caps = edl.get("captions", [])
    ass_path = os.path.join(work, "captions.ass")
    build_ass(caps, resolve, edl.get("brand", {}), ass_path)

    aud = edl.get("audio", {})
    mix = np.zeros((int(SR * total), 2))
    if aud.get("sfx", True):
        mix += build_sfx(segs, starts, caps, resolve, edl.get("sfx_extra"), total) * 10 ** (aud.get("sfx_gain_db", 0) / 20)
    if aud.get("keep_original"):
        mix += build_original_audio(segs, starts, nfr, ctx, info, total) * 10 ** (aud.get("original_gain_db", 0) / 20)
    peak = np.max(np.abs(mix)) if mix.size else 0
    if peak > 0:
        mix *= 10 ** (-1.5 / 20) / peak
    mix_path = os.path.join(work, "mix.wav")
    wavfile.write(mix_path, SR, (mix * 32767).astype(np.int16))
    I, _ = loudness(mix_path) if peak > 0 else (float("-inf"), 0)
    gain = max(-20.0, min(20.0, aud.get("target_lufs", -16) - I)) if I != float("-inf") else 0.0

    with open(os.path.join(work, "list.txt"), "w") as f:
        for p in files:
            f.write(f"file '{p}'\n")
    vf = f"[0:v]ass={ass_path}"
    if edl.get("brand", {}).get("fonts_dir"):
        vf += f":fontsdir={edl['brand']['fonts_dir']}"
    vf += f",format=yuv420p[v];[1:a]volume={gain:.2f}dB,alimiter=limit=0.79:level=false[a]"
    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(work, "list.txt"),
        "-i", mix_path, "-filter_complex", vf, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-profile:v", "high", "-level", "4.1",
        "-pix_fmt", "yuv420p", "-r", fps, "-color_primaries", "bt709", "-color_trc", "bt709",
        "-colorspace", "bt709", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
        "-movflags", "+faststart", out])
    rep = qc(out, ctx, info, edl.get("loop", False))
    json.dump(rep, open(out.rsplit(".", 1)[0] + "_qc.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
