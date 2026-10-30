"""Statistics, checked against the PDF sample's hand-calculated values in spec section 15.2."""

import pytest

from elevator_sim.config import SimConfig
from elevator_sim.engine import simulate
from elevator_sim.metrics import jain_index, nearest_rank, observations, run_stats, time_stats
from elevator_sim.requests import Request

PDF_SAMPLE = [
    Request(0, "passenger1", 1, 51),
    Request(0, "passenger2", 1, 37),
    Request(10, "passenger3", 20, 1),
]
ONE_CAR = SimConfig(floors=60, elevators=1, capacity=6, algorithm="round_robin")


def test_tst05_time_statistics_match_the_worked_example() -> None:
    wait = time_stats([0, 0, 71])
    total = time_stats([50, 36, 90])

    assert wait is not None
    assert (wait.min, wait.max, wait.p95) == (0, 71, 71)
    assert wait.mean == pytest.approx(23.67, abs=0.005)
    assert wait.stdev == pytest.approx(33.47, abs=0.005)
    assert total is not None
    assert (total.min, total.max, total.p95) == (36, 90, 90)
    assert total.mean == pytest.approx(58.67, abs=0.005)
    assert total.stdev == pytest.approx(22.88, abs=0.005)


def test_tst05_no_passengers_give_no_statistics() -> None:
    assert time_stats([]) is None


@pytest.mark.parametrize(
    ("values", "percent", "expected"),
    [
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95, 10),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 90, 9),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50, 5),
        ([7], 95, 7),
        (list(range(1, 21)), 95, 19),
    ],
)
def test_tst05_percentiles_use_the_nearest_rank(
    values: list[int], percent: int, expected: int
) -> None:
    assert nearest_rank(values, percent) == expected


def test_tst05_jain_index() -> None:
    assert jain_index([5, 5, 5]) == 1
    assert jain_index([0, 0, 71]) == pytest.approx(1 / 3)
    assert jain_index([0, 0, 0]) == 1


def test_tst05_run_statistics_for_the_pdf_sample() -> None:
    stats = run_stats(simulate(PDF_SAMPLE, ONE_CAR))

    assert stats["passengers"] == 3
    assert stats["ticks"] == 100
    assert stats["passengers_per_tick"] == pytest.approx(0.03)
    assert stats["wait_min"] == 0
    assert stats["wait_max"] == 71
    assert stats["wait_mean"] == pytest.approx(23.6667, abs=0.0001)
    assert stats["total_stdev"] == pytest.approx(22.8813, abs=0.0001)
    # 36 moves with 2 riders, 14 with 1, 31 empty and 19 with 1: 105 rider moves over 100 moves.
    assert stats["avg_car_load"] == pytest.approx(1.05)
    assert stats["empty_travel_share"] == pytest.approx(0.31)
    assert stats["jain_wait"] == pytest.approx(1 / 3, abs=0.0001)
    assert stats["jain_total"] == pytest.approx(0.8680, abs=0.0001)
    assert stats["times_left_behind"] == 0
    assert stats["max_left_behind_one_passenger"] == 0


def test_tst05_left_behind_counts_come_from_passengers() -> None:
    requests = [Request(0, "a", 1, 3), Request(0, "b", 1, 2)]
    config = SimConfig(floors=5, elevators=1, capacity=1, algorithm="round_robin")

    stats = run_stats(simulate(requests, config))

    assert stats["times_left_behind"] == 1
    assert stats["max_left_behind_one_passenger"] == 1


def test_r20_observations_state_plain_facts_about_one_run() -> None:
    notes = observations(simulate(PDF_SAMPLE, ONE_CAR))

    assert notes == [
        "Longest wait: passenger3 at 71 ticks",
        "Busiest source floor: 1 with 2 passengers",
        "Peak passengers waiting: 1",
        "Share with zero wait: 66.7%",
        "Times left behind: 0",
    ]


def test_i5_no_passengers_give_no_observations() -> None:
    assert observations(simulate([], ONE_CAR)) == []
