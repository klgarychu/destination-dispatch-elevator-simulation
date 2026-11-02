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
        dest = draw(st.integers(1, floors).filter(lambda floor, s=source: floor != s))
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
        dest = draw(st.integers(1, floors).filter(lambda floor, s=source: floor != s))
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
