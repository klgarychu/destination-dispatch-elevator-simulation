"""TST-16: separate statistics per configuration, correct aggregation, and repeatable files."""

import csv
import json
from pathlib import Path

import pytest

from elevator_sim.cli import main
from elevator_sim.config import ALGORITHMS, SimConfig, config_id
from elevator_sim.experiment import (
    AGGREGATE_KEYS,
    STATS_COLUMNS,
    Task,
    aggregate,
    run_tasks,
    sample_inputs,
    suite_tasks,
)

SIX_ROWS = "time,id,source,dest\n0,a,1,5\n0,b,5,1\n2,c,3,8\n4,d,8,2\n9,e,1,9\n12,f,6,4\n"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def compare(tmp_path: Path, name: str, workers: int = 1) -> Path:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    out = tmp_path / name
    code = main(["compare", "--requests", str(file), "--out", str(out), "--workers", str(workers)])
    assert code == 0
    return out


def test_tst16_stats_columns_are_the_ones_in_the_spec() -> None:
    assert STATS_COLUMNS == [
        "run_id",
        "config_id",
        "stage",
        "building",
        "pattern",
        "load",
        "seed",
        "algorithm",
        "behaviour",
        "fairness_weight",
        "guard",
        "guard_value",
        "seat_hold",
        "assignment_rule",
        "rule_value",
        "unguarded",
        "passengers",
        "ticks",
        "passengers_per_tick",
        "wait_min",
        "wait_mean",
        "wait_max",
        "wait_p95",
        "wait_stdev",
        "total_min",
        "total_mean",
        "total_max",
        "total_p95",
        "total_stdev",
        "avg_car_load",
        "empty_travel_share",
        "jain_wait",
        "jain_total",
        "times_left_behind",
        "max_left_behind_one_passenger",
        "flagged_passengers",
        "fallback_count",
        "held_seat_ticks",
        "share_above_wait_limit",
    ]


def test_tst16_config_id_is_readable_and_has_four_parts() -> None:
    assert config_id(SimConfig(algorithm="eta")) == "eta__min_time__none__none"


def test_tst16_compare_gives_each_configuration_its_own_row_in_fixed_order(tmp_path: Path) -> None:
    rows = read_rows(compare(tmp_path, "out") / "simulation_stats.csv")

    assert [row["algorithm"] for row in rows] == list(ALGORITHMS)
    assert list(rows[0]) == STATS_COLUMNS


def test_tst16_each_configuration_has_its_own_file(tmp_path: Path) -> None:
    out = compare(tmp_path, "out")

    assert sorted(path.stem for path in (out / "by_config").glob("*.csv")) == sorted(
        f"{algorithm}__min_time__none__none" for algorithm in ALGORITHMS
    )
    for row in read_rows(out / "simulation_stats.csv"):
        assert read_rows(out / "by_config" / f"{row['config_id']}.csv") == [row]


def test_tst16_all_runs_are_labelled_unguarded_with_guard_columns_off(tmp_path: Path) -> None:
    rows = read_rows(compare(tmp_path, "out") / "simulation_stats.csv")

    assert {row["unguarded"] for row in rows} == {"True"}
    assert {row["guard"] for row in rows} == {"none"}
    assert {row["seat_hold"] for row in rows} == {"False"}
    assert {row["flagged_passengers"] for row in rows} == {"0"}


def test_tst16_aggregate_gives_mean_min_and_max_across_seeds() -> None:
    rows: list[dict[str, object]] = [
        {
            "config_id": "x",
            "building": "b",
            "pattern": "p",
            "load": "l",
            "seed": 1,
            "total_mean": 10.0,
            "wait_max": 4,
        },
        {
            "config_id": "x",
            "building": "b",
            "pattern": "p",
            "load": "l",
            "seed": 2,
            "total_mean": 20.0,
            "wait_max": 8,
        },
        {
            "config_id": "x",
            "building": "b",
            "pattern": "p",
            "load": "other",
            "seed": 1,
            "total_mean": 99.0,
            "wait_max": 1,
        },
    ]

    first, second = aggregate(rows, ["total_mean", "wait_max"])

    assert (first["load"], first["seeds"]) == ("l", 2)
    assert (first["total_mean_mean"], first["total_mean_min"], first["total_mean_max"]) == (
        15.0,
        10.0,
        20.0,
    )
    assert (first["wait_max_mean"], first["wait_max_min"], first["wait_max_max"]) == (6.0, 4, 8)
    assert (second["load"], second["seeds"]) == ("other", 1)


def test_tst16_aggregate_stats_file_has_one_row_per_configuration_and_input_group(
    tmp_path: Path,
) -> None:
    rows = read_rows(compare(tmp_path, "out") / "aggregate_stats.csv")

    assert [row["config_id"].split("__")[0] for row in rows] == list(ALGORITHMS)
    assert rows[0]["seeds"] == "1"
    assert {f"{key}_mean" for key in AGGREGATE_KEYS} <= set(rows[0])


def test_tst14_statistics_files_are_byte_identical_however_many_workers_run(
    tmp_path: Path,
) -> None:
    one = compare(tmp_path, "one", workers=1)
    two = compare(tmp_path, "two", workers=2)

    for name in ("simulation_stats.csv", "aggregate_stats.csv", "report.md"):
        assert (one / name).read_bytes() == (two / name).read_bytes()


def test_compare_writes_a_timing_row_for_each_run_only_in_the_suite_log(tmp_path: Path) -> None:
    out = compare(tmp_path, "out")

    log = read_rows(out / "suite_log.csv")

    assert len(log) == 5
    assert {row["status"] for row in log} == {"ok"}
    assert all(float(row["seconds"]) >= 0 for row in log)
    assert "seconds" not in (out / "simulation_stats.csv").read_text(encoding="utf-8")


def test_a_restarted_suite_skips_finished_runs(tmp_path: Path) -> None:
    out = compare(tmp_path, "out")
    saved = out / "runs" / "eta__min_time__none__none__input.json"
    marker = json.loads(saved.read_text(encoding="utf-8"))
    marker["stats"]["passengers"] = 123
    saved.write_text(json.dumps(marker), encoding="utf-8")

    compare(tmp_path, "out")

    rows = read_rows(out / "simulation_stats.csv")
    assert next(row for row in rows if row["algorithm"] == "eta")["passengers"] == "123"
    assert len(read_rows(out / "suite_log.csv")) == 5


def test_tst17_a_suite_matrix_has_every_configuration_on_every_input() -> None:
    tasks = suite_tasks(Path("data/generated"))

    assert len(tasks) == 800
    assert len({task.run_id for task in tasks}) == 800
    assert {task.building for task in tasks} == {"baseline", "tall"}
    assert {task.pattern for task in tasks} == {"uniform", "up_peak", "down_peak", "lunch"}
    assert {task.load for task in tasks} == {"light", "medium", "heavy", "overload"}
    assert {task.config.algorithm for task in tasks} == set(ALGORITHMS)
    assert {task.config.behaviour for task in tasks} == {"min_time"}


def test_tst17_buildings_are_applied_to_their_own_inputs() -> None:
    tasks = suite_tasks(Path("data/generated"))

    tall = next(task for task in tasks if task.building == "tall")
    baseline = next(task for task in tasks if task.building == "baseline")

    assert (tall.config.floors, tall.config.elevators, tall.config.capacity) == (60, 6, 10)
    assert (baseline.config.floors, baseline.config.elevators, baseline.config.capacity) == (
        10,
        3,
        6,
    )


def test_tst17_quick_suite_uses_seed_1_only() -> None:
    tasks = suite_tasks(Path("data/generated"), quick=True)

    assert len(tasks) == 160
    assert {task.seed for task in tasks} == {1}


def test_sample_runs_are_two_inputs_per_building_for_every_configuration() -> None:
    assert sample_inputs() == {
        ("baseline", "up_peak", "heavy", 1),
        ("baseline", "lunch", "overload", 1),
        ("tall", "up_peak", "heavy", 1),
        ("tall", "lunch", "overload", 1),
    }
    samples = [task for task in suite_tasks(Path("data/generated")) if task.sample]
    assert len(samples) == 20


def test_sample_runs_keep_their_full_logs(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    config = SimConfig(algorithm="eta")
    task = Task("sample", config, 1, "b", "p", "l", 1, file, sample=True)

    run_tasks([task], tmp_path, workers=1)

    logs = tmp_path / "samples" / "input" / "eta__min_time__none__none"
    assert sorted(path.name for path in logs.iterdir()) == [
        "passengers.csv",
        "positions.csv",
        "summary.json",
    ]


def test_runs_outside_the_sample_keep_no_logs(tmp_path: Path) -> None:
    assert not (compare(tmp_path, "out") / "samples").exists()


def test_m12_stage_2_is_rejected_until_it_is_built(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["compare", "--suite", "--stage", "2", "--out", str(tmp_path)])

    assert code == 2
    assert "Phase 4" in capsys.readouterr().err


def test_compare_needs_a_suite_or_a_requests_file(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["compare", "--out", "unused"]) == 2
    assert "--requests" in capsys.readouterr().err
