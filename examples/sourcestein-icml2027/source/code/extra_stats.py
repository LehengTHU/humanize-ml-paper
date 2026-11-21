"""Derived statistics quoted in the text (written to results/extra_stats.txt)."""
import json, os, numpy as np
R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
S = json.load(open(os.path.join(R, "summary.json"))); syn = json.load(open(os.path.join(R, "synthetic_risk.json")))
for m in S:
    s5 = S[m]["sev5"]; pc = s5["per_corruption_bs4"]; ks = ["source", "bn_test", "prior_N16", "alpha_0.9", "stein"]
    print(m, "SourceStein best on", sum(pc["stein"][c] <= min(pc[k][c] for k in ks) for c in pc["stein"]), "of 15 corruptions at n=4")
    for b in ["1", "4", "16", "64", "200"]:
        print(f" n={b} mean lambda_mu corrupted {np.mean(s5['lambda_mean_layer'][b]):.3f} clean {np.mean(S[m]['clean']['lambda_mean_layer'][b]):.3f}"
              f" mean lambda_u corrupted {np.mean(s5['lambda_var_layer'][b]):.3f} max-layer lambda_mu {max(s5['lambda_mean_layer'][b]):.2f}")
    c = S[m]["clean"]; print(" clean max gap SourceStein - Source:", max(c["stein"][b] - c["source"] for b in c["stein"]))
for st in syn["settings"]:
    r = st["rows"]
    print(f"synthetic n={st['n']} {st['noise']} scale={st['scale']}: max(stein-oracle)={max(x['stein'] - x['oracle'] for x in r):.3f}"
          f" shifts where stein>TBN={sum(x['stein'] > x['bn_test'] for x in r)}/{len(r)} zero-shift stein={r[0]['stein']:.3f}"
          f" prior16={r[0]['prior16']:.3f} tbn={r[0]['bn_test']:.3f} largest-shift stein={r[-1]['stein']:.3f} prior16={r[-1]['prior16']:.2f}")
