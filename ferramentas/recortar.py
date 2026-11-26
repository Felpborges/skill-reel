#!/usr/bin/env python3
"""Recorte do apresentador (matte) com Robust Video Matting, para títulos atrás da cabeça e colagem.

Uso: RVM_PYTHON=~/.venvs/rvm/bin/python  $RVM_PYTHON ferramentas/recortar.py <video> <pasta de saída> [--de 0] [--ate fim]
      [--largura W --altura H] [--modelo resnet50|mobilenetv3] [--reduzir 0.25]
Saída: <pasta>/matte/fg.mov (ProRes 4444 com alfa, mesma taxa do original) e <pasta>/matte/fg.webm (VP9 com alfa,
para usar em <video> no HyperFrames). Roda no Python do venv que tem torch (variável RVM_PYTHON, regra R10); baixa
o modelo pelo torch.hub na primeira vez. Em vídeo 2560×1440 leva alguns minutos por minuto de vídeo (MPS/CPU).
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import argparse, json, os, subprocess, sys

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("pasta"); ap.add_argument("--de", type=float, default=0.0); ap.add_argument("--ate", type=float); ap.add_argument("--largura", type=int); ap.add_argument("--altura", type=int); ap.add_argument("--modelo", default="resnet50"); ap.add_argument("--reduzir", type=float, default=0.25)
    a = ap.parse_args()
    try: import numpy as np, torch
    except ImportError: sys.exit("precisa de torch: rode com o Python do venv do RVM (RVM_PYTHON=.../bin/python) ou instale torch, torchvision, numpy")
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:format=duration", "-of", "json", a.video], capture_output=True, text=True).stdout)
    s = j["streams"][0]; W = a.largura or s["width"]; H = a.altura or s["height"]; FPS = s["r_frame_rate"]; fim = a.ate or float(j["format"]["duration"])
    out = os.path.join(a.pasta, "matte"); os.makedirs(out, exist_ok=True); mov = os.path.join(out, "fg.mov"); webm = os.path.join(out, "fg.webm")
    dev = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    model = torch.hub.load("PeterL1n/RobustVideoMatting", a.modelo, pretrained=True, trust_repo=True).eval().to(dev)
    rd = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(a.de), "-to", str(fim), "-i", a.video, "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-"], stdout=subprocess.PIPE)
    wr = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", FPS, "-i", "-", "-c:v", "prores_ks", "-profile:v", "4", "-qscale:v", "9", "-pix_fmt", "yuva444p10le", "-alpha_bits", "8", mov], stdin=subprocess.PIPE)
    n = W * H * 3; rec = [None] * 4; first = True; count = 0
    with torch.no_grad():
        while True:
            buf = rd.stdout.read(n)
            if len(buf) < n: break
            frame = torch.from_numpy(np.frombuffer(buf, np.uint8).copy()).view(H, W, 3).permute(2, 0, 1).float().div(255).unsqueeze(0).to(dev)
            if first:
                for _ in range(12): fgr, pha, *rec = model(frame, *rec, downsample_ratio=a.reduzir)
                first = False
            fgr, pha, *rec = model(frame, *rec, downsample_ratio=a.reduzir)
            rgba = torch.cat([fgr[0], pha[0]], 0).permute(1, 2, 0).mul(255).clamp(0, 255).byte().cpu().numpy()
            wr.stdin.write(rgba.tobytes()); count += 1
            if count % 48 == 0: print(f"{count} quadros", flush=True)
    wr.stdin.close(); wr.wait(); rd.wait()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mov, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24", "-an", webm], check=True)
    json.dump({"quadros": count, "largura": W, "altura": H, "fps": FPS, "de": a.de, "ate": fim, "mov": mov, "webm": webm}, open(os.path.join(out, "matte.json"), "w"), indent=1)
    print(f"pronto: {count} quadros → {mov} e {webm}")

if __name__ == "__main__": main()
