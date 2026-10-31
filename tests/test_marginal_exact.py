"""The target algorithm's cost is exact: tested against full runs, not against its own forecast.

For the last request of a run nothing can arrive later, so the car marginal_insertion picks must
give the lowest real total time of any car. Each alternative is measured by really running it.
"""

import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import DrawFn

from elevator_sim.config import SimConfig
from elevator_sim.engine import SimulationResult, simulate
from elevator_sim.metrics import total_time, wait_time
from elevator_sim.requests import Request
from elevator_sim.schedulers.base import CarView, FleetView, Scheduler
from elevator_sim.schedulers.eta import Eta
from elevator_sim.schedulers.marginal_insertion import MarginalInsertion
from elevator_sim.schedulers.nearest_car import NearestCar


class LastRequestBy(Scheduler):
    """Uses one scheduler for every request but the last, and another rule for the last."""

    name = "last_request_by"

    def __init__(self, last_id: str, last: Scheduler) -> None:
        self.early = NearestCar()
        self.last_id = last_id
        self.last = last

    def assign(self, request: Request, view: FleetView) -> int:
        chooser = self.last if request.id == self.last_id else self.early
        return chooser.assign(request, view)

    def idle_target(self, car: CarView, view: FleetView) -> int | None:
        return None


class Forced(Scheduler):
    name = "forced"

    def __init__(self, car_id: int) -> None:
        self.car_id = car_id

    def assign(self, request: Request, view: FleetView) -> int:
        return self.car_id


@st.composite
def busy_runs(draw: DrawFn) -> tuple[SimConfig, list[Request]]:
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
        requests.append(Request(draw(st.integers(0, 15)), f"p{index}", source, dest))
    return config, sorted(requests, key=lambda request: request.time)


def passenger_time(result: SimulationResult) -> int:
    return sum(total_time(p) for p in result.passengers)


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(busy_runs())
def test_tst11_marginal_insertion_picks_the_car_with_the_lowest_real_total_time(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario
    last = requests[-1].id

    picked = simulate(requests, config, scheduler=LastRequestBy(last, MarginalInsertion()))
    alternatives = [
        passenger_time(simulate(requests, config, scheduler=LastRequestBy(last, Forced(car))))
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

    picked = simulate(requests, config, scheduler=LastRequestBy(last, Eta()))
    alternatives = [
        last_wait(simulate(requests, config, scheduler=LastRequestBy(last, Forced(car))))
        for car in range(1, config.elevators + 1)
    ]

    assert last_wait(picked) == min(alternatives)
