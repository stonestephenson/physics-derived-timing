# FCHANNEL raw battery logs (2026-08-10)

Raw stdout-derived logs behind FCHANNEL.md §9.7 (distributional capacity),
§9.8 (attribution matrix), and the §9 coupling/scouting results — rescued
from the session scratchpad so the evidence outlives /tmp. Each line = one
sim run (config in the line prefix; breach fields are the sim's own
"zone breaches" output). CAUTION when parsing: the line contains BOTH a
`hard` and a `soft` block — sum only the hard block (the §9.7
analysis-erratum was an awk regex matching both). Formalization into
self-describing CSVs via a sweep tool is queued (FCHANNEL §10); until then
these are the reproduction source, regenerable with the commands in
FCHANNEL §9 / the fzone_sweep.py protocol on binary `git 188c255`+.

- afzone_coarse.log, fine_and_smoke.log — A_F(zone) scouting + cliff grids
  (superseded by the committed fzone_tolerance.csv; kept for the record)
- coupling_grid.log — bzone x fzone-z3 grid + A_B uniform cliff (§9.2)
- tuning_grid_n20.log — floor x guard-cap x seed fairness grid (§9.7)
- pclean_curves.log / pclean_spaced.log / pclean_s4000.log — P(clean)
  batteries: unspaced / F_spaced s=1 s / s=4 s (§9.7)
- attribution_rmalloc.log — the RM-alloc + F-economics cell (§9.8)
