"""A car that serves a configured set of floors and passes the rest without stopping (B5)."""

from collections.abc import Collection

from elevator_sim.boarding.behaviours import Behaviour
from elevator_sim.boarding.guards import NO_GUARD, Guard
from elevator_sim.elevators.base import Elevator


class ExpressElevator(Elevator):
    def __init__(
        self,
        car_id: int,
        floors: int,
        capacity: int,
        start_floor: int,
        behaviour: Behaviour,
        served: Collection[int],
        guard: Guard = NO_GUARD,
    ) -> None:
        self._served = frozenset(served)
        # A car can't wait at a floor it doesn't serve (B9).
        start = start_floor if start_floor in self._served else min(self._served)
        super().__init__(car_id, floors, capacity, start, behaviour, guard)

    def serves(self, floor: int) -> bool:
        return floor in self._served
