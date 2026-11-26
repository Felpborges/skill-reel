"""Rastreia BOCA e rosto no vídeo 9:16 → assets/face-track.json (a legenda que segue a boca, K.mouthCaps).

Cada quadro: [t, bocaX, bocaY, larguraBoca, queixoY, testaY, rostoX0, rostoX1] em px do vídeo (1080×1920),
suavizado (média móvel exponencial). Quadro sem rosto repete o último valor.
Rode na pasta do motor:  $VSL_PYTHON ferramentas/rastrear-boca.py [assets/clean.mp4] [assets/face-track.json]
Detector: MediaPipe Face Landmarker (o da referência aprovada; modelo em FACE_MODEL, R10, ou baixado para
./.modelos/). Sem mediapipe, cai para o OpenCV (Haar frontal) com a boca estimada pela caixa do rosto — mais
grosseiro, mas a legenda continua aparecendo abaixo do queixo.
"""
import sys as _s; [getattr(_s, n).reconfigure(encoding="utf-8", errors="replace") for n in ("stdout", "stderr") if hasattr(getattr(_s, n), "reconfigure")]  # Windows: saída em UTF-8
import json, os, sys, urllib.request
import cv2

src = sys.argv[1] if len(sys.argv) > 1 else "assets/clean.mp4"
out = sys.argv[2] if len(sys.argv) > 2 else "assets/face-track.json"
A = 0.35  # suavização (0 = parado, 1 = cru)


def mediapipe_detector():
    import mediapipe as mp
    from mediapipe.tasks.python import vision, BaseOptions
    model = os.environ.get("FACE_MODEL") or os.path.join(".modelos", "face_landmarker.task")
    if not os.path.exists(model):
        os.makedirs(os.path.dirname(model), exist_ok=True)
        urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task", model)
    opts = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=model), running_mode=vision.RunningMode.VIDEO,
                                        num_faces=1, min_face_detection_confidence=0.4, min_tracking_confidence=0.4)
    det = vision.FaceLandmarker.create_from_options(opts)

    def detect(img, ms, W, H):
        r = det.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), ms)
        if not r.face_landmarks: return None
        L = r.face_landmarks[0]
        P = lambda k: (L[k].x * W, L[k].y * H)
        (ux, uy), (lx, ly) = P(13), P(14)
        (cx0, _), (cx1, _) = P(61), P(291)
        xs = [p.x * W for p in L]
        return [(ux + lx) / 2, (uy + ly) / 2, abs(cx1 - cx0), P(152)[1], P(10)[1], min(xs), max(xs)]
    return detect, "mediapipe"


def opencv_detector():
    casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def detect(img, ms, W, H):
        k = 0.5
        g = cv2.cvtColor(cv2.resize(img, None, fx=k, fy=k), cv2.COLOR_BGR2GRAY)
        f = casc.detectMultiScale(g, 1.1, 5, minSize=(int(W * k * 0.18), int(W * k * 0.18)))
        if len(f) == 0: return None
        x, y, w, h = [v / k for v in max(f, key=lambda r: r[2] * r[3])]
        # proporções médias de um rosto frontal na caixa Haar: boca a ~78 % da altura, queixo a ~102 %, testa a ~5 %
        return [x + w / 2, y + 0.78 * h, 0.36 * w, y + 1.02 * h, y + 0.05 * h, x, x + w]
    return detect, "opencv"


try: detect, nome = mediapipe_detector()
except Exception as e:
    print(f"mediapipe indisponível ({type(e).__name__}); usando OpenCV")
    detect, nome = opencv_detector()

cap = cv2.VideoCapture(src); fps = cap.get(cv2.CAP_PROP_FPS) or 30; W = int(cap.get(3)); H = int(cap.get(4))
rows, last, sm, i = [], None, None, 0
while True:
    ok, img = cap.read()
    if not ok: break
    cur = detect(img, int(i * 1000 / fps), W, H)
    if cur is not None: last = cur
    cur = last
    if cur is not None:
        sm = cur if sm is None else [s + A * (c - s) for s, c in zip(sm, cur)]
        rows.append([round(i / fps, 3)] + [round(v, 1) for v in sm])
    i += 1
json.dump({"fps": fps, "w": W, "h": H, "detector": nome, "cols": ["t", "mx", "my", "mw", "chin", "top", "x0", "x1"], "rows": rows}, open(out, "w"))
print(f"{len(rows)} quadros com rosto de {i} ({nome}) -> {out}")
