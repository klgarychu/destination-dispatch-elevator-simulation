"""TST-18: reports state numbers in fixed order and never rank or pick a winner."""

import re
from pathlib import Path

import pytest

from elevator_sim.config import ALGORITHMS, SimConfig, config_id
from elevator_sim.report import render_report


def row(
    algorithm: str, total_mean: float, *, seed: int = 1, unguarded: bool = True
) -> dict[str, object]:
    return {
        "config_id": config_id(SimConfig(algorithm=algorithm)),
        "algorithm": algorithm,
        "behaviour": "min_time",
        "building": "baseline",
        "pattern": "lunch",
        "load": "heavy",
        "seed": seed,
        "unguarded": unguarded,
        "passengers": 100,
        "total_mean": total_mean,
        "wait_mean": total_mean - 4,
        "wait_p95": 40,
        "wait_max": 90,
        "jain_wait": 0.5,
        "times_left_behind": 3,
    }


def rows_scrambled_by_value() -> list[dict[str, object]]:
    values = dict(zip(ALGORITHMS, (50.0, 10.0, 40.0, 20.0, 30.0), strict=True))
    return [row(name, values[name]) for name in reversed(ALGORITHMS)]


def test_tst18_tables_keep_the_fixed_order_whatever_the_values() -> None:
    report = render_report(rows_scrambled_by_value())

    positions = [report.index(f"| `{name}` ") for name in ALGORITHMS]
    assert positions == sorted(positions)


@pytest.mark.parametrize(
    "word", ["rank", "winner", "best", "worst", "fastest", "slowest", "top", "lowest", "highest"]
)
def test_tst18_report_contains_no_ranking_language(word: str) -> None:
    report = render_report(rows_scrambled_by_value())

    assert not re.search(rf"\b{word}\b", report, re.IGNORECASE)


def test_tst18_report_doesnt_highlight_any_value() -> None:
    report = render_report(rows_scrambled_by_value())

    tables = "\n".join(line for line in report.splitlines() if line.startswith("|"))
    assert "**" not in tables
    assert "*" not in tables


def test_report_states_input_counts_and_seeds() -> None:
    report = render_report([row("eta", 10.0, seed=1), row("eta", 12.0, seed=2)])

    assert "Runs: 2" in report
    assert "Inputs: 2" in report
    assert "Configurations: 1" in report
    assert "Seeds: 1, 2" in report


def test_report_says_which_runs_were_unguarded() -> None:
    assert "Unguarded runs: 2 of 2" in render_report([row("eta", 1.0), row("zone_based", 2.0)])
    assert "Unguarded runs: 0 of 1" in render_report([row("eta", 1.0, unguarded=False)])


def test_report_says_a_comparison_is_incomplete_and_names_the_missing_runs() -> None:
    rows = rows_scrambled_by_value()

    report = render_report(rows, not_finished=["zone_light", "eta_heavy"])

    assert "Incomplete comparison: 2 of 7 runs didn't finish" in report
    assert "`zone_light`, `eta_heavy`" in report


def test_report_has_no_incomplete_notice_when_every_run_finished() -> None:
    assert "Incomplete" not in render_report(rows_scrambled_by_value())


def test_report_has_one_section_per_building_pattern_and_load() -> None:
    other = {**row("eta", 1.0), "load": "light"}

    report = render_report([row("eta", 2.0), other])

    assert "## baseline, lunch, heavy" in report
    assert "## baseline, lunch, light" in report


def test_report_gives_the_mean_and_the_spread_across_seeds() -> None:
    report = render_report([row("eta", 10.0, seed=1), row("eta", 14.0, seed=2)])

    assert "| `eta` " in report
    assert "12.00 (10.00 to 14.00)" in report


def test_report_explains_that_wait_and_total_differ_by_a_fixed_distance() -> None:
    assert "fixed" in render_report([row("eta", 1.0)])


def test_report_is_lf_and_ends_with_a_newline(tmp_path: Path) -> None:
    report = render_report([row("eta", 1.0)])

    assert report.endswith("\n")
    assert "\r" not in report
