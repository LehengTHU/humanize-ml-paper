"""Print the LaTeX rows of every result table from results/summary.json (pasted into the chapters verbatim)."""
import json, os
R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
S = json.load(open(os.path.join(R, "summary.json")))
BS = ["1", "2", "4", "8", "16", "64", "200"]
def row(name, vals, best, shade=False, gray=False):
    cells = []
    for v, b in zip(vals, best):
        t = f"{v:.2f}"; t = f"\\textbf{{{t}}}" if (b and not gray) else t
        if gray: t = f"\\ablation{{{t}}}"
        cells.append(("\\cellcolor{oursrowblue}" if shade else "") + t)
    nm = f"\\ablation{{{name}}}" if gray else name
    return ("\\rowcolor{oursrowblue} " if shade else "") + f" & {nm} & " + " & ".join(cells) + " \\\\"
print("% ===== main table (sev 5, mean over 15 corruptions)")
for model, lab in (("resnet14", "ResNet-14"), ("cnn8", "CNN-8")):
    s5 = S[model]["sev5"]
    ranked = ["source", "bn_test", "prior_N16", "alpha_0.9", "stein"]
    best = {b: min(s5[k][b] for k in ranked) for b in BS}
    names = {"source": "Source", "bn_test": "TBN \\citep{PredictionBN}", "prior_N16": "Prior-BN \\citep{BN-Adapt}",
             "alpha_0.9": "$\\alpha$-BN \\citep{AlphaBN}", "oracle_N": "Oracle-$N$ (privileged)", "stein": "\\textbf{SourceStein (Ours)}"}
    print(f"% {lab}")
    for k in ["source", "bn_test", "prior_N16", "alpha_0.9", "oracle_N", "stein"]:
        vals = [s5[k][b] for b in BS]
        print(row(names[k], vals, [abs(v - best[b]) < 1e-9 for v, b in zip(vals, BS)], shade=(k == "stein"), gray=(k == "oracle_N")))
print("% ===== clean table (n=1,4,16)")
for model in ("resnet14", "cnn8"):
    c = S[model]["clean"]
    print(model, "source", c["source"], {k: [round(c[k][b], 1) for b in ("1", "4", "16")] for k in ["bn_test", "prior_N16", "alpha_0.9", "stein"]})
print("% ===== ablation (sev5) n=1,4,16,64")
for model in ("resnet14", "cnn8"):
    s5 = S[model]["sev5"]
    for k in ["stein", "stein_pooled=False", "stein_var_mode=shared", "stein_var_mode=source", "stein_batch_noise=True"]:
        print(model, k, " & ".join(f"{s5[k][b]:.2f}" for b in ("1", "4", "16", "64")))
print("% ===== sev3")
for model in ("resnet14", "cnn8"):
    s3 = S[model]["sev3"]
    for k in ["source", "bn_test", "prior_N16", "alpha_0.9", "stein"]:
        print(model, k, " & ".join(f"{s3[k][b]:.2f}" for b in BS))
print("% ===== tent")
for model in ("resnet14", "cnn8"):
    if "tent" in S[model]:
        for k in ["tent+bn_test", "tent+prior", "tent+stein"]:
            print(model, k, " & ".join(f"{S[model]['tent'][k][b]:.2f}" for b in ("4", "16", "64")))
print("% ===== per-corruption n=4 (resnet14, cnn8)")
for model in ("resnet14", "cnn8"):
    pc = S[model]["sev5"]["per_corruption_bs4"]
    for k in ["source", "bn_test", "prior_N16", "alpha_0.9", "stein"]:
        print(model, k, " & ".join(f"{pc[k][c]:.1f}" for c in pc[k]))
print("oracle N values", {m: S[m]["sev5"]["oracle_N_value"] for m in S})
