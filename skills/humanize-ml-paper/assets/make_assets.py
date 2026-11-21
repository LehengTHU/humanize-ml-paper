"""make_assets.py -- render the reference figures in assets/plots/ and assets/diagrams/.

Every figure here is drawn from INVENTED data and an invented example method ("X", a data-selection
loop: difficulty and diversity scores, a quota sampler, loss feedback) on one shared running example;
none reproduces a real result.

- Plots (assets/plots/*.png): drawn below with templates/plot_style.py exactly as a paper would, saved
  as 1000-px-wide PNG previews.
- Diagrams (assets/diagrams/*.pdf + *.png): each one is a standalone TikZ source in assets/diagram_src/
  on the shared style package templates/housediagram.sty, which implements the diagram conventions of
  references/figures_tables.md section 5. scripts/render_diagram.py builds each at the printed width of
  its float as a vector PDF (include it in LaTeX at exactly that width) plus a 300-dpi PNG preview.
  diagram_src/style_sheet.tex renders every style of the package into diagram_src/style_sheet.png.

Run:  python3 assets/make_assets.py        (needs matplotlib + numpy, Times New Roman for the plots,
                                            a LaTeX engine and PyMuPDF for the diagrams)
"""
from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


HERE = os.path.dirname(os.path.abspath(__file__))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(HERE, "..", "templates"))
import plot_style as ps  # noqa: E402

P = ps.PALETTE
OUT_PLOTS = os.path.join(HERE, "plots")
OUT_DIAG = os.path.join(HERE, "diagrams")
DIAG_SRC = os.path.join(HERE, "diagram_src")
DIAGRAMS = ["teaser_problem_solution", "teaser_failure_modes", "framework_pipeline", "key_idea_loop",
            "cluster_quota"]
THUMB_PX = 1000


def _save_thumb(fig, name, folder):
    """Save a 1000-px-wide PNG preview (the size of every bundled reference plot)."""
    os.makedirs(folder, exist_ok=True)
    fig.canvas.draw()
    bbox = fig.get_tightbbox(fig.canvas.get_renderer())
    dpi = THUMB_PX / (bbox.width + 2 * 0.03)
    out = os.path.join(folder, name + ".png")
    fig.savefig(out, dpi=dpi, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    return out


# ============================================================================ plots
def plot_cost_quality(rng):
    """Dual axis: quality lines (pink family) over cost bars (blue family); metric picks the hue."""
    xs = np.arange(6)
    epochs = ["1", "2", "3", "4", "5", "6"]
    base_t = np.array([4, 9, 16, 25, 36, 49]) * (1 + 0.03 * rng.standard_normal(6))    # re-scores every epoch
    ours_t = np.array([7, 9, 11, 13, 15, 18]) * (1 + 0.03 * rng.standard_normal(6))    # one-off cost, then cheap
    base_a = np.array([68.2, 72.5, 74.8, 76.0, 76.6, 76.9])
    ours_a = np.array([70.9, 76.4, 79.8, 81.6, 82.7, 83.3])
    fig, ax = ps.new_figure("wide")
    ax2 = ax.twinx()
    ax2.bar(xs - .18, base_t, .36, color=P["blue_light"], label="Baseline (Time)")
    ax2.bar(xs + .18, ours_t, .36, color=P["blue"], label="X (Time)")
    ax.plot(xs, ours_a, "-o", color=P["pink"], label="X (Acc.)")
    ax.plot(xs, base_a, "-o", color=P["pink_light"], label="Baseline (Acc.)")
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    ax2.grid(False)
    ax.set_ylim(0, 92)
    ax2.set_ylim(0, 92)
    ax.set_xticks(xs)
    ax.set_xticklabels(epochs)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Accuracy (%)")
    ax2.set_ylabel("Filtering time (min)")
    ps.color_yaxis(ax, P["pink_text"])
    ps.color_yaxis(ax2, P["blue_text"])
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ps.legend(ax, loc="center left", bbox_to_anchor=(0.015, 0.44), handles=h1 + h2, labels=l1 + l2, ncol=1)
    return _save_thumb(fig, "cost_quality_dual_axis", OUT_PLOTS)


def plot_dynamics_sweep(rng):
    """Square panel: ordered sweep of one hyperparameter in khaki (default darkest), raw + smoothed;
    unframed legend, highest curve first."""
    steps = np.arange(0, 302, 2)
    fig, ax = ps.new_figure("square")
    for beta, col, top, rate in zip([0.1, 0.3, 0.5], P["sweep_khaki"], [61, 65, 68], [70, 60, 55]):
        y = 40 + (top - 40) * (1 - np.exp(-steps / rate)) + 1.6 * rng.standard_normal(len(steps))
        ps.raw_and_smoothed(ax, steps, y, col, rf"$\beta={beta}$", w=15)
    ax.set_xlabel("Step")
    ax.set_ylabel("Val. accuracy (%)")
    ax.set_xticks([0, 100, 200, 300])
    h, l = ax.get_legend_handles_labels()
    ps.legend(ax, loc="lower right", frameon=False, handles=h[::-1], labels=l[::-1])
    return _save_thumb(fig, "dynamics_sweep", OUT_PLOTS)


def plot_grouped_bars_hatched(rng):
    """Grouped bars: tint = base, saturated = with X; dark-edged hatched bars for a variant; Avg. group."""
    groups = ["Set-A", "Set-B", "Set-C", "Set-D"]
    base = np.array([47.35, 61.20, 35.84, 70.12])
    ours = np.array([52.68, 63.05, 41.27, 72.46])
    ours_big = np.array([54.90, 66.31, 42.10, 75.83])
    series = [np.append(v, v.mean()) for v in (base, ours, ours_big)]
    x = np.arange(5) * 1.16
    bw = 0.315
    fig, ax = ps.new_figure("wide_bar")
    ax.set_axisbelow(True)
    bars = [ax.bar(x - bw, series[0], bw, color=P["blue_light"], label="Base"),
            ax.bar(x, series[1], bw, color=P["blue"], label="+ X"),
            ps.hatched_bars(ax, x + bw, series[2], bw, P["blue"], dark_edge=True, label=r"+ X ($2\times$ pool)")]
    for b in bars:
        ps.value_labels(ax, b, size=9.5)
    ps.avg_separator(ax, (x[3] + x[4]) / 2, color=P["sep_blue"])
    ax.margins(x=0.02)
    ax.set_ylim(30, 92)
    ax.set_xticks(x)
    ax.set_xticklabels(groups + ["Avg."])
    ax.set_xlabel("Evaluation set")
    ax.set_ylabel("Accuracy (%)")
    ps.legend(ax, loc="upper left", ncol=3)
    return _save_thumb(fig, "grouped_bars_hatched", OUT_PLOTS)


def plot_ablation_bars(rng):
    """Ablation: full method saturated, variants in the tint (a dark-edged hatch separates them); legend above."""
    groups = ["Set-A", "Set-B", "Set-C"]
    full = np.array([78.42, 71.06, 84.37])
    wo_a = np.array([74.10, 68.92, 82.55])
    wo_b = np.array([75.87, 66.35, 81.04])
    series = [np.append(v, v.mean()) for v in (wo_a, wo_b, full)]
    x = np.arange(4)
    bw = 0.26
    fig, ax = ps.new_figure("wide")
    b1 = ax.bar(x - bw, series[0], bw, color=P["pink_light"], label="w/o A")
    b2 = ps.hatched_bars(ax, x, series[1], bw, P["pink_light"], label="w/o B")   # pale fill: dark-edged hatch
    b3 = ax.bar(x + bw, series[2], bw, color=P["pink"], label="X (full)")
    for b in (b1, b2, b3):
        ps.value_labels(ax, b, size=11)
    ps.avg_separator(ax, 2.5)
    ax.set_ylim(60, 91)
    ax.set_xticks(x)
    ax.set_xticklabels(groups + ["Avg."])
    ax.set_xlabel("Evaluation set")
    ax.set_ylabel("Accuracy (%)")
    ps.legend_above(ax, ncol=3)
    return _save_thumb(fig, "ablation_bars_pink", OUT_PLOTS)


# ============================================================================ diagrams
RENDER = os.path.join(HERE, "..", "scripts", "render_diagram.py")


def build_diagrams():
    """Build diagram_src/<name>.tex with scripts/render_diagram.py; returns the written paths."""
    srcs = [os.path.join(DIAG_SRC, n + ".tex") for n in DIAGRAMS]
    subprocess.run([sys.executable, RENDER, *srcs, "--out-dir", OUT_DIAG, "--dpi", "300", "--check"], check=True)
    sheet = os.path.join(DIAG_SRC, "style_sheet.tex")
    subprocess.run([sys.executable, RENDER, sheet, "--out-dir", DIAG_SRC, "--dpi", "300"], check=True)
    os.remove(os.path.join(DIAG_SRC, "style_sheet.pdf"))      # the sheet is a PNG preview only
    return [os.path.join(OUT_DIAG, n + ext) for n in DIAGRAMS for ext in (".pdf", ".png")] + \
        [os.path.join(DIAG_SRC, "style_sheet.png")]


def main():
    rng = np.random.default_rng(0)
    ps.apply()
    written = [plot_cost_quality(rng), plot_dynamics_sweep(rng), plot_grouped_bars_hatched(rng),
               plot_ablation_bars(rng)]
    written += build_diagrams()
    for w in written:
        print(os.path.relpath(w, HERE))


if __name__ == "__main__":
    main()
