#!/usr/bin/env python3
"""Checklist de entrega (R9): mede o vídeo final e escreve VERIFY.md com o que passou e o que falta olhar.

Uso: ferramentas/verificar.py <pasta do projeto> --video render/reel-final.mp4 [--perfil reels|anuncio]
      [--camera corte/clean-916.mp4] [--sfx sons.json] [--notas "texto livre"]
Mede: resolução (1080×1920), fps, duração, LUFS integrado e pico, zona segura (chama zona-segura.py),
densidade de SFX (se sons.json tiver a lista de tempos), e lembra os itens que só o olho confere (R1 rosto,
legibilidade, correções da legenda). Sai com 1 se algum item medido reprovou.
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import argparse, json, os, subprocess, sys, datetime

AQUI = os.path.dirname(os.path.abspath(__file__))

def probe(v):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height,r_frame_rate,codec_type:format=duration", "-of", "json", v], capture_output=True, text=True).stdout)
    vs = next(s for s in j["streams"] if s["codec_type"] == "video"); n, d = vs["r_frame_rate"].split("/")
    return {"largura": vs["width"], "altura": vs["height"], "fps": round(float(n) / float(d), 3), "duracao": round(float(j["format"]["duration"]), 2), "audio": any(s["codec_type"] == "audio" for s in j["streams"])}

def loudness(v):
    out = subprocess.run(["ffmpeg", "-nostats", "-i", v, "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    bloco = out[out.rfind("{"):out.rfind("}") + 1]
    try: j = json.loads(bloco); return {"lufs": float(j["input_i"]), "pico_dbtp": float(j["input_tp"]), "lra": float(j["input_lra"])}
    except Exception: return {"lufs": None, "pico_dbtp": None, "lra": None}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("projeto"); ap.add_argument("--video", required=True); ap.add_argument("--perfil", default="reels"); ap.add_argument("--camera"); ap.add_argument("--sfx"); ap.add_argument("--notas", default="")
    a = ap.parse_args(); proj = os.path.abspath(a.projeto); video = a.video if os.path.isabs(a.video) else os.path.join(proj, a.video)
    itens = []; ok = True
    m = probe(video); itens.append(("Resolução 1080×1920", m["largura"] == 1080 and m["altura"] == 1920, f"{m['largura']}×{m['altura']}"))
    itens.append(("Faixa de áudio presente", m["audio"], "")); itens.append(("Duração", True, f"{m['duracao']} s · {m['fps']} fps"))
    l = loudness(video)
    itens.append(("Loudness −14 LUFS ±0,5 (R8)", l["lufs"] is not None and abs(l["lufs"] + 14) <= 0.5, f"{l['lufs']} LUFS"))
    itens.append(("Pico ≤ −0,5 dBTP (R8)", l["pico_dbtp"] is not None and l["pico_dbtp"] <= -0.5, f"{l['pico_dbtp']} dBTP"))
    zs_dir = os.path.join(proj, "qa"); os.makedirs(zs_dir, exist_ok=True)
    cmd = [sys.executable, os.path.join(AQUI, "zona-segura.py"), video, "--perfil", a.perfil, "--saida", zs_dir] + (["--camera", a.camera] if a.camera else [])
    r = subprocess.run(cmd, capture_output=True, text=True); zs = {}
    try: zs = json.load(open(os.path.join(zs_dir, "zona-segura.json")))
    except Exception: pass
    itens.append(("Zona segura sem suspeitos (R7)", r.returncode == 0, f"{len(zs.get('suspeitos', []))} instantes para olhar em qa/zona-segura.png" if zs else r.stderr.strip()[-200:]))
    if a.sfx and os.path.exists(a.sfx):
        try:
            s = json.load(open(a.sfx)); tempos = sorted(float(x["t"] if isinstance(x, dict) else x) for x in (s if isinstance(s, list) else s.get("efeitos", [])))
            dens = len(tempos) / max(m["duracao"], 1); perto = sum(1 for p, q in zip(tempos, tempos[1:]) if q - p < 0.35)
            itens.append(("SFX ≤ 0,85 por segundo (R2)", dens <= 0.85, f"{len(tempos)} efeitos · {dens:.2f}/s · {perto} pares a menos de 0,35 s"))
        except Exception as e: itens.append(("SFX (sons.json)", True, f"não li: {e}"))
    ok = all(i[1] for i in itens)
    linhas = [f"# VERIFY · {os.path.basename(video)}", f"*{datetime.datetime.now():%Y-%m-%d %H:%M}*", "", "## Medido", "| Item | Resultado | Detalhe |", "|---|---|---|"]
    for nome, passou, det in itens: linhas.append(f"| {nome} | {'✅' if passou else '❌'} | {det} |")
    linhas += ["", "## Conferido no olho (marque)", "- [ ] R1 · nenhum elemento sobre o rosto em nenhum quadro (folha em qa/zona-segura.png e snapshots por beat)", "- [ ] Texto legível, nada cortado, tempo de leitura ≥ 2 s em telas com texto",
               "- [ ] R6 · legenda com o texto corrigido (Claude, IA, nomes de produto como a marca escreve); palavra-código em CAIXA ALTA", "- [ ] R3 · todo número/print/logo com fonte em assets/SOURCES.md", "- [ ] R5 · nenhuma palavra comida nas emendas (conferência da edicao-bruta)", "- [ ] R11 · nenhum nome de terceiro no vídeo nem nos arquivos", "", "## Notas", a.notas or "—", "", f"**Resultado medido: {'APROVADO' if ok else 'REPROVADO'}** · nunca publicar nem enviar o vídeo (R9)."]
    open(os.path.join(proj, "VERIFY.md"), "w", encoding="utf-8").write("\n".join(linhas) + "\n")
    print("\n".join(linhas)); sys.exit(0 if ok else 1)

if __name__ == "__main__": main()
