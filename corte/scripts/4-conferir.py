"""Passo 4 — conferência obrigatória do corte (nunca entregue sem rodar e LER a saída).

1. transcrição inteira do corte, palavra a palavra (vira a base das legendas: cortepalavras.json);
2. cada EMENDA transcrita sozinha numa janela de ±2 s — é aí que aparecem retomadas murmuradas,
   "então" duplicado e meia palavra que a transcrição longa esconde;
3. caça automática de repetição colada (mesma palavra/expressão de 1 a 4 palavras duas vezes seguidas);
4. pausas que sobraram (> 0,25 s abaixo do limiar da fala).

uso:  python3 4-conferir.py PASTA [--prompt "nomes próprios do vídeo"]
saída: PASTA/cortepalavras.json, PASTA/conferencia.txt (e o mesmo na tela)
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import json, os, subprocess, sys, unicodedata
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from comum import palavras, recorte, texto, PROMPT_NOMES

P = sys.argv[1]
args = sys.argv[2:]
prompt = args[args.index("--prompt") + 1] if "--prompt" in args else PROMPT_NOMES
edl = json.load(open(f"{P}/edl.json"))
total = edl[-1]["out"] + edl[-1]["dur"]
rel = []

ws = palavras(f"{P}/corte16k.wav", prompt)
json.dump(ws, open(f"{P}/cortepalavras.json", "w"), ensure_ascii=False)
rel.append("== TEXTO DO CORTE (leia inteiro) ==\n" + " ".join(t for a, b, t in ws) + "\n")

def nz(s): return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if c.isalnum())
toks = [nz(t) for a, b, t in ws]
rep = []
for k in range(1, 5):
    for i in range(len(toks) - 2 * k + 1):
        if toks[i:i + k] == toks[i + k:i + 2 * k] and any(len(x) > 2 for x in toks[i:i + k]):
            rep.append(f"  {ws[i][0]:6.2f}s  \"{' '.join(t for a, b, t in ws[i:i + 2 * k])}\"")
rel.append("== REPETIÇÕES COLADAS ==\n" + ("\n".join(rep) if rep else "  nenhuma") + "\n")

rel.append("== EMENDAS (janela ±2 s, transcrita sozinha) ==")
tmp = f"{P}/_jan.wav"
for c in edl[1:]:
    t = c["out"]
    recorte(f"{P}/corte16k.wav", max(0, t - 2), min(total, t + 2), tmp)
    # sem prompt: em janela curta o prompt de vícios faz o Whisper INVENTAR "é, ah, hum"
    rel.append(f"  {t:6.2f}s  (fonte {c['src']:.2f}) :: {texto(tmp)}")
os.remove(tmp)

r = subprocess.run(["ffmpeg", "-hide_banner", "-i", f"{P}/corte.wav", "-af", "silencedetect=noise=-38dB:d=0.25",
                    "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
pausas = [l.split("silence_end: ")[1] for l in r.splitlines() if "silence_end" in l]
rel.append("\n== PAUSAS > 0,25 s QUE SOBRARAM ==\n" + ("\n".join("  fim " + p for p in pausas) if pausas else "  nenhuma"))
rel.append(f"\nduração do corte: {total:.2f}s")

out = "\n".join(rel) + "\n"
open(f"{P}/conferencia.txt", "w").write(out)
print(out)
