"""Builds the fleet from settings."""

from elevator_sim.boarding.behaviours import make_behaviour
from elevator_sim.boarding.guards import make_guard
from elevator_sim.config import SimConfig
from elevator_sim.elevators.base import Elevator
from elevator_sim.elevators.express import ExpressElevator
from elevator_sim.elevators.normal import NormalElevator


def build_fleet(config: SimConfig) -> list[Elevator]:
    behaviour = make_behaviour(config.behaviour, config.weight, config.floors)
    guard = make_guard(config)
    express = {car.car: car.serves for car in config.express}
    fleet: list[Elevator] = []
    for number in range(1, config.elevators + 1):
        shared = (number, config.floors, config.capacity, config.start_floor, behaviour)
        if number in express:
            fleet.append(ExpressElevator(*shared, express[number], guard))
        else:
            fleet.append(NormalElevator(*shared, guard))
    return fleet
