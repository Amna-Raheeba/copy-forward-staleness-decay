"""Staleness measurement against the generated ground truth.

Every mention in every note can be labelled exactly, because the
finding's true resolution day is known: a mention is stale when it
asserts a finding on or after the day that finding stopped being
true. On top of those labels this module computes:

- stale prevalence by hospital day (what fraction of the problem
  list is false on each day);
- staleness survival and half-life per finding type (once a finding
  resolves, how long its copied span keeps asserting it -- the
  survival curve of the stale mention, and the day it crosses 50%);
- the harm profile: stale mention-days per admission, phantom
  problems on the discharge-day problem list, and mention accuracy
  split by fresh vs copied and by span age -- the decay curve of
  copied text vs freshly written text.
"""

from .models import mention_is_stale


def label_mentions(admission):
    """Return (mention, is_stale) pairs for one admission, in order."""
    return [(m, mention_is_stale(admission, m)) for m in admission.all_mentions()]


def prevalence_by_day(admissions):
    """Stale share of all mentions, per hospital day, pooled."""
    by_day = {}
    for admission in admissions:
        for note in admission.notes:
            total, stale = by_day.get(note.day, (0, 0))
            for mention in note.mentions:
                total += 1
                if mention_is_stale(admission, mention):
                    stale += 1
            by_day[note.day] = (total, stale)
    return dict(
        (day, (stale / total if total else 0.0))
        for day, (total, stale) in sorted(by_day.items())
    )


def _stale_present(admission, finding, day):
    if day > admission.n_days:
        return None
    note = admission.note_for_day(day)
    for mention in note.mentions:
        if mention.finding_id == finding.finding_id:
            return True
    return False


def survival_curve(admissions, finding_type=None):
    """Fraction of resolved findings still asserted k days later.

    The cohort is findings that are stale-asserted on their
    resolution day itself (k = 0). survival[k] is the fraction of
    that cohort still asserted on day resolution_day + k, counting
    only findings whose stay extends that far.
    """
    cohort = []
    for admission in admissions:
        for finding in admission.findings:
            if finding.resolution_day is None:
                continue
            if finding_type is not None and finding.finding_type != finding_type:
                continue
            if _stale_present(admission, finding, finding.resolution_day):
                cohort.append((admission, finding))
    if not cohort:
        return []
    max_k = max(a.n_days - f.resolution_day for (a, f) in cohort)
    curve = []
    for k in range(max_k + 1):
        eligible = 0
        present = 0
        for admission, finding in cohort:
            day = finding.resolution_day + k
            if day > admission.n_days:
                continue
            eligible += 1
            if _stale_present(admission, finding, day):
                present += 1
        if eligible:
            curve.append(present / eligible)
    return curve


def half_life_from_curve(curve):
    """First k where survival crosses 0.5, linearly interpolated.

    Returns None when the curve never crosses 0.5 within the stay.
    """
    if not curve:
        return None
    if curve[0] < 0.5:
        return 0.0
    for k in range(1, len(curve)):
        if curve[k] < 0.5:
            prev = curve[k - 1]
            frac = (prev - 0.5) / (prev - curve[k]) if prev > curve[k] else 0.0
            return (k - 1) + frac
    return None


def half_life_by_type(admissions):
    """Per-type staleness half-life in days (None = outlives the stay)."""
    from .models import TYPE_ORDER

    out = {}
    for finding_type in TYPE_ORDER:
        curve = survival_curve(admissions, finding_type)
        out[finding_type] = {
            "half_life_days": half_life_from_curve(curve),
            "curve": [round(v, 4) for v in curve],
        }
    return out


def harm_profile(admissions):
    """Aggregate harm measures over a set of admissions."""
    n = len(admissions)
    if n == 0:
        return {}
    stale_mention_days = 0
    total_mentions = 0
    stale_mentions = 0
    phantom_final = 0
    stale_age_sum = 0
    for admission in admissions:
        for mention in admission.all_mentions():
            total_mentions += 1
            if mention_is_stale(admission, mention):
                stale_mentions += 1
                stale_mention_days += 1
                finding = admission.finding_by_id(mention.finding_id)
                stale_age_sum += mention.day - finding.resolution_day
        final_note = admission.note_for_day(admission.n_days)
        for mention in final_note.mentions:
            if mention_is_stale(admission, mention):
                phantom_final += 1
    return {
        "n_admissions": n,
        "total_mentions": total_mentions,
        "stale_mentions": stale_mentions,
        "stale_share": (stale_mentions / total_mentions) if total_mentions else 0.0,
        "stale_mention_days_per_admission": stale_mention_days / n,
        "phantom_problems_final_day_per_admission": phantom_final / n,
        "mean_stale_age_days": (stale_age_sum / stale_mentions) if stale_mentions else 0.0,
    }


def accuracy_by_span_age(admissions, max_age=6):
    """Mention accuracy (1 - stale rate) bucketed by span age.

    Age 0 = written today (fresh or edited); ages >= max_age are
    pooled into the last bucket. This is the decay curve of copied
    text: how fast a span stops being true the longer it survives.
    """
    buckets = {}
    for admission in admissions:
        for mention in admission.all_mentions():
            age = min(mention.span_age, max_age)
            total, stale = buckets.get(age, (0, 0))
            total += 1
            if mention_is_stale(admission, mention):
                stale += 1
            buckets[age] = (total, stale)
    return dict(
        (age, 1.0 - (stale / total if total else 0.0))
        for age, (total, stale) in sorted(buckets.items())
    )


def accuracy_by_origin(admissions):
    """Accuracy split by how the span got into today's note.

    "fresh" spans were written after contact with the patient (first
    written at onset, or rewritten after re-examination); "edited"
    spans were reworded in place without re-examination; "copied"
    spans were carried forward verbatim. The three accuracies are
    the decay curve of documentation by provenance.
    """
    stats = {"fresh": [0, 0], "edited": [0, 0], "copied": [0, 0]}
    for admission in admissions:
        for mention in admission.all_mentions():
            if mention.origin in ("new", "recheck"):
                key = "fresh"
            elif mention.origin == "edit":
                key = "edited"
            else:
                key = "copied"
            stats[key][0] += 1
            if mention_is_stale(admission, mention):
                stats[key][1] += 1
    return dict(
        (key, 1.0 - (stale / total if total else 0.0))
        for key, (total, stale) in stats.items()
    )


# Backwards-friendly alias: fresh vs copied are the headline pair.
def accuracy_fresh_vs_copied(admissions):
    return accuracy_by_origin(admissions)
