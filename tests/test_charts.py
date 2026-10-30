"""TST-17 and TST-18: charts are produced, in fixed order, with one colour per algorithm."""

import random
from pathlib import Path

import pytest

from elevator_sim.cli import main
from elevator_sim.config import ALGORITHMS

SIX_ROWS = "time,id,source,dest\n0,a,1,5\n0,b,5,1\n2,c,3,8\n4,d,8,2\n9,e,1,9\n12,f,6,4\n"


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
