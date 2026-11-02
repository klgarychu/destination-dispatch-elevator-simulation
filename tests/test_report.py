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
        "building": "3car-10floor-6cap",
        "pattern": "lunch",
        "load": "heavy",
        "load_basis": "own_limit",
        "fairness_weight": None,
        "seed": seed,
        "stage": 1,
        "guard": "none",
        "guard_value": None,
        "seat_hold": False,
        "unguarded": unguarded,
        "passengers": 100,
        "total_mean": total_mean,
        "wait_mean": total_mean - 4,
        "wait_min": 1,
        "wait_p95": 40,
        "wait_max": 90,
        "total_min": 2,
        "total_max": 95,
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
    assert "Case and input pairs: 2" in report
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

    assert "## 3car-10floor-6cap, lunch, heavy" in report
    assert "## 3car-10floor-6cap, lunch, light" in report


def test_m28_fixed_load_sections_are_labelled_and_follow_the_own_limit_ones() -> None:
    fixed = {**row("eta", 1.0), "load_basis": "fixed", "pattern": "uniform"}

    report = render_report([fixed, row("eta", 2.0)])

    own_section = report.index("## 3car-10floor-6cap, lunch, heavy\n")
    assert own_section < report.index("## 3car-10floor-6cap, uniform, heavy, fixed load\n")


def test_m28_the_report_explains_the_fixed_load_only_when_it_ran() -> None:
    fixed = {**row("eta", 1.0), "load_basis": "fixed"}

    assert "the same arrivals" in render_report([row("eta", 2.0), fixed])
    assert "the same arrivals" not in render_report([row("eta", 2.0)])


def test_gate_1_the_report_gives_the_minimum_and_maximum_the_assignment_asks_for() -> None:
    report = render_report([row("eta", 10.0)])

    assert "Min wait" in report
    assert "Max wait" in report
    assert "Min total" in report
    assert "Max total" in report


def test_m30_express_cases_are_listed_after_the_phase_1_cases() -> None:
    express = {**row("eta", 1.0), "building": "3car-60floor-6cap-split30"}

    report = render_report([express, row("eta", 2.0)])

    assert report.index("## 3car-10floor-6cap,") < report.index("## 3car-60floor-6cap-split30,")


def test_review_15_the_report_calls_the_seed_range_descriptive_not_a_test() -> None:
    report = render_report([row("eta", 10.0)])

    assert "noise" not in report
    assert "isn't a significance test" in report


def test_m32_behaviours_appear_in_a_fixed_order_whatever_the_values() -> None:
    def setting(behaviour: str, weight: float | None, total: float) -> dict[str, object]:
        config = SimConfig(behaviour=behaviour, fairness_weight=weight)
        fields = {"config_id": config_id(config), "behaviour": behaviour, "fairness_weight": weight}
        return {**row("marginal_insertion", total), **fields}

    report = render_report(
        [
            setting("weighted", 2.0, 5.0),
            setting("min_time", None, 1.0),
            setting("weighted", 0.5, 9.0),
            setting("strict", None, 7.0),
        ]
    )

    places = [
        report.index(name) for name in ("`strict`", "`min_time`", "`weighted 0.5`", "`weighted 2`")
    ]
    assert places == sorted(places)


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


def guarded(
    guard: str, value: int | str | None, hold: bool, total_mean: float
) -> dict[str, object]:
    config = SimConfig(
        algorithm="marginal_insertion",
        guard=guard,
        seat_hold=hold,
        **({"skip_limit": value} if guard == "skip_limit" else {}),  # type: ignore[arg-type]
        **({"wait_limit": value} if guard == "wait_expiry" else {}),  # type: ignore[arg-type]
    )
    return {
        **row("marginal_insertion", total_mean),
        "config_id": config_id(config),
        "stage": 2,
        "guard": guard,
        "guard_value": value,
        "seat_hold": hold and guard != "none",
        "unguarded": guard == "none",
    }


STAGE_2_ORDER = [
    ("none", None, True),
    ("skip_limit", 1, True),
    ("skip_limit", 2, True),
    ("skip_limit", 3, True),
    ("wait_expiry", "1rt", True),
    ("wait_expiry", "2rt", True),
    ("wait_expiry", "3rt", True),
    ("skip_limit", 2, False),
    ("wait_expiry", "2rt", False),
]


def test_tst16_stage_2_has_its_own_sections_after_stage_1() -> None:
    report = render_report([guarded("skip_limit", 2, True, 5.0), row("eta", 2.0)])

    stage_1 = report.index("## 3car-10floor-6cap, lunch, heavy\n")
    assert stage_1 < report.index("## Stage 2: 3car-10floor-6cap, lunch, heavy\n")


def test_tst18_stage_2_lists_guard_settings_in_the_spec_order_whatever_the_values() -> None:
    rows = [
        guarded(guard, value, hold, total_mean=100.0 - index)
        for index, (guard, value, hold) in reversed(list(enumerate(STAGE_2_ORDER)))
    ]

    report = render_report(rows)

    labels = [
        "`none`",
        "`skip_limit 1, hold`",
        "`skip_limit 2, hold`",
        "`skip_limit 3, hold`",
        "`wait_expiry 1rt, hold`",
        "`wait_expiry 2rt, hold`",
        "`wait_expiry 3rt, hold`",
        "`skip_limit 2, no hold`",
        "`wait_expiry 2rt, no hold`",
    ]
    positions = [report.index(f"| {label} |") for label in labels]
    assert positions == sorted(positions)


def test_tst16_every_table_names_the_guard_of_each_row() -> None:
    report = render_report([row("eta", 2.0), guarded("skip_limit", 2, True, 5.0)])

    assert "| Algorithm | Behaviour | Guard | Seeds |" in report
    assert "| `eta` | `min_time` | `none` | 1 |" in report
