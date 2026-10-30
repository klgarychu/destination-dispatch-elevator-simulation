"""TST-09 and TST-14: the rules that must hold on any random input."""

import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import DrawFn

from elevator_sim.config import SimConfig
from elevator_sim.engine import simulate
from elevator_sim.requests import Request
from helpers import assert_rules_hold

ALGORITHMS = ("round_robin",)


@st.composite
def scenarios(draw: DrawFn, max_requests: int = 30) -> tuple[SimConfig, list[Request]]:
    floors = draw(st.integers(2, 20))
    config = SimConfig(
        floors=floors,
        elevators=draw(st.integers(1, 4)),
        capacity=draw(st.integers(1, 5)),
        start_floor=draw(st.integers(1, floors)),
        algorithm=draw(st.sampled_from(ALGORITHMS)),
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


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenarios())
def test_tst14_same_input_gives_the_same_run(scenario: tuple[SimConfig, list[Request]]) -> None:
    config, requests = scenario

    first, second = simulate(requests, config), simulate(requests, config)

    assert first.positions == second.positions
    assert first.passengers == second.passengers
