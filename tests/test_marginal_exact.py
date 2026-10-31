"""The target algorithm's cost is exact: tested against full runs, not against its own forecast.

For the last request of a run nothing can arrive later, so the car marginal_insertion picks must
give the lowest real total time of any car. Each alternative is measured by really running it, and
the algorithm handles every earlier request too, so its forecasts have aged as they do in a suite.
"""

import hypothesis.strategies as st
from hypothesis import HealthCheck, example, given, settings
from hypothesis.strategies import DrawFn

from elevator_sim.config import SimConfig
from elevator_sim.engine import SimulationResult, simulate
from elevator_sim.metrics import total_time, wait_time
from elevator_sim.requests import Request
from elevator_sim.schedulers.base import FleetView, Scheduler
from elevator_sim.schedulers.eta import Eta
from elevator_sim.schedulers.marginal_insertion import MarginalInsertion


class ForcedLast(Scheduler):
    """Uses one scheduler for every request but the last, which goes to a chosen car."""

    name = "forced_last"

    def __init__(self, early: Scheduler, last_id: str, car_id: int) -> None:
        self.early = early
        self.last_id = last_id
        self.car_id = car_id

    def assign(self, request: Request, view: FleetView) -> int:
        if request.id == self.last_id:
            return self.car_id
        return self.early.assign(request, view)


@st.composite
def busy_runs(draw: DrawFn) -> tuple[SimConfig, list[Request]]:
    """Runs with idle gaps, so cars finish some passengers before the next request arrives."""
    floors = draw(st.integers(3, 15))
    config = SimConfig(
        floors=floors,
        elevators=draw(st.integers(2, 4)),
        capacity=draw(st.integers(1, 4)),
    )
    requests = []
    for index in range(draw(st.integers(1, 20))):
        source = draw(st.integers(1, floors))
        dest = draw(st.integers(1, floors).filter(lambda floor, s=source: floor != s))
        requests.append(Request(draw(st.integers(0, 60)), f"p{index}", source, dest))
    return config, sorted(requests, key=lambda request: request.time)


def passenger_time(result: SimulationResult) -> int:
    return sum(total_time(p) for p in result.passengers)


def request_at(time: int, name: str = "p0") -> Request:
    return Request(time, name, 1, 2)


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(busy_runs())
@example((SimConfig(floors=3, elevators=2, capacity=1), [request_at(0), request_at(2, "p1")]))
def test_tst11_marginal_insertion_picks_the_car_with_the_lowest_real_total_time(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario
    last = requests[-1].id

    picked = simulate(requests, config, scheduler=MarginalInsertion())
    alternatives = [
        passenger_time(
            simulate(requests, config, scheduler=ForcedLast(MarginalInsertion(), last, car))
        )
        for car in range(1, config.elevators + 1)
    ]

    assert passenger_time(picked) == min(alternatives)


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(busy_runs())
def test_tst11_eta_picks_the_car_with_the_lowest_real_wait_for_the_last_passenger(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario
    last = requests[-1].id

    def last_wait(result: SimulationResult) -> int:
        return wait_time(next(p for p in result.passengers if p.request.id == last))

    picked = simulate(requests, config, scheduler=Eta())
    alternatives = [
        last_wait(simulate(requests, config, scheduler=ForcedLast(Eta(), last, car)))
        for car in range(1, config.elevators + 1)
    ]

    assert last_wait(picked) == min(alternatives)
