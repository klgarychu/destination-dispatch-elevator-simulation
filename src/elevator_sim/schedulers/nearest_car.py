"""Baseline: the highest figure of suitability, after Barney (D23, E2)."""

from elevator_sim.requests import Direction, Request
from elevator_sim.schedulers.base import CarView, FleetView, Scheduler


def suitability(car: CarView, request: Request, floors: int) -> int:
    span = floors - 1
    distance = abs(car.position - request.source)
    if car.direction == Direction.IDLE:
        return (span + 2) - distance
    moving_toward = (request.source - car.position) * car.direction >= 0
    if not moving_toward:
        return 1
    if car.direction == request.direction:
        return (span + 2) - distance
    return (span + 1) - distance


class NearestCar(Scheduler):
    name = "nearest_car"

    def assign(self, request: Request, view: FleetView) -> int:
        best = max(
            view.eligible(request),
            key=lambda car: (suitability(car, request, view.floors), -car.car_id),
        )
        return best.car_id
