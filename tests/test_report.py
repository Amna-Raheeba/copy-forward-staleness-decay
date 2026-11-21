from copy_forward.generate import generate_admission
from copy_forward.report import render_admission_report


def test_report_contains_ground_truth_and_days():
    admission = generate_admission(0, 20261121)
    report = render_admission_report(admission)
    assert "Ground truth" in report
    assert "Day 1:" in report
    assert "Day 14:" in report
    for finding in admission.findings:
        assert finding.finding_type in report


def test_report_marks_stale_mentions():
    # Find an admission with at least one stale mention and check the tag.
    for idx in range(30):
        admission = generate_admission(idx, 20261121, policy="high_copy")
        report = render_admission_report(admission)
        if "STALE" in report:
            assert "detector" in report
            return
    raise AssertionError("no stale mention found in 30 high-copy admissions")


def test_report_lists_resolution_assertions():
    for idx in range(30):
        admission = generate_admission(idx, 20261121)
        if admission.resolution_assertions:
            report = render_admission_report(admission)
            assert "Course-log resolution assertions" in report
            return
    raise AssertionError("no resolution assertions found in 30 admissions")
