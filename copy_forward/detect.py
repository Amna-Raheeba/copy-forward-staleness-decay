"""Staleness detection from chart-visible evidence only.

The detector never sees ground truth. For each mention it computes
features a chart reviewer (or an EHR audit tool) could compute from
the notes themselves:

- span_age: days since this exact span text was (re)written --
  copy provenance;
- days_present: consecutive days the finding has been on the
  problem list up to and including today;
- copied_verbatim: the span is character-identical to yesterday's
  span for the same finding;
- contradiction_cue: the chart's course log already asserts this
  finding resolved on or before today, while the problem list
  still carries it as active.

The proposed detector combines provenance age with the
contradiction cue. The baseline from the copy-paste literature is
text similarity alone: flag any span copied verbatim. That baseline
cannot tell live copied text from stale copied text -- most copied
spans are still true -- and the experiment prices exactly that
blindness. Age-only and cue-only ablations isolate each signal.
"""

from .models import mention_is_stale

AGE_WEIGHT = 0.35
AGE_CAP = 6
CUE_WEIGHT = 2.2
PRESENCE_WEIGHT = 0.10
PRESENCE_CAP = 10
THRESHOLD = 1.6
AGE_ONLY_THRESHOLD = 3


def mention_features(admission, mention):
    """Chart-visible features for one mention."""
    days_present = 0
    day = mention.day
    while day >= 1:
        note = admission.note_for_day(day)
        if any(m.finding_id == mention.finding_id for m in note.mentions):
            days_present += 1
            day -= 1
        else:
            break
    copied_verbatim = False
    if mention.day > 1:
        prev_note = admission.note_for_day(mention.day - 1)
        for prev in prev_note.mentions:
            if prev.finding_id == mention.finding_id and prev.text == mention.text:
                copied_verbatim = True
    cue = any(d <= mention.day for d in admission.assertion_days(mention.finding_id))
    return {
        "span_age": mention.span_age,
        "days_present": days_present,
        "copied_verbatim": copied_verbatim,
        "contradiction_cue": cue,
    }


def detector_score(features):
    return (
        AGE_WEIGHT * min(features["span_age"], AGE_CAP)
        + (CUE_WEIGHT if features["contradiction_cue"] else 0.0)
        + PRESENCE_WEIGHT * min(features["days_present"], PRESENCE_CAP)
    )


def flag_combined(features):
    return detector_score(features) >= THRESHOLD


def flag_similarity(features):
    """Baseline: text similarity only -- flag verbatim copies."""
    return features["copied_verbatim"]


def flag_age_only(features):
    return features["span_age"] >= AGE_ONLY_THRESHOLD


def flag_cue_only(features):
    return features["contradiction_cue"]


DETECTORS = {
    "provenance_x_contradiction": flag_combined,
    "similarity_only": flag_similarity,
    "age_only": flag_age_only,
    "cue_only": flag_cue_only,
}


def score_detector(admissions, flag_fn):
    """Precision / recall / F1 of a flag function against truth."""
    tp = fp = fn = tn = 0
    for admission in admissions:
        for mention in admission.all_mentions():
            features = mention_features(admission, mention)
            flagged = flag_fn(features)
            stale = mention_is_stale(admission, mention)
            if flagged and stale:
                tp += 1
            elif flagged and not stale:
                fp += 1
            elif not flagged and stale:
                fn += 1
            else:
                tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def score_all_detectors(admissions):
    return dict(
        (name, score_detector(admissions, fn)) for name, fn in DETECTORS.items()
    )
