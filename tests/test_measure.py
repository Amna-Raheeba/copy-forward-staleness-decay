from copy_forward.measure import (
    accuracy_by_origin,
    accuracy_by_span_age,
    half_life_by_type,
    half_life_from_curve,
    harm_profile,
    label_mentions,
    prevalence_by_day,
    survival_curve,
)
from copy_forward.models import Admission, DayNote, Finding, Mention


def mention(fid, ftype, day, birth, gen, origin):
    return Mention(
        finding_id=fid,
        finding_type=ftype,
        day=day,
        text="span-%s" % fid,
        variant=0,
        span_birth_day=birth,
        first_day=1,
        generation=gen,
        written_today=(origin in ("new", "recheck", "edit")),
        origin=origin,
    )


def handcrafted():
    """f1 resolves day 3 but is copied through day 4; f2 never resolves."""
    f1 = Finding("f1", "fever", onset_day=1, resolution_day=3)
    f2 = Finding("f2", "anemia", onset_day=1, resolution_day=None)
    notes = []
    for day in (1, 2, 3, 4):
        origin = "new" if day == 1 else "copy"
        notes.append(
            DayNote(
                day=day,
                mentions=[
                    mention("f1", "fever", day, 1, day - 1, origin),
                    mention("f2", "anemia", day, 1, day - 1, origin),
                ],
            )
        )
    return Admission(
        admission_id=0,
        n_days=4,
        policy="standard",
        findings=[f1, f2],
        notes=notes,
        resolution_assertions=[(3, "f1")],
    )


def test_label_mentions_marks_stale_from_resolution_day():
    labels = label_mentions(handcrafted())
    stale_days = sorted(m.day for (m, stale) in labels if stale)
    assert stale_days == [3, 4]
    assert all(m.finding_id == "f1" for (m, stale) in labels if stale)


def test_prevalence_by_day():
    prevalence = prevalence_by_day([handcrafted()])
    assert prevalence[1] == 0.0
    assert prevalence[2] == 0.0
    assert prevalence[3] == 0.5
    assert prevalence[4] == 0.5


def test_survival_curve_full_persistence():
    curve = survival_curve([handcrafted()])
    assert curve[0] == 1.0
    assert curve[1] == 1.0


def test_survival_curve_type_filter():
    curve = survival_curve([handcrafted()], finding_type="anemia")
    assert curve == []


def test_half_life_interpolation():
    assert half_life_from_curve([1.0, 0.6, 0.4]) == 1.5


def test_half_life_never_crosses():
    assert half_life_from_curve([1.0, 0.9, 0.8]) is None


def test_half_life_empty_and_immediate():
    assert half_life_from_curve([]) is None
    assert half_life_from_curve([0.4]) == 0.0


def test_half_life_by_type_keys():
    result = half_life_by_type([handcrafted()])
    assert "fever" in result
    assert result["fever"]["curve"][0] == 1.0


def test_harm_profile_counts():
    harm = harm_profile([handcrafted()])
    assert harm["n_admissions"] == 1
    assert harm["total_mentions"] == 8
    assert harm["stale_mentions"] == 2
    assert harm["stale_share"] == 0.25
    assert harm["stale_mention_days_per_admission"] == 2.0
    assert harm["phantom_problems_final_day_per_admission"] == 1.0
    assert harm["mean_stale_age_days"] == 0.5


def test_harm_profile_empty():
    assert harm_profile([]) == {}


def test_accuracy_by_origin():
    accuracy = accuracy_by_origin([handcrafted()])
    assert accuracy["fresh"] == 1.0
    # copied: days 2-4 for both findings = 6 mentions, 2 stale.
    assert abs(accuracy["copied"] - (4.0 / 6.0)) < 1e-9


def test_accuracy_by_span_age_buckets():
    accuracy = accuracy_by_span_age([handcrafted()])
    assert accuracy[0] == 1.0
    assert accuracy[3] == 0.5
