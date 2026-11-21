"""All result plots, drawn from results/*.json with the house plot style (one PNG + PDF per panel)."""
import json, os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import plot_style as ps
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R, F = os.path.join(ROOT, "results"), os.path.join(ROOT, "figures", "exp")
P = ps.PALETTE
ps.apply()
C = {"source": P["base_gray"], "bn_test": P["pink"], "prior": "#BAAE8B", "oracle": P["spine"], "stein": P["blue"]}
NAMES = {"source": "Source", "bn_test": "TBN", "prior": "Prior-BN ($N$=16)", "oracle": "Oracle weight", "stein": "SourceStein"}

# ---------------------------------------------------------------- synthetic risk (teaser + appendix)
syn = json.load(open(os.path.join(R, "synthetic_risk.json")))
def syn_panel(st, path, legend=True, ylim=None):
    rows = st["rows"]; x = np.array([r["shift"] for r in rows])[1:]
    fig, ax = ps.new_figure("wide" if legend else "square")
    for k, kk, ls, lw in [("source", "source", "-", 2.6), ("bn_test", "bn_test", "-", 2.6), ("prior16", "prior", "-", 2.6),
                          ("oracle", "oracle", "--", 2.0), ("stein", "stein", "-", 3.4)]:
        y = np.array([r[k] for r in rows])[1:]
        ax.plot(x, y, ls, color=C[kk], lw=lw, marker="o" if k == "stein" else None, ms=6, label=NAMES[kk], zorder=3 if k == "stein" else 2)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Per-Channel Shift (Noise Std)" if legend else "Shift (Noise Std)"); ax.set_ylabel("Risk per Channel")
    if ylim: ax.set_ylim(*ylim)
    if legend: ps.legend(ax, loc="upper left", ncol=1)
    ps.save(fig, path)
os.makedirs(os.path.join(F, "synthetic"), exist_ok=True)
for st in syn["settings"]:
    tag = f"n{st['n']}_{st['noise']}_s{st['scale']}".replace(".", "p")
    syn_panel(st, os.path.join(F, "synthetic", f"risk_{tag}"), legend=(tag == "n4_gauss_s1p0"), ylim=(5e-3, 2e2))

# ---------------------------------------------------------------- CIFAR-10-C plots
S = json.load(open(os.path.join(R, "summary.json")))
for model, res in S.items():
    BS = res["batch_sizes"]; s5 = res["sev5"]
    # mixing weight by layer for several batch sizes (mean over the 15 corruptions) + clean data
    os.makedirs(os.path.join(F, "mechanism"), exist_ok=True)
    fig, ax = ps.new_figure("square")
    blues = ["#BFD8EF", "#7FAEE0", "#2F6DB5"]
    for b, col in zip([1, 16, 200], blues):
        y = s5["lambda_mean_layer"][str(b)]; ax.plot(np.arange(1, len(y) + 1), y, "-o", color=col, lw=2.4, ms=5, label=f"$n$={b}")
    yc = res["clean"]["lambda_mean_layer"]["200"]
    ax.plot(np.arange(1, len(yc) + 1), yc, "--", color=P["base_gray"], lw=2.4, label="Clean, $n$=200")
    ax.set_xlabel("BN Layer"); ax.set_ylabel(r"Mean Weight $\hat{\lambda}$"); ax.set_ylim(-0.03, 1.25)
    ps.legend(ax, loc="upper center", ncol=2, frameon=False, columnspacing=0.8, handlelength=1.5)
    ps.save(fig, os.path.join(F, "mechanism", f"lambda_by_layer_{model}"))
    # error vs prior strength N at fixed batch sizes, SourceStein as dashed reference
    os.makedirs(os.path.join(F, "ablation"), exist_ok=True)
    fig, ax = ps.new_figure("square")
    Ns = [2, 4, 8, 16, 32, 64, 128, 256]
    for b, col in [(4, P["pink"]), (16, P["blue"])]:
        ax.plot(Ns, [s5[f"prior_N{N}"][str(b)] for N in Ns], "-o", color=col, lw=2.4, ms=6, label=f"Prior-BN, $n$={b}")
        ax.axhline(s5["stein"][str(b)], color=col, ls="--", lw=2.0, label=f"SourceStein, $n$={b}")
    ax.set_xscale("log", base=2); ax.set_xlabel("Pseudo Sample Size $N$"); ax.set_ylabel("Error (%)")
    lo, hi = ax.get_ylim(); ax.set_ylim(lo, hi + 0.75 * (hi - lo))
    ps.legend(ax, loc="upper left", ncol=1, frameon=False, handlelength=1.5, labelspacing=0.2)
    ps.save(fig, os.path.join(F, "ablation", f"prior_sweep_{model}"))
    # error vs batch size (appendix)
    fig, ax = ps.new_figure("wide")
    for k, kk, lab in [("source", "source", "Source"), ("bn_test", "bn_test", "TBN"), ("prior_N16", "prior", "Prior-BN ($N$=16)"),
                       ("alpha_0.9", None, r"$\alpha$-BN ($\alpha$=0.9)"), ("oracle_N", "oracle", "Oracle-$N$"), ("stein", "stein", "SourceStein")]:
        col = C[kk] if kk else P["pink_light"]
        ax.plot(BS, [s5[k][str(b)] for b in BS], "--" if k == "oracle_N" else "-o", color=col if k != "alpha_0.9" else "#F1667E",
                lw=3.2 if k == "stein" else 2.2, ms=6, label=lab)
    ax.set_xscale("log"); ax.set_xticks(BS); ax.set_xticklabels([str(b) for b in BS]); ax.set_ylim(25, 70)
    ax.set_xlabel("Test Batch Size $n$"); ax.set_ylabel("Error (%)"); ps.legend(ax, loc="upper right", ncol=2)
    ps.save(fig, os.path.join(F, "mechanism", f"error_vs_bs_{model}"))
print("plots written")

# ---------------------------------------------------------------- per-corruption bars at n=4 (ResNet-14)
pc = S["resnet14"]["sev5"]["per_corruption_bs4"]
short = {"gaussian_noise": "Gauss", "shot_noise": "Shot", "impulse_noise": "Impul", "defocus_blur": "Defoc", "glass_blur": "Glass",
         "motion_blur": "Motion", "zoom_blur": "Zoom", "snow": "Snow", "frost": "Frost", "fog": "Fog", "brightness": "Bright",
         "contrast": "Contr", "elastic_transform": "Elast", "pixelate": "Pixel", "jpeg_compression": "JPEG"}
cs = list(pc["stein"].keys()); xs = np.arange(len(cs)); w = 0.27
fig, ax = plt_fig = ps.new_figure("wide_bar")
ax.bar(xs - w, [pc["bn_test"][c] for c in cs], w, color=P["pink_light"], edgecolor=P["hatch_edge"], lw=1.0, label="TBN")
ax.bar(xs, [pc["prior_N16"][c] for c in cs], w, color=P["blue_light"], edgecolor=P["hatch_edge"], lw=1.0, label="Prior-BN ($N$=16)")
ax.bar(xs + w, [pc["stein"][c] for c in cs], w, color=P["blue"], edgecolor=P["blue"], lw=1.0, label="SourceStein")
ax.set_xticks(xs); ax.set_xticklabels([short[c] for c in cs], rotation=55, ha="right"); ax.set_ylabel("Error (%)")
ax.set_ylim(0, 70); ps.legend_above(ax, ncol=3)
ps.save(fig, os.path.join(F, "mechanism", "per_corruption_n4_resnet14"))
print("bars written")
