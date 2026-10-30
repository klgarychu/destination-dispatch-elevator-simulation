"""Baseline: the next car in turn, skipping cars that can't serve the trip."""

from elevator_sim.requests import Request
from elevator_sim.schedulers.base import FleetView, Scheduler


class RoundRobin(Scheduler):
    name = "round_robin"

    def __init__(self) -> None:
        self._next = 0

    def assign(self, request: Request, view: FleetView) -> int:
        eligible = {car.car_id for car in view.eligible(request)}
        count = len(view.cars)
        for offset in range(count):
            index = (self._next + offset) % count
            if view.cars[index].car_id in eligible:
                self._next = (index + 1) % count
                return view.cars[index].car_id
        raise ValueError(f"no car can serve request {request.id}")
