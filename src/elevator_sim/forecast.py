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
    """The fleet's forecasts, cached because a car's plan changes only with a new passenger [11].

    A baseline covers a car's unfinished passengers, and lasts until the car gets a new one. A
    candidate adds one request, and lasts until the next assignment. Both cover the same existing
    passengers, so they can be compared directly, and `fresh` is the reference both must equal.
    """

    def __init__(self, fleet: Sequence[Elevator], next_order: int = 0) -> None:
        self._cars = {car.car_id: car for car in fleet}
        self._next_order = next_order
        self._baselines: dict[int, Forecast] = {}
        self._candidates: dict[tuple[int, str], Forecast] = {}

    def fresh(self, car_id: int, tick: int, extra: Request | None = None) -> Forecast:
        """Simulate the car from scratch, with no cache."""
        return forecast_car(self._cars[car_id], tick, extra, self._next_order)

    def baseline(self, car_id: int, tick: int) -> Forecast:
        if car_id not in self._baselines:
            self._baselines[car_id] = self.fresh(car_id, tick)
        return self._unfinished_baseline(car_id)

    def candidate(self, car_id: int, tick: int, request: Request) -> Forecast:
        key = (car_id, request.id)
        if key not in self._candidates:
            self._candidates[key] = self.fresh(car_id, tick, request)
        return self._candidates[key]

    def confirm(self, car_id: int, request: Request) -> None:
        """Record an assignment. Its candidate, if any, becomes the car's baseline."""
        candidate = self._candidates.get((car_id, request.id))
        if candidate is None:
            self._baselines.pop(car_id, None)
        else:
            self._baselines[car_id] = candidate
        self._candidates.clear()
        self._next_order += 1

    def _unfinished_baseline(self, car_id: int) -> Forecast:
        """The cached baseline, less anyone delivered since it was made."""
        baseline = self._baselines[car_id]
        on_car = {passenger.request.id for passenger in self._cars[car_id].passengers}
        if baseline.keys() != on_car:
            baseline = {name: trip for name, trip in baseline.items() if name in on_car}
            self._baselines[car_id] = baseline
        return baseline
