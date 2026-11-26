"""Remapeia tempos de um corte ANTIGO para o corte NOVO pelas palavras em comum.

Use quando a edição (legendas, cards, zooms, efeitos) já foi cronometrada num corte e a decupagem muda:
não recronometre à mão — mapeie. Âncoras = início de cada palavra que existe nos dois cortes.

como módulo:  from remapear import Mapa;  m = Mapa("velho/cortepalavras.json", "novo/cortepalavras.json")
              m.novo(t_velho) · m.velho(t_novo)
na linha de comando:  python3 remapear.py velho.json novo.json 0.87 2.73 ...   (imprime velho → novo)
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import difflib, json, sys, unicodedata
import numpy as np


def _nz(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if c.isalpha())


class Mapa:
    def __init__(self, velho, novo, fim_velho=None, fim_novo=None):
        o = json.load(open(velho)) if isinstance(velho, str) else velho
        nw = json.load(open(novo)) if isinstance(novo, str) else novo
        sm = difflib.SequenceMatcher(a=[_nz(w[2]) for w in o], b=[_nz(w[2]) for w in nw], autojunk=False)
        po, pn = [0.0], [0.0]
        for blk in sm.get_matching_blocks():
            for k in range(blk.size):
                a, b = o[blk.a + k][0], nw[blk.b + k][0]
                if a > po[-1] and b > pn[-1]:          # mantém o mapa monotônico
                    po.append(a); pn.append(b)
        fo = fim_velho or o[-1][1] + 0.5
        fn = fim_novo or nw[-1][1] + 0.5
        po.append(max(fo, po[-1] + 0.01)); pn.append(max(fn, pn[-1] + 0.01))
        self.po, self.pn = np.array(po), np.array(pn)

    def novo(self, t): return float(np.interp(t, self.po, self.pn))
    def velho(self, t): return float(np.interp(t, self.pn, self.po))


if __name__ == "__main__":
    m = Mapa(sys.argv[1], sys.argv[2])
    print(f"{len(m.po)} âncoras")
    for t in map(float, sys.argv[3:]):
        print(f"{t:7.2f} → {m.novo(t):7.2f}")
