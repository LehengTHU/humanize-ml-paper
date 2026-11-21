"""Wall-clock cost of each normalization rule (ms per image, CPU, 1 thread). Writes results/timing.json."""
import sys, os, json, time, numpy as np, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_c10c import build
from common import load_c10c, to_tensor, ROOT
torch.set_num_threads(1)
x, _ = load_c10c("fog", 5); X = to_tensor(x[:400])
out = {}
for name in ("cnn8", "resnet14"):
    model, wr = build(name)
    for rule, cfg in [("source", {}), ("bn_test", {}), ("prior", {"N": 16}), ("stein", {})]:
        for w in wr: w.rule, w.cfg = rule, cfg
        for bs in (1, 16, 200):
            with torch.no_grad():
                for i in range(0, 50, bs): model(X[i:i + bs])          # warm-up
                t = time.perf_counter()
                for rep in range(3):
                    for i in range(0, 400, bs): model(X[i:i + bs])
                ms = (time.perf_counter() - t) / (3 * 400) * 1000
            out[f"{name}/{rule}/{bs}"] = ms; print(name, rule, bs, round(ms, 3), flush=True)
json.dump(out, open(os.path.join(ROOT, "results", "timing.json"), "w"), indent=1)
