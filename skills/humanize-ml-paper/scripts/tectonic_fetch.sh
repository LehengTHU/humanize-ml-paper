#!/usr/bin/env bash
# tectonic_fetch.sh -- fetch files from the tectonic bundle when tectonic's own
# downloader times out ("error decoding response body" / "operation timed out").
#
# Why: on some networks tectonic 0.17 fetches most files, but large-range reads
# of default_bundle_v33.tar stall (seen for cmti9.pfb, cmsy5.pfb in ICML [accepted]
# builds). curl with small byte ranges and retries gets through.
#
# Usage:
#   tectonic_fetch.sh <outdir> <file> [<file> ...]      e.g. fonts cmti9.pfb cmsy5.pfb
#   tectonic_fetch.sh <outdir> --missing-pfb            every .pfb whose .tfm is cached but .pfb is not
# Then compile with the fetched files on the search path:
#   tectonic -X compile -Z search-path=<outdir> main.tex
set -u
OUT="$1"; shift
mkdir -p "$OUT"
CACHE="${TECTONIC_CACHE:-$HOME/Library/Caches/TectonicProject.Tectonic}/bundles/data"
INDEX=$(ls "$CACHE"/*.index 2>/dev/null | head -1)
[ -n "$INDEX" ] || { echo "no tectonic bundle index under $CACHE (run tectonic once)"; exit 1; }
DATA="${INDEX%.index}"
URL="${TECTONIC_BUNDLE_URL:-https://relay.fullyjustified.net/default_bundle_v33.tar}"
PIECE=8192

if [ "${1:-}" = "--missing-pfb" ]; then
  set -- $(cd "$DATA" && for t in *.tfm; do b=${t%.tfm}; [ -e "$b.pfb" ] || { grep -q "^$b.pfb " "$INDEX" && echo "$b.pfb"; }; done)
fi

fetch_one() {
  local name="$1" line off len have end n tries=0
  line=$(grep -m1 "^$name " "$INDEX") || { echo "not in bundle: $name"; return 1; }
  off=$(echo "$line" | awk '{print $2}'); len=$(echo "$line" | awk '{print $3}')
  [ -e "$DATA/$name" ] && { cp "$DATA/$name" "$OUT/$name"; echo "cached: $name"; return 0; }
  : > "$OUT/$name.part"
  have=0
  while [ "$have" -lt "$len" ] && [ "$tries" -lt 200 ]; do
    end=$((have + PIECE - 1)); [ "$end" -ge "$len" ] && end=$((len - 1))
    curl -sSL --max-time 25 -r $((off + have))-$((off + end)) -o "$OUT/$name.piece" "$URL" 2>/dev/null
    n=$(stat -f %z "$OUT/$name.piece" 2>/dev/null || stat -c %s "$OUT/$name.piece" 2>/dev/null || echo 0)
    if [ "$n" = "$((end - have + 1))" ]; then cat "$OUT/$name.piece" >> "$OUT/$name.part"; have=$((have + n)); fi
    rm -f "$OUT/$name.piece"; tries=$((tries + 1))
  done
  if [ "$have" -eq "$len" ]; then mv "$OUT/$name.part" "$OUT/$name"; echo "fetched: $name ($len B, $tries requests)"
  else echo "FAILED: $name ($have/$len B)"; return 1; fi
}

pids=()
for f in "$@"; do fetch_one "$f" & pids+=($!); while [ "$(jobs -r | wc -l)" -ge 6 ]; do sleep 0.5; done; done
wait
