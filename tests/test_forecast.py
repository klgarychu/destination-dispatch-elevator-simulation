"""TST-10: a forecast matches what really happens if the car gets no further passengers."""

import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import DrawFn

from elevator_sim.config import SimConfig
from elevator_sim.engine import simulate
from elevator_sim.forecast import Forecast
from elevator_sim.requests import Direction, Passenger, Request
from elevator_sim.schedulers.base import FleetView, Scheduler
from elevator_sim.schedulers.registry import make_scheduler
from helpers import car_at, view_of


class ForecastSpy(Scheduler):
    """Wraps a scheduler and keeps each car's latest forecast, with and without the new request."""

    name = "forecast_spy"

    def __init__(self, inner: Scheduler) -> None:
        self.inner = inner
        self.latest: dict[int, Forecast] = {}
        self.latest_cached: dict[int, Forecast] = {}

    def assign(self, request: Request, view: FleetView) -> int:
        car_id = self.inner.assign(request, view)
        self.latest[car_id] = view.forecast(car_id, request)
        for car in view.cars:
            if car.car_id != car_id:
                self.latest_cached[car.car_id] = view.forecast(car.car_id)
        self.latest_cached.pop(car_id, None)
        return car_id


@st.composite
def scenarios(draw: DrawFn) -> tuple[SimConfig, list[Request]]:
    floors = draw(st.integers(2, 15))
    config = SimConfig(
        floors=floors,
        elevators=draw(st.integers(1, 3)),
        capacity=draw(st.integers(1, 4)),
        start_floor=draw(st.integers(1, floors)),
        algorithm=draw(st.sampled_from(("round_robin", "eta"))),
    )
    requests = []
    for index in range(draw(st.integers(1, 25))):
        source = draw(st.integers(1, floors))
        dest = draw(st.integers(1, floors).filter(lambda floor, s=source: floor != s))
        requests.append(Request(draw(st.integers(0, 40)), f"p{index}", source, dest))
    return config, requests


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenarios())
def test_tst10_each_cars_last_forecast_matches_the_real_run(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario
    spy = ForecastSpy(make_scheduler(config.algorithm))

    result = simulate(requests, config, scheduler=spy)

    actual = {p.request.id: p for p in result.passengers}
    for car_id, forecast in [*spy.latest.items(), *spy.latest_cached.items()]:
        on_car = {p.request.id for p in result.passengers if p.car_id == car_id}
        assert set(forecast) <= on_car
        for name, trip in forecast.items():
            assert trip.board_tick == actual[name].board_tick
            assert trip.dropoff_tick == actual[name].dropoff_tick
            assert trip.request_time == actual[name].request.time


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenarios())
def test_tst10_forecasting_changes_nothing_in_the_real_run(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario

    watched = simulate(requests, config, scheduler=ForecastSpy(make_scheduler(config.algorithm)))
    plain = simulate(requests, config)

    assert watched.positions == plain.positions
    assert watched.passengers == plain.passengers


def test_tst10_forecast_records_riders_and_waiting_passengers() -> None:
    view = view_of(car_at(1, 3, Direction.UP, riders=[9], waiting=[("A", 5, 7)]))

    forecast = view.forecast(1)

    assert forecast["rider1.0"].dropoff_tick == 6
    assert (forecast["A"].board_tick, forecast["A"].dropoff_tick) == (2, 4)


def test_tst10_an_empty_car_has_an_empty_forecast() -> None:
    assert view_of(car_at(1, 3)).forecast(1) == {}


def test_tst10_forecast_is_measured_in_absolute_ticks() -> None:
    new = Request(30, "new", 5, 9)

    assert view_of(car_at(1, 3), now=30).forecast(1, new)["new"].board_tick == 32


def test_tst10_a_forecast_leaves_the_real_car_untouched() -> None:
    car = car_at(1, 3, Direction.UP, riders=[9], waiting=[("A", 5, 7)])

    view_of(car).forecast(1, Request(0, "new", 8, 9))

    assert (car.position, car.direction) == (3, Direction.UP)
    assert car.waiting_count == 1
    assert all(rider.dropoff_tick is None for rider in car.riders)


def test_tst10_a_new_passenger_replaces_the_cached_forecast() -> None:
    new = Request(0, "new", 8, 9)
    car = car_at(1, 3, Direction.UP, riders=[9])
    view = view_of(car)

    before = view.forecast(1)
    car.assign(Passenger(new, 100, 1))
    view.forecaster.confirm(1, new)

    assert "new" not in before
    assert view.forecast(1)["new"].board_tick == 5


def test_tst10_the_accepted_trial_becomes_the_cached_forecast() -> None:
    new = Request(0, "new", 8, 9)
    car = car_at(1, 3, Direction.UP, riders=[9])
    view = view_of(car)

    trial = view.forecast(1, new)
    car.assign(Passenger(new, 100, 1))
    view.forecaster.confirm(1, new)

    assert view.forecast(1) is trial


def test_tst10_a_repeated_forecast_comes_from_the_cache() -> None:
    view = view_of(car_at(1, 3, Direction.UP, riders=[9]))

    assert view.forecast(1) is view.forecast(1)
