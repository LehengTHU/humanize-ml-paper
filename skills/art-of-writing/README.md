# art-of-writing

A Claude Code skill for writing and revising ML conference papers (ICLR, NeurIPS, ICML) in one consistent house style. The style was distilled from a set of published conference papers: the section skeleton, paragraph templates, transitions, notation, experiment write-up, figure palette, table layout and LaTeX project layout. Each rule carries an evidence label (`[all]`, `[most]`, `[some]`, `[current]`, `[venue: X]`, ...) that says how strongly the source papers support it. Every example, figure and table in the skill is synthetic.

## Install

Install it as described in the [repository README](../../README.md#install), or copy this folder into your Claude Code skills directory:

```bash
cp -r skills/art-of-writing ~/.claude/skills/
```

Claude Code picks the skill up on the next start. It triggers when you ask for a full paper, a section, a result table, a figure, a page-budget plan, a venue switch or a self-review. You can also invoke it by name.

## Setup (LaTeX, Python, fonts)

Run the self-check first. It tells you what is missing and prints the install command for your system, then builds a one-page test PDF:

```bash
bash ~/.claude/skills/art-of-writing/scripts/check_env.sh
```

### 1. A LaTeX engine (required to build the paper)

Pick one. **tectonic** is the smallest option: a single program that downloads only the packages a paper uses, on the first build (so the first build needs network access). The skill's build recipes are tested with tectonic 0.17. A full TeX Live works too.

| System | tectonic (recommended) | Full TeX Live / MiKTeX |
|---|---|---|
| macOS | `brew install tectonic` (needs [Homebrew](https://brew.sh)) | `brew install --cask mactex-no-gui` (about 5 GB), then open a new terminal |
| Ubuntu / Debian | `curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net \| sh`, then move the `tectonic` binary onto your PATH (e.g. `sudo mv tectonic /usr/local/bin/`) | `sudo apt install latexmk texlive-latex-extra texlive-fonts-recommended texlive-science texlive-pictures` |
| Windows | `scoop install tectonic` (needs [Scoop](https://scoop.sh)), or download the release from https://tectonic-typesetting.github.io | [MiKTeX](https://miktex.org) or [TeX Live](https://tug.org/texlive/) |
| Any (conda) | `conda install -c conda-forge tectonic` | — |

No local install at all: upload the project to [Overleaf](https://www.overleaf.com), which has every package the templates use; only `check_paper.py`'s page check needs a local build.

Build a paper with `tectonic -X compile --keep-intermediates main.tex` (or `latexmk -pdf main.tex`). If tectonic stops with "error decoding response body" or "operation timed out" while downloading a font (e.g. `cmti9.pfb`), run `bash scripts/tectonic_fetch.sh fonts --missing-pfb` and rebuild with `-Z search-path=fonts` (details: `references/venues.md` §2.3).

### 2. Python 3.8+ (for the checker, the phrase tools and the plots)

`check_paper.py`, `bib_to_dblp.py` and `tools/` use only the standard library. Plots need matplotlib and numpy; the diagram builder (`scripts/render_diagram.py`) needs PyMuPDF to check the PDF and write the PNG preview:

```bash
python3 -m pip install --user matplotlib numpy pymupdf
```

Diagrams are TikZ files built with the same LaTeX engine as the paper. tectonic downloads TikZ and the fonts on the first build; with TeX Live, the `texlive-pictures` and `texlive-fonts-recommended` packages listed above cover them.

### 3. Times New Roman (plots only)

Preinstalled on macOS and Windows. On Linux: `sudo apt install ttf-mscorefonts-installer` (or `fonts-texgyre` for the TeX Gyre Termes clone), then clear matplotlib's font cache with `rm -rf ~/.cache/matplotlib`. Without it `plot_style.py` warns and matplotlib falls back to another serif. Diagrams take their fonts (TeX Gyre Heros, Latin Modern math) from the LaTeX engine, and the paper uses the fonts of the venue kit, so neither needs this.

### 4. The venue kit

Download the official style files for your venue and year (next section) and put them next to your main `.tex` file. The test PDF above builds without them; the real templates do not.

## What is included

| Path | Contents |
|---|---|
| `SKILL.md` | The workflow from proposal to finished paper, and the style checklist |
| `references/` | Venue facts and page budgets, paper types, structure, prose templates, Introduction logic (the argument chain, prior-work moves, rules IR1-IR15: `introduction.md`), contribution emphasis without a contribution list (epithet, verb tiers, pending-results wording, rules KR1-KR14: `contributions.md`), key concepts, math, experiments, figures and tables, LaTeX source conventions, annotated examples |
| `templates/` | One-column (ICLR/NeurIPS) and two-column (ICML) main files with chapter scaffolds, a shared `preamble.tex`, table templates, `references.bib`, `plot_style.py` for matplotlib, and `housediagram.sty` + `diagram_skeleton.tex` for TikZ diagrams |
| `scripts/check_paper.py` | Word budget per chapter, page check, venue checks, concept and vocabulary checks, cohesion notes (connective share, double lock, approximate isolation), style lint, Introduction and contribution checks (contribution-list phrasing, "novel" / "first", reference-style difference sentences, the `% epithet:` count, strong result verbs while results are pending), and warnings for 27 recurring draft habits with line numbers (stdlib only; `--vocab PATH` adds a rare-word check against your own word list, e.g. the `vocab.txt` written by `tools/build_corpus.py`) |
| `scripts/bib_to_dblp.py` | Rewrites a verified `.bib` in the DBLP-condensed style (short venue names, arXiv entries as `CoRR`, full author lists from the arXiv API, acronym-only title braces; stdlib only) |
| `scripts/check_env.sh` | Checks Python, matplotlib/numpy, a LaTeX engine and the Times font, prints the install command for anything missing, and builds `templates/env_test.tex` as a smoke test |
| `scripts/tectonic_fetch.sh` | Fetches tectonic bundle files (fonts) when its downloader times out |
| `tools/` | `ps.py` looks a phrase up: by default against the shipped `phrase_index.json.gz` (1-5 word n-gram counts, no setup needed), or against your own sentence corpus with `--corpus`. `build_corpus.py` builds that corpus from your own LaTeX papers (writes to your workspace, never into the skill) and `ngrams.py` lists its recurring n-grams and openers, so drafts reuse expressions you actually write (stdlib only) |
| `scripts/render_diagram.py` | Builds a TikZ diagram into a vector PDF at its printed width plus a PNG preview, and checks it: LaTeX warnings, width against the `% target-width-in:` line, Type 3 fonts, raster images, and (`--check`) the clean-palette metrics |
| `scripts/colour_stats.py` | Checks that a diagram PNG uses the clean palette: white share (≥ 0.72), earthy share (≤ 0.05), hue families (≤ 3), mean saturation of the coloured pixels (0.25-0.75) |
| `assets/lexicon/` | The shipped phrase bank: 1,272 attested expressions (`lexicon.md`, readable; `lexicon.json`, machine-readable) drawn from 6 "house" papers (the imitated style) and 16 "reference" papers (two earlier-work lineages, comparison only), each with its function, per-group counts, tier (core / occasional / retired / ref_only / banned) and an example |
| `assets/` (`diagrams/`, `plots/`) | Reference plots (1000-px PNG) and diagrams (printed-size vector PDF + 300-dpi PNG) drawn from invented data on one running example, the diagrams in the clean palette (white boxes with rose / navy outlines, one filled focal module, amber score and feedback arrows, bold sans labels, LaTeX math); their TikZ sources and `style_sheet.png` (every diagram style with its name) in `assets/diagram_src/`; and `make_assets.py`, which regenerates everything |

Requirements: Python 3 for `check_paper.py`, `tools/` and `bib_to_dblp.py` (network access only for the arXiv author lookups of `bib_to_dblp.py`); matplotlib and numpy for `plot_style.py` and `assets/make_assets.py` (plots use bold Times New Roman when installed); a LaTeX engine (tectonic or latexmk) for the templates and the diagrams, plus PyMuPDF for `render_diagram.py` and `colour_stats.py` (numpy). Installation steps: "Setup" above.

## Venue style files

The official venue kits are **not bundled**. Download them from the official sites for the year you submit to, and re-check the call for papers, because page limits and required statements change every year:

- ICLR: https://iclr.cc (author guide and `iclr<year>_conference` template)
- NeurIPS: https://neurips.cc (call for papers and `neurips_<year>` style files)
- ICML: https://icml.cc (call for papers and `icml<year>` style files; see `templates/venue/icml/README.md`)

Place the kit files next to your main `.tex` file, as described in `SKILL.md` (Step 0) and `references/venues.md`.
