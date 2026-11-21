"""RQ4: entropy minimization (TENT, Wang et al., 2021) on top of different normalization statistics.
Online over each CIFAR-10-C severity-5 corruption (model reset per corruption), Adam lr 1e-3 on BN affine
parameters, one step per batch, predictions taken before the update. Writes results/tent_<model>.json."""
import sys, os, json, time, numpy as np, torch, torch.nn.functional as F
from multiprocessing import get_context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CORRUPTIONS, load_c10c, to_tensor, ROOT
from eval_c10c import build, N_IMG

BS = [4, 16, 64]
VARIANTS = [("bn_test", {}), ("prior", {"N": 16}), ("stein", {})]


def job(args):
    name, c, k = args
    x, y = load_c10c(c, 5)
    sel = np.random.default_rng(100 + k).permutation(len(x))[:N_IMG]
    X, Y = to_tensor(x[sel]), torch.from_numpy(y[sel].astype(np.int64))
    rows = []
    for bs in BS:
        for rule, cfg in VARIANTS:
            model, wr = build(name)
            for w in wr: w.rule, w.cfg = rule, cfg
            params = [p for w in wr for p in (w.bn.weight, w.bn.bias)]
            for p in model.parameters(): p.requires_grad_(False)
            for p in params: p.requires_grad_(True)
            opt = torch.optim.Adam(params, lr=1e-3, betas=(0.9, 0.999))
            wrong = 0
            for i in range(0, len(X), bs):
                logits = model(X[i:i + bs])
                wrong += (logits.argmax(1) != Y[i:i + bs]).sum().item()
                ent = -(logits.softmax(1) * logits.log_softmax(1)).sum(1).mean()
                opt.zero_grad(); ent.backward(); opt.step()
            rows.append({"domain": c, "bs": bs, "method": "tent+" + rule, "cfg": cfg, "err": 100.0 * wrong / len(X)})
    return rows


if __name__ == "__main__":
    name = sys.argv[1]; t0 = time.time(); rows = []
    with get_context("spawn").Pool(int(sys.argv[2]) if len(sys.argv) > 2 else 14) as pool:
        for r in pool.imap_unordered(job, [(name, c, k) for k, c in enumerate(CORRUPTIONS)]):
            rows += r; print(r[0]["domain"], f"{time.time() - t0:.0f}s", flush=True)
    json.dump({"model": name, "elapsed_s": time.time() - t0, "rows": rows},
              open(os.path.join(ROOT, "results", f"tent_{name}.json"), "w"))
