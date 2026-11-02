"""TST-17: each command end to end, through the same entry point a user runs."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from elevator_sim.cli import main
from elevator_sim.config import SimConfig

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


def test_m12_flags_for_assignment_rules_exit_2(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["run", "--requests", SAMPLE, "--out", str(tmp_path), "--assignment-rule", "x"])

    assert caught.value.code == 2


def run_sample(tmp_path: Path, *options: str) -> int:
    arguments = ["run", "--requests", SAMPLE, "--config", SAMPLE_CONFIG, "--out", str(tmp_path)]
    return main([*arguments, *options])


def saved_settings(folder: Path) -> dict[str, object]:
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    settings: dict[str, object] = summary["config"]
    return settings


def test_tst17_run_accepts_a_behaviour(tmp_path: Path) -> None:
    assert run_sample(tmp_path, "--behaviour", "strict") == 0

    assert saved_settings(tmp_path)["behaviour"] == "strict"


def test_tst17_run_accepts_a_weight_for_weighted(tmp_path: Path) -> None:
    assert run_sample(tmp_path, "--behaviour", "weighted", "--weight", "0.5") == 0

    assert saved_settings(tmp_path)["fairness_weight"] == 0.5


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        (["--guard", "skip_limit", "--skip-limit", "3"], ("skip_limit", 3, True)),
        (["--guard", "skip_limit", "--no-seat-hold"], ("skip_limit", 2, False)),
        (["--guard", "wait_expiry", "--wait-limit", "3rt"], ("wait_expiry", "3rt", True)),
        (["--guard", "wait_expiry", "--wait-limit", "36"], ("wait_expiry", 36, True)),
        (["--guard", "none"], ("none", None, False)),
    ],
)
def test_tst17_run_accepts_guard_settings(
    tmp_path: Path, options: list[str], expected: tuple[object, ...]
) -> None:
    assert run_sample(tmp_path, *options) == 0

    settings = saved_settings(tmp_path)
    assert (settings["guard"], settings["guard_value"], settings["seat_hold"]) == expected


@pytest.mark.parametrize(
    ("options", "named"),
    [
        (["--guard", "max_skips"], "unknown guard"),
        (["--guard", "skip_limit", "--skip-limit", "0"], "skip_limit"),
        (["--guard", "wait_expiry", "--wait-limit", "2 trips"], "wait_limit"),
    ],
)
def test_tst17_a_bad_guard_setting_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], options: list[str], named: str
) -> None:
    assert run_sample(tmp_path, *options) == 2
    assert named in capsys.readouterr().err


def test_m12_a_weight_that_would_do_nothing_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_sample(tmp_path, "--weight", "0.5") == 2
    assert "fairness_weight" in capsys.readouterr().err


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
            str(ROOT / "configs" / "3car-10floor-6cap.toml"),
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
    baseline = str(ROOT / "configs" / "3car-10floor-6cap.toml")
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


def test_tst17_a_requests_file_that_is_not_utf_8_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = tmp_path / "latin.csv"
    file.write_bytes(b"time,id,source,dest\n0,caf\xe9,1,2\n")

    assert main(["run", "--requests", str(file), "--out", str(tmp_path / "out")]) == 2
    assert "latin.csv" in capsys.readouterr().err


def test_tst17_a_bad_file_gives_a_readable_error_with_several_workers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = tmp_path / "bad.csv"
    file.write_text("time,id,source,dest\n0,a,1,99\n", encoding="utf-8")
    out = str(tmp_path / "out")

    assert main(["compare", "--requests", str(file), "--workers", "2", "--out", out]) == 2

    assert "row 2: dest 99 is outside floors 1..10" in capsys.readouterr().err


def test_tst17_a_badly_shaped_config_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "bad.toml"
    config.write_text("building = 3\n", encoding="utf-8")

    code = main(["run", "--requests", SAMPLE, "--config", str(config), "--out", str(tmp_path)])

    assert code == 2
    assert "building" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("options", "named"),
    [
        (["--rate", "nan"], "rate"),
        (["--rate", "1", "--ticks", "-5"], "ticks"),
    ],
)
def test_tst17_generate_refuses_bad_values_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], options: list[str], named: str
) -> None:
    out = tmp_path / "requests.csv"

    assert main(["generate", "--pattern", "uniform", *options, "--out", str(out)]) == 2

    assert named in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize("workers", ["0", "-1"])
def test_tst17_compare_refuses_a_worker_count_below_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], workers: str
) -> None:
    out = str(tmp_path / "out")

    assert main(["compare", "--requests", SAMPLE, "--workers", workers, "--out", out]) == 2
    assert "workers" in capsys.readouterr().err


def test_tst17_calibration_refuses_a_worker_count_below_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rates = str(tmp_path / "rates.toml")

    assert main(["generate", "--calibrate", "--workers", "0", "--out", rates]) == 2
    assert "workers" in capsys.readouterr().err


def test_tst17_calibration_uses_the_config_file_it_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "baseline.toml"
    config.write_text("[building]\nfloors = 5\n", encoding="utf-8")
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr("elevator_sim.cli.calibrate", lambda *args: calls.append(args))
    rates = str(tmp_path / "rates.toml")

    assert main(["generate", "--calibrate", "--config", str(config), "--out", rates]) == 0

    assert calls[0][0] == {"baseline": SimConfig(floors=5)}


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


def test_tst17_run_defaults_to_skip_limit_2_with_seat_hold(tmp_path: Path) -> None:
    assert run_sample(tmp_path) == 0

    settings = saved_settings(tmp_path)
    assert (settings["guard"], settings["guard_value"], settings["seat_hold"]) == (
        "skip_limit",
        2,
        True,
    )
    assert settings["unguarded"] is False
