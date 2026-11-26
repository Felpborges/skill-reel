"""Passo 2 — transcrição que NÃO esconde vícios ("éé", "ããã", "hum"), só dentro dos keeps escolhidos.

O Whisper normalmente apaga hesitações; com um prompt cheio delas ele passa a escrevê-las, e o corte
(3-corte.py) consegue tirar cada uma. Transcrever por keep (e não o vídeo inteiro) evita o texto inventado
nos silêncios longos.

uso:  python3 2-vicios.py PASTA          (lê PASTA/keeps.json e PASTA/audio16k.wav)
saída: PASTA/vicios/k{i}.json  (palavras com tempo da FONTE) e o texto de cada keep na tela
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import json, os, sys
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from comum import recorte, palavras, PROMPT_VICIOS

P = sys.argv[1]
keeps = json.load(open(f"{P}/keeps.json"))["keeps"]
os.makedirs(f"{P}/vicios", exist_ok=True)
tmp = f"{P}/_keep.wav"
for i, k in enumerate(keeps):
    recorte(f"{P}/audio16k.wav", k["from"], k["to"], tmp)
    ws = palavras(tmp, PROMPT_VICIOS, deslocamento=k["from"])
    json.dump(ws, open(f"{P}/vicios/k{i}.json", "w"), ensure_ascii=False)
    print(f"[{i}] {k['from']:.2f}-{k['to']:.2f} {k.get('why', '')}\n    " +
          " ".join(f"{t}({a:.2f})" for a, b, t in ws) + "\n", flush=True)
os.remove(tmp)
