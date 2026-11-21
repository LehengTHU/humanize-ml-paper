"""Re-fetch incomplete CIFAR-10-C slices in parallel 2-MB byte-range chunks (Zenodo throttles single connections)."""
import json, subprocess, os
from concurrent.futures import ThreadPoolExecutor
URL = "https://zenodo.org/records/2535967/files/CIFAR-10-C.tar"
idx = json.load(open("data/c10c_index.json")); IMG = 3072; CH = 2 * 1024 * 1024
want = {}
for f in sorted(os.listdir("data/c10c")):
    name, s = (f[:-6], int(f[-4])) if f.endswith(".u8") and "_s" in f else (None, None)
    if name is None: continue
    if os.path.getsize(f"data/c10c/{f}") != 10000 * IMG:
        base = idx[f"CIFAR-10-C/{name}.npy"]["data_offset"] + 128 + (s - 1) * 10000 * IMG
        want[f] = base
jobs = []
for f, base in want.items():
    for k, a in enumerate(range(0, 10000 * IMG, CH)):
        b = min(a + CH, 10000 * IMG) - 1
        jobs.append((f, k, base + a, base + b, b - a + 1))
os.makedirs("data/chunks", exist_ok=True)
def get(j):
    f, k, a, b, n = j; out = f"data/chunks/{f}.{k:04d}"
    for _ in range(8):
        if os.path.exists(out) and os.path.getsize(out) == n: return True
        subprocess.run(["curl", "-s", "-L", "--max-time", "120", "-r", f"{a}-{b}", "-o", out, URL])
    return os.path.getsize(out) == n
with ThreadPoolExecutor(48) as ex:
    ok = list(ex.map(get, jobs))
print(sum(ok), "of", len(ok), "chunks")
for f in want:
    parts = sorted(p for p in os.listdir("data/chunks") if p.startswith(f + "."))
    with open(f"data/c10c/{f}", "wb") as o:
        for p in parts: o.write(open(f"data/chunks/{p}", "rb").read())
    print(f, os.path.getsize(f"data/c10c/{f}") == 10000 * IMG)
