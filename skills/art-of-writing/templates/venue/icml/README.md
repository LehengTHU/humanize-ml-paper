# ICML style files (not bundled)

The ICML kit is not copied into this skill. `icml2026.sty` has no license statement. `algorithm.sty` and `algorithmic.sty` carry only "Copyright 1994 Peter Williams". Only `fancyhdr.sty` and `icml2026.bst` state LPPL terms. Because the kit must stay together and never be edited ("Do not alter the style template"), fetch it from ICML for every paper.

## Get the current kit

1. Check the current year first (`references/venues.md` §1.0). On 2026-09-25, `https://icml.cc/Conferences/2027/CallForPapers` returned 404, so ICML 2026 was the latest kit.
2. Download and unpack the kit next to the main file:
   ```bash
   Y=2026   # use the year of the call you are submitting to
   curl -LO https://media.icml.cc/Conferences/ICML$Y/Styles/icml$Y.zip
   unzip -j icml$Y.zip '*.sty' '*.bst' -d <paper_dir>
   ```
   ICML 2026 files: `icml2026.sty`, `icml2026.bst`, `algorithm.sty`, `algorithmic.sty`, `fancyhdr.sty`. Use them byte for byte; only the kit's `example_paper.tex` is meant to be edited into your main file.
3. Copy `templates/main_skeleton_icml.tex`, `templates/preamble.tex`, `templates/references.bib`, and `templates/chapters_icml/` (renamed to `chapters/`) into the same folder.
4. For a new year, replace `icml2026` with `icml<Y>` in `\usepackage{}` and `\bibliographystyle{}`, and re-check the rules in `references/venues.md` §2.

## Build

```bash
tectonic -X compile --keep-intermediates main_skeleton_icml.tex
```

If tectonic times out on a font download, fetch the font with `scripts/tectonic_fetch.sh` and compile with `-Z search-path=<dir>` (`references/venues.md` §2.3). Before camera-ready submission, run the official format checker at https://papercheck.icml.cc/papercheck.html.
