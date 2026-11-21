from copy_forward.models import (
    FINDING_TYPES,
    Admission,
    DayNote,
    Finding,
    Mention,
    admission_from_dict,
    admission_to_dict,
    mention_is_stale,
    span_text,
)


def make_finding(**kw):
    base = {"finding_id": "f1", "finding_type": "fever", "onset_day": 1}
    base.update(kw)
    return Finding(**base)


def make_mention(**kw):
    base = {
        "finding_id": "f1",
        "finding_type": "fever",
        "day": 3,
        "text": "x",
        "variant": 0,
        "span_birth_day": 1,
        "first_day": 1,
        "generation": 2,
        "written_today": False,
        "origin": "copy",
    }
    base.update(kw)
    return Mention(**base)


def test_span_text_deterministic_and_wraps():
    assert span_text("fever", 0) == FINDING_TYPES["fever"]["spans"][0]
    n = len(FINDING_TYPES["fever"]["spans"])
    assert span_text("fever", n) == span_text("fever", 0)


def test_all_types_have_spans_and_params():
    for finding_type, params in FINDING_TYPES.items():
        assert params["spans"]
        assert 0.0 < params["hazard"] < 1.0
        assert 0.0 < params["prevalence"] < 1.0


def test_finding_active_window():
    finding = make_finding(onset_day=2, resolution_day=5)
    assert not finding.is_active(1)
    assert finding.is_active(2)
    assert finding.is_active(4)
    assert not finding.is_active(5)


def test_finding_never_resolves_stays_active():
    finding = make_finding(onset_day=1, resolution_day=None)
    assert finding.is_active(14)
    assert not finding.is_stale_on(14)


def test_finding_stale_boundary():
    finding = make_finding(onset_day=1, resolution_day=3)
    assert not finding.is_stale_on(2)
    assert finding.is_stale_on(3)
    assert finding.is_stale_on(9)


def test_mention_span_age_and_copied():
    mention = make_mention(day=5, span_birth_day=2, generation=0)
    assert mention.span_age == 3
    assert not mention.copied
    assert make_mention(generation=1).copied


def test_mention_is_stale_uses_ground_truth():
    finding = make_finding(resolution_day=3)
    admission = Admission(
        admission_id=0, n_days=5, policy="standard", findings=[finding]
    )
    assert not mention_is_stale(admission, make_mention(day=2))
    assert mention_is_stale(admission, make_mention(day=3))


def test_admission_helpers():
    finding = make_finding()
    note = DayNote(day=1, mentions=[make_mention(day=1)])
    admission = Admission(
        admission_id=0,
        n_days=1,
        policy="standard",
        findings=[finding],
        notes=[note],
        resolution_assertions=[(2, "f1"), (1, "f1"), (3, "other")],
    )
    assert admission.finding_by_id("f1") is finding
    assert admission.note_for_day(1) is note
    assert len(admission.all_mentions()) == 1
    assert admission.assertion_days("f1") == [1, 2]


def test_serialisation_round_trip():
    finding = make_finding(resolution_day=4, resolution_observed_day=4)
    mention = make_mention(day=2, origin="edit", written_today=True)
    admission = Admission(
        admission_id=7,
        n_days=2,
        policy="high_copy",
        findings=[finding],
        notes=[DayNote(day=2, mentions=[mention])],
        resolution_assertions=[(4, "f1")],
    )
    restored = admission_from_dict(admission_to_dict(admission))
    assert admission_to_dict(restored) == admission_to_dict(admission)
    assert restored.findings[0].resolution_day == 4
    assert restored.notes[0].mentions[0].origin == "edit"
