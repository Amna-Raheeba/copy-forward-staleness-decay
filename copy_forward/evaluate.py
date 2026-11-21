"""The headline experiment.

Seeded admissions are generated under four copy policies. On the
standard policy the audit measures stale prevalence by hospital
day, the staleness half-life overall and per finding type, and the
accuracy decay of copied vs freshly written spans. The detector
(provenance age x contradiction cue) is scored against the
text-similarity-only baseline and the age-only / cue-only
ablations. Harm is then compared across all four policies, so the
effect of copy propensity and of writer attentiveness is priced
separately: standard vs high_copy isolates copying, standard vs
attentive isolates observation.
"""

import csv
import json
import os

from .detect import score_all_detectors
from .generate import POLICY_ORDER, generate_admissions
from .measure import (
    accuracy_by_span_age,
    accuracy_fresh_vs_copied,
    half_life_by_type,
    half_life_from_curve,
    harm_profile,
    prevalence_by_day,
    survival_curve,
)

DEFAULT_CONFIG = {
    "seed": 20261121,
    "n_admissions": 60,
    "n_days": 14,
}

DRIFT_KEYS = [
    "standard.prevalence_day7",
    "standard.prevalence_day14",
    "standard.overall_half_life_days",
    "standard.detector_f1",
    "baseline.similarity_f1",
    "standard.fresh_accuracy",
    "standard.copied_accuracy",
    "harm.high_copy.stale_days_per_admission",
    "harm.low_copy.stale_days_per_admission",
]

DRIFT_TOLERANCE = 1e-6


def _round(value, digits=4):
    if isinstance(value, float):
        return round(value, digits)
    return value


def _round_map(mapping):
    return dict((k, _round(v)) for k, v in mapping.items())


def run_evaluation(config=None):
    config = dict(DEFAULT_CONFIG, **(config or {}))
    seed = config["seed"]
    n = config["n_admissions"]
    n_days = config["n_days"]

    standard = generate_admissions(n, seed, n_days=n_days, policy="standard")
    prevalence = prevalence_by_day(standard)
    overall_curve = survival_curve(standard)
    overall_half_life = half_life_from_curve(overall_curve)
    detectors = score_all_detectors(standard)
    fresh_copied = accuracy_fresh_vs_copied(standard)
    age_curve = accuracy_by_span_age(standard)

    harm = {}
    for policy in POLICY_ORDER:
        admissions = generate_admissions(n, seed, n_days=n_days, policy=policy)
        harm[policy] = harm_profile(admissions)

    results = {
        "config": config,
        "standard": {
            "prevalence_by_day": _round_map(
                dict((str(d), v) for d, v in prevalence.items())
            ),
            "prevalence_day7": _round(prevalence.get(7, 0.0)),
            "prevalence_day14": _round(prevalence.get(n_days, 0.0)),
            "overall_half_life_days": (
                _round(overall_half_life) if overall_half_life is not None else None
            ),
            "overall_survival_curve": [_round(v) for v in overall_curve],
            "half_life_by_type": half_life_by_type(standard),
            "detectors": dict(
                (name, _round_map(scores)) for name, scores in detectors.items()
            ),
            "detector_f1": _round(detectors["provenance_x_contradiction"]["f1"]),
            "accuracy_fresh_vs_copied": _round_map(fresh_copied),
            "fresh_accuracy": _round(fresh_copied["fresh"]),
            "copied_accuracy": _round(fresh_copied["copied"]),
            "accuracy_by_span_age": _round_map(
                dict((str(a), v) for a, v in age_curve.items())
            ),
            "harm": harm["standard"],
        },
        "baseline": {
            "similarity_f1": _round(detectors["similarity_only"]["f1"]),
            "similarity_precision": _round(detectors["similarity_only"]["precision"]),
            "similarity_recall": _round(detectors["similarity_only"]["recall"]),
        },
        "harm": dict(
            (
                policy,
                {
                    "stale_days_per_admission": _round(
                        harm[policy]["stale_mention_days_per_admission"]
                    ),
                    "stale_share": _round(harm[policy]["stale_share"]),
                    "phantom_final_day": _round(
                        harm[policy]["phantom_problems_final_day_per_admission"]
                    ),
                    "mean_stale_age_days": _round(harm[policy]["mean_stale_age_days"]),
                },
            )
            for policy in POLICY_ORDER
        ),
    }
    return results


def _flatten(results):
    return {
        "standard.prevalence_day7": results["standard"]["prevalence_day7"],
        "standard.prevalence_day14": results["standard"]["prevalence_day14"],
        "standard.overall_half_life_days": results["standard"][
            "overall_half_life_days"
        ],
        "standard.detector_f1": results["standard"]["detector_f1"],
        "baseline.similarity_f1": results["baseline"]["similarity_f1"],
        "standard.fresh_accuracy": results["standard"]["fresh_accuracy"],
        "standard.copied_accuracy": results["standard"]["copied_accuracy"],
        "harm.high_copy.stale_days_per_admission": results["harm"]["high_copy"][
            "stale_days_per_admission"
        ],
        "harm.low_copy.stale_days_per_admission": results["harm"]["low_copy"][
            "stale_days_per_admission"
        ],
    }


def check_drift(stored, fresh):
    """Compare stored vs fresh headline aggregates; returns (ok, problems)."""
    stored_flat = _flatten(stored)
    fresh_flat = _flatten(fresh)
    problems = []
    for key in DRIFT_KEYS:
        sv = stored_flat.get(key)
        fv = fresh_flat.get(key)
        if sv is None or fv is None:
            if sv != fv:
                problems.append((key, sv, fv, None))
            continue
        diff = abs(sv - fv)
        if diff > DRIFT_TOLERANCE:
            problems.append((key, sv, fv, diff))
    return (len(problems) == 0, problems)


def save_results(results, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "evaluation.json"), "w") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "evaluation.csv"), "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "value"])
        for key, value in sorted(_flatten(results).items()):
            writer.writerow([key, value])
        std = results["standard"]
        for name, scores in sorted(std["detectors"].items()):
            writer.writerow(["detector.%s.f1" % name, scores["f1"]])
            writer.writerow(["detector.%s.precision" % name, scores["precision"]])
            writer.writerow(["detector.%s.recall" % name, scores["recall"]])
    with open(os.path.join(out_dir, "evaluation_summary.md"), "w") as handle:
        handle.write(render_summary(results))
    with open(os.path.join(out_dir, "HEADLINE.md"), "w") as handle:
        handle.write(render_headline(results))


def render_summary(results):
    std = results["standard"]
    lines = []
    lines.append("# Evaluation summary")
    lines.append("")
    lines.append(
        "Seed %d, %d admissions x %d days per policy."
        % (
            results["config"]["seed"],
            results["config"]["n_admissions"],
            results["config"]["n_days"],
        )
    )
    lines.append("")
    lines.append("## Standard policy")
    lines.append("")
    lines.append(
        "- Stale prevalence: day 7 = %.3f, day %d = %.3f"
        % (
            std["prevalence_day7"],
            results["config"]["n_days"],
            std["prevalence_day14"],
        )
    )
    half = std["overall_half_life_days"]
    lines.append(
        "- Overall staleness half-life: %s days"
        % ("%.2f" % half if half is not None else "beyond stay")
    )
    lines.append(
        "- Mention accuracy: fresh %.3f vs copied %.3f"
        % (std["fresh_accuracy"], std["copied_accuracy"])
    )
    lines.append("")
    lines.append("## Detectors (standard policy)")
    lines.append("")
    for name in sorted(std["detectors"]):
        s = std["detectors"][name]
        lines.append(
            "- %s: P %.3f / R %.3f / F1 %.3f"
            % (name, s["precision"], s["recall"], s["f1"])
        )
    lines.append("")
    lines.append("## Harm by policy")
    lines.append("")
    for policy in POLICY_ORDER:
        h = results["harm"][policy]
        lines.append(
            "- %s: %.2f stale mention-days/admission, stale share %.3f, "
            "phantom problems on final day %.2f"
            % (
                policy,
                h["stale_days_per_admission"],
                h["stale_share"],
                h["phantom_final_day"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_headline(results):
    std = results["standard"]
    det = std["detectors"]["provenance_x_contradiction"]
    sim = std["detectors"]["similarity_only"]
    half = std["overall_half_life_days"]
    half_text = "%.1f" % half if half is not None else "more than the whole stay"
    lines = []
    lines.append("# Headline results")
    lines.append("")
    lines.append(
        "Copy-forward staleness measured on %d seeded synthetic admissions "
        "(%d hospital days each, seed %d; reproduce with "
        "`python scripts/reproduce_results.py`)."
        % (
            results["config"]["n_admissions"],
            results["config"]["n_days"],
            results["config"]["seed"],
        )
    )
    lines.append("")
    lines.append(
        "- Under the standard copy policy, **%.1f%%** of the problem list is "
        "stale -- asserting findings that have already resolved -- by day 7, "
        "and **%.1f%%** by day %d."
        % (
            100 * std["prevalence_day7"],
            100 * std["prevalence_day14"],
            results["config"]["n_days"],
        )
    )
    lines.append(
        "- Once a finding resolves, its copied span keeps asserting it with a "
        "staleness half-life of **%s days**: half of resolved findings are "
        "still being charted as active that long after they stopped being true."
        % half_text
    )
    lines.append(
        "- Freshly written spans are **%.1f%%** accurate; copied spans are "
        "**%.1f%%** accurate. The gap is the decay the copy button causes."
        % (100 * std["fresh_accuracy"], 100 * std["copied_accuracy"])
    )
    lines.append(
        "- The provenance x contradiction detector flags stale spans at "
        "precision **%.3f** / recall **%.3f** (F1 **%.3f**). The "
        "text-similarity-only baseline reaches F1 **%.3f** (precision %.3f) "
        "-- it flags every verbatim copy, live or stale, and cannot tell "
        "the difference."
        % (det["precision"], det["recall"], det["f1"], sim["f1"], sim["precision"])
    )
    lines.append(
        "- Copy policy is the lever: high-copy documentation produces **%.1f "
        "stale mention-days per admission** vs **%.1f** under low-copy, while "
        "an attentive writer at the same copy rate cuts it to **%.1f**."
        % (
            results["harm"]["high_copy"]["stale_days_per_admission"],
            results["harm"]["low_copy"]["stale_days_per_admission"],
            results["harm"]["attentive"]["stale_days_per_admission"],
        )
    )
    lines.append("")
    lines.append(
        "Caveat: all admissions are synthetic and seeded, generated from "
        "known resolution schedules; copy, edit and observation rates are "
        "declared parameters, not measurements of any real EHR. The audit "
        "measures what copy-forward costs under those declared conditions, "
        "and gives the detector benchmark a ground truth that observational "
        "copy-paste studies do not have."
    )
    lines.append("")
    return "\n".join(lines)
