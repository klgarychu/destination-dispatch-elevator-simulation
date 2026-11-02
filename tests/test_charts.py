"""TST-17 and TST-18: charts are produced, in fixed order, with one colour per algorithm."""

import csv
import random
from pathlib import Path
from typing import Any

import pytest

from elevator_sim.cli import main
from elevator_sim.config import ALGORITHMS, ALL_ALGORITHMS, SimConfig, config_id
from elevator_sim.experiment import Task, run_suite
from elevator_sim.output import MANIFEST_FILE, read_manifest

SIX_ROWS = "time,id,source,dest\n0,a,1,5\n0,b,5,1\n2,c,3,8\n4,d,8,2\n9,e,1,9\n12,f,6,4\n"
ONE_ROW = "time,id,source,dest\n0,a,1,2\n"
TWO_ROWS = "time,id,source,dest\n0,b,1,3\n0,c,1,4\n"
EMPTY = "time,id,source,dest\n"


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

    pooled = pooled_times(out, read_manifest(out).runs, "custom")
    return {key: len(times["wait"]) for key, times in pooled.items()}


def sample_tasks(file: Path) -> list[Task]:
    """Every algorithm on one input, keeping full logs under the run ids the suite gives them."""
    configs = [SimConfig(algorithm=algorithm) for algorithm in ALGORITHMS]
    return [
        Task(f"{config_id(c)}__{file.stem}", c, 1, "custom", "up_peak", "heavy", 1, file, True)
        for c in configs
    ]


def test_m28_charts_show_only_the_own_limit_load(tmp_path: Path) -> None:
    own_file = write_input(tmp_path, "own.csv", SIX_ROWS)
    fixed_file = write_input(tmp_path, "fixed.csv", TWO_ROWS)
    configs = [SimConfig(algorithm=algorithm) for algorithm in ALGORITHMS]
    own = [
        Task(f"own_{c.algorithm}", c, 1, "custom", "uniform", "light", 1, own_file) for c in configs
    ]
    fixed = [
        Task(
            f"fixed_{c.algorithm}",
            c,
            1,
            "custom",
            "uniform",
            "light",
            1,
            fixed_file,
            load_basis="fixed",
        )
        for c in configs
    ]
    run_suite(own, tmp_path / "own_only", workers=1)
    run_suite(own + fixed, tmp_path / "both", workers=1)

    assert draw(tmp_path / "own_only", tmp_path / "own_charts") == 0
    assert draw(tmp_path / "both", tmp_path / "both_charts") == 0

    drawn = sorted(path.name for path in (tmp_path / "own_charts").glob("*.png"))
    assert drawn
    for name in drawn:
        assert (tmp_path / "both_charts" / name).read_bytes() == (
            tmp_path / "own_charts" / name
        ).read_bytes()


def test_tst17_chart_data_holds_exactly_the_runs_in_the_report(tmp_path: Path) -> None:
    out = tmp_path / "out"
    compare(write_input(tmp_path, "first.csv", ONE_ROW), out)
    compare(write_input(tmp_path, "second.csv", TWO_ROWS), out)

    with (out / "simulation_stats.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert read_manifest(out).runs == [row["run_id"] for row in rows]
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


def test_tst17_charts_stop_on_a_saved_run_they_cannot_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    compare(write_input(tmp_path, "input.csv", SIX_ROWS), out)
    (out / "runs" / "eta__min_time__skip_limit-2-hold__none__input.json").unlink()

    assert draw(out, tmp_path / "charts") == 2

    assert "run compare" in capsys.readouterr().err


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


def uniform_task(
    run_id: str, algorithm: str, load: str, file: Path, seed: int = 1, max_ticks: int | None = None
) -> Task:
    config = SimConfig(algorithm=algorithm, max_ticks=max_ticks)
    return Task(run_id, config, 1, "custom", "uniform", load, seed, file)


def test_tst17_charts_write_nothing_for_a_comparison_with_no_passengers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out, charts = tmp_path / "out", tmp_path / "charts"
    compare(write_input(tmp_path, "busy.csv", SIX_ROWS), out)
    assert draw(out, charts) == 0
    compare(write_input(tmp_path, "empty.csv", EMPTY), out)
    capsys.readouterr()

    assert draw(out, charts) == 0

    assert "no passengers" in capsys.readouterr().out
    assert list(charts.glob("*.png")) == []


def test_tst17_charts_refuse_a_comparison_with_a_run_that_did_not_finish(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out, charts = tmp_path / "out", tmp_path / "charts"
    file = write_input(tmp_path, "input.csv", SIX_ROWS)
    run_suite(
        [
            uniform_task("eta_light", "eta", "light", file),
            uniform_task("rr_light", "round_robin", "light", file),
            uniform_task("eta_heavy", "eta", "heavy", file),
            uniform_task("rr_heavy", "round_robin", "heavy", file, max_ticks=1),
        ],
        out,
        1,
    )

    assert draw(out, charts) == 2

    assert "rr_heavy" in capsys.readouterr().err
    assert not charts.exists()


def test_tst17_charts_refuse_a_comparison_missing_a_whole_algorithm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    file = write_input(tmp_path, "input.csv", SIX_ROWS)
    run_suite(
        [
            uniform_task(name, name, "light", file, max_ticks=1 if name == "eta" else None)
            for name in ALGORITHMS
        ],
        out,
        1,
    )

    assert draw(out, tmp_path / "charts") == 2

    assert "eta" in capsys.readouterr().err


def test_tst17_charts_refuse_a_comparison_with_fewer_seeds_for_one_algorithm(
    tmp_path: Path,
) -> None:
    out = tmp_path / "out"
    file = write_input(tmp_path, "input.csv", SIX_ROWS)
    tasks = [uniform_task(f"eta{seed}", "eta", "light", file, seed) for seed in (1, 2, 3)]
    tasks += [
        uniform_task(f"rr{seed}", "round_robin", "light", file, seed, 1 if seed > 1 else None)
        for seed in (1, 2, 3)
    ]
    run_suite(tasks, out, 1)

    assert draw(out, tmp_path / "charts") == 2


def test_tst17_refused_charts_leave_earlier_charts_in_place(tmp_path: Path) -> None:
    out, charts = tmp_path / "out", tmp_path / "charts"
    file = write_input(tmp_path, "input.csv", SIX_ROWS)
    run_suite([uniform_task(name, name, "light", file) for name in ALGORITHMS], out, 1)
    assert draw(out, charts) == 0
    earlier = sorted(path.name for path in charts.glob("*.png"))
    run_suite([uniform_task("eta", "eta", "light", file, max_ticks=1)], out, 1)

    assert draw(out, charts) == 2

    assert sorted(path.name for path in charts.glob("*.png")) == earlier


def test_tst17_charts_draw_the_rest_when_one_input_has_no_passengers(tmp_path: Path) -> None:
    out, charts = tmp_path / "out", tmp_path / "charts"
    busy = write_input(tmp_path, "busy.csv", SIX_ROWS)
    empty = write_input(tmp_path, "empty.csv", EMPTY)
    tasks = [uniform_task(f"{name}_busy", name, "light", busy) for name in ALGORITHMS]
    tasks += [uniform_task(f"{name}_empty", name, "heavy", empty) for name in ALGORITHMS]
    run_suite(tasks, out, 1)

    assert draw(out, charts) == 0

    assert len(list(charts.glob("*.png"))) == 4


def test_tst17_charts_draw_a_finished_comparison_with_uneven_combinations(tmp_path: Path) -> None:
    out, charts = tmp_path / "out", tmp_path / "charts"
    file = write_input(tmp_path, "input.csv", SIX_ROWS)
    run_suite(
        [
            uniform_task("eta_light", "eta", "light", file),
            uniform_task("rr_light", "round_robin", "light", file),
            uniform_task("eta_heavy", "eta", "heavy", file),
        ],
        out,
        1,
    )

    assert draw(out, charts) == 0

    assert (charts / "distributions_custom.png").exists()


@pytest.mark.parametrize("contents", ["not json", '["an", "old", "list"]', '{"runs": []}'])
def test_tst17_charts_stop_on_a_run_list_they_cannot_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], contents: str
) -> None:
    out = tmp_path / "out"
    compare(write_input(tmp_path, "input.csv", SIX_ROWS), out)
    (out / MANIFEST_FILE).write_text(contents, encoding="utf-8")

    assert draw(out, tmp_path / "charts") == 2

    assert "run compare" in capsys.readouterr().err


@pytest.mark.parametrize("fonts", [["Segoe UI", "DejaVu Sans"], ["DejaVu Sans"]])
def test_tst18_titles_notes_and_legends_fit_a_chart_of_one_input(
    stats: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fonts: list[str]
) -> None:
    import matplotlib.pyplot as plt

    kept: list[Any] = []
    monkeypatch.setattr("elevator_sim.charts.FONTS", fonts)
    monkeypatch.setattr("elevator_sim.charts.plt.close", kept.append)

    assert draw(stats, tmp_path) == 0

    assert len(kept) == 4
    for figure in kept:
        renderer = figure.canvas.get_renderer()
        for artist in [*figure.texts, *figure.legends]:
            assert artist.get_window_extent(renderer).x1 <= figure.bbox.x1
    monkeypatch.undo()
    plt.close("all")


def test_m32_only_the_fairness_chart_shows_other_seat_behaviours(tmp_path: Path) -> None:
    file = write_input(tmp_path, "input.csv", SIX_ROWS)

    def tasks(behaviour: str, weight: float | None) -> list[Task]:
        configs = [
            SimConfig(algorithm=name, behaviour=behaviour, fairness_weight=weight)
            for name in ALGORITHMS
        ]
        return [
            Task(f"{config_id(c)}_run", c, 1, "custom", "uniform", "light", 1, file)
            for c in configs
        ]

    plain = tasks("min_time", None)
    run_suite(plain, tmp_path / "one", workers=1)
    run_suite(plain + tasks("strict", None) + tasks("weighted", 2.0), tmp_path / "three", workers=1)

    assert draw(tmp_path / "one", tmp_path / "one_charts") == 0
    assert draw(tmp_path / "three", tmp_path / "three_charts") == 0

    drawn = sorted(path.name for path in (tmp_path / "one_charts").glob("*.png"))
    assert "fairness_vs_efficiency_custom.png" in drawn
    for name in drawn:
        same = (tmp_path / "three_charts" / name).read_bytes() == (
            tmp_path / "one_charts" / name
        ).read_bytes()
        assert same == (not name.startswith("fairness"))


def test_m32_each_seat_setting_has_its_own_marker() -> None:
    from elevator_sim.charts import SETTING_MARKERS

    assert list(SETTING_MARKERS) == [
        "strict",
        "min_time",
        "weighted 0.5",
        "weighted 1",
        "weighted 2",
    ]
    assert len(set(SETTING_MARKERS.values())) == 5


def test_review_15_chart_notes_call_the_seed_range_descriptive_not_a_test() -> None:
    from elevator_sim.charts import SPREAD_NOTE

    assert "noise" not in SPREAD_NOTE
    assert "isn't a significance test" in SPREAD_NOTE


def test_tst18_each_algorithm_has_one_distinct_colour_and_marker() -> None:
    from elevator_sim.charts import COLOURS, MARKERS

    assert list(COLOURS) == list(ALL_ALGORITHMS)
    assert len(set(COLOURS.values())) == len(ALL_ALGORITHMS)
    assert list(MARKERS) == list(ALL_ALGORITHMS)
    assert len(set(MARKERS.values())) == len(ALL_ALGORITHMS)


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
