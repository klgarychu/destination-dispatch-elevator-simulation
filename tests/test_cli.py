"""TST-17: each command end to end, through the same entry point a user runs."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from elevator_sim.cli import main

ROOT = Path(__file__).parent.parent
SAMPLE = str(ROOT / "examples" / "pdf_sample.csv")
SAMPLE_CONFIG = str(ROOT / "configs" / "pdf_sample.toml")


def test_tst17_run_writes_the_pdf_sample_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["run", "--requests", SAMPLE, "--config", SAMPLE_CONFIG, "--out", str(tmp_path)])

    assert code == 0
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_time"]["mean"] == 58.67
    assert (tmp_path / "positions.csv").exists()
    assert (tmp_path / "passengers.csv").exists()
    assert "58.67" in capsys.readouterr().out


def test_tst17_run_defaults_to_the_agreed_building_and_target_algorithm(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text("time,id,source,dest\n0,a,1,9\n", encoding="utf-8")

    code = main(["run", "--requests", str(file), "--out", str(tmp_path / "out")])

    assert code == 0
    summary = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))
    assert summary["building"]["floors"] == 10
    assert summary["building"]["elevators"] == 3
    assert summary["building"]["capacity"] == 6
    assert summary["config"]["algorithm"] == "marginal_insertion"
    assert summary["config"]["behaviour"] == "min_time"


def test_tst17_flags_override_the_config_file(tmp_path: Path) -> None:
    code = main(
        [
            "run",
            "--requests",
            SAMPLE,
            "--config",
            SAMPLE_CONFIG,
            "--out",
            str(tmp_path),
            "--elevators",
            "2",
            "--capacity",
            "4",
            "--algorithm",
            "round_robin",
        ]
    )

    assert code == 0
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["building"]["elevators"] == 2
    assert summary["building"]["capacity"] == 4
    assert summary["config"]["algorithm"] == "round_robin"


def test_tst17_invalid_input_exits_2_and_lists_the_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = tmp_path / "bad.csv"
    file.write_text("time,id,source,dest\nx,a,1,2\n0,b,1,99\n", encoding="utf-8")

    code = main(["run", "--requests", str(file), "--out", str(tmp_path / "out")])

    assert code == 2
    err = capsys.readouterr().err
    assert "row 2" in err
    assert "row 3" in err
    assert "Traceback" not in err


def test_c10_pdf_sample_with_defaults_gives_a_validation_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", "--requests", SAMPLE, "--out", str(tmp_path)]) == 2
    assert "outside floors" in capsys.readouterr().err


def test_tst17_invalid_settings_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["run", "--requests", SAMPLE, "--out", str(tmp_path), "--floors", "1"])

    assert code == 2
    assert "floors" in capsys.readouterr().err


def test_tst17_a_missing_requests_file_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["run", "--requests", str(tmp_path / "absent.csv"), "--out", str(tmp_path)])

    assert code == 2
    assert "absent.csv" in capsys.readouterr().err


def test_tst17_reaching_max_ticks_exits_3(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "run",
            "--requests",
            SAMPLE,
            "--config",
            SAMPLE_CONFIG,
            "--out",
            str(tmp_path),
            "--max-ticks",
            "5",
        ]
    )

    assert code == 3
    assert "stalled" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--guard", "--weight"])
def test_m12_flags_from_later_phases_exit_2(tmp_path: Path, flag: str) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["run", "--requests", SAMPLE, "--out", str(tmp_path), flag, "1"])

    assert caught.value.code == 2


def test_m12_a_behaviour_from_a_later_phase_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "run",
            "--requests",
            SAMPLE,
            "--config",
            SAMPLE_CONFIG,
            "--out",
            str(tmp_path),
            "--behaviour",
            "strict",
        ]
    )

    assert code == 2
    assert "Phase 3" in capsys.readouterr().err


def test_tst17_generate_writes_one_custom_file(tmp_path: Path) -> None:
    out = tmp_path / "one.csv"

    code = main(
        [
            "generate",
            "--pattern",
            "up_peak",
            "--rate",
            "0.5",
            "--ticks",
            "100",
            "--seed",
            "1",
            "--config",
            str(ROOT / "configs" / "baseline.toml"),
            "--out",
            str(out),
        ]
    )

    assert code == 0
    with out.open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    assert rows[0] == ["time", "id", "source", "dest"]
    assert len(rows) > 10


def test_tst17_generate_needs_a_pattern_and_rate(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["generate", "--out", "unused.csv"]) == 2
    assert "pattern" in capsys.readouterr().err


def test_tst17_generated_file_runs_through_every_step(tmp_path: Path) -> None:
    baseline = str(ROOT / "configs" / "baseline.toml")
    file = tmp_path / "one.csv"

    main(
        [
            "generate",
            "--pattern",
            "lunch",
            "--rate",
            "0.3",
            "--ticks",
            "100",
            "--seed",
            "2",
            "--config",
            baseline,
            "--out",
            str(file),
        ]
    )

    assert main(["run", "--requests", str(file), "--config", baseline, "--out", str(tmp_path)]) == 0


def test_tst17_module_entry_point_runs_with_no_traceback_on_bad_input(tmp_path: Path) -> None:
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "elevator_sim",
            "run",
            "--requests",
            str(tmp_path / "absent.csv"),
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 2
    assert "Traceback" not in done.stderr
