"""Builds the fleet from settings."""

from elevator_sim.boarding.behaviours import make_behaviour
from elevator_sim.config import SimConfig
from elevator_sim.elevators.base import Elevator
from elevator_sim.elevators.normal import NormalElevator


def build_fleet(config: SimConfig) -> list[Elevator]:
    behaviour = make_behaviour(config.behaviour)
    return [
        NormalElevator(number, config.floors, config.capacity, config.start_floor, behaviour)
        for number in range(1, config.elevators + 1)
    ]
