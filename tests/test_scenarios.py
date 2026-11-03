"""TST-13: the starvation scenarios, with and without guards."""

from dataclasses import replace

import hypothesis.strategies as st
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import DrawFn

from elevator_sim.config import ALGORITHMS, ALL_ALGORITHMS, SimConfig
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


SHORTAGE = [Request(0, "a", 1, 3), Request(0, "b", 1, 2)]


@pytest.mark.parametrize(
    ("behaviour", "weight", "expected"),
    [
        ("strict", None, {"a": (0, 2), "b": (4, 5)}),
        ("min_time", None, {"a": (2, 4), "b": (0, 1)}),
    ],
)
def test_tst08_the_seat_shortage_fixture(
    behaviour: str, weight: float | None, expected: dict[str, tuple[int, int]]
) -> None:
    config = SimConfig(
        floors=5, elevators=1, capacity=1, behaviour=behaviour, fairness_weight=weight
    )

    result = simulate(SHORTAGE, config)

    assert {p.request.id: (wait_time(p), total_time(p)) for p in result.passengers} == expected


# Worked by hand for WP 3.5. The car is alone, with one seat, on 5 floors. x and a tie at the lobby,
# so x goes first and the car is back at tick 4, when a has waited 4 and b has just arrived. a then
# scores (1 + 0.8w) / 2 and b scores 1 / 1, so a wins only if w is above 1.25.
WEIGHTED_CASE = [Request(0, "x", 1, 3), Request(0, "a", 1, 3), Request(4, "b", 1, 2)]
SHORT_RIDE_FIRST = {"x": (0, 2), "a": (6, 8), "b": (0, 1)}
OLDEST_FIRST = {"x": (0, 2), "a": (4, 6), "b": (4, 5)}


@pytest.mark.parametrize(
    ("behaviour", "weight", "expected"),
    [
        ("min_time", None, SHORT_RIDE_FIRST),
        ("weighted", 0.0, SHORT_RIDE_FIRST),
        ("weighted", 1.0, SHORT_RIDE_FIRST),
        ("weighted", 2.0, OLDEST_FIRST),
        ("strict", None, OLDEST_FIRST),
    ],
)
def test_wp35_a_weighted_seat_shortage_worked_by_hand(
    behaviour: str, weight: float | None, expected: dict[str, tuple[int, int]]
) -> None:
    config = SimConfig(
        floors=5, elevators=1, capacity=1, behaviour=behaviour, fairness_weight=weight
    )

    result = simulate(WEIGHTED_CASE, config)

    assert {p.request.id: (wait_time(p), total_time(p)) for p in result.passengers} == expected


def lobby_flood() -> list[Request]:
    """One early mid-floor passenger, then a lobby flood that fills a two-seat car on every trip."""
    rows = [(0, 5, 9)]
    rows += [(t, 1, 8) for t in range(0, 40, 2) for _ in range(3)]
    return requests_at(*rows)


def test_tst13_strict_stops_a_lobby_flood_starving_a_mid_floor_passenger() -> None:
    config = SimConfig(elevators=1, capacity=2, behaviour="strict")

    held = simulate(lobby_flood(), config).passengers[0]

    # The car reaches floor 5 on its first trip, four ticks in, with the seat kept free.
    assert wait_time(held) == 4
    assert held.times_left_behind == 0


def test_tst13_min_time_lets_that_flood_fill_the_car_past_them() -> None:
    config = SimConfig(elevators=1, capacity=2, guard="none")

    passed = simulate(lobby_flood(), config).passengers[0]

    assert wait_time(passed) > 4
    assert passed.times_left_behind >= 1


# Worked by hand. The car leaves floor 1 at ticks 0, 14, 28 ... with two lobby passengers, passes
# floor 5 four ticks later, and comes back down past it at ticks 10, 24 ... going the wrong way.
# Unguarded, the 60 lobby passengers fill it two at a time until trip 29, at tick 406, so the
# floor 5 passenger is left behind on all 30 trips, and boards at tick 416, when the empty car
# comes back down and turns for them. With S = 2 they are flagged after trip 1, at tick 18. With
# seat hold, trip 2 boards one lobby passenger at tick 28 and keeps the other seat, so they board
# at tick 32. Without it, a flag only helps at their own floor, and the car still arrives full.
@pytest.mark.parametrize(
    ("guard", "seat_hold", "wait", "left_behind"),
    [
        ("none", True, 416, 30),
        ("skip_limit", True, 32, 2),
        ("skip_limit", False, 416, 30),
    ],
)
def test_tst13_seat_hold_keeps_a_seat_through_a_lobby_flood(
    guard: str, seat_hold: bool, wait: int, left_behind: int
) -> None:
    config = SimConfig(elevators=1, capacity=2, guard=guard, skip_limit=2, seat_hold=seat_hold)

    held = simulate(lobby_flood(), config).passengers[0]

    assert (wait_time(held), held.times_left_behind) == (wait, left_behind)


@pytest.mark.parametrize(
    ("behaviour", "weight"),
    [("strict", None), ("weighted", 0.5), ("weighted", 1.0), ("weighted", 2.0)],
)
@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_tst13_overload_ramp_serves_everyone_under_every_behaviour(
    algorithm: str, behaviour: str, weight: float | None
) -> None:
    config = SimConfig(algorithm=algorithm, behaviour=behaviour, fairness_weight=weight)
    requests = overload_ramp(config.floors)

    result = simulate(requests, config)

    assert len(result.passengers) == len(requests)
    assert_rules_hold(result, config.capacity, config.floors)


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
        dest = draw(st.integers(1, floors).filter(source.__ne__))
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


def same_floor_flood() -> list[Request]:
    """A long ride at floor 1, and a short ride arriving there every 2 ticks until tick 38."""
    return requests_at((0, 1, 10), *[(tick, 1, 2) for tick in range(0, 40, 2)])


# Worked by hand. One car with one seat on 10 floors, back at floor 1 every 2 ticks, so a short ride
# is always waiting there. min_time seats the short ride each time. Unguarded, the long ride boards
# at tick 40, after the last short ride, having been left behind at ticks 0, 2, ... 38.
@pytest.mark.parametrize(
    ("guard", "limits", "wait", "left_behind"),
    [
        ("none", {}, 40, 20),
        # Left behind at ticks 0 and 2, so flagged at tick 4, and boards first.
        ("skip_limit", {"skip_limit": 2}, 4, 2),
        ("skip_limit", {"skip_limit": 1}, 2, 1),
        # Waited 4 at tick 4, below the limit of 5, and 6 at tick 6.
        ("wait_expiry", {"wait_limit": 5}, 6, 3),
        # One round trip on 10 floors is 18 ticks.
        ("wait_expiry", {"wait_limit": "1rt"}, 18, 9),
    ],
)
def test_tst13_same_floor_starvation_ends_at_the_guards_limit(
    guard: str, limits: dict[str, int | str], wait: int, left_behind: int
) -> None:
    # mypy can't match a dict of mixed value types to the fields it sets.
    config = replace(
        SimConfig(elevators=1, capacity=1, algorithm="round_robin", guard=guard),
        **limits,  # type: ignore[arg-type]
    )

    long_ride = simulate(same_floor_flood(), config).passengers[0]

    assert (wait_time(long_ride), long_ride.times_left_behind) == (wait, left_behind)
