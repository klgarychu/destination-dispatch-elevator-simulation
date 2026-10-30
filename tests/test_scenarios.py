"""TST-13: the starvation scenarios that apply before guards exist."""

import hypothesis.strategies as st
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import DrawFn

from elevator_sim.config import ALGORITHMS, SimConfig
from elevator_sim.engine import simulate
from elevator_sim.metrics import total_time, wait_time
from elevator_sim.requests import Request
from elevator_sim.workload import generate_requests
from helpers import assert_rules_hold, requests_at


def overload_ramp(floors: int) -> list[Request]:
    """Arrivals that rise past saturation in four steps of 150 ticks."""
    requests: list[Request] = []
    for step, rate in enumerate((0.5, 1.5, 3.0, 5.0)):
        for request in generate_requests("lunch", rate, 150, 40 + step, floors):
            time = request.time + 150 * step
            requests.append(Request(time, f"r{len(requests)}", request.source, request.dest))
    return requests


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_tst13_overload_ramp_serves_everyone_with_no_max_ticks_error(algorithm: str) -> None:
    config = SimConfig(algorithm=algorithm)
    requests = overload_ramp(config.floors)

    result = simulate(requests, config)

    assert len(result.passengers) == len(requests)
    assert_rules_hold(result, config.capacity, config.floors)
    assert sum(p.times_left_behind for p in result.passengers) > 0


@st.composite
def roomy_scenarios(draw: DrawFn) -> tuple[SimConfig, list[Request]]:
    """Capacity above the passenger count, so seats are never short."""
    floors = draw(st.integers(2, 15))
    count = draw(st.integers(1, 30))
    config = SimConfig(
        floors=floors,
        elevators=draw(st.integers(1, 3)),
        capacity=count + 1,
        start_floor=draw(st.integers(1, floors)),
        algorithm=draw(st.sampled_from(ALGORITHMS)),
    )
    requests = []
    for index in range(count):
        source = draw(st.integers(1, floors))
        dest = draw(st.integers(1, floors).filter(lambda floor, s=source: floor != s))
        requests.append(Request(draw(st.integers(0, 50)), f"p{index}", source, dest))
    return config, requests


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(roomy_scenarios())
def test_tst13_with_seats_to_spare_wait_and_total_stay_inside_the_bounds(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario
    span = config.floors - 1

    result = simulate(requests, config)

    for passenger in result.passengers:
        assert wait_time(passenger) < 2 * span
        assert total_time(passenger) < 3 * span


def test_tst13_without_a_guard_a_long_ride_can_be_skipped_repeatedly() -> None:
    # One car with one seat. A long ride waits at floor 1 while short rides keep arriving, and
    # min_time gives each seat to the shortest ride. This is the gap guards close in Phase 4.
    rows = [(0, 1, 10)] + [(tick, 1, 2) for tick in range(0, 40, 2)]
    config = SimConfig(elevators=1, capacity=1, algorithm="round_robin")

    result = simulate(requests_at(*rows), config)

    assert result.passengers[0].times_left_behind >= 5
