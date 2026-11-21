"""Command line interface: python -m copy_forward <command>.

Commands:
- demo: generate one seeded admission and print its audited chart.
- evaluate: run the full evaluation, print the headline, and write
  the result files into results/.
- audit: print detector scores for a seeded batch of admissions.
"""

import argparse
import os

from .detect import score_all_detectors
from .evaluate import DEFAULT_CONFIG, run_evaluation, save_results
from .generate import generate_admission, generate_admissions
from .report import render_admission_report


def _demo(_args):
    admission = generate_admission(
        0, DEFAULT_CONFIG["seed"], n_days=DEFAULT_CONFIG["n_days"]
    )
    print(render_admission_report(admission))
    return 0


def _evaluate(_args):
    results = run_evaluation()
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "results"
    )
    save_results(results, os.path.normpath(out_dir))
    std = results["standard"]
    print(
        "Evaluated %d admissions x %d days under 4 copy policies."
        % (results["config"]["n_admissions"], results["config"]["n_days"])
    )
    print(
        "Standard policy: stale prevalence day 7 = %.3f, detector F1 = %.3f, "
        "similarity baseline F1 = %.3f."
        % (
            std["prevalence_day7"],
            std["detector_f1"],
            results["baseline"]["similarity_f1"],
        )
    )
    return 0


def _audit(args):
    admissions = generate_admissions(
        args.n, DEFAULT_CONFIG["seed"], n_days=DEFAULT_CONFIG["n_days"]
    )
    scores = score_all_detectors(admissions)
    for name in sorted(scores):
        s = scores[name]
        print(
            "%s: P %.3f / R %.3f / F1 %.3f (tp %d, fp %d, fn %d)"
            % (name, s["precision"], s["recall"], s["f1"], s["tp"], s["fp"], s["fn"])
        )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="copy_forward")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    sub.add_parser("evaluate")
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args(argv)
    if args.command == "demo":
        return _demo(args)
    if args.command == "evaluate":
        return _evaluate(args)
    return _audit(args)


if __name__ == "__main__":
    raise SystemExit(main())
