"""Run output files, read back as a user would."""

import csv
import json
from pathlib import Path

from elevator_sim.config import ExpressCar, SimConfig
from elevator_sim.engine import simulate
from elevator_sim.output import (
    RunRecord,
    format_summary,
    read_run_record,
    summary_data,
    write_run,
    write_run_record,
)
from elevator_sim.requests import Request

PDF_SAMPLE = [
    Request(0, "passenger1", 1, 51),
    Request(0, "passenger2", 1, 37),
    Request(10, "passenger3", 20, 1),
]
ONE_CAR = SimConfig(floors=60, elevators=1, capacity=6, algorithm="round_robin")


def read_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.reader(file))


def test_tst04_positions_file_has_one_row_per_tick_from_zero(tmp_path: Path) -> None:
    write_run(simulate(PDF_SAMPLE, ONE_CAR), tmp_path)

    rows = read_rows(tmp_path / "positions.csv")

    assert rows[0] == ["time", "elevator_1"]
    assert rows[1] == ["0", "1"]
    assert rows[2] == ["1", "2"]
    assert rows[-1] == ["100", "1"]
    assert len(rows) == 102


def test_tst04_positions_file_has_a_column_for_each_car(tmp_path: Path) -> None:
    config = SimConfig(elevators=3, algorithm="round_robin")
    write_run(simulate([Request(0, "a", 1, 2)], config), tmp_path)

    rows = read_rows(tmp_path / "positions.csv")

    assert rows[0] == ["time", "elevator_1", "elevator_2", "elevator_3"]
    assert rows[1] == ["0", "1", "1", "1"]


def test_o3_passengers_file_has_one_row_per_passenger_in_request_order(tmp_path: Path) -> None:
    write_run(simulate(PDF_SAMPLE, ONE_CAR), tmp_path)

    rows = read_rows(tmp_path / "passengers.csv")

    assert rows[0] == [
        "id",
        "time",
        "source",
        "dest",
        "elevator",
        "board_time",
        "dropoff_time",
        "wait_time",
        "travel_time",
        "total_time",
        "times_left_behind",
    ]
    assert rows[3] == ["passenger3", "10", "20", "1", "1", "81", "100", "71", "19", "90", "0"]
    assert len(rows) == 4


def test_tst05_summary_file_matches_the_spec_example(tmp_path: Path) -> None:
    write_run(simulate(PDF_SAMPLE, ONE_CAR), tmp_path)

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert summary["building"] == {"floors": 60, "elevators": 1, "capacity": 6, "express_cars": []}
    assert summary["passengers"] == 3
    assert summary["ticks"] == 100
    assert summary["wait_time"] == {"min": 0, "mean": 23.67, "max": 71, "p95": 71, "stdev": 33.47}
    assert summary["total_time"] == {"min": 36, "mean": 58.67, "max": 90, "p95": 90, "stdev": 22.88}
    assert summary["observations"][0] == "Longest wait: passenger3 at 71 ticks"


def test_summary_config_holds_all_settings_in_full() -> None:
    config = summary_data(simulate(PDF_SAMPLE, ONE_CAR))["config"]

    assert config == {
        "algorithm": "round_robin",
        "behaviour": "min_time",
        "fairness_weight": None,
        "guard": "none",
        "guard_value": None,
        "seat_hold": False,
        "assignment_rule": "none",
        "rule_value": None,
        "unguarded": True,
    }


def test_summary_lists_the_express_cars() -> None:
    config = SimConfig(floors=8, elevators=2, express=(ExpressCar(2, (1, 5, 6, 7, 8)),))

    summary = summary_data(simulate([Request(0, "a", 1, 6)], config))

    assert summary["building"]["express_cars"] == [2]


def a_record(run_id: str = "run", sample_dir: str | None = None) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        fingerprint="abc",
        config_id="eta__min_time__none__none",
        stage=1,
        building="3car-10floor-6cap",
        pattern="lunch",
        load="heavy",
        load_basis="own_limit",
        seed=1,
        settings={"algorithm": "eta"},
        stats={"passengers": 2},
        waits=[0, 3],
        totals=[4, 9],
        sample_dir=sample_dir,
    )


def test_a_saved_run_reads_back_the_same(tmp_path: Path) -> None:
    (tmp_path / "runs").mkdir()
    record = a_record(sample_dir="samples/input/eta__min_time__none__none")

    write_run_record(tmp_path, record)

    assert read_run_record(tmp_path, "run") == record


def test_saving_a_run_leaves_only_the_finished_file(tmp_path: Path) -> None:
    (tmp_path / "runs").mkdir()

    write_run_record(tmp_path, a_record())

    assert [path.name for path in (tmp_path / "runs").iterdir()] == ["run.json"]


def test_a_missing_run_reads_as_none(tmp_path: Path) -> None:
    assert read_run_record(tmp_path, "absent") is None


def test_i5_empty_run_has_null_statistics(tmp_path: Path) -> None:
    write_run(simulate([], ONE_CAR), tmp_path)

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["passengers"] == 0
    assert summary["wait_time"] is None
    assert summary["total_time"] is None
    assert len(read_rows(tmp_path / "positions.csv")) == 2


def test_console_summary_gives_min_max_and_average_wait_and_total() -> None:
    text = format_summary(summary_data(simulate(PDF_SAMPLE, ONE_CAR)))

    assert "wait" in text
    assert "total" in text
    assert "71" in text
    assert "58.67" in text


def test_tst14_same_input_gives_byte_identical_files(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"

    write_run(simulate(PDF_SAMPLE, ONE_CAR), first)
    write_run(simulate(PDF_SAMPLE, ONE_CAR), second)

    for name in ("positions.csv", "passengers.csv", "summary.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_output_files_use_lf_line_endings(tmp_path: Path) -> None:
    write_run(simulate(PDF_SAMPLE, ONE_CAR), tmp_path)

    for name in ("positions.csv", "passengers.csv", "summary.json"):
        assert b"\r" not in (tmp_path / name).read_bytes()
