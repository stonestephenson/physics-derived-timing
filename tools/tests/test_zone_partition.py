#!/usr/bin/env python3
"""Tests for tools/zone_partition.py (partition invariance across profiles,
PAPER_NOTES 2026-09-04 (d)). Pure arithmetic on synthetic runs; the probe
binary is not needed."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import zone_partition as zp  # noqa: E402


class ArcLengthTests(unittest.TestCase):
    def test_cumulative_arc_length(self):
        s = zp.arc_length([0, 3, 3, 0], [0, 0, 4, 4])
        self.assertEqual(s, [0.0, 3.0, 7.0, 10.0])

    def test_runs_to_metres(self):
        s = [float(i) for i in range(11)]           # 1 m per tick, lap 10 ticks
        runs = [(0, 0, 4), (2, 4, 6)]               # (zone, start_tick, len_ticks)
        out = zp.runs_to_metres(runs, s, lap_ticks=10)
        self.assertEqual(out, [(0, 0.0, 4.0), (2, 4.0, 6.0)])

    def test_wrap_run_length(self):
        s = [float(i) for i in range(11)]
        out = zp.runs_to_metres([(1, 8, 4)], s, lap_ticks=10)   # 8..11 wraps: 8,9 + 0,1
        self.assertEqual(out, [(1, 8.0, 4.0)])


class CompareTests(unittest.TestCase):
    def test_boundary_match(self):
        ref = [(0, 0.0, 100.0), (2, 100.0, 50.0), (0, 150.0, 850.0)]
        other = [(0, 0.0, 100.4), (2, 100.4, 49.5), (0, 149.9, 850.1)]
        report = zp.compare(other, ref)
        self.assertAlmostEqual(report["max_boundary_dev_m"], 0.4)
        self.assertEqual(report["n_boundaries"], 3)
        self.assertEqual(report["unmatched"], [])

    def test_missing_zone_entry_is_reported(self):
        ref = [(0, 0.0, 100.0), (3, 100.0, 50.0), (0, 150.0, 850.0)]
        other = [(0, 0.0, 1000.0)]
        report = zp.compare(other, ref)
        # both ref boundaries without a partner within 25 m are reported
        self.assertEqual(report["unmatched"], [(3, 100.0), (0, 150.0)])

    def test_slivers_are_set_aside(self):
        # a 20 cm zero-crossing sliver must not count as a boundary deviation
        ref = [(1, 0.0, 300.0), (0, 300.0, 0.2), (1, 300.2, 699.8)]
        other = [(1, 0.0, 1000.0)]
        report = zp.compare(other, ref)
        self.assertEqual(report["unmatched"], [])
        self.assertEqual(report["slivers"], [(0, 300.0, 0.2)])
        self.assertEqual(report["n_boundaries"], 1)

    def test_zone_totals(self):
        runs = [(0, 0.0, 100.0), (2, 100.0, 50.0), (0, 150.0, 850.0)]
        self.assertEqual(zp.zone_totals(runs), {0: 950.0, 1: 0.0, 2: 50.0, 3: 0.0})


if __name__ == "__main__":
    unittest.main()
