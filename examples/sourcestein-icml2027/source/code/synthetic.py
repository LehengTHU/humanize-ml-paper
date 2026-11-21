"""RQ2 (synthetic): risk of test-time mean estimates vs. the whitened shift, for several batch sizes.
Per-sample features are C-dimensional with known source noise; the target mean is shifted from the source
mean by a random direction of controlled size. Risk = E||estimate - target mean||^2_{Sigma^{-1}} / C."""
import json, os, numpy as np
rng = np.random.default_rng(0)
C, T = 64, 4000                      # channels, Monte-Carlo repetitions per setting
shifts = np.concatenate([[0.0], np.logspace(-2, 1, 13)])   # per-channel shift in noise std units (squared: shift^2)
out = {"C": C, "T": T, "per_channel_shift": shifts.tolist(), "settings": []}

def run(n, noise="gauss", scale=1.0):
    rows = []
    for s in shifts:
        R = {k: 0.0 for k in ["source", "bn_test", "prior16", "stein", "oracle"]}
        lam_mean = 0.0
        for t in range(T // 200):
            d = rng.standard_normal((200, C)); d *= s * np.sqrt(C) / np.linalg.norm(d, axis=1, keepdims=True)
            theta = d                                        # target mean (source mean = 0, unit noise)
            if noise == "gauss":
                e = rng.standard_normal((200, n, C)) * scale
            else:                                            # heavy-tailed: Student-t with 3 dof, unit variance
                e = rng.standard_t(3, (200, n, C)) / np.sqrt(3.0) * scale
            y = theta + e.mean(1)                            # batch mean
            z2 = (y ** 2).sum(1) * n                         # whitened with the SOURCE noise level (unit)
            lam = np.clip(1 - (C - 2) / z2, 0, None)[:, None]
            w = n / (n + 16.0)
            delta2 = (theta ** 2).sum(1, keepdims=True) * n  # whitened true shift
            lam_star = delta2 / (delta2 + C * scale ** 2)    # oracle weight of the convex family
            est = {"source": 0 * y, "bn_test": y, "prior16": w * y, "stein": lam * y, "oracle": lam_star * y}
            for k, v in est.items():
                R[k] += (((v - theta) ** 2).sum(1) * n / C).sum()
            lam_mean += lam.sum()
        rows.append({"shift": float(s), **{k: v / T for k, v in R.items()}, "lambda": lam_mean / T})
    return rows

for n in (1, 4, 16, 64):
    out["settings"].append({"n": n, "noise": "gauss", "scale": 1.0, "rows": run(n)})
for noise, scale in (("student_t3", 1.0), ("gauss", 0.7), ("gauss", 1.4)):
    out["settings"].append({"n": 4, "noise": noise, "scale": scale, "rows": run(4, noise, scale)})
os.makedirs("results", exist_ok=True)
json.dump(out, open("results/synthetic_risk.json", "w"), indent=1)
for st in out["settings"]:
    print(st["n"], st["noise"], st["scale"], [(round(r["shift"], 3), round(r["stein"], 3), round(r["bn_test"], 3), round(r["prior16"], 3), round(r["oracle"], 3)) for r in st["rows"][::4]])
