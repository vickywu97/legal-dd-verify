#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-end smoke test for legal-dd-verify.

Runs the full pipeline (extract -> analyze -> render -> verify) on every bundled
scenario and asserts the independent verifier returns PASS for each. Each
scenario is an ORIGINAL, fully synthetic data room; switching scenarios proves
the engine is data-driven (not hardcoded to one instance).

No network, no pip install, no third-party services.

Usage:
  python3 tests/smoke_test.py
"""
import os, sys, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "pipeline", "run.py")

# built-in key or relative path to a scenario directory
SCENARIOS = [
    "cloudlink",                       # repo-root bundled demo (backward compatible)
    os.path.join("scenarios", "hanwei_semi"),
]


def run_one(scenario):
    py = sys.executable or "python3"
    out = tempfile.mkdtemp(prefix="legal_dd_verify_smoke_")
    proc = subprocess.run(
        [py, RUN, "--scenario", scenario, "--out", out, "--verify"],
        capture_output=True, text=True,
    )
    sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    ok = proc.returncode == 0 and "RESULT: PASS" in proc.stdout
    if not ok:
        print(f"\nSMOKE TEST FAIL (scenario={scenario})")
        sys.exit(1)
    print(f"  [ok] scenario={scenario}")


def main():
    for scn in SCENARIOS:
        run_one(scn)
    print("\nSMOKE TEST PASS (all scenarios)")
    sys.exit(0)


if __name__ == "__main__":
    main()
