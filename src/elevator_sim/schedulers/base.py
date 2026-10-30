"""The scheduler interface, and the read-only view of the fleet it works from."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from elevator_sim.requests import Direction, Request


@dataclass(frozen=True, slots=True)
class CarView:
    """A read-only snapshot of one car at the current tick."""

    car_id: int
    position: int
    direction: Direction
    rider_count: int
    waiting_count: int
    can_serve: Callable[[int, int], bool]


@dataclass(frozen=True, slots=True)
class FleetView:
    """What a scheduler sees. It holds no requests, so future ones are out of reach (R-15)."""

    now: int
    floors: int
    capacity: int
    cars: tuple[CarView, ...]

    def eligible(self, request: Request) -> tuple[CarView, ...]:
        return tuple(car for car in self.cars if car.can_serve(request.source, request.dest))


class Scheduler(ABC):
    name: str

    @abstractmethod
    def assign(self, request: Request, view: FleetView) -> int:
        """Return the id of a car from view.eligible(request)."""

    def idle_target(self, car: CarView, view: FleetView) -> int | None:
        """Return the floor an idle car should head for, or None to stay put (D8)."""
        return None
