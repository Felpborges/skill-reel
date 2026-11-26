#!/usr/bin/env python3
"""Acha o tempo de uma frase (ou palavra) no palavras.json: toda entrada de elemento é ancorada na fala.

Uso: ferramentas/ancoras.py <pasta com palavras.json> "frase exata" ["outra frase" ...] [--n 1] [--fim] [--json]
  Imprime o início (ou o fim, com --fim) da N-ésima ocorrência da frase, em segundos. Erro (saída 2) se a
  frase não existir: nunca chute um tempo. Compara sem acento, caixa ou pontuação.
  Com --json imprime {"frase": {"i":…, "f":…, "palavras": […]}} para todas as frases pedidas.
Em código (gerador do estilo): `from ancoras import Ancoras; A = Ancoras("preparo"); t = A.at("três ferramentas")`.
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import argparse, json, os, re, sys, unicodedata

def norm(s): return re.sub(r"[^\w ]", "", unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()).split()

class Ancoras:
    def __init__(self, pasta_ou_arquivo):
        arq = pasta_ou_arquivo if pasta_ou_arquivo.endswith(".json") else os.path.join(pasta_ou_arquivo, "palavras.json")
        self.pal = json.load(open(arq, encoding="utf-8")); self.tok = [norm(p["t"])[0] if norm(p["t"]) else "" for p in self.pal]
    def achar(self, frase, n=1):
        alvo = norm(frase); k = 0
        if not alvo: raise ValueError("frase vazia")
        for i in range(len(self.tok) - len(alvo) + 1):
            if self.tok[i:i + len(alvo)] == alvo:
                k += 1
                if k == n: ps = self.pal[i:i + len(alvo)]; return {"i": ps[0]["i"], "f": ps[-1]["f"], "palavras": ps}
        raise LookupError(f"frase não encontrada na fala: {frase!r} (ocorrência {n})")
    def at(self, frase, n=1): return self.achar(frase, n)["i"]
    def fim(self, frase, n=1): return self.achar(frase, n)["f"]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("pasta"); ap.add_argument("frases", nargs="+"); ap.add_argument("--n", type=int, default=1); ap.add_argument("--fim", action="store_true"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args(); A = Ancoras(a.pasta); out = {}
    for fr in a.frases:
        try: out[fr] = A.achar(fr, a.n)
        except LookupError as e: print(f"ERRO: {e}", file=sys.stderr); sys.exit(2)
    if a.json: print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for fr, r in out.items(): print(f"{(r['f'] if a.fim else r['i']):.3f}\t{fr}")

if __name__ == "__main__": main()
