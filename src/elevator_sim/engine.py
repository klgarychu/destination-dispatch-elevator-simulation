"""simulate(): the tick loop. The only module that holds requests not yet released (R-15)."""

from collections.abc import Sequence
from dataclasses import dataclass

from elevator_sim.config import SimConfig
from elevator_sim.elevators.base import Elevator
from elevator_sim.elevators.factory import build_fleet
from elevator_sim.requests import Passenger, Request, validate_requests
from elevator_sim.schedulers.base import CarView, FleetView, Scheduler
from elevator_sim.schedulers.registry import make_scheduler


class SimulationStalledError(RuntimeError):
    """The run reached max_ticks with passengers still unfinished."""


class SchedulerError(RuntimeError):
    """A scheduler chose a car that can't serve the request."""


@dataclass(slots=True)
class SimulationResult:
    config: SimConfig
    positions: list[tuple[int, ...]]
    passengers: list[Passenger]
    moves: int
    empty_moves: int
    rider_moves: int

    @property
    def ticks(self) -> int:
        return len(self.positions) - 1


def default_max_ticks(requests: Sequence[Request], floors: int) -> int:
    last_request = requests[-1].time if requests else 0
    return last_request + 4 * (len(requests) + 1) * (floors - 1)


def _snapshot(fleet: Sequence[Elevator], tick: int, config: SimConfig) -> FleetView:
    cars = tuple(
        CarView(
            car.car_id,
            car.position,
            car.direction,
            len(car.riders),
            car.waiting_count,
            car.can_serve,
        )
        for car in fleet
    )
    return FleetView(tick, config.floors, config.capacity, cars)


def simulate(
    requests: Sequence[Request], config: SimConfig, scheduler: Scheduler | None = None
) -> SimulationResult:
    """Run the requests through the building. Writes no files, so tests can call it directly."""
    ordered = validate_requests(requests, config.floors)
    chooser = scheduler if scheduler is not None else make_scheduler(config.algorithm)
    fleet = build_fleet(config)
    cars = {car.car_id: car for car in fleet}
    max_ticks = config.max_ticks or default_max_ticks(ordered, config.floors)
    passengers: list[Passenger] = []
    positions: list[tuple[int, ...]] = []
    tick = 0

    while True:
        while len(passengers) < len(ordered) and ordered[len(passengers)].time == tick:
            request = ordered[len(passengers)]
            view = _snapshot(fleet, tick, config)
            car_id = chooser.assign(request, view)
            if car_id not in {car.car_id for car in view.eligible(request)}:
                raise SchedulerError(f"{chooser.name} chose car {car_id} for {request.id}")
            passenger = Passenger(request, len(passengers), car_id)
            passengers.append(passenger)
            cars[car_id].assign(passenger)

        for car in fleet:
            car.exchange(tick)
        positions.append(tuple(car.position for car in fleet))

        if len(passengers) == len(ordered) and not any(car.has_passengers for car in fleet):
            break
        if tick >= max_ticks:
            delivered = sum(1 for p in passengers if p.dropoff_tick is not None)
            raise SimulationStalledError(
                f"stalled at tick {tick}: {len(ordered) - delivered} passengers unfinished"
            )

        view = _snapshot(fleet, tick, config)
        for car, car_view in zip(fleet, view.cars, strict=True):
            car.move(chooser.idle_target(car_view, view))
        tick += 1

    return SimulationResult(
        config,
        positions,
        passengers,
        sum(car.moves for car in fleet),
        sum(car.empty_moves for car in fleet),
        sum(car.rider_moves for car in fleet),
    )
