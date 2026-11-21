from copy_forward.generate import POLICIES, generate_admission, generate_admissions
from copy_forward.models import admission_to_dict, mention_is_stale

SEED = 20261121


def test_deterministic_same_seed():
    a = generate_admission(3, SEED, policy="standard")
    b = generate_admission(3, SEED, policy="standard")
    assert admission_to_dict(a) == admission_to_dict(b)


def test_different_seed_differs():
    a = generate_admission(3, SEED, policy="standard")
    b = generate_admission(3, SEED + 1, policy="standard")
    assert admission_to_dict(a) != admission_to_dict(b)


def test_all_policies_generate():
    for policy in POLICIES:
        admission = generate_admission(0, SEED, policy=policy)
        assert admission.policy == policy
        assert len(admission.notes) == 14


def test_batch_shape():
    admissions = generate_admissions(5, SEED)
    assert len(admissions) == 5
    assert [a.admission_id for a in admissions] == [0, 1, 2, 3, 4]


def test_finding_count_capped():
    for admission in generate_admissions(30, SEED):
        assert 1 <= len(admission.findings) <= 6


def test_onset_day_always_written_fresh():
    for admission in generate_admissions(30, SEED):
        for finding in admission.findings:
            note = admission.note_for_day(finding.onset_day)
            matches = [
                m for m in note.mentions if m.finding_id == finding.finding_id
            ]
            assert len(matches) == 1
            assert matches[0].origin == "new"
            assert matches[0].generation == 0


def test_no_mention_before_onset():
    for admission in generate_admissions(30, SEED):
        for finding in admission.findings:
            for note in admission.notes:
                if note.day < finding.onset_day:
                    assert all(
                        m.finding_id != finding.finding_id for m in note.mentions
                    )


def test_mentions_reference_known_findings():
    for admission in generate_admissions(10, SEED):
        ids = set(f.finding_id for f in admission.findings)
        for mention in admission.all_mentions():
            assert mention.finding_id in ids
            assert mention.text


def test_resolution_within_stay_or_none():
    for admission in generate_admissions(30, SEED):
        for finding in admission.findings:
            if finding.resolution_day is not None:
                assert finding.onset_day < finding.resolution_day <= admission.n_days


def test_assertions_only_after_resolution():
    for admission in generate_admissions(30, SEED):
        for day, fid in admission.resolution_assertions:
            finding = admission.finding_by_id(fid)
            assert finding.resolution_day is not None
            assert day >= finding.resolution_day


def test_first_written_day_set_for_written_findings():
    for admission in generate_admissions(10, SEED):
        for finding in admission.findings:
            assert finding.first_written_day == finding.onset_day


def test_high_copy_produces_stale_mentions():
    admissions = generate_admissions(30, SEED, policy="high_copy")
    stale = sum(
        1
        for a in admissions
        for m in a.all_mentions()
        if mention_is_stale(a, m)
    )
    assert stale > 0


def test_copied_mentions_keep_text_and_birth():
    for admission in generate_admissions(10, SEED):
        by_key = {}
        for mention in admission.all_mentions():
            by_key[(mention.finding_id, mention.day)] = mention
        for mention in admission.all_mentions():
            if mention.origin == "copy":
                prev = by_key[(mention.finding_id, mention.day - 1)]
                assert mention.text == prev.text
                assert mention.span_birth_day == prev.span_birth_day
                assert mention.generation == prev.generation + 1
