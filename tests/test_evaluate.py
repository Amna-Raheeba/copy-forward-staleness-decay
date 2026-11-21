import json
import os

from copy_forward.evaluate import (
    DRIFT_KEYS,
    check_drift,
    render_headline,
    render_summary,
    run_evaluation,
    save_results,
)


def small_results():
    return run_evaluation({"n_admissions": 8})


def test_run_evaluation_structure():
    results = small_results()
    assert "standard" in results
    assert "baseline" in results
    assert "harm" in results
    std = results["standard"]
    assert 0.0 <= std["prevalence_day7"] <= 1.0
    assert 0.0 <= std["detector_f1"] <= 1.0
    assert std["accuracy_fresh_vs_copied"]["fresh"] == 1.0


def test_harm_orders_policies():
    results = run_evaluation({"n_admissions": 30})
    harm = results["harm"]
    assert (
        harm["high_copy"]["stale_days_per_admission"]
        > harm["low_copy"]["stale_days_per_admission"]
    )
    assert (
        harm["attentive"]["stale_days_per_admission"]
        < harm["standard"]["stale_days_per_admission"]
    )


def test_check_drift_identical_passes():
    results = small_results()
    ok, problems = check_drift(results, results)
    assert ok
    assert problems == []


def test_check_drift_detects_tampering():
    results = small_results()
    tampered = json.loads(json.dumps(results))
    tampered["standard"]["detector_f1"] = results["standard"]["detector_f1"] + 0.5
    ok, problems = check_drift(results, tampered)
    assert not ok
    assert any(key == "standard.detector_f1" for key, _, _, _ in problems)


def test_drift_keys_cover_headline():
    assert "standard.detector_f1" in DRIFT_KEYS
    assert "baseline.similarity_f1" in DRIFT_KEYS
    assert len(DRIFT_KEYS) >= 8


def test_save_results_writes_four_files(tmp_path):
    results = small_results()
    save_results(results, str(tmp_path))
    for name in (
        "evaluation.json",
        "evaluation.csv",
        "evaluation_summary.md",
        "HEADLINE.md",
    ):
        assert os.path.exists(os.path.join(str(tmp_path), name))
    with open(os.path.join(str(tmp_path), "evaluation.json")) as handle:
        loaded = json.load(handle)
    assert loaded["standard"]["detector_f1"] == results["standard"]["detector_f1"]


def test_renderers_produce_text():
    results = small_results()
    summary = render_summary(results)
    headline = render_headline(results)
    assert "standard" in summary.lower()
    assert "half-life" in headline
    assert "Caveat" in headline
