from copy_forward.detect import (
    DETECTORS,
    detector_score,
    flag_combined,
    mention_features,
    score_all_detectors,
    score_detector,
)
from copy_forward.generate import generate_admissions
from copy_forward.models import Admission, DayNote, Finding, Mention


def mention(fid, day, text, birth, gen):
    return Mention(
        finding_id=fid,
        finding_type="fever",
        day=day,
        text=text,
        variant=0,
        span_birth_day=birth,
        first_day=1,
        generation=gen,
        written_today=(gen == 0),
        origin="new" if gen == 0 else "copy",
    )


def handcrafted():
    f1 = Finding("f1", "fever", onset_day=1, resolution_day=3)
    notes = [
        DayNote(day=1, mentions=[mention("f1", 1, "span", 1, 0)]),
        DayNote(day=2, mentions=[mention("f1", 2, "span", 1, 1)]),
        DayNote(day=3, mentions=[mention("f1", 3, "span", 1, 2)]),
    ]
    return Admission(
        admission_id=0,
        n_days=3,
        policy="standard",
        findings=[f1],
        notes=notes,
        resolution_assertions=[(3, "f1")],
    )


def test_features_span_age_and_verbatim():
    admission = handcrafted()
    day2 = admission.note_for_day(2).mentions[0]
    features = mention_features(admission, day2)
    assert features["span_age"] == 1
    assert features["copied_verbatim"] is True
    assert features["contradiction_cue"] is False


def test_features_first_day_not_verbatim():
    admission = handcrafted()
    day1 = admission.note_for_day(1).mentions[0]
    features = mention_features(admission, day1)
    assert features["copied_verbatim"] is False
    assert features["days_present"] == 1


def test_features_cue_after_assertion():
    admission = handcrafted()
    day3 = admission.note_for_day(3).mentions[0]
    features = mention_features(admission, day3)
    assert features["contradiction_cue"] is True
    assert features["days_present"] == 3


def test_detector_score_increases_with_age():
    base = {"copied_verbatim": False, "contradiction_cue": False, "days_present": 1}
    young = dict(base, span_age=0)
    old = dict(base, span_age=5)
    assert detector_score(old) > detector_score(young)


def test_detector_score_cue_dominates():
    plain = {
        "span_age": 0,
        "days_present": 1,
        "copied_verbatim": False,
        "contradiction_cue": False,
    }
    cued = dict(plain, contradiction_cue=True)
    assert flag_combined(cued)
    assert not flag_combined(plain)


def test_cue_only_detector_is_perfect_on_handcrafted():
    scores = score_detector(handcrafted_admissions(), DETECTORS["cue_only"])
    assert scores["precision"] == 1.0


def handcrafted_admissions():
    return [handcrafted()]


def test_score_detector_counts():
    scores = score_detector(handcrafted_admissions(), DETECTORS["similarity_only"])
    # Day 2 (live) and day 3 (stale) are both verbatim copies.
    assert scores["tp"] == 1
    assert scores["fp"] == 1
    assert scores["fn"] == 0


def test_score_all_detectors_keys():
    scores = score_all_detectors(handcrafted_admissions())
    assert set(scores.keys()) == set(DETECTORS.keys())
    for entry in scores.values():
        assert 0.0 <= entry["f1"] <= 1.0


def test_combined_beats_similarity_on_canonical_corpus():
    admissions = generate_admissions(60, 20261121, n_days=14, policy="standard")
    scores = score_all_detectors(admissions)
    assert (
        scores["provenance_x_contradiction"]["f1"]
        > scores["similarity_only"]["f1"]
    )


def test_similarity_baseline_high_recall_low_precision():
    admissions = generate_admissions(60, 20261121, n_days=14, policy="standard")
    scores = score_all_detectors(admissions)
    sim = scores["similarity_only"]
    assert sim["recall"] > 0.8
    assert sim["precision"] < 0.4
