#!/usr/bin/env bash
# Presentation demo: "zero hard breaches far past the classical limit".
# Rate-monotonic (the classical fixed-priority baseline) vs aguard
# (our age-criticality scheduler), worst-case execution, 3 cloud cores.
# Usage:  bash tools/demo_capacity.sh            # summary table at N=10,12,18
#         bash tools/demo_capacity.sh 10 12 18 20
set -euo pipefail
cd "$(dirname "$0")/.."
CPS=./build/cps
Ns=("${@:-10 12 18}")
# allow "10 12 18" as one arg or as several
if [ "$#" -le 1 ]; then read -ra Ns <<< "${1:-10 12 18}"; else Ns=("$@"); fi

hdr() { printf "%-4s  %-20s  %-14s  %-13s  %-11s\n" "$@"; }
hdr "N" "scheduler" "hard breaches" "cars stalled" "worst soft%"
hdr "--" "--------------------" "-------------" "-------------" "-----------"
for N in "${Ns[@]}"; do
  for S in rm aguard; do
    out=$("$CPS" --headless --vehicles "$N" --scheduler "$S" --exec worst --duration 30 2>&1)
    hard=$(echo "$out" | awk 'NR>2 && $1~/^[0-9]+$/{h+=$5}END{print h+0}')
    nact=$(echo "$out" | awk 'NR>2 && $1~/^[0-9]+$/ && $6=="n/a"{c++}END{print c+0}')
    soft=$(echo "$out" | awk 'NR>2 && $1~/^[0-9]+$/{gsub(/%/,"",$4);if($4>m)m=$4}END{printf "%.0f%%",m}')
    name=$([ "$S" = "rm" ] && echo "rate-monotonic" || echo "aguard (age-crit)")
    hdr "$N" "$name" "$hard" "$nact" "$soft"
  done
  echo ""
done
