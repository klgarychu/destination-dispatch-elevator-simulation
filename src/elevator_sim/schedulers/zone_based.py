"""Baseline: each car owns a block of floors (D21)."""

from elevator_sim.requests import Request
from elevator_sim.schedulers.base import CarView, FleetView, Scheduler


def zone_bounds(floors: int, cars: int) -> list[tuple[int, int]]:
    """Contiguous (low, high) floors per car, as equal as possible, with extras going lowest."""
    size, extra = divmod(floors, cars)
    bounds = []
    low = 1
    for index in range(min(cars, floors)):
        count = size + (1 if index < extra else 0)
        bounds.append((low, low + count - 1))
        low += count
    return bounds


class ZoneBased(Scheduler):
    name = "zone_based"

    def assign(self, request: Request, view: FleetView) -> int:
        # From the lobby the destination decides, or up-peak would put everyone on one car.
        floor = request.dest if request.source == 1 else request.source
        for index, (low, high) in enumerate(zone_bounds(view.floors, len(view.cars))):
            if low <= floor <= high:
                owner = view.cars[index]
                if owner.can_serve(request.source, request.dest):
                    return owner.car_id
                nearest = min(
                    view.eligible(request),
                    key=lambda car: (abs(car.position - request.source), car.car_id),
                )
                return nearest.car_id
        raise ValueError(f"floor {floor} has no zone")

    def idle_target(self, car: CarView, view: FleetView) -> int | None:
        zones = zone_bounds(view.floors, len(view.cars))
        index = view.cars.index(car)
        if index >= len(zones):
            return None
        low, high = zones[index]
        middle = (low + high) // 2
        served = [floor for floor in range(1, view.floors + 1) if car.can_serve(floor, floor)]
        return min(served, key=lambda floor: (abs(floor - middle), floor))
