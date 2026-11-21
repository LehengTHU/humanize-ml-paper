"""colour_stats.py IMG [IMG ...] -- cleanliness metrics for a diagram PNG.
white: share of near-white pixels (target >= 0.75, reference figures ~0.80)
earthy/colored: share of brown/khaki/beige/peach-brown pixels among coloured ones (target <= 0.05)
mean-sat: mean saturation of coloured pixels (reference ~0.5: clean, saturated outlines)
hue families: coloured hue bins covering >= 6% of coloured pixels (target <= 3; semantic green/red extra).
Needs numpy, plus PyMuPDF or matplotlib to read the PNG; scripts/render_diagram.py calls metrics() directly."""
import sys

import numpy as np


def _rgb_to_hsv(px):
    r, g, b = px[:, 0], px[:, 1], px[:, 2]
    v = px.max(axis=1)
    c = v - px.min(axis=1)
    s = np.where(v > 0, c / np.maximum(v, 1e-12), 0.0)
    safe = np.maximum(c, 1e-12)
    h = np.where(v == r, ((g - b) / safe) % 6, np.where(v == g, (b - r) / safe + 2, (r - g) / safe + 4))
    h = np.where(c > 0, h / 6.0, 0.0)
    return h * 360, s, v


def metrics(rgb):
    """rgb: H x W x 3 array in [0, 1]. Returns (white, earthy_share, mean_sat, hue_families)."""
    px = rgb.reshape(-1, 3)[::5].astype(float)
    h, s, v = _rgb_to_hsv(px)
    white = (s < 0.06) & (v > 0.95)
    ink = v < 0.35
    gray = (s < 0.10) & ~white & ~ink
    col = ~white & ~ink & ~gray
    earthy = col & (h >= 15) & (h <= 55) & (s < 0.55) & (v < 0.93)
    hist = np.histogram(h[col & (s > 0.15)], bins=12, range=(0, 360))[0]
    nh = int((hist > 0.06 * hist.sum()).sum()) if hist.sum() else 0
    return float(white.mean()), float(earthy.sum() / max(1, col.sum())), float(s[col].mean() if col.any() else 0), nh


def load_png(path):
    try:
        import fitz  # PyMuPDF
        pix = fitz.Pixmap(path)
        if pix.colorspace and pix.colorspace.n != 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n) / 255.0
        if pix.alpha:
            return a[..., :3] * a[..., 3:4] + (1.0 - a[..., 3:4])
        return a[..., :3]
    except ImportError:
        import matplotlib.image as mpimg
        im = mpimg.imread(path)
        if im.max() > 1:
            im = im / 255.0
        if im.shape[2] == 4:
            a = im[..., 3:4]
            im = im[..., :3] * a + (1 - a)
        return im[..., :3]


def line(name, rgb):
    w, e, s, nh = metrics(rgb)
    return f"{name:32s} white={w:.2f} earthy/colored={e:.2f} mean-sat={s:.2f} hue-families={nh}"


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print(line(f.split('/')[-1], load_png(f)))
