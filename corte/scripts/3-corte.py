"""Passo 3 — o motor de corte: corte pelo SOM + vícios fora + bordas no vale + J/L.

Portado de tight-jl-cut.py / tight-cut.py (pacote-edite-reels) e calibrado na v2 do reel
"3 ferramentas do Claude" (out/2026).

1. fala detectada pelo SOM: volume E inclinação espectral (graves vs. agudos). Respiração e ruído de boca
   são agudos ou baixos demais → saem; finais de palavra ficam (TAIL protege o "s" final).
   Os limiares do pacote (−33/−26 dB) são deslocados pelo nível da SUA gravação (p90 da fala → −20 dB).
2. vícios listados em vicios/k*.json viram silêncio: hesitação pura sai inteira; conjunção esticada
   ("e", "é", "a", "um", "o" com 0,45–1,6 s) fica só com o começo (0,14 s).
3. bordas de cada keep encostam no vale de energia mais próximo, procurando PARA FORA do texto mantido.
4. J/L alternados em cada emenda real (pausa ≥ 0,25 s removida): a imagem corta JL quadros depois (J) ou
   antes (L) do som.

uso:  python3 3-corte.py VIDEO PASTA [--jl 4] [--sem-video]
entradas: PASTA/keeps.json {"keeps":[{"from","to","why", "raw"?}]}, PASTA/audio16k.wav,
          PASTA/vicios/k*.json (opcional), PASTA/ajustes.json (opcional):
          {"cut":[[ini,fim]], "keep":[t], "force":[[ini,fim]]}  (tempos da FONTE; "force" mantém um som
          que não é voz — estalo, palma — e "keep" protege um vício que deve ficar)
saídas:   PASTA/edl.json (trechos + deslocamento da imagem), PASTA/corte.wav (48 kHz estéreo),
          PASTA/corte16k.wav, PASTA/vicios-removidos.txt, PASTA/clean.mp4 (horizontal, com J/L)
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import glob, json, os, subprocess, sys, unicodedata, wave
import numpy as np

VIDEO, P = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
JL = int(args[args.index("--jl") + 1]) if "--jl" in args else 4
FPS = 30
SR, HOP, WIN = 16000, 160, 480            # quadros de 10 ms, janela de análise de 30 ms
LEAD, TAIL = 0.06, 0.14                   # antes do 1º / depois do último quadro de fala
HOLE, ISLAND = 0.20, 0.07                 # fecha buracos < HOLE; descarta ilhas de "fala" < ISLAND
REF_DB = -20.0                            # p90 da fala é levado a este nível; MENOR = limiares mais altos (corta mais)
fr = lambda t: round(t * FPS) / FPS

w = wave.open(f"{P}/audio16k.wav")
a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
n = (len(a) - WIN) // HOP
f = np.fft.rfftfreq(WIN, 1 / SR); lo_b = (f > 80) & (f < 900); hi_b = (f > 2000) & (f < 7000); hann = np.hanning(WIN)
quadros = np.lib.stride_tricks.sliding_window_view(a, WIN)[::HOP][:n]
db = 20 * np.log10(np.sqrt((quadros ** 2).mean(1)) + 1e-9)
X = np.abs(np.fft.rfft(quadros * hann, axis=1)) ** 2
tilt = 10 * np.log10((X[:, lo_b].sum(1) + 1e-12) / (X[:, hi_b].sum(1) + 1e-12))

ref = np.percentile(db[db > -60], 90)
OFF = ref - REF_DB
T1, T2 = -33 + OFF, -26 + OFF
sp = ((db > T1) & (tilt > 12)) | ((db > T2) & (tilt > 0))
print(f"nível da fala (p90) {ref:.1f} dB → limiares {T1:.1f} / {T2:.1f} dB")

# ---- vícios → silêncio forçado
def nz(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if c.isalpha())
cuts = []
for arq in sorted(glob.glob(f"{P}/vicios/k*.json")):
    for s0, e0, t in json.load(open(arq)):
        tt, d = nz(t), e0 - s0
        pura = tt in ("aa", "aaa", "ee", "eee", "eh", "ah", "hum", "hm", "uh", "umm", "mm") or (len(tt) > 1 and len(set(tt)) == 1)
        if pura: cuts.append([s0, e0, t])
        elif tt in ("e", "a", "um", "o") and 0.45 < d < 1.6: cuts.append([s0 + 0.14, e0, t + " (esticado)"])
aj = json.load(open(f"{P}/ajustes.json")) if os.path.exists(f"{P}/ajustes.json") else {}
cuts = [c for c in cuts if not any(abs(c[0] - k) < 0.3 for k in aj.get("keep", []))] + [[x, y, "manual"] for x, y in aj.get("cut", [])]
for s0, e0, _ in cuts:
    sp[max(0, int(s0 * 100)):min(n, int(e0 * 100))] = False
for s0, e0 in aj.get("force", []):
    sp[max(0, int(s0 * 100)):min(n, int(e0 * 100))] = True
open(f"{P}/vicios-removidos.txt", "w").write("\n".join(f"{s0:.2f}-{e0:.2f}  {t}" for s0, e0, t in cuts) + "\n")
print(f"vícios removidos: {len(cuts)}")

def runs(mask):
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j < len(mask) and mask[j]: j += 1
            out.append([i, j]); i = j
        else: i += 1
    return out
merged = []
for s0, e0 in runs(sp):
    # não fecha o buraco se ele é um vício removido de propósito
    vicio = merged and any(merged[-1][1] * 0.01 <= c[0] + 0.02 and c[1] - 0.02 <= s0 * 0.01 for c in cuts)
    if merged and (s0 - merged[-1][1]) * 0.01 < HOLE and not vicio:
        merged[-1][1] = e0
    else: merged.append([s0, e0])
regions = [(s0 * 0.01, e0 * 0.01) for s0, e0 in merged if (e0 - s0) * 0.01 >= ISLAND]

def valley(t, before=0.15, after=0.03):
    i0, i1 = max(0, int((t - before) * 100)), min(n, int((t + after) * 100))
    return (i0 + int(np.argmin(db[i0:i1]))) * 0.01 if i1 > i0 else t

segs = []
for k in json.load(open(f"{P}/keeps.json"))["keeps"]:
    if k.get("raw"):                       # mantém o trecho como está (ataque de palavra soprado que o detector perderia)
        segs.append([k["from"], k["to"]]); continue
    k0, k1 = valley(k["from"], 0.15, 0.03), valley(k["to"], 0.03, 0.15)
    for s0, e0 in regions:
        if e0 <= k0 or s0 >= k1: continue
        segs.append([max(k0, s0 - LEAD), min(k1, e0 + TAIL)])
segs.sort()
final = []
for s0, e0 in segs:
    if final and s0 - final[-1][1] < 0.08: final[-1][1] = max(final[-1][1], e0)
    else: final.append([s0, e0])
final = [[fr(s0), fr(e0)] for s0, e0 in final if fr(e0) - fr(s0) >= 2 / FPS]

# ---- J/L: shift[i] = quanto o corte da IMAGEM entre i-1 e i acontece depois (+, J) ou antes (−, L) do som
d = JL / FPS
shift = [0.0] * len(final)
flip = 0
for i in range(len(final) - 1):
    if final[i + 1][0] - final[i][1] < 0.25 or d == 0: continue
    shift[i + 1] = d if flip % 2 == 0 else -d
    flip += 1

edl, t = [], 0.0
for (s0, e0), sh in zip(final, shift):
    nf = round((e0 - s0) * FPS)
    edl.append({"src": s0, "dur": nf / FPS, "out": round(t, 4), "nf": nf, "vshift": sh})
    t += nf / FPS
json.dump(edl, open(f"{P}/edl.json", "w"), indent=1)
print(f"{len(edl)} trechos · J/L em {flip} emendas · duração {t:.2f}s")

# ---- áudio: 48 kHz estéreo, fade 8 ms na entrada e 12 ms na saída de cada trecho
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", VIDEO, "-ac", "2", "-ar", "48000", "-f", "f32le", "-"],
                     capture_output=True).stdout
x = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
SR2 = 48000; FI, FO = int(0.008 * SR2), int(0.012 * SR2)
partes = []
for c in edl:
    s0 = int(round(c["src"] * SR2)); m = int(round(c["dur"] * SR2))
    p = x[s0:s0 + m].copy()
    p[:FI] *= np.linspace(0, 1, FI)[:, None]; p[-FO:] *= np.linspace(1, 0, FO)[:, None]
    partes.append(p)
np.concatenate(partes).astype(np.float32).tofile(f"{P}/corte.f32")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", "48000", "-ac", "2", "-i", f"{P}/corte.f32", f"{P}/corte.wav"], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{P}/corte.wav", "-ac", "1", "-ar", "16000", f"{P}/corte16k.wav"], check=True)
os.remove(f"{P}/corte.f32")

if "--sem-video" in args:
    sys.exit(0)

# ---- imagem: cada trecho visual j vai de VSTART[j] a VSTART[j+1] no tempo de saída, fonte = src_j + (T − out_j)
VSTART = [0.0] + [c["out"] + c["vshift"] for c in edl[1:]] + [t]
fc = []
for j, c in enumerate(edl):
    vs = c["src"] + VSTART[j] - c["out"]; ve = c["src"] + VSTART[j + 1] - c["out"]
    fc.append(f"[0:v]trim={vs:.4f}:{ve:.4f},setpts=PTS-STARTPTS,fps={FPS},format=yuv420p[v{j}];")
fc.append("".join(f"[v{j}]" for j in range(len(edl))) + f"concat=n={len(edl)}:v=1:a=0[v]")
filtro = "".join(fc)
enc = ["-c:v", "h264_videotoolbox", "-b:v", "16M"] if sys.platform == "darwin" else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
cmd = lambda e: ["ffmpeg", "-v", "error", "-y", "-i", VIDEO, "-i", f"{P}/corte.wav", "-filter_complex", filtro,
                 "-map", "[v]", "-map", "1:a", *e, "-g", str(FPS), "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
                 "-shortest", f"{P}/clean.mp4"]
if subprocess.run(cmd(enc)).returncode != 0:
    subprocess.run(cmd(["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]), check=True)
print(f"→ {P}/clean.mp4")
