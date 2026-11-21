"""Aggregate raw results into results/summary.json (every number in the paper's tables comes from here)."""
import json, os, numpy as np
R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
from common import CORRUPTIONS
GRID_N = [2, 4, 8, 16, 32, 64, 128, 256]


def key(r):
    m, c = r["method"], r["cfg"]
    if m == "prior": return f"prior_N{c['N']}"
    if m == "alpha": return f"alpha_{c['alpha']}"
    if m == "stein":
        if not c: return "stein"
        return "stein_" + "_".join(f"{k}={v}" for k, v in sorted(c.items()))
    return m


out = {}
for model in ("cnn8", "resnet14"):
    f = os.path.join(R, f"c10c_{model}.json")
    if not os.path.exists(f): continue
    d = json.load(open(f)); rows = d["rows"]; BS = d["batch_sizes"]
    tab = {}
    for r in rows:
        tab[(r["domain"], r["severity"], r["bs"], key(r))] = r
    res = {"batch_sizes": BS, "elapsed_s": d["elapsed_s"]}
    def avg(sev, bs, k, doms=CORRUPTIONS):
        v = [tab[(c, sev, bs, k)]["err"] for c in doms if (c, sev, bs, k) in tab]
        return float(np.mean(v)) if len(v) == len(doms) else None
    for sev in (5, 3):
        src = float(np.mean([tab[(c, sev, None, "source")]["err"] for c in CORRUPTIONS]))
        block = {"source": {str(b): src for b in BS}}
        keys = ["bn_test", "prior_N16", "alpha_0.9", "stein"] + ([f"prior_N{N}" for N in GRID_N if N != 16] +
               ["stein_pooled=False", "stein_var_mode=shared", "stein_var_mode=source", "stein_batch_noise=True"] if sev == 5 else [])
        for k in keys:
            block[k] = {str(b): avg(sev, b, k) for b in BS}
        if sev == 5:
            block["oracle_N"] = {}; block["oracle_N_value"] = {}
            for b in BS:
                best = min(GRID_N, key=lambda N: block[f"prior_N{N}"][str(b)])
                block["oracle_N"][str(b)] = block[f"prior_N{best}"][str(b)]; block["oracle_N_value"][str(b)] = best
            block["per_corruption_bs4"] = {k: {c: tab[(c, 5, 4, k)]["err"] for c in CORRUPTIONS}
                                           for k in ["bn_test", "prior_N16", "alpha_0.9", "stein"]}
            block["per_corruption_bs4"]["source"] = {c: tab[(c, 5, None, "source")]["err"] for c in CORRUPTIONS}
            # mixing weights of SourceStein per layer (mean over batches), averaged over corruptions
            block["lambda_mean_layer"] = {str(b): np.mean([tab[(c, 5, b, "stein")]["lam_mean_layer"] for c in CORRUPTIONS], 0).tolist() for b in BS}
            block["lambda_var_layer"] = {str(b): np.mean([tab[(c, 5, b, "stein")]["lam_var_layer"] for c in CORRUPTIONS], 0).tolist() for b in BS}
            block["lambda_mean_layer_fog"] = {str(b): tab[("fog", 5, b, "stein")]["lam_mean_layer"] for b in BS}
        res[f"sev{sev}"] = block
    clean = {"source": tab[("clean", 0, None, "source")]["err"]}
    for k in ["bn_test", "prior_N16", "alpha_0.9", "stein"]:
        clean[k] = {str(b): tab[("clean", 0, b, k)]["err"] for b in BS}
    clean["lambda_mean_layer"] = {str(b): tab[("clean", 0, b, "stein")]["lam_mean_layer"] for b in BS}
    res["clean"] = clean
    t = os.path.join(R, f"tent_{model}.json")
    if os.path.exists(t):
        td = json.load(open(t)); tt = {}
        for r in td["rows"]: tt.setdefault((r["method"], r["bs"]), []).append(r["err"])
        res["tent"] = {m: {str(b): float(np.mean(v)) for (mm, b), v in tt.items() if mm == m} for m in {k[0] for k in tt}}
        res["tent_elapsed_s"] = td["elapsed_s"]
    tr = os.path.join(R, f"train_{model}.json")
    if os.path.exists(tr):
        tj = json.load(open(tr)); res["train"] = {"epochs": len(tj), "clean_test_acc": tj[-1]["clean_test_acc"], "elapsed_s": tj[-1]["elapsed_s"]}
    out[model] = res
json.dump(out, open(os.path.join(R, "summary.json"), "w"), indent=1)
for m, res in out.items():
    print("==", m, res.get("train"))
    s5 = res["sev5"]
    for k in ["source", "bn_test", "prior_N16", "alpha_0.9", "oracle_N", "stein", "stein_pooled=False", "stein_var_mode=shared", "stein_var_mode=source", "stein_batch_noise=True"]:
        print(f"{k:26s}", " ".join(f"{s5[k][str(b)]:6.2f}" for b in res["batch_sizes"]))
    print("oracle N", s5["oracle_N_value"])
    print("clean", res["clean"]["source"], {k: [round(v, 1) for v in res["clean"][k].values()] for k in ["bn_test", "prior_N16", "stein"]})
    if "tent" in res: print("tent", res["tent"])
