"""Notebook 1 (runnable .py): one admission, audited day by day.

Generates the canonical demo admission, prints the chart with
ground-truth labels and detector flags, and prints the detector
scores for the demo admission alone.

Run: python notebooks/01_demo_run.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from copy_forward.detect import score_all_detectors
from copy_forward.evaluate import DEFAULT_CONFIG
from copy_forward.generate import generate_admission
from copy_forward.report import render_admission_report


def main():
    admission = generate_admission(
        0, DEFAULT_CONFIG["seed"], n_days=DEFAULT_CONFIG["n_days"]
    )
    print(render_admission_report(admission))
    print("")
    scores = score_all_detectors([admission])
    for name in sorted(scores):
        s = scores[name]
        print(
            "%s: P %.3f / R %.3f / F1 %.3f"
            % (name, s["precision"], s["recall"], s["f1"])
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
