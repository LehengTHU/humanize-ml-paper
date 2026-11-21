# NOTES — SourceStein (ICML 2027 submission draft)

**Title.** SourceStein: Shrinking Test-Time Normalization Statistics toward the Source in Closed Form

**Idea (one paragraph).** Test-time normalization makes a BatchNorm classifier more robust to covariate shift: it re-estimates the BN statistics on each test batch. Existing rules (TBN, Prior-BN with a pseudo sample size N, α-BN) mix the stored source statistics with the test-batch statistics through a weight λ. That weight is fixed before the batch is seen. As a result, the statistics are either stale (large shift, small λ: shift bias) or noisy (small batch, large λ: estimation variance). SourceStein sets λ separately for each BN layer and each batch with the positive-part James–Stein rule λ̂ = (1 − (C−2)/S)₊. Here S = n‖μ̂ − μ^src‖²_{Σ⁻¹} is a shift score whitened by between-sample variances τ² that are measured once on 5,000 training images, so the rule also works at batch size 1. The variance is handled the same way, through per-sample second moments and their variances ρ². The rule is training-free and has no hyperparameters. Under a Gaussian model its risk never exceeds that of TBN and is within 4(C−1)/(C+Δ) of the oracle mixing weight (Proposition 1, proved in Appendix B). Paper type: T (objective + closed form).

## Venue
- ICML 2027 call (icml.cc/Conferences/2027/CallForPapers, AuthorInstructions, UseOfGenerativeAIByAuthors), fetched 2026-11-14. The rules: 8-page main body; references, Impact Statement and appendix unlimited, in one PDF; Impact Statement required; **new in 2027: an AI Disclosure Statement is required** (not counted toward the limit).
- Kit: `media.icml.cc/Conferences/ICML2027/styles/icml2027.zip` (copy in `kit_download/`). `icml2027.sty` matches `icml2026.sty` except for the year (checked with `diff`). The skill's ICML skeleton is used with `icml2026` swapped to `icml2027`.
- The AI Disclosure Statement says that a generative AI agent did the ideation, code, experiments, analysis, figures, literature check and drafting. **The human authors must review and, if needed, edit this statement and the whole paper before submitting it.**

## Experiments (all on CPU, 15 cores; wall-clock times from `results/log_*.txt`)
| Step | Script | Output | Time |
|---|---|---|---|
| Download CIFAR-10 + severity-3/5 slices of the 15 CIFAR-10-C corruptions (byte ranges from Zenodo) | `code/tar_index.py`, `code/fetch_c10c.py`, `code/fetch_c10c_chunked.py` | `data/` | network only (~10 min) |
| Train CNN-8 (8 epochs) and ResNet-14 (5 epochs), in parallel | `code/train.py` | `results/train_*.json`, `results/models/*.pt` | 11.6 / 11.9 min (parallel, ≈12 min wall) |
| Simulation (risk vs. shift, C=64) | `code/synthetic.py` | `results/synthetic_risk.json` | 2 s |
| CIFAR-10-C evaluation: all rules, ablations, N sweep, both severities, clean | `code/eval_c10c.py` (`code/tta.py` = the method) | `results/c10c_{resnet14,cnn8}.json` | 7.9 / 12.2 min (overlapping, ≈14 min wall) |
| TENT extension | `code/tent_eval.py` | `results/tent_{resnet14,cnn8}.json` | 4.8 / 3.7 min |
| Inference timing | `code/timing.py` | `results/timing.json` | 0.6 min |
| Quick sanity check before the full runs (not reported) | (/tmp script) | — | ~0.5 min |

Total compute ≈ 37 min wall-clock, within the 45-minute budget.

Post-processing (no new compute): `code/analyze.py` → `results/summary.json`; `code/make_tables.py` → `results/table_rows.txt`; `code/extra_stats.py` → `results/extra_stats.txt`; `code/make_plots.py` → `figures/exp/**`. The diagram is `figures/src/main_figure.tex`, built with `render_diagram.py --check` (6.06 in vs. a 6.10 in target; white 0.77, earthy 0.00, 1 hue family, mean-sat 0.73).

## Where each number comes from
- **Table 1 (main), Table 4 (severity 3), Table 5 (ablation), Tables 8–9 (appendix), Figures 3–5, 7:** `results/summary.json` (from `results/c10c_*.json`). The rows are printed by `code/make_tables.py` (`results/table_rows.txt`); Table 9 was filled programmatically from the same file.
- **Table 2 (clean):** `summary.json` → `[model].clean`.
- **Table 3 (timing):** `results/timing.json`.
- **Table 6 (TENT):** `summary.json` → `[model].tent` (from `results/tent_*.json`).
- **Figures 1, 6, 9 and the simulation numbers in the text (0.023, 0.114, 6 of 14, 0.5 floor, 256):** `results/synthetic_risk.json`; derived values in `results/extra_stats.txt`.
- **Weights quoted in RQ2 (0.06→0.46, 0.11→0.47, 1.5–3.5×), "12 of 15 corruptions", "within 2.2 points on clean data":** `results/extra_stats.txt`.
- **Clean accuracies (86.54%, 82.56%) and training times:** `results/train_*.json`, `results/log_train_*.txt`.
- **Oracle-N values (Appendix C):** `summary.json` → `sev5.oracle_N_value`.
- **Compute times (Appendix C):** `results/log_*.txt` (`time` output).

## Honest caveats visible in the paper
- At n=1, the privileged Oracle-N is lower than SourceStein; at severity 3 with n=1, α-BN is lower. For n ≥ 64, TBN is slightly lower on CNN-8.
- On clean data SourceStein is up to 2.2 points worse than the Source model.
- Combined with TENT, SourceStein helps ResNet-14 but not CNN-8.
- Each corruption is evaluated on a 1,000-image subset of CIFAR-10-C with one seed, and the models are small and trained briefly on CPU.

## References
All 19 entries were checked against the arXiv API (title, authors, year, venue from the arXiv comments). James & Stein (1961) and Efron & Morris (1973) were checked against Crossref. `bib/verified.bib` was converted with `scripts/bib_to_dblp.py` into `example_paper.bib`. Pages for the two statistics classics were added by hand, and proper names were braced. DBLP itself blocks scripted access, so it was not queried. Where a venue could not be confirmed from arXiv (Nado et al., You et al., Li et al., Khoshsirat & Kambhamettu, Ivolgina et al.), the entry is cited as CoRR.

## Build
`tectonic -X compile --keep-intermediates example_paper.tex`: 0 errors, 0 undefined references or citations, 0 overfull boxes, 0 missing characters, no Type 3 fonts. Two hyperref notices remain; they come from the template. The main text ends at the bottom of page 8 (right column about 1.5 lines short). Page 9 holds the AI Disclosure and Impact Statements and the references, followed by a one-column appendix (pp. 10–14).

## Final `check_paper.py . --venue icml --stage submission --limit 8` summary
- Page check: `main-text-end on page 8 (limit 8): ok: fills the limit`.
- Venue: 0 hits. The only remaining NOTE is that the kit year (2027) is newer than the script's last-verified year (2026). The 2027 call was checked by hand, and the limits and statements are unchanged apart from the new AI disclosure, which is included.
- Concepts: 0 hits (5 core + 3 framing, 8 marks, all core concepts echoed). Terms: 0 warnings (2 coined: "shift score", "SourceStein"). Vocabulary: 0 hits (14.3 compounds per 1k words). Lint: 0 hits. Intro & contributions: 0 warnings (epithet "adaptive and stable" appears in all four places).
- Habits: 7 warnings, all for the verb "shrink", which is the technical term of shrinkage estimation (James–Stein); kept on purpose.
- Sentences: 16 pattern-match warnings, reviewed by hand. They are mostly sentence-final "which" clauses, and the intro's standard sentence has two "(i.e. ...)" parentheses because it follows the skill's own template.
- Word count: 4,325 prose words (HIGH against the 3,650–3,900 blueprint; Experiments 1,473 is HIGH). The page fill itself is exact; the number of floats (about 13) sets the length.
- Cohesion (soft targets): connective-led share is Intro 52.5%, Method 44.2%, Experiments 31.4%, slightly below the targets.
