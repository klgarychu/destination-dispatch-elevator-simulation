"""Builds a scheduler by name. A new instance per run keeps runs independent."""

from elevator_sim.schedulers.base import Scheduler
from elevator_sim.schedulers.eta import Eta
from elevator_sim.schedulers.marginal_insertion import MarginalInsertion
from elevator_sim.schedulers.nearest_car import NearestCar
from elevator_sim.schedulers.round_robin import RoundRobin
from elevator_sim.schedulers.zone_based import ZoneBased


def make_scheduler(name: str) -> Scheduler:
    schedulers: dict[str, type[Scheduler]] = {
        "round_robin": RoundRobin,
        "nearest_car": NearestCar,
        "zone_based": ZoneBased,
        "eta": Eta,
        "marginal_insertion": MarginalInsertion,
    }
    return schedulers[name]()
