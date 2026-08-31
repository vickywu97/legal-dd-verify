#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-end smoke test for legal-dd-verify.

Runs the full pipeline (extract -> analyze -> render -> verify) on the bundled
original demo data room and asserts the independent verifier returns PASS.
No network, no pip install, no third-party services.

Usage:
  python3 tests/smoke_test.py
"""
import os, sys, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "pipeline", "run.py")
MAT = os.path.join(ROOT, "materials")
CHK = os.path.join(ROOT, "checklist", "checklist_52.json")


def main():
    py = sys.executable or "python3"
    out = tempfile.mkdtemp(prefix="legal_dd_verify_smoke_")
    proc = subprocess.run(
        [py, RUN, "--input", MAT, "--checklist", CHK, "--out", out, "--verify"],
        capture_output=True, text=True,
    )
    sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    ok = proc.returncode == 0 and "RESULT: PASS" in proc.stdout
    if not ok:
        print("\nSMOKE TEST FAIL")
        sys.exit(1)
    print("\nSMOKE TEST PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
