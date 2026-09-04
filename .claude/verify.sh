#!/usr/bin/env bash
# Fast, SAFE verification gates (USAGE.md §Verification & baselines).
# Default: G0 (tool unit tests) + G1 (baseline) + G2 (predictor fidelity) — ~5s, for the every-finish
# done-gate. With `--full`: also G3 (RTA cross-check, ~15-100s) — for /ship or
# before committing. Asserts the golden numbers. READ-ONLY: writes no committed
# file — it never calls the destructive reproduce/sweep scripts.
#
# Used two ways:
#   * the agentic "done-gate" hook runs it automatically and blocks finishing on
#     failure;
#   * you can run it by hand:  bash .claude/verify.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
CPS=./build/cps
fail=0
out=/tmp/cps_verify_out

check() { # label  expected-substring
  if grep -qF "$2" "$out"; then printf '  PASS  %s\n' "$1"
  else printf '  FAIL  %s  (expected: %s)\n' "$1" "$2"; fail=1; fi
}

# --- incremental build (fast; configure first if build/ is missing) ---
if [ ! -x "$CPS" ]; then
  echo "no $CPS — configure first: cmake -B build -S . -DCMAKE_BUILD_TYPE=Release"; exit 1
fi
if ! cmake --build build -j >/tmp/cps_verify_build.log 2>&1; then
  echo "BUILD FAILED:"; tail -20 /tmp/cps_verify_build.log; exit 1
fi

echo "G0 tool unit tests (tools/tests, mocked simulator):"
if python3 -m unittest discover -s tools/tests -p 'test_*.py' >"$out" 2>&1; then
  printf '  PASS  %s\n' "$(grep -E '^Ran [0-9]+ tests' "$out")"
else
  printf '  FAIL  unit tests\n'; tail -15 "$out"; fail=1
fi

echo "G1 baseline (vehicles 6, rm, worst, 30s):"
"$CPS" --headless --vehicles 6 --scheduler rm --exec worst --duration 30 >"$out" 2>&1
check "worst-case data age 90.50/100.50 ms" "90.50 ms (freshest) / 100.50 ms (path)"
check "veh3 avg_perf 0.50700"               "0.50700"
check "veh3 soft% 13.43%"                    "13.43%"

echo "G2 predictor fidelity (vehicles 1, 120s, --validate-predictor):"
"$CPS" --headless --vehicles 1 --scheduler rm --exec worst --duration 120 --validate-predictor >"$out" 2>&1
check "max|dev| = 1.490e-08 m -> PASS"       "1.490e-08 m -> PASS"

# G3 is the compute-heavy RTA solver (~15-100s). Skipped by default so the
# done-gate stays fast; run `verify.sh --full` (used at /ship / before commit).
if [ "${1:-}" = "--full" ]; then
  echo "G3 RTA machine-check (rta_solve --cross-check):"
  python3 tools/rta_solve.py --cross-check >"$out" 2>&1
  check "certified capacity = 5"               "certified capacity = 5"
  check "empirical capacity = 10"              "empirical capacity = 10"
  check "all checks passed"                    "RESULT: all checks passed."
else
  echo "G3 RTA machine-check: SKIPPED (run 'verify.sh --full' before committing)"
fi

if [ "$fail" -eq 0 ]; then echo "verify: ALL GATES PASS"; exit 0; fi
echo "verify: FAILURES ABOVE — do not finish until green"; exit 1
