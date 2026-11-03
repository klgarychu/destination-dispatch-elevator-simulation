"""TST-10: a forecast matches what really happens if the car gets no further passengers."""

import hypothesis.strategies as st
from hypothesis import HealthCheck, example, given, settings
from hypothesis.strategies import DrawFn

from elevator_sim.boarding.guards import Guard
from elevator_sim.config import ExpressCar, SimConfig
from elevator_sim.elevators.normal import NormalElevator
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
        self.latest[car_id] = view.candidate_forecast(car_id, request)
        for car in view.cars:
            if car.car_id != car_id:
                self.latest_cached[car.car_id] = view.baseline_forecast(car.car_id)
        self.latest_cached.pop(car_id, None)
        return car_id


class DecisionSpy(Scheduler):
    """Wraps a scheduler and records whose trips each car's forecasts hold at every decision."""

    name = "decision_spy"

    def __init__(self, inner: Scheduler) -> None:
        self.inner = inner
        self.decisions: list[tuple[int, int, int, set[str], set[str]]] = []
        self.count = 0

    def assign(self, request: Request, view: FleetView) -> int:
        for car in view.cars:
            without = set(view.baseline_forecast(car.car_id))
            with_new = set(view.candidate_forecast(car.car_id, request))
            self.decisions.append((self.count, view.now, car.car_id, without, with_new))
        self.count += 1
        return self.inner.assign(request, view)


class ReferenceSpy(Scheduler):
    """Wraps a scheduler and checks every cached forecast against a fresh one, at every decision."""

    name = "reference_spy"

    def __init__(self, inner: Scheduler) -> None:
        self.inner = inner

    def assign(self, request: Request, view: FleetView) -> int:
        for car in view.cars:
            fresh = view.forecaster.fresh
            assert view.baseline_forecast(car.car_id) == fresh(car.car_id, view.now)
            candidate = view.candidate_forecast(car.car_id, request)
            assert candidate == fresh(car.car_id, view.now, request)
        return self.inner.assign(request, view)


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
def scenarios(draw: DrawFn) -> tuple[SimConfig, list[Request]]:
    floors = draw(st.integers(2, 15))
    elevators = draw(st.integers(1, 3))
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
        capacity=draw(st.integers(1, 4)),
        start_floor=draw(st.integers(1, floors)),
        algorithm=draw(
            st.sampled_from(("round_robin", "eta", "marginal_insertion", "rush_express"))
        ),
        express=express,
        behaviour=behaviour,
        fairness_weight=weight,
    )
    requests = []
    for index in range(draw(st.integers(1, 25))):
        source = draw(st.integers(1, floors))
        dest = draw(st.integers(1, floors).filter(source.__ne__))
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


def still_travelling(passenger: Passenger, tick: int) -> bool:
    """A rider arriving at this tick still counts, because assignment comes before the exchange."""
    assert passenger.dropoff_tick is not None
    return passenger.dropoff_tick >= tick


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenarios())
@example(
    (
        SimConfig(floors=2, elevators=1, capacity=1),
        [Request(2, "p0", 1, 2), Request(0, "p1", 1, 2)],
    )
)
def test_tst10_every_forecast_holds_exactly_the_cars_unfinished_passengers(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario
    spy = DecisionSpy(make_scheduler(config.algorithm))

    result = simulate(requests, config, scheduler=spy)

    for order, tick, car_id, without, with_new in spy.decisions:
        unfinished = {
            p.request.id
            for p in result.passengers
            if p.car_id == car_id and p.order < order and still_travelling(p, tick)
        }
        assert without == unfinished
        assert with_new == unfinished | {result.passengers[order].request.id}


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scenarios())
def test_tst10_every_cached_forecast_equals_a_fresh_one(
    scenario: tuple[SimConfig, list[Request]],
) -> None:
    config, requests = scenario

    simulate(requests, config, scheduler=ReferenceSpy(make_scheduler(config.algorithm)))


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

    forecast = view.baseline_forecast(1)

    assert forecast["rider1.0"].dropoff_tick == 6
    assert (forecast["A"].board_tick, forecast["A"].dropoff_tick) == (2, 4)


def test_tst10_an_empty_car_has_an_empty_forecast() -> None:
    assert view_of(car_at(1, 3)).baseline_forecast(1) == {}


def test_tst10_forecast_is_measured_in_absolute_ticks() -> None:
    new = Request(30, "new", 5, 9)

    assert view_of(car_at(1, 3), now=30).candidate_forecast(1, new)["new"].board_tick == 32


def test_tst10_a_forecast_leaves_the_real_car_untouched() -> None:
    car = car_at(1, 3, Direction.UP, riders=[9], waiting=[("A", 5, 7)])

    view_of(car).candidate_forecast(1, Request(0, "new", 8, 9))

    assert (car.position, car.direction) == (3, Direction.UP)
    assert car.waiting_count == 1
    assert all(rider.dropoff_tick is None for rider in car.riders)


def test_tst10_a_new_passenger_replaces_the_cached_forecast() -> None:
    new = Request(0, "new", 8, 9)
    car = car_at(1, 3, Direction.UP, riders=[9])
    view = view_of(car)

    before = view.baseline_forecast(1)
    car.assign(Passenger(new, 100, 1))
    view.forecaster.confirm(1, new)

    assert "new" not in before
    assert view.baseline_forecast(1)["new"].board_tick == 5


def test_tst10_the_accepted_trial_becomes_the_cached_forecast() -> None:
    new = Request(0, "new", 8, 9)
    car = car_at(1, 3, Direction.UP, riders=[9])
    view = view_of(car)

    trial = view.candidate_forecast(1, new)
    car.assign(Passenger(new, 100, 1))
    view.forecaster.confirm(1, new)

    assert view.baseline_forecast(1) is trial


def test_tst10_a_repeated_forecast_comes_from_the_cache() -> None:
    view = view_of(car_at(1, 3, Direction.UP, riders=[9]))

    assert view.baseline_forecast(1) is view.baseline_forecast(1)


def ride_to_the_next_tick(car: NormalElevator, tick: int) -> None:
    car.exchange(tick)
    car.move()


def test_tst10_a_cached_forecast_loses_a_passenger_once_delivered() -> None:
    car = car_at(1, 3, Direction.UP, riders=[5, 9])
    view = view_of(car)
    assert set(view.baseline_forecast(1)) == {"rider1.0", "rider1.1"}

    ride_to_the_next_tick(car, 0)
    ride_to_the_next_tick(car, 1)
    car.exchange(2)

    assert list(view.baseline_forecast(1)) == ["rider1.1"]
    assert view.baseline_forecast(1)["rider1.1"].dropoff_tick == 6


def test_tst10_a_rider_arriving_this_tick_stays_in_the_forecast_until_the_exchange() -> None:
    car = car_at(1, 3, Direction.UP, riders=[4, 9])
    view = view_of(car)
    view.baseline_forecast(1)

    ride_to_the_next_tick(car, 0)

    assert set(view.baseline_forecast(1)) == {"rider1.0", "rider1.1"}


def test_tst10_a_forecast_keeps_each_passengers_count_of_times_left_behind() -> None:
    car = car_at(1, 1, Direction.UP, waiting=[("long", 1, 9), ("short", 1, 2)], capacity=1)
    car.guard = Guard("skip_limit", 1)
    car.passengers[0].times_left_behind = 1

    forecast = view_of(car, capacity=1).baseline_forecast(1)

    # The long ride is flagged, so it boards first, and the car is back for the short ride at 16.
    assert (forecast["long"].board_tick, forecast["long"].dropoff_tick) == (0, 8)
    assert (forecast["short"].board_tick, forecast["short"].dropoff_tick) == (16, 17)
