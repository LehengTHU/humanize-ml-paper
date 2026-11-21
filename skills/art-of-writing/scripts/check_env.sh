#!/usr/bin/env bash
# check_env.sh -- check that this machine can build papers and run the skill's scripts.
# Usage: bash scripts/check_env.sh        (run from the skill folder or anywhere)
# Checks: Python 3.8+, matplotlib + numpy, PyMuPDF, a LaTeX engine (tectonic or latexmk/pdflatex),
# Times New Roman (for plots), then builds templates/env_test.tex and templates/diagram_skeleton.tex
# in a temp folder.
# Every missing item prints the install command; see README.md "Setup" for details.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
ok(){ printf "  [ok]   %s\n" "$1"; }
bad(){ printf "  [MISSING] %s\n         -> %s\n" "$1" "$2"; FAIL=1; }
warn(){ printf "  [warn] %s\n         -> %s\n" "$1" "$2"; }
FAIL=0
OS="$(uname -s)"
echo "== Python"
if command -v python3 >/dev/null 2>&1; then
  V=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
  python3 -c 'import sys;sys.exit(0 if sys.version_info>=(3,8) else 1)' && ok "python3 $V" || bad "python3 $V is older than 3.8" "install a newer Python (https://www.python.org/downloads/)"
  for m in matplotlib numpy; do
    python3 -c "import $m" 2>/dev/null && ok "$m" || warn "$m (only needed for plots)" "python3 -m pip install --user matplotlib numpy"
  done
  python3 -c "import fitz" 2>/dev/null && ok "PyMuPDF" || warn "PyMuPDF (needed for diagram previews and checks)" "python3 -m pip install --user pymupdf"
else
  bad "python3" "macOS: brew install python  |  Ubuntu/Debian: sudo apt install python3 python3-pip  |  Windows: https://www.python.org/downloads/"
fi
echo "== LaTeX engine"
ENGINE=""
if command -v tectonic >/dev/null 2>&1; then ENGINE=tectonic; ok "$(tectonic --version | head -1)"
elif command -v latexmk >/dev/null 2>&1 && command -v pdflatex >/dev/null 2>&1; then ENGINE=latexmk; ok "latexmk + pdflatex ($(pdflatex --version | head -1))"
else
  case "$OS" in
    Darwin) HINT="brew install tectonic   (or the full TeX Live: brew install --cask mactex-no-gui)";;
    Linux)  HINT="curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh   (installs tectonic into the current folder; move it onto your PATH)  |  or: sudo apt install latexmk texlive-latex-extra texlive-fonts-recommended texlive-science texlive-pictures";;
    *)      HINT="Windows: scoop install tectonic  (or install MiKTeX / TeX Live)  |  or use Overleaf";;
  esac
  bad "no LaTeX engine (tectonic or latexmk+pdflatex)" "$HINT"
fi
echo "== Fonts (plots)"
if python3 -c 'import matplotlib' 2>/dev/null; then
  F=$(python3 - <<'PY'
from matplotlib import font_manager as fm
names={f.name for f in fm.fontManager.ttflist}
for n in ["Times New Roman","Times","Nimbus Roman","TeX Gyre Termes","Liberation Serif"]:
    if n in names: print(n); break
PY
)
  if [ "$F" = "Times New Roman" ]; then ok "Times New Roman"
  elif [ -n "$F" ]; then warn "Times New Roman not found; plots will use $F" "Ubuntu/Debian: sudo apt install ttf-mscorefonts-installer, then rm -rf ~/.cache/matplotlib"
  else warn "no Times-like font found" "Ubuntu/Debian: sudo apt install ttf-mscorefonts-installer fonts-texgyre, then rm -rf ~/.cache/matplotlib"; fi
else
  warn "skipped (matplotlib missing)" "python3 -m pip install --user matplotlib numpy"
fi
echo "== Test build (templates/env_test.tex)"
if [ -n "$ENGINE" ]; then
  T=$(mktemp -d); cp "$HERE/templates/env_test.tex" "$HERE/templates/preamble.tex" "$T/"
  if [ "$ENGINE" = tectonic ]; then
    (cd "$T" && tectonic -X compile env_test.tex >"$T/build.log" 2>&1)
  else
    (cd "$T" && latexmk -pdf -interaction=nonstopmode env_test.tex >"$T/build.log" 2>&1)
  fi
  if [ -s "$T/env_test.pdf" ]; then ok "built $T/env_test.pdf"
  else
    bad "test build failed (log: $T/build.log)" "tectonic needs network access on the first build; if a font download times out run: bash scripts/tectonic_fetch.sh <dir> --missing-pfb and add -Z search-path=<dir>. With TeX Live, install the missing package named in the log."
    tail -15 "$T/build.log" | sed 's/^/         | /'
  fi
else
  warn "skipped (no LaTeX engine)" "install one of the engines above, then re-run this script"
fi
echo "== Test diagram (templates/diagram_skeleton.tex)"
if [ -n "$ENGINE" ] && python3 -c "import fitz" 2>/dev/null; then
  T=$(mktemp -d)
  if python3 "$HERE/scripts/render_diagram.py" "$HERE/templates/diagram_skeleton.tex" --out-dir "$T" >"$T/render.log" 2>&1; then ok "built $T/diagram_skeleton.pdf and .png"
  else bad "diagram build failed (log: $T/render.log)" "read the log; with TeX Live install texlive-pictures and texlive-fonts-recommended"; tail -15 "$T/render.log" | sed 's/^/         | /'; fi
else
  warn "skipped (needs a LaTeX engine and PyMuPDF)" "install them, then re-run this script"
fi
echo
if [ "$FAIL" = 0 ]; then echo "Environment ready. Next: download the venue kit (README.md 'Venue style files')."; else echo "Fix the MISSING items above, then re-run: bash scripts/check_env.sh"; fi
exit $FAIL
