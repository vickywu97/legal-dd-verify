#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Independent deliverable-consistency verifier (thin entry point).

The real checks live in pipeline/verify.py so there is a single source of
truth. This module just points at the bundled demo output / data room and
delegates, so the evaluation/ directory can be used as a standalone gate
without duplicating the verification logic.

Usage:
  python3 verify.py [--out DIR] [--input DATAROOM_DIR]
"""
import os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SUB = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_SUB, "pipeline"))

from verify import main as _verify_main  # canonical verifier


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Independent DD deliverable verifier")
    ap.add_argument("--out", default=os.path.join(_SUB, "examples"))
    ap.add_argument("--input", default=os.path.join(_SUB, "materials"))
    args = ap.parse_args()
    sys.exit(_verify_main(args.out, args.input))
