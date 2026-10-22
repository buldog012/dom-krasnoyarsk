# Превращает эскиз на бумаге в «чернила» с прозрачным фоном для водяного знака.
# python ink.py вход.jpg выход.webp [цвет чернил, например EDE7DC] [обрезать снизу px]
import sys
import numpy as np
from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
hexc = sys.argv[3] if len(sys.argv) > 3 else 'EDE7DC'
cut = int(sys.argv[4]) if len(sys.argv) > 4 else 0
im = Image.open(src).convert('L')
if cut:
    im = im.crop((0, 0, im.width, im.height - cut))
a = np.asarray(im).astype(np.float32)
# фон бумаги: яркость по рамке кадра
border = np.concatenate([a[:12].ravel(), a[-12:].ravel(), a[:, :12].ravel(), a[:, -12:].ravel()])
bg = float(np.percentile(border, 60))
dark = float(np.percentile(a, 2))
alpha = np.clip((bg - a - 16) / max(bg - 16 - dark, 1.0), 0.0, 1.0) ** 0.85   # минус зерно бумаги
alpha = (alpha * 255).astype(np.uint8)
r, g, b = int(hexc[0:2], 16), int(hexc[2:4], 16), int(hexc[4:6], 16)
rgba = np.zeros((a.shape[0], a.shape[1], 4), dtype=np.uint8)
rgba[..., 0], rgba[..., 1], rgba[..., 2], rgba[..., 3] = r, g, b, alpha
out = Image.fromarray(rgba, 'RGBA')
# обрезать прозрачные поля
bbox = Image.fromarray(alpha).point(lambda v: 255 if v > 18 else 0).getbbox()
if bbox:
    out = out.crop(bbox)
if out.width > 1400:
    out = out.resize((1400, round(out.height * 1400 / out.width)), Image.LANCZOS)
out.save(dst, 'WEBP' if dst.lower().endswith('.webp') else None, quality=85, method=6)
print('ink saved', dst, out.size, 'paper', round(bg), 'ink', round(dark))
