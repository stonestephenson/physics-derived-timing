#!/usr/bin/env python3
"""Unit tests for tools/zone_sweep.py's phase-aware aggregation (min-over-phase
A(zone), paper/PLAN.md §3 / PAPER_NOTES 2026-09-04). The simulator is mocked:
these test the tool's arithmetic and schemas, not the physics.

Run:  python3 -m unittest discover -s tools/tests -p 'test_*.py'
"""
import csv
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import zone_sweep as zs  # noqa: E402


def result(age, hard, soft=2.7, ey=0.3):
    """Canned simulator result. hard = per-zone list."""
    return {"age_path": age, "hard": list(hard), "soft_pct": soft,
            "fleet_ey": ey, "zone_ey": [ey, 0.1, 0.1, ey], "f_stale_max": 22.3}


class ParseTests(unittest.TestCase):
    def test_phase_range_includes_last_tick(self):
        # The half-open interval's sup (STOP - 0.1 ms tick) is the worst phase
        # at every measured cliff; a grid that omits it under-reports A(zone)
        # (cold review 2026-09-04: v12.5 z3 150.5 -> 140.5).
        self.assertEqual(zs.parse_phases("0:20:5"), [0.0, 5.0, 10.0, 15.0, 19.9])
        ph = zs.parse_phases("0:20:1")
        self.assertEqual(len(ph), 21)
        self.assertEqual(ph[-1], 19.9)
        self.assertEqual(ph[:3], [0.0, 1.0, 2.0])

    def test_phase_range_fractional_step(self):
        self.assertEqual(zs.parse_phases("0:2:0.5"), [0.0, 0.5, 1.0, 1.5, 1.9])

    def test_phase_range_no_duplicate_last_tick(self):
        self.assertEqual(zs.parse_phases("0:1:0.1")[-1], 0.9)
        self.assertEqual(len(zs.parse_phases("0:1:0.1")), 10)

    def test_build_cmd_ff_extra(self):
        # A2 instrument (PROOF_DRAFT §8.3): delay every F publish by D ms.
        # Off by default (byte-identical); rendered only when > 0.
        base = zs.build_cmd(3, 80, 120, "10", ("offset_ms", 0.0))
        self.assertNotIn("--ff-extra-ms", base)
        ff = zs.build_cmd(3, 80, 120, "10", ("offset_ms", 0.0), ff_extra_ms=13.5)
        self.assertEqual(ff[ff.index("--ff-extra-ms") + 1], "13.5")

    def test_check_ff_extra(self):
        zs.check_ff_extra(0.0, legacy=True)            # off: fine anywhere
        zs.check_ff_extra(13.5, legacy=False)          # phase mode: fine
        with self.assertRaises(SystemExit):
            zs.check_ff_extra(13.5, legacy=True)       # legacy schema can't record it
        with self.assertRaises(SystemExit):
            zs.check_ff_extra(-1.0, legacy=False)      # negative: never sent to the binary

    def test_build_cmd_zone_consts(self):
        # partition-sensitivity instrument: pass the six constants through
        base = zs.build_cmd(2, 80, 95, "12.5", ("offset_ms", 0.0))
        self.assertNotIn("--zone-consts", base)
        zc = zs.build_cmd(2, 80, 95, "12.5", ("offset_ms", 0.0),
                          zone_consts="0.0172,0.0035,0.0040,50,100,350")
        self.assertEqual(zc[zc.index("--zone-consts") + 1], "0.0172,0.0035,0.0040,50,100,350")

    def test_check_zone_consts_needs_phase_mode(self):
        zs.check_zone_consts("", legacy=True)
        zs.check_zone_consts("0.0215,0.0035,0.0040,50,100,350", legacy=False)
        with self.assertRaises(SystemExit):
            zs.check_zone_consts("0.0215,0.0035,0.0040,50,100,350", legacy=True)
        with self.assertRaises(SystemExit):
            zs.check_zone_consts("0.0215,0.0035", legacy=False)   # not six values

    def test_build_cmd_renders_phase_flags(self):
        base = zs.build_cmd(3, 80, 120, "10")
        self.assertNotIn("--start-offsets-ms", base)
        self.assertNotIn("--offset-seed", base)
        off = zs.build_cmd(3, 80, 120, "10", ("offset_ms", 19.9))
        self.assertEqual(off[off.index("--start-offsets-ms") + 1], "19.9")
        seed = zs.build_cmd(3, 80, 120, "10", ("seed", 7))
        self.assertEqual(seed[seed.index("--offset-seed") + 1], "7")
        self.assertEqual(off[off.index("--zone-extra-ms") + 1], "80")

    def test_phase_list(self):
        self.assertEqual(zs.parse_phases("0,19,19.9"), [0.0, 19.0, 19.9])

    def test_seed_count(self):
        self.assertEqual(zs.parse_seeds("3"), [1, 2, 3])

    def test_seed_list(self):
        self.assertEqual(zs.parse_seeds("1,7,9"), [1, 7, 9])

    def test_seed_zero_rejected(self):
        # seed 0 is the deterministic single-phase path (Simulation.cpp:109)
        with self.assertRaises(SystemExit):
            zs.parse_seeds("0,1")


class LegacyTests(unittest.TestCase):
    """No phase option: rows/table must match the pre-phase tool exactly."""

    def runner(self, zone, extra, phase):
        self.assertIsNone(phase)
        age = 90.5 + extra
        hard = [0, 0, 0, 0] if extra <= 50 else [0, 0, 0, 3]
        return result(age, hard)

    def test_rows_and_table(self):
        rows, table = zs.sweep([3], [0, 50, 100], [None], self.runner)
        self.assertEqual(rows, [[3, "lane-change", 0, 90.5, 0, 0, 0, 0, 0],
                                [3, "lane-change", 50, 140.5, 0, 0, 0, 0, 0],
                                [3, "lane-change", 100, 190.5, 3, 0, 0, 0, 3]])
        (entry,) = table
        self.assertEqual(entry.zone, 3)
        self.assertEqual(entry.a_zone, 140.5)
        self.assertEqual(entry.first_breach, (190.5, [0, 0, 0, 3], None))

    def test_legacy_header(self):
        self.assertEqual(zs.csv_header([None]),
                         ["zone", "zone_name", "extra_ms", "age_path_ms",
                          "total_hard", "z0_hard", "z1_hard", "z2_hard",
                          "z3_hard"])


class PhaseTests(unittest.TestCase):
    """Two phases: phase 0 clean through +80, phase 19 clean only through +60."""

    PH = [("offset_ms", 0.0), ("offset_ms", 19.0)]

    def runner(self, zone, extra, phase):
        kind, val = phase
        age = 90.5 + extra
        limit = 80 if val == 0.0 else 60
        hard = [0, 0, 0, 0] if extra <= limit else [0, 0, 0, 5]
        soft = 2.7 if extra < 70 else 6.9          # soft budget fails at +70
        return result(age, hard, soft=soft, ey=0.5 if extra <= limit else 0.9)

    def test_min_over_phase(self):
        rows, table = zs.sweep([3], [50, 60, 70, 80, 90], self.PH, self.runner)
        (e,) = table
        self.assertEqual(e.a_zone, 150.5)            # min over phases
        self.assertEqual(e.first_breach[0], 160.5)   # first age any phase breaches
        self.assertEqual(e.first_breach[2], 19.0)    # ... and which phase did it
        self.assertEqual(e.non_monotone, [])
        # per-phase A: phase 0 -> 170.5, phase 19 -> 150.5  => spread
        self.assertEqual(e.per_phase_a, [170.5, 150.5])
        self.assertEqual(e.spread, (150.5, 170.5))
        # clean-phase counts per grid point
        self.assertEqual(e.clean_counts, {50: 2, 60: 2, 70: 1, 80: 1, 90: 0})
        self.assertEqual(e.n_phases, 2)

    def test_soft_secondary(self):
        _, table = zs.sweep([3], [50, 60, 70, 80], self.PH, self.runner)
        (e,) = table
        # hard-clean-at-all-phases through +60 (150.5); soft fails from +70 on
        # -> soft-criterion A coincides here; check it is tracked separately
        self.assertEqual(e.a_soft, 150.5)

    def test_soft_can_bind_before_hard(self):
        def runner(zone, extra, phase):
            soft = 2.7 if extra < 60 else 5.5
            return result(90.5 + extra, [0, 0, 0, 0], soft=soft)
        _, table = zs.sweep([3], [50, 60, 70], self.PH, runner)
        (e,) = table
        self.assertEqual(e.a_zone, 160.5)      # never a hard breach
        self.assertEqual(e.a_soft, 140.5)      # >95%-within budget binds at +60

    def test_non_monotone_island_is_not_a_zone(self):
        # clean at +50, ALL phases breach at +60, clean again at +70 (island):
        # A(zone) must stop at the cliff and the island must be flagged.
        def runner(zone, extra, phase):
            hard = [0, 0, 0, 4] if extra == 60 else [0, 0, 0, 0]
            return result(90.5 + extra, hard)
        _, table = zs.sweep([3], [50, 60, 70], self.PH, runner)
        (e,) = table
        self.assertEqual(e.a_zone, 140.5)
        self.assertEqual(e.first_breach[0], 150.5)
        self.assertEqual(e.non_monotone, [70])
        self.assertEqual(e.per_phase_a, [140.5, 140.5])   # island not credited

    def test_never_clean_phase(self):
        def runner(zone, extra, phase):
            hard = [0, 0, 0, 1] if phase[1] == 19.0 else [0, 0, 0, 0]
            return result(90.5 + extra, hard)
        _, table = zs.sweep([3], [50, 60], self.PH, runner)
        (e,) = table
        self.assertIsNone(e.a_zone)
        self.assertEqual(e.first_breach[0], 140.5)
        self.assertEqual(e.first_breach[2], 19.0)
        self.assertEqual(e.per_phase_a, [150.5, None])  # phase 19's A is below the grid
        self.assertIsNone(e.spread)                     # so the spread is undefined

    def test_extended_row_matches_header_with_extra_cols(self):
        rows, _ = zs.sweep([3], [50], self.PH, self.runner)
        header = zs.csv_header(self.PH, ("profile", "duration_s", "git_sha", "ff_extra_ms"))
        for r in rows:
            self.assertEqual(len(r + ["10", 120, "abc-dirty", 0.0]), len(header))
        self.assertEqual(header[-4:], ["profile", "duration_s", "git_sha", "ff_extra_ms"])

    def test_rows_schema_and_order(self):
        rows, _ = zs.sweep([3], [50, 60], self.PH, self.runner)
        header = zs.csv_header(self.PH)
        self.assertEqual(header[:6], ["zone", "zone_name", "extra_ms",
                                      "phase_kind", "phase", "age_path_ms"])
        self.assertIn("soft_pct", header)
        self.assertIn("fleet_max_ey_m", header)
        self.assertIn("z3_max_ey_m", header)
        self.assertIn("f_stale_max_ms", header)      # delivered F dose per row
        self.assertEqual(len(rows), 4)
        for r in rows:
            self.assertEqual(len(r), len(header))
        # deterministic order: zone, extra, phase index
        self.assertEqual([(r[2], r[4]) for r in rows],
                         [(50, 0.0), (50, 19.0), (60, 0.0), (60, 19.0)])

    def test_parallel_matches_serial(self):
        serial = zs.sweep([0, 3], [50, 60, 70], self.PH, self.runner, jobs=1)
        par = zs.sweep([0, 3], [50, 60, 70], self.PH, self.runner, jobs=4)
        self.assertEqual(serial[0], par[0])
        self.assertEqual([e.__dict__ for e in serial[1]],
                         [e.__dict__ for e in par[1]])

    def test_cell_age_is_min_over_phases(self):
        # phases deliver different ages in the same cell (z1): certify the min
        def runner(zone, extra, phase):
            age = 90.5 + extra + (10.0 if phase[1] == 0.0 else 0.0)
            return result(age, [0, 0, 0, 0] if extra <= 60 else [0, 0, 0, 2])
        _, table = zs.sweep([1], [50, 60, 70], self.PH, runner)
        (e,) = table
        self.assertEqual(e.a_zone, 150.5)             # not 160.5 (phase 0's age)
        self.assertEqual(e.first_breach[0], 160.5)

    def test_seed_phase_rows(self):
        ph = [("seed", 1), ("seed", 2)]
        rows, table = zs.sweep([3], [50], ph, lambda z, x, p: result(140.5, [0] * 4))
        self.assertEqual([r[3:5] for r in rows], [["seed", 1], ["seed", 2]])
        self.assertEqual(table[0].a_zone, 140.5)


class ParseOutputTests(unittest.TestCase):
    SAMPLE = """  veh      avg_perf     max_roll      soft%       hard age_fresh(ms)  age_path(ms)  min_pnr(ms)  pnr0(ms)
  0         0.58612     15.37017      6.73%          0        170.50        170.50          0.0     325.0
  worst-case data age: 170.50 ms (freshest) / 170.50 ms (path)
  zone breaches (frame-decimated): hard z0=0 z1=0 z2=7 z3=4 | soft z0=393 z1=0 z2=0 z3=415
  zone frames: z0=5364 z1=1716 z2=3866 z3=1054
  max |e_y| (per-tick): fleet 0.7983 m (margin 0.0017 m to 0.8) | zones 0.6816 0.0937 0.1069 0.7983
  F staleness (act-stamped, ms): zone max 35.8 35.8 35.8 35.8 | in-zone ticks >500ms: 0 0 0 0
"""

    def test_parse(self):
        r = zs.parse_output(self.SAMPLE)
        self.assertEqual(r["age_path"], 170.5)
        self.assertEqual(r["hard"], [0, 0, 7, 4])
        self.assertEqual(r["soft_pct"], 6.73)
        self.assertEqual(r["fleet_ey"], 0.7983)
        self.assertEqual(r["zone_ey"], [0.6816, 0.0937, 0.1069, 0.7983])
        self.assertEqual(r["f_stale_max"], 35.8)
        self.assertEqual(r["zone_frames"], [5364, 1716, 3866, 1054])

    def test_parse_without_f_staleness_line(self):
        # cart-pole runs print no F-staleness line; the field is then None
        r = zs.parse_output(self.SAMPLE.rsplit("\n  F staleness", 1)[0] + "\n")
        self.assertIsNone(r["f_stale_max"])

    def test_parse_failure_is_none(self):
        self.assertIsNone(zs.parse_output("garbage"))


if __name__ == "__main__":
    unittest.main()
