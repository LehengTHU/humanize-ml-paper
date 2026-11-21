"""RQ1/RQ3/RQ2b: error of every normalization rule on CIFAR-10-C (severity 5 and 3) and clean CIFAR-10.
Usage: eval_c10c.py <model> [workers]. Writes results/c10c_<model>.json."""
import sys, os, json, time, numpy as np, torch
from multiprocessing import get_context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CORRUPTIONS, load_c10c, load_cifar10, to_tensor, make_model, ROOT
from tta import wrap, fit_source_noise, set_rule

N_IMG, N_SRC = 1000, 5000
BS = [1, 2, 4, 8, 16, 64, 200]
MAIN = [("bn_test", {}), ("prior", {"N": 16}), ("alpha", {"alpha": 0.9}), ("stein", {})]
ABL = [("stein", {"pooled": False}), ("stein", {"var_mode": "shared"}), ("stein", {"var_mode": "source"}),
       ("stein", {"batch_noise": True})]
GRID = [("prior", {"N": N}) for N in (2, 4, 8, 32, 64, 128, 256)]


def build(name):
    torch.set_num_threads(1)
    model = make_model(name); model.load_state_dict(torch.load(os.path.join(ROOT, "results", "models", f"{name}.pt")))
    model.eval(); wr = wrap(model)
    xtr, _ = load_cifar10("train")
    sel = np.random.default_rng(1).choice(len(xtr), N_SRC, replace=False)
    fit_source_noise(model, wr, to_tensor(xtr[sel]))
    return model, wr


@torch.no_grad()
def evaluate(model, wr, X, Y, bs, rule, cfg, track=False):
    set_rule(wr, rule, **cfg); wrong, lam = 0, []
    for i in range(0, len(X), bs):
        wrong += (model(X[i:i + bs]).argmax(1) != Y[i:i + bs]).sum().item()
        if track: lam.append([w.last_lam for w in wr])
    out = {"err": 100.0 * wrong / len(X)}
    if track:
        a = np.array(lam)  # batches x layers x 2
        out["lam_mean_layer"] = a[:, :, 0].mean(0).tolist(); out["lam_var_layer"] = a[:, :, 1].mean(0).tolist()
    return out


def job(args):
    name, domain, sev, d_idx = args
    model, wr = build(name)
    if domain == "clean":
        x, y = load_cifar10("test")
    else:
        x, y = load_c10c(domain, sev)
    sel = np.random.default_rng(100 + d_idx).permutation(len(x))[:N_IMG]   # same subset for every model and rule
    X, Y = to_tensor(x[sel]), torch.from_numpy(y[sel].astype(np.int64))
    rows = [{"domain": domain, "severity": sev, "bs": None, "method": "source", "cfg": {}, **evaluate(model, wr, X, Y, 500, "source", {})}]
    confs = MAIN if sev == 3 else MAIN + ABL + GRID
    for bs in BS:
        for rule, cfg in confs:
            tr = rule == "stein" and not cfg
            rows.append({"domain": domain, "severity": sev, "bs": bs, "method": rule, "cfg": cfg,
                         **evaluate(model, wr, X, Y, bs, rule, cfg, track=tr)})
    return rows


if __name__ == "__main__":
    name = sys.argv[1]; workers = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    jobs = [(name, "clean", 0, 99)] + [(name, c, 5, k) for k, c in enumerate(CORRUPTIONS)] + \
           [(name, c, 3, 50 + k) for k, c in enumerate(CORRUPTIONS)]
    t0 = time.time(); rows = []
    with get_context("spawn").Pool(workers) as pool:
        for r in pool.imap_unordered(job, jobs):
            rows += r; print(f"{r[0]['domain']} s{r[0]['severity']} done {time.time() - t0:.0f}s", flush=True)
    json.dump({"model": name, "n_img": N_IMG, "n_src": N_SRC, "batch_sizes": BS, "elapsed_s": time.time() - t0,
               "rows": rows}, open(os.path.join(ROOT, "results", f"c10c_{name}.json"), "w"))
