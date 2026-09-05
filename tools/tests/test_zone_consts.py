#!/usr/bin/env python3
"""End-to-end test of the `--zone-consts` harness flag (zone-partition
sensitivity, PAPER_NOTES 2026-09-04 (d)). Runs the real binary for a few
seconds of sim: the defaults must reproduce the baseline partition
byte-for-byte, and a perturbed sharp-turn threshold must move frames between
z1 and z2 while leaving z3 alone. Skipped if the binary is missing."""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BIN = ROOT / "build" / "cps"
FRAMES = re.compile(r"zone frames: z0=(\d+) z1=(\d+) z2=(\d+) z3=(\d+)")
DEFAULTS = "0.0215,0.0035,0.0040,50,100,350"   # sharp, ff1, delta, window_ms, pad_ms, bridge_ms


def run(*extra):
    cmd = [str(BIN), "--headless", "--vehicles", "1", "--scheduler", "rm", "--exec",
           "worst", "--duration", "30", "--profile", "12.5", *extra]
    return subprocess.run(cmd, capture_output=True, text=True).stdout


def frames(out):
    m = FRAMES.search(out)
    return tuple(int(m.group(i)) for i in range(1, 5)) if m else None


@unittest.skipUnless(BIN.exists(), "build/cps not built")
class ZoneConstsTests(unittest.TestCase):
    def test_defaults_are_byte_identical(self):
        base = run()
        explicit = run("--zone-consts", DEFAULTS)
        self.assertEqual(frames(base), frames(explicit))
        self.assertIsNotNone(frames(base))
        # the whole summary is identical apart from wall-clock lines (the
        # "simulated ... wall" line, the predictor us/prediction cost, the
        # rollout "ms wall" line)
        def tail(out):
            return [l for l in out.split("simulated", 1)[1].splitlines()[1:]
                    if "us/prediction" not in l and " wall" not in l]
        self.assertEqual(tail(base), tail(explicit))
        self.assertGreater(len(tail(base)), 5)

    def test_sharp_threshold_moves_z1_z2_boundary(self):
        base = frames(run())
        lower = frames(run("--zone-consts", "0.0172,0.0035,0.0040,50,100,350"))   # x0.8
        self.assertIsNotNone(lower)
        self.assertGreater(lower[2], base[2])        # more sharp-turn frames
        self.assertLess(lower[1], base[1])           # fewer slight-turn frames
        self.assertEqual(lower[3], base[3])          # lane-change untouched

    def test_time_constants_grow_z3(self):
        base = frames(run())
        wide = frames(run("--zone-consts", "0.0215,0.0035,0.0040,75,150,525"))    # x1.5
        self.assertGreater(wide[3], base[3])

    def test_bad_value_rejected(self):
        p = subprocess.run([str(BIN), "--headless", "--vehicles", "1", "--duration", "1",
                            "--zone-consts", "0.02,0.0035"], capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("--zone-consts", p.stderr + p.stdout)


if __name__ == "__main__":
    unittest.main()
