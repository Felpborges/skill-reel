#!/usr/bin/env python3
"""Mede o rosto do apresentador ao longo do vídeo: topo da cabeça, queixo, centro, largura.

Uso: ferramentas/rosto.py <video> <pasta de saída> [--passo 0.5] [--916]
Saída: <pasta>/rosto.json com:
  quadros: [{"t", "x", "y", "w", "h", "topo", "queixo", "cx"}]  (em px do vídeo de entrada)
  resumo: mediana/p5/min/max do topo da cabeça e do queixo, centro médio, e as sugestões de enquadramento
          para 1080×1920 (--916 converte tudo para o recorte 9:16 centrado no rosto):
          - dividido: y do topo da câmera para o rosto inteiro ficar na metade de baixo (R1: vídeo desce ≈ 990 − topo)
          - livre_acima_da_cabeca: px livres acima do topo no recorte (título atrás da cabeça só com ≥ ~300)
          - punch_max: zoom máximo sem o queixo passar de y 950 nem o topo sair do quadro
Detector: OpenCV Haar (frontal); a cabeça inteira é estimada como o retângulo do rosto esticado 35 % para cima.
Precisa: python3 -m pip install opencv-python-headless numpy
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import argparse, json, os, sys
import numpy as np
try: import cv2
except ImportError: sys.exit("precisa de opencv: python3 -m pip install opencv-python-headless numpy")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("pasta"); ap.add_argument("--passo", type=float, default=0.5); ap.add_argument("--916", dest="v916", action="store_true")
    a = ap.parse_args(); os.makedirs(a.pasta, exist_ok=True)
    cap = cv2.VideoCapture(a.video); fps = cap.get(cv2.CAP_PROP_FPS) or 24; W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    esc = 0.5 if W > 1400 else 1.0; quadros = []
    for k in range(0, N, max(1, int(round(fps * a.passo)))):
        cap.set(cv2.CAP_PROP_POS_FRAMES, k); ok, f = cap.read()
        if not ok: break
        g = cv2.cvtColor(cv2.resize(f, None, fx=esc, fy=esc), cv2.COLOR_BGR2GRAY)
        fs = casc.detectMultiScale(g, 1.1, 6, minSize=(int(60 * esc), int(60 * esc)))
        if len(fs) == 0: continue
        x, y, w, h = max(fs, key=lambda r: r[2] * r[3]); x, y, w, h = [int(v / esc) for v in (x, y, w, h)]
        topo = max(0, int(y - 0.35 * h)); queixo = int(y + h * 1.02)
        quadros.append({"t": round(k / fps, 2), "x": x, "y": y, "w": w, "h": h, "topo": topo, "queixo": queixo, "cx": x + w // 2})
    if not quadros: sys.exit("nenhum rosto detectado")
    topos = np.array([q["topo"] for q in quadros]); queixos = np.array([q["queixo"] for q in quadros]); cxs = np.array([q["cx"] for q in quadros]); ws = np.array([q["w"] for q in quadros])
    resumo = {"largura": W, "altura": H, "fps": round(fps, 3), "amostras": len(quadros),
              "topo": {"mediana": int(np.median(topos)), "p5": int(np.percentile(topos, 5)), "min": int(topos.min()), "max": int(topos.max())},
              "queixo": {"mediana": int(np.median(queixos)), "p95": int(np.percentile(queixos, 95)), "max": int(queixos.max())},
              "centro_x": int(np.median(cxs)), "largura_rosto": int(np.median(ws))}
    # recorte 9:16 centrado no rosto (x), escala para 1080×1920
    rh = H; rw = int(round(H * 9 / 16))
    if rw > W: rw = W; rh = int(round(W * 16 / 9))
    x0 = int(min(max(0, resumo["centro_x"] - rw // 2), W - rw)); s = 1920 / rh
    topo916 = int(resumo["topo"]["p5"] * s); queixo916 = int(resumo["queixo"]["p95"] * s)
    resumo["recorte_916"] = {"x0": x0, "y0": 0, "largura": rw, "altura": rh, "escala": round(s, 4), "topo_p5": topo916, "queixo_p95": queixo916, "centro_x": int((resumo["centro_x"] - x0) * s)}
    resumo["sugestoes"] = {
        "dividido_y_da_camera": int(990 - topo916), "livre_acima_da_cabeca": topo916,
        "titulo_atras_da_cabeca": "sim" if topo916 >= 300 else "não (menos de 300 px livres: use lettering no peito)",
        "punch_max": round(min(950 / max(queixo916, 1), 1.35), 3) if queixo916 > 0 else 1.0}
    if a.v916:
        for q in quadros:
            for ch in ("x", "cx"): q[ch] = int((q[ch] - x0) * s)
            for ch in ("y", "w", "h", "topo", "queixo"): q[ch] = int(q[ch] * s)
    json.dump({"resumo": resumo, "quadros": quadros}, open(os.path.join(a.pasta, "rosto.json"), "w"), indent=1)
    print(json.dumps(resumo, indent=1, ensure_ascii=False))

if __name__ == "__main__": main()
