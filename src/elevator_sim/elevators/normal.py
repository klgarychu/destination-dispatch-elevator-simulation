"""The default car, which serves every floor (B4)."""

from elevator_sim.elevators.base import Elevator


class NormalElevator(Elevator):
    def serves(self, floor: int) -> bool:
        return 1 <= floor <= self.floors
