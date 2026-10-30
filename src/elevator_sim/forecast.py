"""Forward simulation of one car, using only the passengers already known.

This runs the real exchange code on a copy of the car, so there is no second model of movement or
boarding to keep in step, and later boarding rules reach forecasts automatically.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from elevator_sim.elevators.base import Elevator
from elevator_sim.requests import Passenger, Request


@dataclass(frozen=True, slots=True)
class PredictedTrip:
    request_time: int
    board_tick: int
    dropoff_tick: int


Forecast = Mapping[str, PredictedTrip]  # by request id


def forecast_car(car: Elevator, tick: int, extra: Request | None, order: int) -> Forecast:
    """Simulate a copy of the car to the end of its work, starting at this tick's exchange."""
    twin = car.clone()
    if extra is not None:
        twin.assign(Passenger(extra, order, car.car_id))
    tracked = twin.passengers
    now = tick
    while True:
        twin.exchange(now)
        if not twin.has_passengers:
            break
        step = twin.distance_to_next_event()
        twin.jump(step)
        now += step
    trips = {}
    for passenger in tracked:
        assert passenger.board_tick is not None
        assert passenger.dropoff_tick is not None
        trips[passenger.request.id] = PredictedTrip(
            passenger.request.time, passenger.board_tick, passenger.dropoff_tick
        )
    return trips


class Forecaster:
    """Caches each car's forecast, which stays exact until that car gets a new passenger [11]."""

    def __init__(self, fleet: Sequence[Elevator], next_order: int = 0) -> None:
        self._cars = {car.car_id: car for car in fleet}
        self._next_order = next_order
        self._plans: dict[int, Forecast] = {}
        self._trials: dict[tuple[int, str], Forecast] = {}

    def forecast(self, car_id: int, tick: int, extra: Request | None = None) -> Forecast:
        if extra is None:
            if car_id not in self._plans:
                car = self._cars[car_id]
                self._plans[car_id] = forecast_car(car, tick, None, self._next_order)
            return self._plans[car_id]
        key = (car_id, extra.id)
        if key not in self._trials:
            car = self._cars[car_id]
            self._trials[key] = forecast_car(car, tick, extra, self._next_order)
        return self._trials[key]

    def confirm(self, car_id: int, request: Request) -> None:
        """Record an assignment. Its trial forecast, if any, becomes the car's cached one."""
        trial = self._trials.get((car_id, request.id))
        if trial is None:
            self._plans.pop(car_id, None)
        else:
            self._plans[car_id] = trial
        self._trials.clear()
        self._next_order += 1
