"""Run the audit on the stored demo admission and print its report.

Run: python examples/run_audit.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from copy_forward.models import admission_from_dict
from copy_forward.report import render_admission_report


def main():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "demo_admission.json")
    with open(os.path.normpath(path)) as handle:
        admission = admission_from_dict(json.load(handle))
    print(render_admission_report(admission))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
