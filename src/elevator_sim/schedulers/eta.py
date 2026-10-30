"""Comparator: the lowest predicted wait for the new passenger only."""

from elevator_sim.requests import Request
from elevator_sim.schedulers.base import FleetView, Scheduler


class Eta(Scheduler):
    name = "eta"

    def waits(self, request: Request, view: FleetView) -> dict[int, int]:
        return {
            car.car_id: view.forecast(car.car_id, request)[request.id].board_tick - request.time
            for car in view.eligible(request)
        }

    def assign(self, request: Request, view: FleetView) -> int:
        waits = self.waits(request, view)
        return min(waits, key=lambda car_id: (waits[car_id], car_id))
