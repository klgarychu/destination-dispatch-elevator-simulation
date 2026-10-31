"""TST-17 and TST-18: charts are produced, in fixed order, with one colour per algorithm."""

import csv
import random
from pathlib import Path

import pytest

from elevator_sim.cli import main
from elevator_sim.config import ALGORITHMS, SimConfig, config_id
from elevator_sim.experiment import Task, run_suite
from elevator_sim.output import MANIFEST_FILE, read_manifest

SIX_ROWS = "time,id,source,dest\n0,a,1,5\n0,b,5,1\n2,c,3,8\n4,d,8,2\n9,e,1,9\n12,f,6,4\n"
ONE_ROW = "time,id,source,dest\n0,a,1,2\n"
TWO_ROWS = "time,id,source,dest\n0,b,1,3\n0,c,1,4\n"


@pytest.fixture(scope="module")
def stats(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("charts")
    file = base / "input.csv"
    file.write_text(SIX_ROWS, encoding="utf-8")
    out = base / "results"
    assert main(["compare", "--requests", str(file), "--out", str(out), "--workers", "1"]) == 0
    return out


def test_tst17_charts_command_writes_each_chart_for_each_building(
    stats: Path, tmp_path: Path
) -> None:
    assert main(["charts", "--stats", str(stats), "--out", str(tmp_path)]) == 0

    names = sorted(path.name for path in tmp_path.glob("*.png"))
    assert names == [
        "algorithm_comparison_custom.png",
        "distributions_custom.png",
        "fairness_vs_efficiency_custom.png",
        "load_response_custom.png",
    ]
    assert all(path.stat().st_size > 1000 for path in tmp_path.glob("*.png"))


def test_tst17_charts_on_missing_statistics_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["charts", "--stats", str(tmp_path / "absent"), "--out", str(tmp_path)]) == 2
    assert "absent" in capsys.readouterr().err


def write_input(folder: Path, name: str, rows: str) -> Path:
    file = folder / name
    file.write_text(rows, encoding="utf-8")
    return file


def compare(file: Path, out: Path) -> None:
    assert main(["compare", "--requests", str(file), "--out", str(out), "--workers", "1"]) == 0


def draw(out: Path, charts: Path) -> int:
    return main(["charts", "--stats", str(out), "--out", str(charts)])


def passengers_charted(out: Path) -> dict[tuple[str, str], int]:
    from elevator_sim.charts import pooled_times

    pooled = pooled_times(out, read_manifest(out), "custom")
    return {key: len(times["wait"]) for key, times in pooled.items()}


def sample_tasks(file: Path) -> list[Task]:
    """Every algorithm on one input, keeping full logs under the run ids the suite gives them."""
    configs = [SimConfig(algorithm=algorithm) for algorithm in ALGORITHMS]
    return [
        Task(f"{config_id(c)}__{file.stem}", c, 1, "custom", "up_peak", "heavy", 1, file, True)
        for c in configs
    ]


def test_tst17_chart_data_holds_exactly_the_runs_in_the_report(tmp_path: Path) -> None:
    out = tmp_path / "out"
    compare(write_input(tmp_path, "first.csv", ONE_ROW), out)
    compare(write_input(tmp_path, "second.csv", TWO_ROWS), out)

    with (out / "simulation_stats.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert read_manifest(out) == [row["run_id"] for row in rows]
    assert passengers_charted(out) == {("custom", name): 2 for name in ALGORITHMS}


def test_tst17_a_narrower_comparison_keeps_other_runs_on_disk_but_out_of_the_charts(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    file = write_input(tmp_path, "input.csv", SIX_ROWS)
    wide = [
        Task(f"seed{seed}", SimConfig(algorithm="eta"), 1, "custom", "uniform", "light", seed, file)
        for seed in (1, 2)
    ]
    run_suite(wide, out, workers=1)

    run_suite(wide[:1], out, workers=1)

    assert passengers_charted(out) == {("light", "eta"): 6}
    assert (out / "runs" / "seed2.json").exists()
    assert run_suite(wide, out, workers=1).reused == 2
    assert passengers_charted(out) == {("light", "eta"): 12}


def test_tst17_a_run_left_by_an_earlier_comparison_does_not_break_the_charts(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    file = write_input(tmp_path, "input.csv", SIX_ROWS)
    leftover = Task("old", SimConfig(algorithm="eta"), 1, "custom", "uniform", "heavy", 1, file)
    run_suite([leftover], out, workers=1)
    compare(file, out)

    assert draw(out, tmp_path / "charts") == 0


def test_tst17_car_movement_is_drawn_from_a_sample_in_the_comparison(tmp_path: Path) -> None:
    out = tmp_path / "out"
    run_suite(sample_tasks(write_input(tmp_path, "custom_up_peak_heavy_s1.csv", SIX_ROWS)), out, 1)

    assert draw(out, tmp_path / "charts") == 0

    assert (tmp_path / "charts" / "car_movement_custom.png").exists()


def test_tst17_car_movement_is_not_drawn_from_a_sample_left_by_an_earlier_comparison(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    run_suite(sample_tasks(write_input(tmp_path, "custom_up_peak_heavy_s1.csv", SIX_ROWS)), out, 1)
    compare(write_input(tmp_path, "other.csv", SIX_ROWS), out)

    assert draw(out, tmp_path / "charts") == 0

    assert not (tmp_path / "charts" / "car_movement_custom.png").exists()


def test_tst17_charts_replace_their_own_earlier_files_and_leave_others_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out, charts = tmp_path / "out", tmp_path / "charts"
    run_suite(sample_tasks(write_input(tmp_path, "custom_up_peak_heavy_s1.csv", SIX_ROWS)), out, 1)
    assert draw(out, charts) == 0
    (charts / "my_notes.png").write_bytes(b"not a chart")
    compare(write_input(tmp_path, "other.csv", SIX_ROWS), out)
    capsys.readouterr()

    assert draw(out, charts) == 0

    assert "Wrote 4 charts" in capsys.readouterr().out
    assert not (charts / "car_movement_custom.png").exists()
    assert (charts / "my_notes.png").exists()


def test_tst17_charts_stop_on_a_folder_with_no_finished_comparison(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out, charts = tmp_path / "out", tmp_path / "charts"
    compare(write_input(tmp_path, "input.csv", SIX_ROWS), out)
    assert draw(out, charts) == 0
    (out / MANIFEST_FILE).unlink()
    capsys.readouterr()

    assert draw(out, charts) == 2

    assert "run compare" in capsys.readouterr().err
    assert (charts / "load_response_custom.png").exists()


def test_tst17_an_interrupted_compare_leaves_no_old_run_list_beside_changed_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    file = write_input(tmp_path, "input.csv", SIX_ROWS)
    compare(file, out)

    def interrupted(*_: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("elevator_sim.experiment.run_tasks", interrupted)
    with pytest.raises(KeyboardInterrupt):
        compare(file, out)

    assert draw(out, tmp_path / "charts") == 2


def test_tst18_each_algorithm_has_one_distinct_colour_and_marker() -> None:
    from elevator_sim.charts import COLOURS, MARKERS

    assert list(COLOURS) == list(ALGORITHMS)
    assert len(set(COLOURS.values())) == 5
    assert list(MARKERS) == list(ALGORITHMS)
    assert len(set(MARKERS.values())) == 5


def test_tst18_chart_order_is_fixed_whatever_order_the_data_arrives_in() -> None:
    from elevator_sim.charts import fixed_order

    scrambled = list(ALGORITHMS)
    random.Random(4).shuffle(scrambled)

    assert fixed_order(scrambled) == list(ALGORITHMS)


def test_tst18_chart_titles_contain_no_ranking_language() -> None:
    from elevator_sim.charts import TITLES

    words = {"rank", "winner", "best", "worst", "fastest", "slowest", "lowest", "highest"}
    for title in TITLES.values():
        assert not words & set(title.lower().split())


def test_wait_and_total_charts_are_labelled_as_differing_by_a_fixed_distance() -> None:
    from elevator_sim.charts import FIXED_DISTANCE_NOTE

    assert "fixed" in FIXED_DISTANCE_NOTE
