#!/usr/bin/env python3
"""Generate reproducible synthetic fault telemetry and train/evaluate the advisory model."""
from __future__ import annotations
import argparse
import pathlib
import sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from aibars_advanced.ml_classifier import save_model_and_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples-per-class", type=int, default=240)
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "artifacts")
    args = parser.parse_args()
    if args.samples_per_class < 20 or args.samples_per_class > 100000:
        parser.error("--samples-per-class must be between 20 and 100000")
    report = save_model_and_report(args.out, args.samples_per_class)
    print(f"Model: {report['algorithm']}")
    print(f"Train/test: {report['training_samples']}/{report['test_samples']}")
    print(f"Synthetic hold-out accuracy: {report['accuracy']:.3%}")
    print(f"Outputs: {args.out}")
    print("This metric applies to generated synthetic signatures only, not real equipment.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
