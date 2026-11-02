"""TST-16: separate statistics per configuration, correct aggregation, and repeatable files."""

import csv
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from elevator_sim.cli import main
from elevator_sim.config import (
    ALGORITHMS,
    ALL_ALGORITHMS,
    SimConfig,
    config_id,
    settings_record,
)
from elevator_sim.experiment import (
    AGGREGATE_KEYS,
    STATS_COLUMNS,
    SuiteOutcome,
    Task,
    aggregate,
    behaviour_tasks,
    express_tasks,
    run_suite,
    run_tasks,
    sample_inputs,
    source_fingerprint,
    stage_1_tasks,
    stage_2_tasks,
    suite_tasks,
)
from elevator_sim.output import read_manifest
from elevator_sim.workload import BUILDINGS, building_config, suite_inputs

SIX_ROWS = "time,id,source,dest\n0,a,1,5\n0,b,5,1\n2,c,3,8\n4,d,8,2\n9,e,1,9\n12,f,6,4\n"
ONE_ROW = "time,id,source,dest\n0,a,1,2\n"
TWO_ROWS = "time,id,source,dest\n0,a,1,2\n0,b,1,3\n"


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


def compare_file(file: Path, out: Path, *options: str) -> None:
    arguments = ["compare", "--requests", str(file), "--out", str(out), "--workers", "1"]
    assert main([*arguments, *options]) == 0


def column(out: Path, name: str) -> set[str]:
    return {row[name] for row in read_rows(out / "simulation_stats.csv")}


def runs_executed(out: Path) -> int:
    return len(read_rows(out / "suite_log.csv"))


# compare on one file runs every Stage 1 configuration: 6 algorithms under 5 seat settings.
PER_FILE = 30


def test_tst16_stats_columns_are_the_ones_in_the_spec() -> None:
    assert STATS_COLUMNS == [
        "run_id",
        "config_id",
        "stage",
        "building",
        "pattern",
        "load",
        "load_basis",
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
    assert config_id(SimConfig(algorithm="eta")) == "eta__min_time__skip_limit-2-hold__none"
    assert config_id(SimConfig(algorithm="eta", guard="none")) == "eta__min_time__none__none"


def test_tst16_compare_gives_each_configuration_its_own_row_in_fixed_order(tmp_path: Path) -> None:
    rows = read_rows(compare(tmp_path, "out") / "simulation_stats.csv")

    assert [row["algorithm"] for row in rows] == list(ALL_ALGORITHMS) * 5
    assert list(rows[0]) == STATS_COLUMNS


def test_tst16_each_configuration_has_its_own_file(tmp_path: Path) -> None:
    out = compare(tmp_path, "out")

    rows = read_rows(out / "simulation_stats.csv")
    assert sorted(path.stem for path in (out / "by_config").glob("*.csv")) == sorted(
        row["config_id"] for row in rows
    )
    assert len(rows) == PER_FILE
    for row in read_rows(out / "simulation_stats.csv"):
        assert read_rows(out / "by_config" / f"{row['config_id']}.csv") == [row]


def test_tst16_runs_on_the_default_guard_are_labelled_with_it(tmp_path: Path) -> None:
    every = read_rows(compare(tmp_path, "out") / "simulation_stats.csv")
    rows = [row for row in every if row["behaviour"] != "strict"]

    assert {row["unguarded"] for row in every} == {"False"}
    assert {row["guard"] for row in rows} == {"skip_limit"}
    assert {row["guard_value"] for row in rows} == {"2"}
    assert {row["seat_hold"] for row in rows} == {"True"}


def test_tst16_runs_with_no_guard_are_labelled_unguarded(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    config = tmp_path / "none.toml"
    config.write_text('[dispatch]\nguard = "none"\n', encoding="utf-8")
    out = tmp_path / "out"

    compare_file(file, out, "--config", str(config))

    every = read_rows(out / "simulation_stats.csv")
    rows = [row for row in every if row["behaviour"] != "strict"]
    assert {row["unguarded"] for row in rows} == {"True"}
    assert {row["guard"] for row in every} == {"none"}
    assert {row["seat_hold"] for row in rows} == {"False"}
    assert {row["flagged_passengers"] for row in rows} == {"0"}


def test_tst16_aggregate_gives_mean_min_and_max_across_seeds() -> None:
    rows: list[dict[str, object]] = [
        {
            "config_id": "x",
            "stage": 1,
            "algorithm": "eta",
            "behaviour": "min_time",
            "building": "b",
            "pattern": "p",
            "load": "l",
            "load_basis": "own_limit",
            "fairness_weight": None,
            "seed": 1,
            "total_mean": 10.0,
            "wait_max": 4,
        },
        {
            "config_id": "x",
            "stage": 1,
            "algorithm": "eta",
            "behaviour": "min_time",
            "building": "b",
            "pattern": "p",
            "load": "l",
            "load_basis": "own_limit",
            "fairness_weight": None,
            "seed": 2,
            "total_mean": 20.0,
            "wait_max": 8,
        },
        {
            "config_id": "x",
            "stage": 1,
            "algorithm": "eta",
            "behaviour": "min_time",
            "building": "b",
            "pattern": "p",
            "load": "other",
            "load_basis": "own_limit",
            "fairness_weight": None,
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

    assert [row["algorithm"] for row in rows] == list(ALL_ALGORITHMS) * 5
    assert {row["behaviour"] for row in rows} == {"strict", "min_time", "weighted"}
    assert rows[0]["seeds"] == "1"
    assert {f"{key}_mean" for key in AGGREGATE_KEYS} <= set(rows[0])


def test_tst14_statistics_files_are_byte_identical_however_many_workers_run(
    tmp_path: Path,
) -> None:
    one = compare(tmp_path, "one", workers=1)
    two = compare(tmp_path, "two", workers=2)

    for name in ("simulation_stats.csv", "aggregate_stats.csv", "report.md", "run_manifest.json"):
        assert (one / name).read_bytes() == (two / name).read_bytes()


def test_compare_writes_a_timing_row_for_each_run_only_in_the_suite_log(tmp_path: Path) -> None:
    out = compare(tmp_path, "out")

    log = read_rows(out / "suite_log.csv")

    assert len(log) == PER_FILE
    assert {row["status"] for row in log} == {"ok"}
    assert all(float(row["seconds"]) >= 0 for row in log)
    assert "seconds" not in (out / "simulation_stats.csv").read_text(encoding="utf-8")


def test_tst14_a_restarted_suite_reuses_unchanged_runs_without_running_them(
    tmp_path: Path,
) -> None:
    out = compare(tmp_path, "out")
    saved = {path.name: path.read_bytes() for path in (out / "runs").iterdir()}

    compare(tmp_path, "out")

    assert {path.name: path.read_bytes() for path in (out / "runs").iterdir()} == saved
    assert runs_executed(out) == PER_FILE


def test_an_interrupted_suite_runs_only_what_is_missing(tmp_path: Path) -> None:
    out = compare(tmp_path, "out")
    (out / "runs" / "eta__min_time__skip_limit-2-hold__none__input.json").unlink()
    (out / "runs" / "round_robin__min_time__skip_limit-2-hold__none__input.json").unlink()

    compare(tmp_path, "out")

    assert runs_executed(out) == PER_FILE + 2
    assert len(read_rows(out / "simulation_stats.csv")) == PER_FILE


def test_a_saved_run_is_not_reused_once_its_input_changes(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(ONE_ROW, encoding="utf-8")
    compare_file(file, tmp_path / "out")

    file.write_text(TWO_ROWS, encoding="utf-8")
    compare_file(file, tmp_path / "out")

    assert column(tmp_path / "out", "passengers") == {"2"}
    assert runs_executed(tmp_path / "out") == 2 * PER_FILE


def test_a_saved_run_is_not_reused_once_its_settings_change(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(ONE_ROW, encoding="utf-8")
    config = tmp_path / "custom.toml"
    config.write_text("[building]\nstart_floor = 1\n", encoding="utf-8")
    compare_file(file, tmp_path / "out", "--config", str(config))

    config.write_text("[building]\nstart_floor = 5\n", encoding="utf-8")
    compare_file(file, tmp_path / "out", "--config", str(config))

    # A car now starts on floor 5: 4 ticks down to the passenger, then 1 tick of riding.
    assert column(tmp_path / "out", "ticks") == {"5"}


def test_a_saved_run_is_not_reused_for_a_different_file_with_the_same_name(tmp_path: Path) -> None:
    first, second = tmp_path / "x" / "input.csv", tmp_path / "y" / "input.csv"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text(ONE_ROW, encoding="utf-8")
    second.write_text(TWO_ROWS, encoding="utf-8")
    compare_file(first, tmp_path / "out")

    compare_file(second, tmp_path / "out")

    assert column(tmp_path / "out", "passengers") == {"2"}


def test_a_saved_run_is_not_reused_once_the_source_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = tmp_path / "input.csv"
    file.write_text(ONE_ROW, encoding="utf-8")
    compare_file(file, tmp_path / "out")

    monkeypatch.setattr("elevator_sim.experiment.source_fingerprint", lambda: "different code")
    compare_file(file, tmp_path / "out")

    assert runs_executed(tmp_path / "out") == 2 * PER_FILE


def test_the_source_fingerprint_covers_every_source_file(tmp_path: Path) -> None:
    (tmp_path / "inner").mkdir()
    (tmp_path / "top.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "inner" / "deep.py").write_text("b = 2\n", encoding="utf-8")
    original = source_fingerprint(tmp_path)

    assert source_fingerprint(tmp_path) == original

    (tmp_path / "inner" / "deep.py").write_text("b = 3\n", encoding="utf-8")

    assert source_fingerprint(tmp_path) != original


def test_a_saved_run_still_counts_when_the_same_input_moves_folder(tmp_path: Path) -> None:
    first, second = tmp_path / "x" / "input.csv", tmp_path / "y" / "input.csv"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text(ONE_ROW, encoding="utf-8")
    second.write_text(ONE_ROW, encoding="utf-8")
    compare_file(first, tmp_path / "out")

    compare_file(second, tmp_path / "out")

    assert runs_executed(tmp_path / "out") == PER_FILE


@pytest.mark.parametrize("contents", ["not json", '{"run_id": "made before fingerprints"}'])
def test_a_saved_run_that_cannot_be_checked_is_run_again(tmp_path: Path, contents: str) -> None:
    out = compare(tmp_path, "out")
    (out / "runs" / "eta__min_time__skip_limit-2-hold__none__input.json").write_text(
        contents, encoding="utf-8"
    )

    compare(tmp_path, "out")

    assert runs_executed(out) == PER_FILE + 1
    assert column(out, "passengers") == {"6"}


def test_a_stale_run_that_then_stalls_leaves_no_old_result(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    out = tmp_path / "out"
    finished = Task("run", SimConfig(algorithm="eta"), 1, "b", "p", "l", 1, file, sample=True)
    run_suite([finished], out, workers=1)
    assert (out / "runs" / "run.json").exists()

    outcome = run_suite([replace(finished, config=replace(finished.config, max_ticks=1))], out, 1)

    assert outcome.stalled == ["run"]
    assert not (out / "runs" / "run.json").exists()
    assert not (out / "samples" / "input" / "eta__min_time__skip_limit-2-hold__none").exists()
    assert read_rows(out / "simulation_stats.csv") == []


def test_every_output_leaves_out_a_configuration_with_no_finished_runs(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    out = tmp_path / "out"
    finished = [
        Task(name, SimConfig(algorithm=name), 1, "b", "p", "l", 1, file)
        for name in ("eta", "round_robin")
    ]
    run_suite(finished, out, workers=1)
    stalled = replace(finished[1].config, max_ticks=1)

    run_suite([finished[0], replace(finished[1], config=stalled)], out, workers=1)

    assert column(out, "algorithm") == {"eta"}
    assert read_manifest(out).runs == ["eta"]
    assert [path.name for path in (out / "by_config").iterdir()] == [
        "eta__min_time__skip_limit-2-hold__none.csv"
    ]


def test_a_stalled_run_is_recorded_as_not_finished_in_task_order(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    out = tmp_path / "out"
    limits = {"zone_based": 1, "eta": None, "round_robin": 1}
    tasks = [
        Task(name, SimConfig(algorithm=name, max_ticks=limit), 1, "b", "p", "l", 1, file)
        for name, limit in limits.items()
    ]

    run_suite(tasks, out, workers=1)

    assert read_manifest(out).runs == ["eta"]
    assert read_manifest(out).not_finished == ["zone_based", "round_robin"]
    assert "`zone_based`, `round_robin`" in (out / "report.md").read_text(encoding="utf-8")


def test_the_manifest_lists_the_runs_that_kept_full_logs(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    out = tmp_path / "out"
    config = SimConfig(algorithm="eta")
    tasks = [
        Task("logged", config, 1, "b", "p", "l", 1, file, sample=True),
        Task("plain", config, 1, "b", "p", "l", 2, file),
    ]

    run_suite(tasks, out, workers=1)

    assert read_manifest(out).samples == ["logged"]


def test_a_refused_worker_count_leaves_the_last_comparison_intact(tmp_path: Path) -> None:
    out = compare(tmp_path, "out")

    code = main(
        ["compare", "--requests", str(tmp_path / "input.csv"), "--workers", "0", "--out", str(out)]
    )

    assert code == 2
    assert read_manifest(out).runs


def test_compare_says_how_many_runs_it_ran_and_how_many_it_reused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = compare(tmp_path, "out")
    (out / "runs" / "eta__min_time__skip_limit-2-hold__none__input.json").unlink()
    capsys.readouterr()

    compare(tmp_path, "out")

    assert "Finished 30 of 30 runs (1 run, 29 reused)" in capsys.readouterr().out


def test_compare_suite_stops_on_an_input_that_no_longer_matches_the_rates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / next(suite_inputs((1,))).name).write_text(ONE_ROW, encoding="utf-8")

    code = main(
        ["compare", "--suite", "--quick", "--inputs", str(inputs), "--out", str(tmp_path / "out")]
    )

    assert code == 2
    assert "generate --suite" in capsys.readouterr().err


def test_tst17_a_suite_matrix_has_every_configuration_on_every_input() -> None:
    tasks = suite_tasks(Path("data/generated"))

    assert len(tasks) == 6000
    assert len({task.run_id for task in tasks}) == 6000
    assert {task.building for task in tasks} == set(BUILDINGS)
    assert {task.pattern for task in tasks} == {"uniform", "up_peak", "down_peak", "lunch"}
    assert {task.load for task in tasks} == {"light", "medium", "heavy", "overload"}
    assert {task.config.algorithm for task in tasks} == set(ALGORITHMS)
    assert {task.config.behaviour for task in tasks} == {"min_time"}


def test_tst17_buildings_are_applied_to_their_own_inputs() -> None:
    for task in suite_tasks(Path("data/generated")):
        assert task.config == replace(
            building_config(task.building), algorithm=task.config.algorithm, guard="none"
        )
        if task.load_basis == "own_limit":
            assert task.input_path.name.startswith(f"{task.building}_")


def test_m28_the_fixed_load_gives_every_other_case_the_same_arrivals() -> None:
    tasks = [t for t in suite_tasks(Path("data/generated")) if t.load_basis == "fixed"]

    assert len(tasks) == 2800
    assert not any(task.sample for task in tasks)
    assert {
        task.building: task.input_path.name
        for task in tasks
        if (task.pattern, task.load, task.seed, task.config.algorithm)
        == ("lunch", "heavy", 2, "eta")
    } == {
        "1car-10floor-6cap": "fixed-10floor_lunch_heavy_s2.csv",
        "3car-10floor-6cap": "fixed-10floor_lunch_heavy_s2.csv",
        "3car-35floor-6cap": "fixed-35floor_lunch_heavy_s2.csv",
        "6car-60floor-6cap": "3car-60floor-6cap_lunch_heavy_s2.csv",
        "9car-60floor-6cap": "3car-60floor-6cap_lunch_heavy_s2.csv",
        "3car-60floor-9cap": "3car-60floor-6cap_lunch_heavy_s2.csv",
        "3car-60floor-12cap": "3car-60floor-6cap_lunch_heavy_s2.csv",
    }


def test_m28_a_fixed_load_run_keeps_the_logs_of_the_run_that_shares_its_file(
    tmp_path: Path,
) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    config = SimConfig(algorithm="eta")
    own = Task("own", config, 1, "a", "p", "l", 1, file, sample=True)
    fixed = Task("fixed", config, 1, "b", "p", "l", 1, file, load_basis="fixed")
    run_tasks([own], tmp_path, workers=1)

    run_tasks([own, fixed], tmp_path, workers=1)

    assert (tmp_path / "samples" / "input" / "eta__min_time__skip_limit-2-hold__none").exists()


def test_m28_the_statistics_keep_the_two_load_bases_apart(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    config = SimConfig(algorithm="eta")
    own = Task("own", config, 1, "a", "p", "l", 1, file)
    fixed = Task("fixed", config, 1, "a", "p", "l", 1, file, load_basis="fixed")
    out = tmp_path / "out"

    run_suite([own, fixed], out, workers=1)

    assert [row["load_basis"] for row in read_rows(out / "simulation_stats.csv")] == [
        "own_limit",
        "fixed",
    ]
    assert [row["load_basis"] for row in read_rows(out / "aggregate_stats.csv")] == [
        "own_limit",
        "fixed",
    ]


def test_m30_the_express_suite_has_every_algorithm_on_every_case() -> None:
    tasks = express_tasks(Path("data/generated"))

    assert len(tasks) == 4800
    assert len({task.run_id for task in tasks}) == 4800
    assert {task.config.algorithm for task in tasks} == set(ALL_ALGORITHMS)
    assert {task.building for task in tasks} == {
        "3car-10floor-6cap",
        "3car-60floor-6cap",
        "6car-60floor-6cap",
        "6car-60floor-6cap-express",
        "3car-60floor-6cap-1high31",
        "3car-60floor-6cap-1high41",
        "3car-60floor-6cap-2high31",
        "3car-60floor-6cap-split30",
        "3car-60floor-6cap-overlap",
    }


def test_m30_express_cases_run_on_the_passengers_of_the_building_they_change() -> None:
    tasks = express_tasks(Path("data/generated"))

    def inputs(building: str, basis: str) -> set[str]:
        return {
            task.input_path.name
            for task in tasks
            if task.building == building
            and task.load_basis == basis
            and (task.pattern, task.load, task.seed) == ("lunch", "heavy", 2)
        }

    assert inputs("3car-60floor-6cap-split30", "fixed") == {"3car-60floor-6cap_lunch_heavy_s2.csv"}
    assert inputs("6car-60floor-6cap-express", "fixed") == {"6car-60floor-6cap_lunch_heavy_s2.csv"}
    assert inputs("6car-60floor-6cap-express", "own_limit") == {
        "6car-60floor-6cap-express_lunch_heavy_s2.csv"
    }
    assert inputs("3car-60floor-6cap", "own_limit") == {"3car-60floor-6cap_lunch_heavy_s2.csv"}


def test_m30_the_phase_1_cases_keep_their_run_ids_so_rows_can_be_compared() -> None:
    phase_1 = {task.run_id: task for task in suite_tasks(Path("data/generated"))}
    shared = [
        task
        for task in express_tasks(Path("data/generated"))
        if task.building in ("3car-10floor-6cap", "3car-60floor-6cap", "6car-60floor-6cap")
        and task.config.algorithm in ALGORITHMS
    ]

    assert len(shared) == 1200
    for task in shared:
        assert task.run_id in phase_1
        assert task.input_path == phase_1[task.run_id].input_path
        assert task.config == phase_1[task.run_id].config


def test_m30_the_phase_1_suite_is_unchanged() -> None:
    tasks = suite_tasks(Path("data/generated"))

    assert len(tasks) == 6000
    assert {task.config.algorithm for task in tasks} == set(ALGORITHMS)


def test_m30_compare_runs_the_suite_of_the_phase_it_is_asked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sizes: list[int] = []

    def fake_run(tasks: list[Task], out: Path, workers: int) -> SuiteOutcome:
        sizes.append(len(tasks))
        return SuiteOutcome([], 0)

    monkeypatch.setattr("elevator_sim.cli.ensure_inputs", lambda *args: None)
    monkeypatch.setattr("elevator_sim.cli.run_suite", fake_run)
    out = str(tmp_path / "out")

    assert main(["compare", "--suite", "--phase", "1", "--out", out]) == 0

    assert sizes == [6000]


def test_m30_a_fixed_load_sample_keeps_its_logs_apart_from_the_run_that_shares_its_file(
    tmp_path: Path,
) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    config = SimConfig(algorithm="eta")
    own = Task("own", config, 1, "a", "p", "l", 1, file, sample=True)
    fixed = Task("fixed", config, 1, "b", "p", "l", 1, file, sample=True, load_basis="fixed")

    run_tasks([own, fixed], tmp_path, workers=1)

    assert (tmp_path / "samples" / "input" / "eta__min_time__skip_limit-2-hold__none").exists()
    assert (tmp_path / "samples" / "b__input" / "eta__min_time__skip_limit-2-hold__none").exists()


def test_m32_the_behaviour_suite_has_every_setting_on_every_algorithm() -> None:
    tasks = behaviour_tasks(Path("data/generated"))

    assert len(tasks) == 7200
    assert len({task.run_id for task in tasks}) == 7200
    assert {task.config.algorithm for task in tasks} == set(ALL_ALGORITHMS)
    assert {(task.config.behaviour, task.config.fairness_weight) for task in tasks} == {
        ("strict", None),
        ("min_time", None),
        ("weighted", 0.5),
        ("weighted", 1.0),
        ("weighted", 2.0),
    }
    assert {task.building for task in tasks} == {
        "3car-10floor-6cap",
        "3car-60floor-6cap",
        "3car-60floor-6cap-overlap",
    }


def test_m32_the_overlap_layout_runs_on_the_reference_passengers() -> None:
    tasks = behaviour_tasks(Path("data/generated"))

    assert {
        task.input_path.name
        for task in tasks
        if task.building == "3car-60floor-6cap-overlap"
        and (task.pattern, task.load, task.seed) == ("lunch", "heavy", 2)
    } == {"3car-60floor-6cap_lunch_heavy_s2.csv"}


def test_m32_min_time_keeps_its_phase_2_run_ids_so_rows_can_be_compared() -> None:
    phase_2 = {task.run_id: task for task in express_tasks(Path("data/generated"))}
    shared = [
        task
        for task in behaviour_tasks(Path("data/generated"))
        if task.config.behaviour == "min_time"
    ]

    assert len(shared) == 1440
    for task in shared:
        assert task.run_id in phase_2
        assert task.input_path == phase_2[task.run_id].input_path
        assert task.config == phase_2[task.run_id].config


def test_m32_compare_defaults_to_the_behaviour_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sizes: list[int] = []

    def fake_run(tasks: list[Task], out: Path, workers: int) -> SuiteOutcome:
        sizes.append(len(tasks))
        return SuiteOutcome([], 0)

    monkeypatch.setattr("elevator_sim.cli.ensure_inputs", lambda *args: None)
    monkeypatch.setattr("elevator_sim.cli.run_suite", fake_run)
    out = str(tmp_path / "out")

    assert main(["compare", "--suite", "--phase", "3", "--out", out]) == 0
    assert main(["compare", "--suite", "--phase", "2", "--out", out]) == 0

    assert sizes == [7200, 4800]


def test_m32_aggregate_keeps_each_weight_apart(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    light = SimConfig(behaviour="weighted", fairness_weight=0.5)
    heavy = SimConfig(behaviour="weighted", fairness_weight=2.0)
    out = tmp_path / "out"

    run_suite(
        [
            Task("light", light, 1, "a", "p", "l", 1, file),
            Task("heavy", heavy, 1, "a", "p", "l", 1, file),
        ],
        out,
        workers=1,
    )

    assert [row["fairness_weight"] for row in read_rows(out / "aggregate_stats.csv")] == [
        "0.5",
        "2.0",
    ]


def test_tst17_quick_suite_uses_seed_1_only() -> None:
    tasks = suite_tasks(Path("data/generated"), quick=True)

    assert len(tasks) == 1200
    assert {task.seed for task in tasks} == {1}


def test_sample_runs_are_two_inputs_per_building_for_every_configuration() -> None:
    assert sample_inputs() == {
        (building, pattern, load, 1)
        for building in BUILDINGS
        for pattern, load in (("up_peak", "heavy"), ("lunch", "overload"))
    }
    samples = [task for task in suite_tasks(Path("data/generated")) if task.sample]
    assert len(samples) == 80


def test_sample_runs_keep_their_full_logs(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    config = SimConfig(algorithm="eta")
    task = Task("sample", config, 1, "b", "p", "l", 1, file, sample=True)

    run_tasks([task], tmp_path, workers=1)

    logs = tmp_path / "samples" / "input" / "eta__min_time__skip_limit-2-hold__none"
    assert sorted(path.name for path in logs.iterdir()) == [
        "passengers.csv",
        "positions.csv",
        "summary.json",
    ]


def test_runs_outside_the_sample_keep_no_logs(tmp_path: Path) -> None:
    assert not (compare(tmp_path, "out") / "samples").exists()


def test_tst17_stage_2_runs_only_in_the_phase_4_suite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["compare", "--suite", "--phase", "3", "--stage", "2", "--out", str(tmp_path)])

    assert code == 2
    assert "Stage 2" in capsys.readouterr().err


def test_compare_needs_a_suite_or_a_requests_file(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["compare", "--out", "unused"]) == 2
    assert "--requests" in capsys.readouterr().err


@pytest.mark.parametrize("suite", [suite_tasks, express_tasks, behaviour_tasks])
def test_m8_the_phase_1_to_3_suites_keep_no_guard_so_their_results_stand(
    suite: Callable[[Path], list[Task]],
) -> None:
    tasks = suite(Path("data/generated"))

    assert {task.config.guard_in_force for task in tasks} == {"none"}
    assert all(task.run_id.split("__")[2] == "none" for task in tasks)


INPUTS = Path("data/generated")


def test_g7_stage_1_runs_every_seat_setting_with_the_default_guard() -> None:
    tasks = stage_1_tasks(INPUTS)

    assert len(tasks) == 7200
    assert {task.stage for task in tasks} == {1}
    assert {task.run_id.split("__")[2] for task in tasks if task.config.behaviour != "strict"} == {
        "skip_limit-2-hold"
    }
    assert {task.run_id.split("__")[2] for task in tasks if task.config.behaviour == "strict"} == {
        "none"
    }


def test_g16_stage_2_runs_nine_guard_settings_on_two_behaviours() -> None:
    tasks = stage_2_tasks(INPUTS)

    assert len(tasks) == 3240
    assert {task.stage for task in tasks} == {2}
    assert {task.config.algorithm for task in tasks} == {"marginal_insertion"}
    assert {task.load for task in tasks} == {"medium", "heavy", "overload"}
    assert {task.building for task in tasks} == {
        "3car-10floor-6cap",
        "3car-60floor-6cap",
        "3car-60floor-6cap-overlap",
    }
    one_input = [
        t.run_id for t in tasks if t.input_path.name == "3car-60floor-6cap_lunch_heavy_s1.csv"
    ]
    assert [run_id.split("__")[1] + " " + run_id.split("__")[2] for run_id in one_input[:9]] == [
        "min_time none",
        "min_time skip_limit-1-hold",
        "min_time skip_limit-2-hold",
        "min_time skip_limit-3-hold",
        "min_time wait_expiry-1rt-hold",
        "min_time wait_expiry-2rt-hold",
        "min_time wait_expiry-3rt-hold",
        "min_time skip_limit-2-nohold",
        "min_time wait_expiry-2rt-nohold",
    ]
    assert len({run_id.split("__")[1] for run_id in one_input}) == 2


def test_m11_the_runs_in_both_stages_are_the_default_guard_on_marginal_insertion() -> None:
    stage_1 = {task.run_id: task for task in stage_1_tasks(INPUTS)}
    shared = [task for task in stage_2_tasks(INPUTS) if task.run_id in stage_1]

    assert len(shared) == 360
    assert {tuple(task.run_id.split("__")[1:3]) for task in shared} == {
        ("min_time", "skip_limit-2-hold"),
        ("weighted-1", "skip_limit-2-hold"),
    }
    for task in shared:
        assert task.config == stage_1[task.run_id].config
        assert task.input_path == stage_1[task.run_id].input_path


def test_m8_runs_with_no_guard_and_strict_runs_keep_their_phase_3_run_ids() -> None:
    phase_3 = {task.run_id: task for task in behaviour_tasks(INPUTS)}
    strict = [task for task in stage_1_tasks(INPUTS) if task.config.behaviour == "strict"]
    no_guard = [task for task in stage_2_tasks(INPUTS) if task.config.guard_in_force == "none"]

    assert (len(strict), len(no_guard)) == (1440, 360)
    for task in strict + no_guard:
        assert task.run_id in phase_3
        assert task.input_path == phase_3[task.run_id].input_path
        assert settings_record(task.config) == settings_record(phase_3[task.run_id].config)


def test_m11_a_run_in_both_stages_executes_once_and_writes_a_row_for_each(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    config = SimConfig(algorithm="eta")
    first = Task("shared", config, 1, "b", "p", "medium", 1, file)
    second = Task("shared", config, 2, "b", "p", "medium", 1, file)
    other = Task("other", replace(config, guard="none"), 2, "b", "p", "medium", 1, file)
    out = tmp_path / "out"

    run_suite([first, other, second], out, workers=1)

    assert runs_executed(out) == 2
    rows = read_rows(out / "simulation_stats.csv")
    assert [(row["run_id"], row["stage"]) for row in rows] == [
        ("shared", "1"),
        ("other", "2"),
        ("shared", "2"),
    ]
    assert read_manifest(out).runs == ["shared", "other"]
    aggregated = read_rows(out / "aggregate_stats.csv")
    assert [(row["config_id"], row["stage"], row["seeds"]) for row in aggregated] == [
        (config_id(config), "1", "1"),
        (config_id(other.config), "2", "1"),
        (config_id(config), "2", "1"),
    ]


def test_m11_a_run_saved_for_one_stage_is_reused_for_the_other(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    config = SimConfig(algorithm="eta")
    out = tmp_path / "out"
    run_suite([Task("shared", config, 2, "b", "p", "medium", 1, file)], out, workers=1)

    outcome = run_suite([Task("shared", config, 1, "b", "p", "medium", 1, file)], out, workers=1)

    assert outcome.reused == 1
    assert [row["stage"] for row in read_rows(out / "simulation_stats.csv")] == ["1"]


@pytest.mark.parametrize(("stage", "size"), [("all", 10440), ("1", 7200), ("2", 3240)])
def test_tst17_compare_runs_the_stages_it_is_asked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, size: int
) -> None:
    sizes: list[int] = []

    def fake_run(tasks: list[Task], out: Path, workers: int) -> SuiteOutcome:
        sizes.append(len(tasks))
        return SuiteOutcome([], 0)

    monkeypatch.setattr("elevator_sim.cli.ensure_inputs", lambda *args: None)
    monkeypatch.setattr("elevator_sim.cli.run_suite", fake_run)

    assert main(["compare", "--suite", "--stage", stage, "--out", str(tmp_path / "out")]) == 0

    assert sizes == [size]


def stage_1_settings() -> list[tuple[str, str]]:
    return [
        (behaviour, algorithm)
        for behaviour in ("strict", "min_time", "weighted-0.5", "weighted-1", "weighted-2")
        for algorithm in ALL_ALGORITHMS
    ]


def test_spec_10_2_compare_on_one_file_runs_every_stage_1_configuration(tmp_path: Path) -> None:
    rows = read_rows(compare(tmp_path, "out") / "simulation_stats.csv")

    assert [
        (row["config_id"].split("__")[1], row["algorithm"]) for row in rows
    ] == stage_1_settings()


def test_spec_10_2_compare_on_one_file_keeps_the_files_building_and_guard(tmp_path: Path) -> None:
    file = tmp_path / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    config = tmp_path / "mine.toml"
    config.write_text(
        '[building]\nfloors = 9\ncapacity = 2\n\n[dispatch]\nalgorithm = "eta"\n'
        'behaviour = "weighted"\nfairness_weight = 0.5\nguard = "wait_expiry"\nwait_limit = 7\n',
        encoding="utf-8",
    )
    out = tmp_path / "out"

    compare_file(file, out, "--config", str(config))

    rows = read_rows(out / "simulation_stats.csv")
    assert len(rows) == 30
    assert {row["building"] for row in rows} == {"mine"}
    assert {(row["guard"], row["guard_value"]) for row in rows if row["behaviour"] != "strict"} == {
        ("wait_expiry", "7")
    }
    assert {row["guard"] for row in rows if row["behaviour"] == "strict"} == {"none"}


@pytest.mark.parametrize(
    ("options", "guard"),
    [
        ([], "none"),
        (["--guard", "skip_limit"], "skip_limit"),
        (["--guard", "wait_expiry"], "wait_expiry"),
    ],
)
@pytest.mark.parametrize(("phase", "size"), [("1", 6000), ("2", 4800), ("3", 7200)])
def test_tst17_an_earlier_suite_runs_with_no_guard_unless_one_is_given(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    size: int,
    options: list[str],
    guard: str,
) -> None:
    seen: list[list[Task]] = []

    def fake_run(tasks: list[Task], out: Path, workers: int) -> SuiteOutcome:
        seen.append(tasks)
        return SuiteOutcome([], 0)

    monkeypatch.setattr("elevator_sim.cli.ensure_inputs", lambda *args: None)
    monkeypatch.setattr("elevator_sim.cli.run_suite", fake_run)

    code = main(["compare", "--suite", "--phase", phase, *options, "--out", str(tmp_path / "out")])

    assert code == 0
    assert len(seen[0]) == size
    assert {t.config.guard_in_force for t in seen[0] if t.config.behaviour != "strict"} == {guard}


def test_tst17_the_phase_4_suite_refuses_a_guard_because_it_sets_its_own(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["compare", "--suite", "--guard", "none", "--out", str(tmp_path / "out")])

    assert code == 2
    assert "--guard" in capsys.readouterr().err
