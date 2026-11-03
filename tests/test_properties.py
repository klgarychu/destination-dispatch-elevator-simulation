"""TST-09 and TST-14: the rules that must hold on any random input."""

from dataclasses import replace

import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import DrawFn

from elevator_sim.config import ALL_ALGORITHMS, ExpressCar, SimConfig
from elevator_sim.engine import SimulationResult, simulate
from elevator_sim.requests import Request
from helpers import assert_rules_hold

SETTINGS = (("min_time", None), ("strict", None), ("weighted", 0.5), ("weighted", 2.0))
# Every guard, with seat hold on and off, at limits low enough to act on these short inputs.
GUARDS: tuple[dict[str, object], ...] = (
    {"guard": "none"},
    {"guard": "skip_limit", "skip_limit": 1},
    {"guard": "skip_limit", "skip_limit": 2, "seat_hold": False},
    {"guard": "wait_expiry", "wait_limit": 5},
    {"guard": "wait_expiry", "wait_limit": "1rt", "seat_hold": False},
)


@st.composite
def scenarios(draw: DrawFn, max_requests: int = 30) -> tuple[SimConfig, list[Request]]:
    floors = draw(st.integers(2, 20))
    elevators = draw(st.integers(1, 4))
    # Car 1 stays normal, so every pair of floors has a car (B8).
    express = tuple(
        ExpressCar(car, tuple(sorted(draw(st.sets(st.integers(1, floors), min_size=2)))))
        for car in range(2, elevators + 1)
        if draw(st.booleans())
    )
    behaviour, weight = draw(st.sampled_from(SETTINGS))
    config = SimConfig(
        **draw(st.sampled_from(GUARDS)),  # type: ignore[arg-type]
        floors=floors,
        elevators=elevators,
        capacity=draw(st.integers(1, 5)),
        start_floor=draw(st.integers(1, floors)),
        algorithm=draw(st.sampled_from(ALL_ALGORITHMS)),
        express=express,
        behaviour=behaviour,
        fairness_weight=weight,
    )
    count = draw(st.integers(0, max_requests))
    requests = []
    for index in range(count):
        source = draw(st.integers(1, floors))
        dest = draw(st.integers(1, floors).filter(source.__ne__))
        requests.append(Request(draw(st.integers(0, 60)), f"p{index}", source, dest))
    return config, requests


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenarios())
def test_tst09_rules_hold_on_random_inputs(scenario: tuple[SimConfig, list[Request]]) -> None:
    config, requests = scenario

    result = simulate(requests, config)

    assert len(result.passengers) == len(requests)
    assert_rules_hold(result, config.capacity, config.floors)
    served = {car.car: car.serves for car in config.express}
    for passenger in result.passengers:
        if passenger.car_id in served:
            assert passenger.request.source in served[passenger.car_id]
            assert passenger.request.dest in served[passenger.car_id]


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenarios())
def test_tst14_same_input_gives_the_same_run(scenario: tuple[SimConfig, list[Request]]) -> None:
    config, requests = scenario

    first, second = simulate(requests, config), simulate(requests, config)

    assert first.positions == second.positions
    assert first.passengers == second.passengers


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenarios(), st.integers(0, 60), st.integers(0, 10_000))
def test_tst06_later_requests_never_change_earlier_assignments(
    scenario: tuple[SimConfig, list[Request]], cut: int, salt: int
) -> None:
    config, requests = scenario
    known = [r for r in requests if r.time <= cut]
    changed = [
        Request(r.time, r.id, r.dest, r.source) if (salt + index) % 2 else r
        for index, r in enumerate(r for r in requests if r.time > cut)
    ]

    full = simulate(requests, config)
    removed = simulate(known, config)
    altered = simulate(known + changed, config)

    def assignments(run: SimulationResult) -> dict[str, int]:
        return {p.request.id: p.car_id for p in run.passengers if p.request.time <= cut}

    assert assignments(full) == assignments(removed) == assignments(altered)

    shared = min(cut + 1, len(full.positions), len(removed.positions), len(altered.positions))
    assert full.positions[:shared] == removed.positions[:shared] == altered.positions[:shared]


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenarios())
def test_d14_weighted_at_weight_zero_matches_min_time(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario
    plain = replace(config, behaviour="min_time", fairness_weight=None)
    weightless = replace(config, behaviour="weighted", fairness_weight=0.0)

    first, second = simulate(requests, plain), simulate(requests, weightless)

    assert first.positions == second.positions
    assert [p.car_id for p in first.passengers] == [p.car_id for p in second.passengers]
    assert [p.board_tick for p in first.passengers] == [p.board_tick for p in second.passengers]


@st.composite
def single_cars(draw: DrawFn) -> tuple[SimConfig, list[Request]]:
    floors = draw(st.integers(3, 12))
    config = SimConfig(
        floors=floors, elevators=1, capacity=draw(st.integers(1, 4)), behaviour="strict"
    )
    requests = []
    for index in range(draw(st.integers(1, 25))):
        source = draw(st.integers(1, floors))
        dest = draw(st.integers(1, floors).filter(source.__ne__))
        requests.append(Request(draw(st.integers(0, 60)), f"p{index}", source, dest))
    return config, requests


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(single_cars())
def test_tst13_strict_keeps_a_wait_within_the_bound_on_one_car(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario
    round_trip = 2 * (config.floors - 1)

    result = simulate(requests, config)

    for passenger in result.passengers:
        earlier = [
            other
            for other in result.passengers
            if other.order < passenger.order and (other.board_tick or 0) >= passenger.request.time
        ]
        assert passenger.board_tick is not None
        wait = passenger.board_tick - passenger.request.time
        assert wait <= (len(earlier) // config.capacity + 2) * round_trip


@st.composite
def guarded_single_cars(draw: DrawFn, guard: str) -> tuple[SimConfig, list[Request]]:
    floors = draw(st.integers(3, 12))
    behaviour, weight = draw(st.sampled_from((("min_time", None), ("weighted", 1.0))))
    config = SimConfig(
        floors=floors,
        elevators=1,
        capacity=draw(st.integers(1, 4)),
        behaviour=behaviour,
        fairness_weight=weight,
        guard=guard,
        skip_limit=draw(st.integers(1, 3)),
        wait_limit=draw(st.integers(1, 30)),
        seat_hold=True,
    )
    requests = []
    for index in range(draw(st.integers(1, 25))):
        source = draw(st.integers(1, floors))
        dest = draw(st.integers(1, floors).filter(source.__ne__))
        requests.append(Request(draw(st.integers(0, 60)), f"p{index}", source, dest))
    return config, requests


def flagged_fit_in_one_car(result: SimulationResult, flagged: list[bool], capacity: int) -> bool:
    """Whether no direction ever has more flagged passengers than the car has seats."""
    for direction in (-1, 1):
        count = sum(
            is_flagged
            for passenger, is_flagged in zip(result.passengers, flagged, strict=True)
            if passenger.request.direction == direction
        )
        if count > capacity:
            return False
    return True


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(guarded_single_cars("skip_limit"))
def test_tst13_with_seat_hold_a_flagged_passenger_boards_on_the_next_pass(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario

    result = simulate(requests, config)

    flagged = [p.times_left_behind >= config.skip_limit for p in result.passengers]
    if flagged_fit_in_one_car(result, flagged, config.capacity):
        assert all(p.times_left_behind <= config.skip_limit for p in result.passengers)


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(guarded_single_cars("wait_expiry"))
def test_tst13_with_seat_hold_an_expired_wait_ends_within_the_next_full_pass(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario
    limit = config.wait_limit_ticks

    result = simulate(requests, config)

    waits = [p.board_tick - p.request.time for p in result.passengers if p.board_tick is not None]
    if flagged_fit_in_one_car(result, [wait >= limit for wait in waits], config.capacity):
        # A passenger flagged mid-sweep can miss that sweep, and the next one starts within
        # 2(n - 1) ticks and reaches them within n - 1 more.
        assert all(wait <= limit + 3 * (config.floors - 1) for wait in waits)
