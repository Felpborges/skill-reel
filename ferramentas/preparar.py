#!/usr/bin/env python3
"""Preparo do vídeo limpo: áudio 16 kHz, transcrição palavra a palavra, pausas e metadados.

Uso: ferramentas/preparar.py <video> <pasta de saída> [--prompt "Nomes próprios, Produto X"] [--modelo caminho.bin]
Saída na pasta:
  meta.json        fps, duração, largura, altura, quadros
  audio16k.wav     mono 16 kHz (análise)
  voz48k.wav       estéreo 48 kHz (mix)
  palavras.json    [{"i": início, "f": fim, "t": "palavra"}] em segundos do vídeo de entrada
  texto.txt        a fala corrida, uma frase por linha (corrija à mão: R6)
  pausas.json      pausas > 0,4 s entre palavras
Precisa de ffmpeg/ffprobe e whisper-cli (whisper.cpp) com um modelo ggml; a variável WHISPER_MODEL aponta o modelo.
O motor de corte (corte/) usa a mesma transcrição; se ele já gerou cortepalavras.json, use --de-corte para só converter.
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import argparse, json, os, shutil, subprocess, sys, tempfile

MODELOS = ["~/.cache/whisper-cpp/ggml-large-v3-turbo.bin", "~/.cache/whisper-cpp/ggml-large-v3.bin", "~/.cache/whisper-cpp/ggml-medium.bin"]

def modelo(arg):
    for c in [arg, os.environ.get("WHISPER_MODEL")] + MODELOS:
        if c and os.path.exists(os.path.expanduser(c)): return os.path.expanduser(c)
    sys.exit("Modelo do Whisper não encontrado. Baixe ggml-large-v3-turbo.bin para ~/.cache/whisper-cpp/ ou defina WHISPER_MODEL.")

def dtw(caminho):
    nome = os.path.basename(caminho).replace("ggml-", "").replace(".bin", "").split("-q")[0]
    return {"large-v3-turbo": "large.v3.turbo", "large-v3": "large.v3", "large-v2": "large.v2", "medium": "medium", "small": "small", "base": "base", "tiny": "tiny"}.get(nome)

def ffprobe(video):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", video], capture_output=True, text=True).stdout)
    s = j["streams"][0]; n, d = s["r_frame_rate"].split("/"); fps = float(n) / float(d)
    return {"largura": s["width"], "altura": s["height"], "fps": round(fps, 3), "duracao": round(float(j["format"]["duration"]), 3), "quadros": int(s.get("nb_frames") or round(float(j["format"]["duration"]) * fps))}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("pasta"); ap.add_argument("--prompt", default="Claude, Claude Code, IA, Instagram, YouTube."); ap.add_argument("--modelo"); ap.add_argument("--de-corte", help="cortepalavras.json da edicao-bruta: só converte, não transcreve")
    a = ap.parse_args(); os.makedirs(a.pasta, exist_ok=True)
    meta = ffprobe(a.video); json.dump(meta, open(os.path.join(a.pasta, "meta.json"), "w"), indent=1)
    wav = os.path.join(a.pasta, "audio16k.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vn", "-ac", "2", "-ar", "48000", os.path.join(a.pasta, "voz48k.wav")], check=True)
    palavras = []
    if a.de_corte:
        for p in json.load(open(a.de_corte, encoding="utf-8")):
            if isinstance(p, dict): palavras.append({"i": p.get("i", p.get("start")), "f": p.get("f", p.get("end")), "t": p.get("t", p.get("text", "")).strip()})
            else: palavras.append({"i": p[0], "f": p[1], "t": str(p[2]).strip()})
    else:
        w = shutil.which("whisper-cli") or shutil.which("whisper-cpp") or sys.exit("whisper-cli não encontrado (brew install whisper-cpp).")
        m = modelo(a.modelo)
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "w"); cmd = [w, "-m", m, "-f", wav, "-l", "pt", "-ojf", "-ml", "1", "-sow", "-of", base, "-np", "--prompt", a.prompt]
            if dtw(m): cmd += ["-dtw", dtw(m)]
            subprocess.run(cmd, capture_output=True)
            dados = json.load(open(base + ".json", encoding="utf-8"))
        for s in dados["transcription"]:
            t = s["text"].strip()
            if t: palavras.append({"i": round(s["offsets"]["from"] / 1000, 3), "f": round(s["offsets"]["to"] / 1000, 3), "t": t})
    json.dump(palavras, open(os.path.join(a.pasta, "palavras.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    # texto corrido, quebrando em pontuação final
    frases, atual = [], []
    for p in palavras:
        atual.append(p["t"])
        if p["t"][-1:] in ".!?": frases.append(" ".join(atual)); atual = []
    if atual: frases.append(" ".join(atual))
    open(os.path.join(a.pasta, "texto.txt"), "w", encoding="utf-8").write("\n".join(frases) + "\n")
    pausas = [{"de": palavras[k]["f"], "ate": palavras[k + 1]["i"], "dur": round(palavras[k + 1]["i"] - palavras[k]["f"], 3)} for k in range(len(palavras) - 1) if palavras[k + 1]["i"] - palavras[k]["f"] > 0.4]
    json.dump(pausas, open(os.path.join(a.pasta, "pausas.json"), "w"), indent=1)
    print(json.dumps({"meta": meta, "palavras": len(palavras), "pausas_maiores_que_0.4s": len(pausas), "pasta": a.pasta}, ensure_ascii=False, indent=1))
    if pausas: print("AVISO: há pausas > 0,4 s. Se o vídeo ainda não passou pelo motor de corte, corte antes de editar (R5).", file=sys.stderr)

if __name__ == "__main__": main()
