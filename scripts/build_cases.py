"""Build the stored demo admission used by the dashboard and examples.

Generates one seeded admission under the standard policy and writes
it to data/demo_admission.json in the serialised form defined by
copy_forward.models.

Run: python scripts/build_cases.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from copy_forward.evaluate import DEFAULT_CONFIG
from copy_forward.generate import generate_admission
from copy_forward.models import admission_to_dict


def main():
    root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    admission = generate_admission(
        0, DEFAULT_CONFIG["seed"], n_days=DEFAULT_CONFIG["n_days"]
    )
    path = os.path.join(root, "data", "demo_admission.json")
    with open(path, "w") as handle:
        json.dump(admission_to_dict(admission), handle, indent=2, sort_keys=True)
    print("Wrote %s (%d mentions)" % (path, len(admission.all_mentions())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
