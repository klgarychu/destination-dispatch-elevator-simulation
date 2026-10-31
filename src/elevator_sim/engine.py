"""simulate(): the tick loop. The only module that holds requests not yet released (R-15)."""

from collections.abc import Sequence
from dataclasses import dataclass

from elevator_sim.config import SimConfig
from elevator_sim.elevators.factory import build_fleet
from elevator_sim.forecast import Forecaster
from elevator_sim.requests import Passenger, Request, validate_requests
from elevator_sim.schedulers.base import Scheduler, fleet_view
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


def simulate(
    requests: Sequence[Request], config: SimConfig, scheduler: Scheduler | None = None
) -> SimulationResult:
    """Run the requests through the building. Writes no files, so tests can call it directly."""
    ordered = validate_requests(requests, config.floors)
    chooser = scheduler if scheduler is not None else make_scheduler(config.algorithm)
    fleet = build_fleet(config)
    cars = {car.car_id: car for car in fleet}
    forecaster = Forecaster(fleet)
    max_ticks = config.max_ticks or default_max_ticks(ordered, config.floors)
    passengers: list[Passenger] = []
    positions: list[tuple[int, ...]] = []
    next_request = 0
    tick = 0

    while True:
        while next_request < len(ordered) and ordered[next_request].time == tick:
            request = ordered[next_request]
            view = fleet_view(fleet, tick, config.floors, config.capacity, forecaster)
            car_id = chooser.assign(request, view)
            if car_id not in {car.car_id for car in view.eligible(request)}:
                raise SchedulerError(f"{chooser.name} chose car {car_id} for {request.id}")
            passenger = Passenger(request, next_request, car_id)
            passengers.append(passenger)
            cars[car_id].assign(passenger)
            forecaster.confirm(car_id, request)
            next_request += 1

        for car in fleet:
            car.exchange(tick)
        positions.append(tuple(car.position for car in fleet))

        if next_request == len(ordered) and not any(car.has_passengers for car in fleet):
            break
        if tick >= max_ticks:
            delivered = sum(1 for p in passengers if p.dropoff_tick is not None)
            raise SimulationStalledError(
                f"stalled at tick {tick}: {len(ordered) - delivered} passengers unfinished"
            )

        view = fleet_view(fleet, tick, config.floors, config.capacity, forecaster)
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
