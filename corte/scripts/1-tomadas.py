"""Passo 1 — mapa de TOMADAS do bruto: onde há fala e o que foi dito em cada trecho.

Não confie na transcrição palavra a palavra do vídeo inteiro: em silêncios longos o Whisper inventa texto
(repete a frase anterior) e desloca os tempos. Aqui a fala é achada pela ENERGIA e cada trecho é
transcrito sozinho — é isso que mostra as retomadas, frases abandonadas e falsas largadas de verdade.

uso:  python3 1-tomadas.py VIDEO PASTA
saída: PASTA/audio16k.wav, PASTA/tomadas.json, PASTA/tomadas.txt  (leia o .txt para escolher os keeps)
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import json, os, sys, wave
import numpy as np
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from comum import audio16k, recorte, texto, PROMPT_VICIOS

VIDEO, P = sys.argv[1], sys.argv[2]
os.makedirs(P, exist_ok=True)
wav = f"{P}/audio16k.wav"
audio16k(VIDEO, wav)

w = wave.open(wav)
x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
n = len(x) // 160
db = 20 * np.log10(np.sqrt((x[:n * 160].reshape(n, 160) ** 2).mean(1)) + 1e-9)   # 10 ms
thr = np.percentile(db, 10) + 18          # piso de ruído da sala + 18 dB
sp = db > thr

regioes, i = [], 0
while i < n:
    if sp[i]:
        j = i
        while j < n and (sp[j] or sp[j:j + 15].any()):   # junta buracos < 0,15 s
            j += 1
        regioes.append((i / 100, j / 100)); i = j
    else:
        i += 1

linhas, saida = [], []
tmp = f"{P}/_trecho.wav"
for a, b in regioes:
    if b - a < 0.3:
        continue
    a0, b0 = max(0, a - 0.15), b + 0.15
    recorte(wav, a0, b0, tmp)
    t = texto(tmp, PROMPT_VICIOS)
    saida.append({"from": round(a0, 2), "to": round(b0, 2), "texto": t})
    linhas.append(f"{a0:7.2f}-{b0:7.2f} ({b0 - a0:4.1f}s) :: {t}")
    print(linhas[-1], flush=True)
os.remove(tmp)
json.dump(saida, open(f"{P}/tomadas.json", "w"), ensure_ascii=False, indent=1)
open(f"{P}/tomadas.txt", "w").write("\n".join(linhas) + "\n")
