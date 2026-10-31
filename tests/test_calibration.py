"""G15 and M23: calibration measures backlog growth, and is honest about what it finds."""

import pytest

from elevator_sim.calibration import (
    backlog_at,
    backlog_growth,
    check_load_levels,
    find_rate_boundary,
)
from elevator_sim.config import ConfigError, SimConfig
from elevator_sim.engine import simulate
from elevator_sim.requests import Request
from elevator_sim.workload import generate_requests


def test_backlog_counts_passengers_still_travelling_at_the_tick() -> None:
    requests = [Request(0, "a", 1, 3), Request(0, "b", 1, 9)]
    result = simulate(requests, SimConfig(elevators=1, algorithm="round_robin"))

    assert backlog_at(result, 1) == 2
    assert backlog_at(result, 2) == 1
    assert backlog_at(result, 8) == 0


def test_backlog_leaves_out_passengers_who_have_not_requested_yet() -> None:
    # a is delivered at tick 2. b requests at tick 5, and the car fetches them from floor 3.
    requests = [Request(0, "a", 1, 3), Request(5, "b", 1, 2)]
    result = simulate(requests, SimConfig(elevators=1, algorithm="round_robin"))

    assert backlog_at(result, 1) == 1
    assert backlog_at(result, 3) == 0
    assert backlog_at(result, 6) == 1
    assert backlog_at(result, 8) == 0


def test_a_flooded_car_shows_a_growing_backlog_and_a_quiet_car_does_not() -> None:
    # min_time favours short hops, so one seat carries under 0.5 passengers a tick. At 1.0 arrivals
    # a tick, about 500 arrive between ticks 500 and 1,000 and at most about 250 leave, so the
    # backlog must grow by well over 150. At 0.02 a tick the car keeps up.
    config = SimConfig(elevators=1, capacity=1, algorithm="round_robin")

    quiet = simulate(generate_requests("uniform", 0.02, 1000, 1, 10), config)
    flooded = simulate(generate_requests("uniform", 1.0, 1000, 1, 10), config)

    assert -2 <= backlog_growth(quiet) <= 2
    assert backlog_growth(flooded) > 150


def test_the_search_finds_where_one_hundredth_more_fails() -> None:
    assert find_rate_boundary(lambda rate: rate <= 0.37) == pytest.approx(0.37)
    assert find_rate_boundary(lambda rate: rate <= 2.91) == pytest.approx(2.91)


def test_the_search_accepts_the_lowest_rate_once_it_has_really_passed() -> None:
    assert find_rate_boundary(lambda rate: rate <= 0.01) == pytest.approx(0.01)


def test_the_search_tests_the_lowest_rate_and_refuses_if_nothing_passes() -> None:
    tested: list[float] = []

    def passes(rate: float) -> bool:
        tested.append(rate)
        return False

    with pytest.raises(ConfigError, match="no passing rate"):
        find_rate_boundary(passes)

    assert tested == [0.01]


def test_the_search_stops_and_refuses_if_nothing_fails() -> None:
    tested: list[float] = []

    def passes(rate: float) -> bool:
        tested.append(rate)
        assert len(tested) < 40, "the search is not stopping"
        return True

    with pytest.raises(ConfigError, match="no failing rate"):
        find_rate_boundary(passes)


def test_the_search_finds_one_edge_when_a_higher_rate_also_passes() -> None:
    def passes(rate: float) -> bool:
        return rate <= 0.50 or 1.00 <= rate <= 1.20

    found = find_rate_boundary(passes)

    assert found == pytest.approx(0.50)
    assert passes(found)
    assert not passes(found + 0.01)


def test_a_rate_is_accepted_when_heavy_passes_and_overload_fails() -> None:
    check_load_levels(2.0, lambda rate: rate <= 2.0)


def test_a_rate_is_refused_when_heavy_load_does_not_keep_up() -> None:
    with pytest.raises(ConfigError, match="heavy"):
        check_load_levels(2.0, lambda rate: rate < 1.0)


def test_a_rate_is_refused_when_overload_is_not_past_capacity() -> None:
    with pytest.raises(ConfigError, match="overload"):
        check_load_levels(2.0, lambda rate: True)
