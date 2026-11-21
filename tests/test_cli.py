from copy_forward.cli import main


def test_cli_demo(capsys):
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "Ground truth" in out
    assert "Day 14:" in out


def test_cli_audit(capsys):
    assert main(["audit", "--n", "5"]) == 0
    out = capsys.readouterr().out
    assert "provenance_x_contradiction" in out
    assert "similarity_only" in out


def test_cli_evaluate(capsys):
    assert main(["evaluate"]) == 0
    out = capsys.readouterr().out
    assert "detector F1" in out
