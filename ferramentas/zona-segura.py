#!/usr/bin/env python3
"""Zona segura (R7): folha de quadros a cada 0,25 s com a caixa desenhada + alerta automático nas margens.

Uso: ferramentas/zona-segura.py <video 1080x1920> [--perfil reels|anuncio] [--passo 0.25] [--saida pasta]
      [--camera video-so-camera.mp4]
Saída: <saida>/zona-segura.png (folha de quadros com a caixa) e <saida>/zona-segura.json com os instantes
suspeitos. O alerta compara, nas faixas fora da caixa, a densidade de bordas do vídeo final com a do vídeo
só-câmera (se --camera for dado) ou com um limiar fixo; serve para apontar ONDE olhar, a decisão final é visual.
Perfis: reels = x 90–990, y 220–1520, e coluna de botões x>940 & y>1150 proibida; anuncio = x 65–1015, y 270–1248.
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import argparse, json, os, subprocess, sys, tempfile
import numpy as np
try: import cv2
except ImportError: sys.exit("precisa de opencv: python3 -m pip install opencv-python-headless numpy")

PERFIS = {"reels": {"x": (90, 990), "y": (220, 1520), "botoes": (940, 1150)}, "anuncio": {"x": (65, 1015), "y": (270, 1248), "botoes": None}}

def quadros(video, passo, d):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", f"fps=1/{passo},scale=1080:1920", os.path.join(d, "q-%04d.png")], check=True)
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.startswith("q-"))

def densidade(img, caixa, botoes):
    g = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 80, 160) > 0
    h, w = g.shape; mask = np.ones_like(g, dtype=bool)
    mask[caixa["y"][0]:caixa["y"][1], caixa["x"][0]:caixa["x"][1]] = False  # dentro da caixa não interessa
    fora = g & mask
    val = {"topo": fora[:caixa["y"][0]].mean(), "base": fora[caixa["y"][1]:].mean(), "esq": fora[:, :caixa["x"][0]].mean(), "dir": fora[:, caixa["x"][1]:].mean()}
    if botoes: val["botoes"] = g[botoes[1]:, botoes[0]:].mean()
    return {k: float(round(v, 4)) for k, v in val.items()}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--perfil", default="reels", choices=PERFIS); ap.add_argument("--passo", type=float, default=0.25); ap.add_argument("--saida"); ap.add_argument("--camera"); ap.add_argument("--limiar", type=float, default=0.012)
    a = ap.parse_args(); caixa = PERFIS[a.perfil]; saida = a.saida or os.path.dirname(os.path.abspath(a.video)); os.makedirs(saida, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        qs = quadros(a.video, a.passo, d); cam = quadros(a.camera, a.passo, os.path.join(d, "c")) if a.camera and os.makedirs(os.path.join(d, "c"), exist_ok=True) is None else []
        suspeitos, tiles = [], []
        for k, q in enumerate(qs):
            img = cv2.imread(q); t = round(k * a.passo, 2); dv = densidade(img, caixa, caixa["botoes"])
            ref = densidade(cv2.imread(cam[k]), caixa, caixa["botoes"]) if k < len(cam) else None
            alerta = [z for z, v in dv.items() if (v - (ref[z] if ref else 0)) > a.limiar]
            if alerta: suspeitos.append({"t": t, "zonas": alerta, "densidade": dv})
            cv2.rectangle(img, (caixa["x"][0], caixa["y"][0]), (caixa["x"][1], caixa["y"][1]), (0, 255, 120), 4)
            if caixa["botoes"]: cv2.rectangle(img, (caixa["botoes"][0], caixa["botoes"][1]), (1080, 1920), (0, 80, 255), 4)
            if alerta: cv2.rectangle(img, (0, 0), (1079, 1919), (0, 0, 255), 18)
            cv2.putText(img, f"{t:.2f}s" + (" !" + ",".join(alerta) if alerta else ""), (24, 80), cv2.FONT_HERSHEY_SIMPLEX, 2.2, (255, 255, 255), 6)
            tiles.append(cv2.resize(img, (270, 480)))
        col = 8; linhas = [np.hstack(tiles[i:i + col] + [np.zeros((480, 270, 3), np.uint8)] * (col - len(tiles[i:i + col]))) for i in range(0, len(tiles), col)]
        cv2.imwrite(os.path.join(saida, "zona-segura.png"), np.vstack(linhas))
    json.dump({"perfil": a.perfil, "passo": a.passo, "quadros": len(qs), "suspeitos": suspeitos}, open(os.path.join(saida, "zona-segura.json"), "w"), indent=1)
    print(f"{len(qs)} quadros · {len(suspeitos)} suspeitos → {saida}/zona-segura.png" + ("" if not suspeitos else f" · olhe em: {[s['t'] for s in suspeitos][:12]}"))
    sys.exit(1 if suspeitos else 0)

if __name__ == "__main__": main()
