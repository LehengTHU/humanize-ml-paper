"""Fetch only the severity-3 and severity-5 slices of the 15 standard CIFAR-10-C corruptions via byte ranges."""
import json, subprocess, sys, os
from concurrent.futures import ThreadPoolExecutor
URL = "https://zenodo.org/records/2535967/files/CIFAR-10-C.tar"
CORR = ["gaussian_noise", "shot_noise", "impulse_noise", "defocus_blur", "glass_blur", "motion_blur", "zoom_blur",
        "snow", "frost", "fog", "brightness", "contrast", "elastic_transform", "pixelate", "jpeg_compression"]
idx = json.load(open("data/c10c_index.json")); os.makedirs("data/c10c", exist_ok=True)
IMG = 32 * 32 * 3
jobs = []
for c in CORR:
    base = idx[f"CIFAR-10-C/{c}.npy"]["data_offset"] + 128
    for s in (3, 5):
        a = base + (s - 1) * 10000 * IMG
        jobs.append((f"data/c10c/{c}_s{s}.u8", a, a + 10000 * IMG - 1))
lab = idx["CIFAR-10-C/labels.npy"]["data_offset"] + 128
jobs.append(("data/c10c/labels.u8", lab, lab + 9999))
def get(j):
    out, a, b = j
    for _ in range(5):
        subprocess.run(["curl", "-s", "-L", "-r", f"{a}-{b}", "-o", out, URL])
        if os.path.exists(out) and os.path.getsize(out) == b - a + 1:
            return out, True
    return out, False
with ThreadPoolExecutor(16) as ex:
    for out, ok in ex.map(get, jobs):
        print(out, ok, flush=True)
