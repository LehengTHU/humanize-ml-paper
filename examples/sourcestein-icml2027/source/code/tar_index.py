"""Index the CIFAR-10-C tar on Zenodo by reading only its 512-byte headers (HTTP range requests)."""
import json, subprocess, sys
URL = "https://zenodo.org/records/2535967/files/CIFAR-10-C.tar"
def rng(a, b):
    return subprocess.run(["curl", "-s", "-L", "-r", f"{a}-{b}", URL], capture_output=True).stdout
off, index = 0, {}
while True:
    h = rng(off, off + 511)
    if len(h) < 512 or h[:1] == b"\0":
        break
    name = h[:100].rstrip(b"\0").decode()
    size = int(h[124:136].rstrip(b"\0 ").decode() or "0", 8)
    if name.endswith(".npy"):
        index[name] = {"data_offset": off + 512, "size": size}
        print(name, size, flush=True)
    off += 512 + ((size + 511) // 512) * 512
json.dump(index, open(sys.argv[1], "w"), indent=1)
