"""Seeded longitudinal note generator.

For each admission the generator first draws a ground-truth course:
which findings occur, when they onset, and when they truly resolve.
It then simulates the note-writer day by day. The writer:

- writes every new-onset finding fresh on its onset day;
- carries yesterday's problem list forward span by span -- each span
  is copied verbatim with the policy's copy probability, edited
  (reworded, provenance age reset) with a small probability, or
  dropped;
- only partially observes resolutions: a resolution is noticed with
  the policy's observation probability on the day it happens (and
  with a smaller late-observation probability afterwards). Noticing
  writes a resolution assertion into the chart's course log, but the
  problem-list span is dropped only with DROP_ON_RESOLUTION -- the
  classic failure where the course says "resolved" and the problem
  list still carries the finding;
- re-examines and freshly rewrites a still-active finding whose span
  was dropped, with RECHECK probability per day.

Everything runs off one random.Random seeded per admission, so the
whole corpus is deterministic and reproducible offline.
"""

import random

from .models import (
    FINDING_TYPES,
    TYPE_ORDER,
    Admission,
    DayNote,
    Finding,
    Mention,
    span_text,
)

# Copy policies: how documentation behaviour varies between services.
# p_copy: base probability a span is copied forward verbatim.
# p_observe: probability a resolution is noticed the day it happens.
POLICIES = {
    "low_copy": {"p_copy": 0.50, "p_observe": 0.60},
    "standard": {"p_copy": 0.75, "p_observe": 0.50},
    "attentive": {"p_copy": 0.75, "p_observe": 0.90},
    "high_copy": {"p_copy": 0.92, "p_observe": 0.40},
}

POLICY_ORDER = ["low_copy", "standard", "attentive", "high_copy"]

EDIT_PROB = 0.08
DROP_ON_RESOLUTION = 0.65
DROP_AFTER_OBSERVED = 0.85
LATE_OBSERVE_FACTOR = 0.5
RECHECK_PROB = 0.30
MAX_FINDINGS = 6


def _sample_duration(rng, hazard):
    duration = 1
    while rng.random() > hazard:
        duration += 1
        if duration > 60:
            break
    return duration


def _draw_findings(rng, admission_id, n_days):
    findings = []
    chosen = []
    for finding_type in TYPE_ORDER:
        params = FINDING_TYPES[finding_type]
        if rng.random() < params["prevalence"]:
            chosen.append(finding_type)
    rng.shuffle(chosen)
    chosen = chosen[:MAX_FINDINGS]
    if not chosen:
        chosen = ["fever"]
    for finding_type in chosen:
        params = FINDING_TYPES[finding_type]
        if rng.random() < 0.5:
            onset = 1
        else:
            onset = rng.randint(2, min(5, n_days))
        duration = _sample_duration(rng, params["hazard"])
        resolution = onset + duration
        if resolution > n_days:
            resolution = None
        findings.append(
            Finding(
                finding_id="adm%d-%s" % (admission_id, finding_type),
                finding_type=finding_type,
                onset_day=onset,
                resolution_day=resolution,
            )
        )
    return findings


def _fresh_mention(finding, day, variant, origin):
    if finding.first_written_day is None:
        finding.first_written_day = day
    return Mention(
        finding_id=finding.finding_id,
        finding_type=finding.finding_type,
        day=day,
        text=span_text(finding.finding_type, variant),
        variant=variant,
        span_birth_day=day,
        first_day=finding.first_written_day,
        generation=0,
        written_today=True,
        origin=origin,
    )


def generate_admission(admission_id, seed, n_days=14, policy="standard"):
    """Generate one admission deterministically."""
    params = POLICIES[policy]
    policy_index = POLICY_ORDER.index(policy)
    rng = random.Random(seed * 100003 + admission_id * 9176 + policy_index * 131)
    findings = _draw_findings(rng, admission_id, n_days)
    by_id = dict((f.finding_id, f) for f in findings)
    admission = Admission(
        admission_id=admission_id,
        n_days=n_days,
        policy=policy,
        findings=findings,
    )

    variants = dict((f.finding_id, 0) for f in findings)
    yesterday = {}  # finding_id -> Mention in yesterday's note

    for day in range(1, n_days + 1):
        # 1. Resolution observation at the start of the day.
        for finding in findings:
            if finding.resolution_day is None:
                continue
            if finding.resolution_observed_day is not None:
                continue
            if day < finding.resolution_day:
                continue
            if day == finding.resolution_day:
                p_obs = params["p_observe"]
            else:
                p_obs = params["p_observe"] * LATE_OBSERVE_FACTOR
            if rng.random() < p_obs:
                finding.resolution_observed_day = day
                admission.resolution_assertions.append((day, finding.finding_id))

        todays = {}

        # 2. Carry yesterday's spans forward.
        for finding_id, prev in yesterday.items():
            finding = by_id[finding_id]
            observed = finding.resolution_observed_day
            if observed is not None and observed == day:
                if rng.random() < DROP_ON_RESOLUTION:
                    continue
            elif observed is not None and observed < day:
                if rng.random() < DROP_AFTER_OBSERVED:
                    continue
            p_copy = params["p_copy"] * FINDING_TYPES[finding.finding_type]["copy_mult"]
            p_copy = min(p_copy, 0.98)
            roll = rng.random()
            if roll < p_copy:
                todays[finding_id] = Mention(
                    finding_id=finding_id,
                    finding_type=prev.finding_type,
                    day=day,
                    text=prev.text,
                    variant=prev.variant,
                    span_birth_day=prev.span_birth_day,
                    first_day=prev.first_day,
                    generation=prev.generation + 1,
                    written_today=False,
                    origin="copy",
                )
            elif roll < p_copy + EDIT_PROB:
                variants[finding_id] += 1
                todays[finding_id] = Mention(
                    finding_id=finding_id,
                    finding_type=prev.finding_type,
                    day=day,
                    text=span_text(prev.finding_type, variants[finding_id]),
                    variant=variants[finding_id],
                    span_birth_day=day,
                    first_day=prev.first_day,
                    generation=0,
                    written_today=True,
                    origin="edit",
                )
            # else: dropped.

        # 3. Fresh writes: new onsets, and re-examination of active
        # findings whose span is missing.
        for finding in findings:
            if finding.finding_id in todays:
                continue
            if day == finding.onset_day:
                todays[finding.finding_id] = _fresh_mention(
                    finding, day, variants[finding.finding_id], "new"
                )
            elif (
                day > finding.onset_day
                and finding.is_active(day)
                and finding.finding_id not in yesterday
                and rng.random() < RECHECK_PROB
            ):
                variants[finding.finding_id] += 1
                todays[finding.finding_id] = _fresh_mention(
                    finding, day, variants[finding.finding_id], "recheck"
                )

        note = DayNote(day=day, mentions=[todays[fid] for fid in sorted(todays)])
        admission.notes.append(note)
        yesterday = todays

    return admission


def generate_admissions(n, seed, n_days=14, policy="standard"):
    return [generate_admission(i, seed, n_days=n_days, policy=policy) for i in range(n)]
