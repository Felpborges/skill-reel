"""Passo 0 — confere se a máquina tem tudo para a Edição Bruta e diz como instalar o que faltar.

uso:  python3 0-checar.py
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import os, platform, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ok = True
mac = platform.system() == "Darwin"
win = platform.system() == "Windows"

def linha(nome, passou, dica=""):
    global ok
    ok &= passou
    print(f"[{'ok' if passou else 'FALTA'}] {nome}" + ("" if passou else f"\n       → {dica}"))

ff = shutil.which("ffmpeg")
ver = ""
if ff:
    ver = subprocess.run([ff, "-version"], capture_output=True, text=True).stdout.split("\n")[0]
linha(f"ffmpeg {ver.split(' ')[2] if ver else ''}", bool(ff),
      "Mac: brew install ffmpeg · Windows: winget install Gyan.FFmpeg")

w = shutil.which("whisper-cli") or shutil.which("whisper-cpp") or shutil.which("main")
linha("whisper-cli (whisper.cpp)", bool(w),
      "Mac: brew install whisper-cpp · Windows: baixe o zip 'whisper-bin-x64' em github.com/ggml-org/whisper.cpp/releases e ponha a pasta no PATH")

try:
    import numpy
    linha(f"numpy {numpy.__version__} (python {platform.python_version()})", True)
except ImportError:
    linha("numpy", False, f"{sys.executable} -m pip install numpy")

from comum import MODELOS_PADRAO
m = os.environ.get("WHISPER_MODEL")
cands = [m] if m else MODELOS_PADRAO
achado = next((os.path.expanduser(c) for c in cands if c and os.path.exists(os.path.expanduser(c))), None)
linha(f"modelo do Whisper {achado or ''}", bool(achado),
      "baixe ggml-large-v3-turbo.bin (1,6 GB) de huggingface.co/ggerganov/whisper.cpp para "
      "~/.cache/whisper-cpp/  (ou defina WHISPER_MODEL com o caminho)")

print("\nTudo pronto." if ok else "\nInstale o que falta e rode de novo.")
sys.exit(0 if ok else 1)
